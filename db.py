"""
db.py
Gestión de la base de datos TinyDB.
"""

from tinydb import TinyDB
from pathlib import Path

DB_PATH = Path("/data/garmin_coach.json")
_db_instance = None


def get_db() -> TinyDB:
    global _db_instance
    if _db_instance is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db_instance = TinyDB(DB_PATH, indent=2, ensure_ascii=False)
    return _db_instance


def get_context_for_ai(days: int = 14) -> dict:
    """
    Extrae un resumen de los últimos `days` días de todas las tablas
    para pasárselo al modelo de IA como contexto.
    """
    from datetime import date, timedelta
    from tinydb import Query

    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    Q = Query()

    # Actividades recientes (startTimeLocal desde nueva implementación)
    activities = sorted(
        db.table("activities").search(
            Q.startTimeLocal.test(lambda v: bool(v) and v >= cutoff)
        ),
        key=lambda x: x.get("startTimeLocal", ""),
        reverse=True,
    )[:20]  # máx 20

    # Sueño reciente
    sleep = sorted(
        db.table("sleep").search(Q.date >= cutoff),
        key=lambda x: x.get("date", ""),
        reverse=True,
    )

    # HRV reciente
    hrv = sorted(
        db.table("hrv").search(Q.date >= cutoff),
        key=lambda x: x.get("date", ""),
        reverse=True,
    )

    # Body Battery reciente
    body_battery = sorted(
        db.table("body_battery").search(Q.date >= cutoff),
        key=lambda x: x.get("date", ""),
        reverse=True,
    )

    # Memoria del entrenador (notas guardadas)
    memory = db.table("memory").all()

    return {
        "activities": activities,
        "sleep": sleep,
        "hrv": hrv,
        "body_battery": body_battery,
        "memory": memory,
        "days_covered": days,
    }


def is_db_empty() -> bool:
    """Return True if no fitness data exists across all data tables."""
    db = get_db()
    return (
        len(db.table("activities").all()) == 0
        and len(db.table("sleep").all()) == 0
        and len(db.table("hrv").all()) == 0
        and len(db.table("body_battery").all()) == 0
    )


def get_last_date_in_db() -> str | None:
    """Return the most recent date (YYYY-MM-DD) across all data tables, or None if empty."""
    db = get_db()
    dates = []

    for act in db.table("activities").all():
        start = act.get("startTimeLocal") or act.get("startTime", "")
        if start:
            dates.append(start[:10])

    for table_name in ("sleep", "hrv", "body_battery"):
        for record in db.table(table_name).all():
            d = record.get("date", "")
            if d:
                dates.append(d)

    return max(dates) if dates else None


def purge_old_data(days: int = 30) -> dict:
    """Remove records older than `days` days from all data tables. Returns removed counts."""
    from datetime import date, timedelta
    from tinydb import Query

    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    Q = Query()
    removed = {}

    act_table = db.table("activities")
    old_acts = act_table.search(
        Q.startTimeLocal.test(lambda v: bool(v) and v[:10] < cutoff)
    )
    removed["activities"] = len(old_acts)
    act_table.remove(Q.startTimeLocal.test(lambda v: bool(v) and v[:10] < cutoff))

    for table_name in ("sleep", "hrv", "body_battery"):
        table = db.table(table_name)
        old = table.search(Q.date < cutoff)
        removed[table_name] = len(old)
        table.remove(Q.date < cutoff)

    return removed


def save_memory(note: str):
    """Guarda una nota de memoria del entrenador."""
    from datetime import datetime, timezone
    db = get_db()
    db.table("memory").insert({
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def get_last_sync() -> str | None:
    """Devuelve la fecha/hora del último sync."""
    db = get_db()
    records = db.table("sync_log").all()
    if not records:
        return None
    latest = max(records, key=lambda x: x.get("synced_at", ""))
    return latest.get("synced_at")


def log_sync(summary: dict):
    """Registra cuándo se hizo el último sync."""
    from datetime import datetime, timezone
    db = get_db()
    db.table("sync_log").insert({
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    })
