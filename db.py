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

    # Actividades recientes
    activities = sorted(
        db.table("activities").search(Q.startTime >= cutoff),
        key=lambda x: x.get("startTime", ""),
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


def save_memory(note: str):
    """Guarda una nota de memoria del entrenador."""
    from datetime import datetime
    db = get_db()
    db.table("memory").insert({
        "note": note,
        "created_at": datetime.utcnow().isoformat(),
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
    from datetime import datetime
    db = get_db()
    db.table("sync_log").insert({
        "synced_at": datetime.utcnow().isoformat(),
        "summary": summary,
    })
