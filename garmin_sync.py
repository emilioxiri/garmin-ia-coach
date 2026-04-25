"""
garmin_sync.py
Descarga datos de Garmin Connect y los almacena en TinyDB.
La sesión se persiste en disco para evitar logins repetidos (429).
"""

import asyncio
import logging
import os
import threading
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

from garminconnect import Garmin
from db import get_db

logger = logging.getLogger(__name__)

SESSION_PATH = Path("/data/garmin_session.json")

# ── MFA state ─────────────────────────────────────────────────────────────────

_bot_app = None
_bot_loop = None
_mfa_event = threading.Event()
_mfa_code: str | None = None


def set_bot_app(app) -> None:
    global _bot_app
    _bot_app = app


def set_event_loop(loop) -> None:
    """Call this from an async context so _bot_loop is the running loop."""
    global _bot_loop
    _bot_loop = loop


def provide_mfa_code(code: str) -> None:
    global _mfa_code
    _mfa_code = code
    _mfa_event.set()


def _prompt_mfa() -> str:
    global _mfa_code
    _mfa_event.clear()
    _mfa_code = None

    if _bot_app and _bot_loop and _bot_loop.is_running():
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
            _bot_loop,
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

def get_garmin_client(email: str, password: str) -> Garmin:
    """
    Devuelve un cliente autenticado de Garmin Connect.
    Reutiliza la sesión guardada en disco si sigue siendo válida.
    Solo hace login completo cuando la sesión ha expirado o no existe.
    """
    client = Garmin(email, password, prompt_mfa=_prompt_mfa)

    if SESSION_PATH.exists():
        try:
            client.login(tokenstore=str(SESSION_PATH))
            logger.info("✅ Sesión de Garmin reutilizada desde disco")
            return client
        except Exception as e:
            logger.warning(f"⚠️  Sesión expirada o inválida, haciendo login completo: {e}")
            SESSION_PATH.unlink(missing_ok=True)

    try:
        client.login()
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        client.client.dump(str(SESSION_PATH))
        logger.info("✅ Login completo en Garmin. Sesión guardada en disco.")
    except Exception as e:
        raise RuntimeError(f"No se pudo autenticar en Garmin Connect: {e}") from e

    return client


def sync_all(email: str, password: str, days: int = 30) -> dict:
    """
    Sincroniza datos de Garmin. Si la BD está vacía descarga los últimos `days` días;
    si ya tiene datos descarga sólo desde el último registro hasta hoy.
    Purga registros con más de `days` días de antigüedad antes de sincronizar.
    """
    from db import is_db_empty, get_last_date_in_db, purge_old_data

    client = get_garmin_client(email, password)
    db = get_db()

    today = date.today()

    purged = purge_old_data(days=days)
    logger.info(f"🗑 Datos purgados (>{days}d): {purged}")

    if is_db_empty():
        start = today - timedelta(days=days)
        logger.info(f"📭 BD vacía — sincronizando últimos {days} días desde {start}")
    else:
        last_date_str = get_last_date_in_db()
        start = date.fromisoformat(last_date_str)
        logger.info(f"📬 BD no vacía — sincronizando desde {start} (último registro)")

    summary = {"activities": 0, "sleep": 0, "hrv": 0, "body_battery": 0, "purged": purged}

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
            # Store full summary dict; try to merge in detailed metrics
            record = {**act, "activityId": act_id, "synced_at": datetime.now(timezone.utc).isoformat()}
            try:
                details = client.get_activity(act_id)
                for key, value in details.items():
                    if key not in record:
                        record[key] = value
            except Exception as detail_err:
                logger.debug(f"No se pudieron obtener detalles de actividad {act_id}: {detail_err}")

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
                        "synced_at": datetime.now(timezone.utc).isoformat(),
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
                        "synced_at": datetime.now(timezone.utc).isoformat(),
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
                        "synced_at": datetime.now(timezone.utc).isoformat(),
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
