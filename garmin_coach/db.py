"""
db.py — backward-compatibility shim (Phase 2 refactor).

All public symbols are preserved with identical signatures so that legacy
modules (coach.py, coach_tools.py, context_builder.py, garmin_sync.py,
bot.py) continue to work without modification.

Internally, each function builds a repository on top of `get_db()` which
still returns the raw TinyDB instance.  This preserves the test seam:

    with patch("garmin_coach.db._db_instance", mock_tinydb):
        ...  # legacy tests keep working

When _db_instance has been replaced by a test patch the repos receive that
mocked TinyDB.  When it is None (production), TinyDBFactory creates the
real database lazily.

TODO (Phase 3): delete this file once all callers import from the new layer.
"""

from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB

from garmin_coach.infrastructure.db.tinydb_factory import TinyDBFactory

DB_PATH = Path("/data/garmin_coach.json")

_db_instance: TinyDB | None = None


def get_db() -> TinyDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = TinyDBFactory(DB_PATH).get()
    return _db_instance


# ── lazy repo helpers ────────────────────────────────────────────────────────
# Each call builds a fresh repo on top of the current _db_instance so that
# test patches to _db_instance are always respected.


def _activity_repo():
    from garmin_coach.infrastructure.db.activity_repository import ActivityRepository

    return ActivityRepository(get_db())


def _sleep_repo():
    from garmin_coach.infrastructure.db.wellness_repository import SleepRepository

    return SleepRepository(get_db())


def _hrv_repo():
    from garmin_coach.infrastructure.db.wellness_repository import HRVRepository

    return HRVRepository(get_db())


def _body_battery_repo():
    from garmin_coach.infrastructure.db.wellness_repository import BodyBatteryRepository

    return BodyBatteryRepository(get_db())


def _training_status_repo():
    from garmin_coach.infrastructure.db.wellness_repository import (
        TrainingStatusRepository,
    )

    return TrainingStatusRepository(get_db())


def _training_readiness_repo():
    from garmin_coach.infrastructure.db.wellness_repository import (
        TrainingReadinessRepository,
    )

    return TrainingReadinessRepository(get_db())


def _respiration_repo():
    from garmin_coach.infrastructure.db.wellness_repository import RespirationRepository

    return RespirationRepository(get_db())


def _spo2_repo():
    from garmin_coach.infrastructure.db.wellness_repository import SPO2Repository

    return SPO2Repository(get_db())


def _stress_repo():
    from garmin_coach.infrastructure.db.wellness_repository import StressRepository

    return StressRepository(get_db())


def _fitness_metrics_repo():
    from garmin_coach.infrastructure.db.fitness_repository import (
        FitnessMetricsRepository,
    )

    return FitnessMetricsRepository(get_db())


def _race_predictions_repo():
    from garmin_coach.infrastructure.db.fitness_repository import (
        RacePredictionsRepository,
    )

    return RacePredictionsRepository(get_db())


def _lactate_repo():
    from garmin_coach.infrastructure.db.fitness_repository import (
        LactateThresholdRepository,
    )

    return LactateThresholdRepository(get_db())


def _endurance_repo():
    from garmin_coach.infrastructure.db.fitness_repository import (
        EnduranceScoreRepository,
    )

    return EnduranceScoreRepository(get_db())


def _memory_repo():
    from garmin_coach.infrastructure.db.memory_repository import MemoryRepository

    return MemoryRepository(get_db())


def _sync_log_repo():
    from garmin_coach.infrastructure.db.sync_log_repository import SyncLogRepository

    return SyncLogRepository(get_db())


# ── Public API (same signatures as original db.py) ───────────────────────────


def get_context_for_ai(days: int = 14) -> dict:
    """Extract a summary of the last `days` days from all tables for the AI."""
    from datetime import date, timedelta

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    today = date.today().isoformat()

    def _date_sorted(rows: list[dict]) -> list[dict]:
        return sorted(rows, key=lambda r: r.get("date", ""), reverse=True)

    activities = sorted(
        [
            a
            for a in _activity_repo().all()
            if bool(a.get("startTimeLocal")) and a.get("startTimeLocal", "") >= cutoff
        ],
        key=lambda x: x.get("startTimeLocal", ""),
        reverse=True,
    )[:20]

    sleep = _date_sorted(_sleep_repo().find_by_date_range("date", cutoff, today))
    hrv = _date_sorted(_hrv_repo().find_by_date_range("date", cutoff, today))
    body_battery = _date_sorted(
        _body_battery_repo().find_by_date_range("date", cutoff, today)
    )
    training_status = _date_sorted(
        _training_status_repo().find_by_date_range("date", cutoff, today)
    )
    training_readiness = _date_sorted(
        _training_readiness_repo().find_by_date_range("date", cutoff, today)
    )
    respiration = _date_sorted(
        _respiration_repo().find_by_date_range("date", cutoff, today)
    )
    spo2 = _date_sorted(_spo2_repo().find_by_date_range("date", cutoff, today))
    stress = _date_sorted(_stress_repo().find_by_date_range("date", cutoff, today))

    fitness_metrics = _fitness_metrics_repo().latest()
    race_predictions = _race_predictions_repo().latest()
    lactate_threshold = _lactate_repo().latest()
    endurance_score = _endurance_repo().latest()

    memory = _memory_repo().all()

    return {
        "activities": activities,
        "sleep": sleep,
        "hrv": hrv,
        "body_battery": body_battery,
        "training_status": training_status,
        "training_readiness": training_readiness,
        "respiration": respiration,
        "spo2": spo2,
        "stress": stress,
        "fitness_metrics": fitness_metrics,
        "race_predictions": race_predictions,
        "lactate_threshold": lactate_threshold,
        "endurance_score": endurance_score,
        "memory": memory,
        "days_covered": days,
    }


def get_compact_context_for_ai(days: int = 7, max_activities: int = 10) -> dict:
    """Compact version of get_context_for_ai for LLM consumption."""
    from garmin_coach.context_builder import build_context

    raw = get_context_for_ai(days=days)
    return build_context(raw, max_activities=max_activities)


def is_db_empty() -> bool:
    """Return True if no fitness data exists across all data tables."""
    return (
        _activity_repo().is_empty()
        and _sleep_repo().is_empty()
        and _hrv_repo().is_empty()
        and _body_battery_repo().is_empty()
    )


def get_last_date_in_db() -> str | None:
    """Return the most recent date (YYYY-MM-DD) across all data tables, or None."""
    dates: list[str] = []

    for act in _activity_repo().all():
        start = act.get("startTimeLocal") or act.get("startTime", "")
        if start and len(start) >= 10:
            dates.append(start[:10])

    for repo in (_sleep_repo(), _hrv_repo(), _body_battery_repo()):
        for record in repo.all():
            d = record.get("date", "")
            if d:
                dates.append(d)

    return max(dates) if dates else None


def purge_old_data(days: int = 30) -> dict:
    """Remove records older than `days` days from wellness tables.

    NOTE: activities are intentionally NOT purged (historical PRs must survive).
    """
    from datetime import date, timedelta

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    removed: dict[str, int] = {"activities": 0}

    for name, repo in (
        ("sleep", _sleep_repo()),
        ("hrv", _hrv_repo()),
        ("body_battery", _body_battery_repo()),
        ("training_status", _training_status_repo()),
        ("training_readiness", _training_readiness_repo()),
        ("respiration", _respiration_repo()),
        ("spo2", _spo2_repo()),
        ("stress", _stress_repo()),
    ):
        removed[name] = repo.delete_older_than("date", cutoff)

    return removed


def save_memory(note: str) -> None:
    """Save a coach memory note."""
    _memory_repo().add(note)


def get_last_sync() -> str | None:
    """Return the timestamp of the most recent sync."""
    return _sync_log_repo().last_sync()


def log_sync(summary: dict) -> None:
    """Record a sync run."""
    _sync_log_repo().log(summary)
