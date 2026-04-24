"""
garmin_sync.py
Descarga datos de Garmin Connect y los almacena en TinyDB.
La sesión se persiste en disco para evitar logins repetidos (429).
"""

import asyncio
import logging
import os
import threading
from datetime import date, timedelta, datetime
from pathlib import Path

from garminconnect import Garmin
from db import get_db

logger = logging.getLogger(__name__)

SESSION_PATH = Path("/data/garmin_session.pkl")

# ── MFA state ─────────────────────────────────────────────────────────────────

_bot_app = None
_mfa_event = threading.Event()
_mfa_code: str | None = None


def set_bot_app(app) -> None:
    global _bot_app
    _bot_app = app


def provide_mfa_code(code: str) -> None:
    global _mfa_code
    _mfa_code = code
    _mfa_event.set()


def _prompt_mfa() -> str:
    global _mfa_code
    _mfa_event.clear()
    _mfa_code = None

    if _bot_app:
        loop = getattr(_bot_app.update_queue, "_loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _bot_app.bot.send_message(
                    chat_id=int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0")),
                    text=(
                        "🔐 *Garmin necesita verificación MFA*\n"
                        "Revisa tu email o app de autenticación y responde con:\n"
                        "`/mfa <código>`"
                    ),
                    parse_mode="Markdown",
                ),
                loop,
            )

    logger.info("⏳ Esperando código MFA del usuario (timeout: 5 min)...")
    got_code = _mfa_event.wait(timeout=300)
    if not got_code or not _mfa_code:
        raise RuntimeError(
            "Timeout esperando código MFA. Vuelve a intentar /sync "
            "y envía /mfa <código> en los primeros 5 minutos."
        )
    return _mfa_code


# ── Auth ───────────────────────────────────────────────────────────────────────

def _is_rate_limited(exc: Exception) -> bool:
    return "429" in str(exc) or "Too Many Requests" in str(exc)


def get_garmin_client(email: str, password: str) -> Garmin:
    """
    Devuelve un cliente autenticado de Garmin Connect.
    Reutiliza la sesión guardada en disco si sigue siendo válida.
    Solo hace login completo cuando la sesión ha expirado o no existe.
    """
    client = Garmin(email, password, prompt_mfa=_prompt_mfa)

    if SESSION_PATH.exists():
        try:
            saved_tokens = SESSION_PATH.read_text(encoding="utf-8")
            client.login(saved_tokens)
            client.get_full_name()
            logger.info("✅ Sesión de Garmin reutilizada desde disco")
            return client
        except Exception as e:
            if _is_rate_limited(e):
                raise RuntimeError(
                    "Garmin Connect está bloqueando las peticiones (429 Too Many Requests). "
                    "Espera unas horas antes de volver a intentarlo."
                ) from e
            logger.warning(f"⚠️  Sesión expirada o inválida, haciendo login completo: {e}")
            SESSION_PATH.unlink(missing_ok=True)

    try:
        client.login()
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        SESSION_PATH.write_text(client.garth.dumps(), encoding="utf-8")
        logger.info("✅ Login completo en Garmin. Sesión guardada en disco.")
    except Exception as e:
        if _is_rate_limited(e):
            raise RuntimeError(
                "Garmin Connect está bloqueando las peticiones (429 Too Many Requests). "
                "Espera unas horas antes de volver a intentarlo."
            ) from e
        raise RuntimeError(f"No se pudo autenticar en Garmin Connect: {e}") from e

    return client


def sync_all(email: str, password: str, days: int = 30) -> dict:
    """
    Sincroniza todos los datos de los últimos `days` días.
    Devuelve un resumen de cuántos registros se han guardado/actualizado.
    """
    client = get_garmin_client(email, password)
    db = get_db()

    today = date.today()
    start = today - timedelta(days=days)
    summary = {"activities": 0, "sleep": 0, "hrv": 0, "body_battery": 0}

    # ── Actividades ────────────────────────────────────────────────────
    try:
        activities = client.get_activities_by_date(
            start.isoformat(), today.isoformat()
        )
        act_table = db.table("activities")
        from tinydb import Query
        Act = Query()
        for act in activities:
            act_id = str(act.get("activityId", ""))
            record = {
                "activityId": act_id,
                "name": act.get("activityName"),
                "type": act.get("activityType", {}).get("typeKey"),
                "startTime": act.get("startTimeLocal"),
                "duration_s": act.get("duration"),
                "distance_m": act.get("distance"),
                "calories": act.get("calories"),
                "avgHR": act.get("averageHR"),
                "maxHR": act.get("maxHR"),
                "aerobicTE": act.get("aerobicTrainingEffect"),
                "anaerobicTE": act.get("anaerobicTrainingEffect"),
                "avgPace": act.get("avgSpeed"),
                "elevationGain": act.get("elevationGain"),
                "synced_at": datetime.utcnow().isoformat(),
            }
            if act_table.search(Act.activityId == act_id):
                act_table.update(record, Act.activityId == act_id)
            else:
                act_table.insert(record)
            summary["activities"] += 1
        logger.info(f"📊 Actividades: {summary['activities']} registros")
    except Exception as e:
        logger.error(f"❌ Error al obtener actividades: {e}")

    # ── Sueño ──────────────────────────────────────────────────────────
    try:
        sleep_table = db.table("sleep")
        from tinydb import Query
        Sleep = Query()
        current = start
        while current <= today:
            day_str = current.isoformat()
            try:
                sleep_data = client.get_sleep_data(day_str)
                daily = sleep_data.get("dailySleepDTO", {})
                if daily:
                    record = {
                        "date": day_str,
                        "duration_s": daily.get("sleepTimeSeconds"),
                        "deep_s": daily.get("deepSleepSeconds"),
                        "light_s": daily.get("lightSleepSeconds"),
                        "rem_s": daily.get("remSleepSeconds"),
                        "awake_s": daily.get("awakeSleepSeconds"),
                        "score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
                        "restingHR": daily.get("restingHeartRate"),
                        "synced_at": datetime.utcnow().isoformat(),
                    }
                    if sleep_table.search(Sleep.date == day_str):
                        sleep_table.update(record, Sleep.date == day_str)
                    else:
                        sleep_table.insert(record)
                    summary["sleep"] += 1
            except Exception:
                pass
            current += timedelta(days=1)
        logger.info(f"😴 Sueño: {summary['sleep']} registros")
    except Exception as e:
        logger.error(f"❌ Error al obtener sueño: {e}")

    # ── HRV ───────────────────────────────────────────────────────────
    try:
        hrv_table = db.table("hrv")
        from tinydb import Query
        HRV = Query()
        current = start
        while current <= today:
            day_str = current.isoformat()
            try:
                hrv_data = client.get_hrv_data(day_str)
                summary_hrv = hrv_data.get("hrvSummary", {})
                if summary_hrv:
                    record = {
                        "date": day_str,
                        "weeklyAvg": summary_hrv.get("weeklyAvg"),
                        "lastNight": summary_hrv.get("lastNight"),
                        "lastNight5MinHigh": summary_hrv.get("lastNight5MinHigh"),
                        "status": summary_hrv.get("status"),
                        "feedbackPhrase": summary_hrv.get("feedbackPhrase"),
                        "synced_at": datetime.utcnow().isoformat(),
                    }
                    if hrv_table.search(HRV.date == day_str):
                        hrv_table.update(record, HRV.date == day_str)
                    else:
                        hrv_table.insert(record)
                    summary["hrv"] += 1
            except Exception:
                pass
            current += timedelta(days=1)
        logger.info(f"💓 HRV: {summary['hrv']} registros")
    except Exception as e:
        logger.error(f"❌ Error al obtener HRV: {e}")

    # ── Body Battery ───────────────────────────────────────────────────
    try:
        bb_table = db.table("body_battery")
        from tinydb import Query
        BB = Query()
        current = start
        while current <= today:
            day_str = current.isoformat()
            try:
                bb_data = client.get_body_battery(day_str, day_str)
                if bb_data:
                    values = bb_data[0].get("bodyBatteryValuesArray", [])
                    charged = max((v[1] for v in values if v), default=None)
                    drained = min((v[1] for v in values if v), default=None)
                    record = {
                        "date": day_str,
                        "max": charged,
                        "min": drained,
                        "synced_at": datetime.utcnow().isoformat(),
                    }
                    if bb_table.search(BB.date == day_str):
                        bb_table.update(record, BB.date == day_str)
                    else:
                        bb_table.insert(record)
                    summary["body_battery"] += 1
            except Exception:
                pass
            current += timedelta(days=1)
        logger.info(f"🔋 Body Battery: {summary['body_battery']} registros")
    except Exception as e:
        logger.error(f"❌ Error al obtener Body Battery: {e}")

    logger.info(f"✅ Sync completado: {summary}")
    return summary
