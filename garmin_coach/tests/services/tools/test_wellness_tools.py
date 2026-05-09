"""Tests for services/tools/wellness_tools.py."""

from datetime import date, timedelta

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from garmin_coach.infrastructure.db.wellness_repository import (
    BodyBatteryRepository,
    HRVRepository,
    SleepRepository,
    TrainingReadinessRepository,
)
from garmin_coach.services.tools.wellness_tools import (
    GetBodyBatteryWindowTool,
    GetHRVWindowTool,
    GetSleepWindowTool,
    GetTrainingReadinessWindowTool,
)


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _make_sleep_repo(records: list[dict]):
    db = TinyDB(storage=MemoryStorage)
    repo = SleepRepository(db)
    for r in records:
        repo.upsert(r)
    return repo


def _make_hrv_repo(records: list[dict]):
    db = TinyDB(storage=MemoryStorage)
    repo = HRVRepository(db)
    for r in records:
        repo.upsert(r)
    return repo


def _make_bb_repo(records: list[dict]):
    db = TinyDB(storage=MemoryStorage)
    repo = BodyBatteryRepository(db)
    for r in records:
        repo.upsert(r)
    return repo


def _make_tr_repo(records: list[dict]):
    db = TinyDB(storage=MemoryStorage)
    repo = TrainingReadinessRepository(db)
    for r in records:
        repo.upsert(r)
    return repo


# ── GetSleepWindowTool ────────────────────────────────────────────────────────


def test_sleep_window_returns_recent_records():
    records = [
        {"date": _days_ago(1), "duration_s": 28800, "score": 80},
        {"date": _days_ago(10), "duration_s": 25200, "score": 60},
    ]
    repo = _make_sleep_repo(records)
    tool = GetSleepWindowTool(repo)
    result = tool.handle(days=7)
    assert result.error is None
    assert len(result.data) == 1
    assert result.data[0]["score"] == 80


def test_sleep_window_empty():
    repo = _make_sleep_repo([])
    result = GetSleepWindowTool(repo).handle(days=7)
    assert result.data == []


def test_sleep_window_slims_records():
    records = [
        {"date": _days_ago(1), "duration_s": 28800, "score": 85, "restingHR": 48}
    ]
    repo = _make_sleep_repo(records)
    result = GetSleepWindowTool(repo).handle(days=7)
    row = result.data[0]
    assert "total_h" in row
    assert "score" in row
    assert "duration_s" not in row


# ── GetHRVWindowTool ──────────────────────────────────────────────────────────


def test_hrv_window_returns_recent_records():
    records = [
        {"date": _days_ago(2), "lastNight": 55, "weeklyAvg": 52, "status": "balanced"},
        {"date": _days_ago(20), "lastNight": 45},
    ]
    repo = _make_hrv_repo(records)
    result = GetHRVWindowTool(repo).handle(days=7)
    assert len(result.data) == 1
    assert result.data[0]["lastNight"] == 55


def test_hrv_window_slims_records():
    records = [
        {"date": _days_ago(1), "lastNight": 60, "weeklyAvg": 58, "status": "balanced"}
    ]
    repo = _make_hrv_repo(records)
    result = GetHRVWindowTool(repo).handle(days=7)
    row = result.data[0]
    assert "lastNight" in row
    assert "weeklyAvg" in row
    assert "status" in row


# ── GetBodyBatteryWindowTool ──────────────────────────────────────────────────


def test_body_battery_window_filters_by_date():
    records = [
        {"date": _days_ago(3), "max": 90, "min": 30},
        {"date": _days_ago(15), "max": 80, "min": 20},
    ]
    repo = _make_bb_repo(records)
    result = GetBodyBatteryWindowTool(repo).handle(days=7)
    assert len(result.data) == 1
    assert result.data[0]["max"] == 90


def test_body_battery_slims_records():
    records = [{"date": _days_ago(1), "max": 95, "min": 25, "extra_field": "ignored"}]
    repo = _make_bb_repo(records)
    result = GetBodyBatteryWindowTool(repo).handle(days=7)
    row = result.data[0]
    assert "max" in row
    assert "min" in row


# ── GetTrainingReadinessWindowTool ────────────────────────────────────────────


def test_training_readiness_window_returns_recent():
    records = [
        {"date": _days_ago(1), "score": 75, "level": "good", "feedback": "Ready"},
        {"date": _days_ago(30), "score": 50},
    ]
    repo = _make_tr_repo(records)
    result = GetTrainingReadinessWindowTool(repo).handle(days=7)
    assert len(result.data) == 1
    assert result.data[0]["score"] == 75


def test_training_readiness_caps_days():
    records = [{"date": _days_ago(1), "score": 80}]
    repo = _make_tr_repo(records)
    # days=200 gets capped to MAX_WINDOW_DAYS=90 internally, still returns the record
    result = GetTrainingReadinessWindowTool(repo).handle(days=200)
    assert len(result.data) == 1
