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
from garmin_coach.db import get_db

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
    from garmin_coach.db import is_db_empty, get_last_date_in_db, purge_old_data

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

    summary = {
        "activities": 0, "sleep": 0, "hrv": 0, "body_battery": 0,
        "training_status": 0, "training_readiness": 0, "respiration": 0, "spo2": 0, "stress": 0,
        "purged": purged,
    }

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
                    if value is not None:
                        record[key] = value
                for key, value in details.get("summaryDTO", {}).items():
                    if value is not None:
                        record[key] = value
            except Exception as detail_err:
                logger.debug(f"No se pudieron obtener detalles de actividad {act_id}: {detail_err}")
            try:
                splits = client.get_activity_splits(act_id)
                record["splits"] = splits.get("lapDTOs", [])
            except Exception as e:
                logger.debug(f"No splits for {act_id}: {e}")
            try:
                record["hrZones"] = client.get_activity_hr_in_timezones(act_id)
            except Exception as e:
                logger.debug(f"No HR zones for {act_id}: {e}")

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

    # ── Daily wellness metrics ─────────────────────────────────────────────
    _DAILY_METRICS = [
        ("training_status",    client.get_training_status,
         lambda r: r.get("trainingStatusDTO") or (r if r else None)),
        ("training_readiness", client.get_training_readiness,
         lambda r: r.get("trainingReadinessDTO") or (r if r else None)),
        ("respiration",        client.get_respiration_data,
         lambda r: {k: r[k] for k in ("avgWakingRespirationValue", "avgSleepRespirationValue",
                                       "highestRespirationValue", "lowestRespirationValue") if r.get(k) is not None} or None),
        ("spo2",               client.get_spo2_data,
         lambda r: {k: r[k] for k in ("averageSpO2", "lowestSpO2", "lastSevenDaysAvgSpO2") if r.get(k) is not None} or None),
        ("stress",             client.get_stress_data,
         lambda r: {k: r[k] for k in ("avgStressLevel", "maxStressLevel") if r.get(k) is not None} or None),
    ]
    from tinydb import Query as _Q
    DQ = _Q()
    for table_name, method, extract in _DAILY_METRICS:
        table = db.table(table_name)
        current = start
        while current <= today:
            day_str = current.isoformat()
            try:
                data = extract(method(day_str))
                if data:
                    record = {"date": day_str, **data, "synced_at": datetime.now(timezone.utc).isoformat()}
                    if table.search(DQ.date == day_str):
                        table.update(record, DQ.date == day_str)
                    else:
                        table.insert(record)
                    summary[table_name] += 1
            except Exception:
                pass
            current += timedelta(days=1)
        logger.info(f"📈 {table_name}: {summary[table_name]} registros")

    # ── Fitness snapshot (today) ───────────────────────────────────────────
    today_str = today.isoformat()
    from tinydb import Query as _Q2
    SQ = _Q2()

    try:
        max_m = client.get_max_metrics(today_str)
        vo2max = None
        try:
            # API may return list or dict — handle both
            if isinstance(max_m, list):
                for item in max_m:
                    v = item.get("vO2MaxValue") if isinstance(item, dict) else None
                    if v is not None:
                        vo2max = v
                        break
            else:
                metrics_map = max_m.get("allMetrics", {}).get("metricsMap", {})
                vo2max_list = metrics_map.get("VO2MAX_VALUE", [])
                if vo2max_list:
                    vo2max = vo2max_list[-1].get("value")
        except Exception as parse_err:
            logger.debug(f"VO2max parse failed: {parse_err}. Raw: {max_m}")

        # Fallback 1: training_status.mostRecentVO2Max.generic
        if vo2max is None:
            ts_recs = sorted(
                db.table("training_status").all(),
                key=lambda r: r.get("date", ""),
            )
            for rec in reversed(ts_recs):
                try:
                    vo2max = rec["mostRecentVO2Max"]["generic"]["vo2MaxValue"]
                    if vo2max is not None:
                        break
                except (KeyError, TypeError):
                    continue

        # Fallback 2: latest activity with vO2MaxValue
        if vo2max is None:
            acts = sorted(
                [a for a in db.table("activities").all() if a.get("vO2MaxValue")],
                key=lambda a: a.get("startTimeLocal", ""),
            )
            if acts:
                vo2max = acts[-1]["vO2MaxValue"]

        t = db.table("fitness_metrics")
        r = {"date": today_str, "vo2max": vo2max, "maxMetrics": max_m, "synced_at": datetime.now(timezone.utc).isoformat()}
        t.update(r, SQ.date == today_str) if t.search(SQ.date == today_str) else t.insert(r)
        logger.info(f"🫀 VO2max: {vo2max}")
    except Exception as e:
        logger.debug(f"No max metrics: {e}")

    try:
        predictions = client.get_race_predictions(start.isoformat(), today_str)
        t = db.table("race_predictions")
        r = {"date": today_str, "predictions": predictions, "synced_at": datetime.now(timezone.utc).isoformat()}
        t.update(r, SQ.date == today_str) if t.search(SQ.date == today_str) else t.insert(r)
        logger.info("🏁 Race predictions actualizadas")
    except Exception as e:
        logger.debug(f"No race predictions: {e}")

    try:
        lt = client.get_lactate_threshold()
        t = db.table("lactate_threshold")
        r = {"date": today_str, **lt, "synced_at": datetime.now(timezone.utc).isoformat()}
        t.update(r, SQ.date == today_str) if t.search(SQ.date == today_str) else t.insert(r)
        logger.info("🧪 Lactate threshold actualizado")
    except Exception as e:
        logger.debug(f"No lactate threshold: {e}")

    try:
        endurance = client.get_endurance_score(start.isoformat(), today_str)
        t = db.table("endurance_score")
        r = {"date": today_str, "data": endurance, "synced_at": datetime.now(timezone.utc).isoformat()}
        t.update(r, SQ.date == today_str) if t.search(SQ.date == today_str) else t.insert(r)
        logger.info("💪 Endurance score actualizado")
    except Exception as e:
        logger.debug(f"No endurance score: {e}")

    logger.info(f"✅ Sync completado: {summary}")
    return summary
