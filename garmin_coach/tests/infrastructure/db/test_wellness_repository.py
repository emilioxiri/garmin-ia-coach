"""Tests for wellness repositories."""

from __future__ import annotations

from datetime import date, timedelta


def _dates(days_back: int = 0) -> str:
    return (date.today() - timedelta(days=days_back)).isoformat()


# ── SleepRepository ───────────────────────────────────────────────────────────


def test_sleep_upsert_and_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import SleepRepository

    repo = SleepRepository(memory_db)
    today = _dates(0)
    old = _dates(20)
    repo.upsert({"date": today, "score": 80})
    repo.upsert({"date": old, "score": 70})
    rows = repo.window(days=7)
    assert len(rows) == 1
    assert rows[0]["score"] == 80


def test_sleep_window_sorted_desc(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import SleepRepository

    repo = SleepRepository(memory_db)
    for i in range(5):
        repo.upsert({"date": _dates(i), "score": 80 - i})
    rows = repo.window(days=7)
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)


def test_sleep_upsert_updates_existing(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import SleepRepository

    repo = SleepRepository(memory_db)
    today = _dates(0)
    repo.upsert({"date": today, "score": 75})
    repo.upsert({"date": today, "score": 85})
    assert repo.count() == 1
    assert repo.all()[0]["score"] == 85


# ── HRVRepository ─────────────────────────────────────────────────────────────


def test_hrv_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import HRVRepository

    repo = HRVRepository(memory_db)
    repo.upsert({"date": _dates(0), "lastNight": 55})
    repo.upsert({"date": _dates(30), "lastNight": 45})
    rows = repo.window(days=7)
    assert len(rows) == 1
    assert rows[0]["lastNight"] == 55


# ── BodyBatteryRepository ─────────────────────────────────────────────────────


def test_body_battery_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import BodyBatteryRepository

    repo = BodyBatteryRepository(memory_db)
    repo.upsert({"date": _dates(0), "max": 90})
    repo.upsert({"date": _dates(14), "max": 80})
    rows = repo.window(days=7)
    assert len(rows) == 1
    assert rows[0]["max"] == 90


# ── TrainingReadinessRepository ───────────────────────────────────────────────


def test_training_readiness_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import (
        TrainingReadinessRepository,
    )

    repo = TrainingReadinessRepository(memory_db)
    repo.upsert({"date": _dates(0), "score": 72})
    rows = repo.window(days=7)
    assert len(rows) == 1
    assert rows[0]["score"] == 72


# ── TrainingStatusRepository ──────────────────────────────────────────────────


def test_training_status_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import (
        TrainingStatusRepository,
    )

    repo = TrainingStatusRepository(memory_db)
    repo.upsert({"date": _dates(0), "trainingStatus": "productive"})
    rows = repo.window(days=7)
    assert len(rows) == 1


# ── RespirationRepository ─────────────────────────────────────────────────────


def test_respiration_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import RespirationRepository

    repo = RespirationRepository(memory_db)
    repo.upsert({"date": _dates(0), "avgWakingRespirationValue": 14})
    rows = repo.window(days=7)
    assert len(rows) == 1


# ── SPO2Repository ────────────────────────────────────────────────────────────


def test_spo2_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import SPO2Repository

    repo = SPO2Repository(memory_db)
    repo.upsert({"date": _dates(0), "averageSpO2": 97})
    rows = repo.window(days=7)
    assert len(rows) == 1


# ── StressRepository ──────────────────────────────────────────────────────────


def test_stress_window(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import StressRepository

    repo = StressRepository(memory_db)
    repo.upsert({"date": _dates(0), "avgStressLevel": 35})
    rows = repo.window(days=7)
    assert len(rows) == 1


def test_wellness_delete_older_than(memory_db):
    from garmin_coach.infrastructure.db.wellness_repository import SleepRepository

    repo = SleepRepository(memory_db)
    old = _dates(40)
    recent = _dates(0)
    repo.upsert({"date": old, "score": 70})
    repo.upsert({"date": recent, "score": 80})
    removed = repo.delete_older_than("date", _dates(7))
    assert removed == 1
    assert repo.count() == 1
    assert repo.all()[0]["date"] == recent
