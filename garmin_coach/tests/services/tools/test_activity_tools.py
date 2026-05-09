"""Tests for services/tools/activity_tools.py."""

from datetime import date, timedelta

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from garmin_coach.infrastructure.db.activity_repository import ActivityRepository
from garmin_coach.services.tools.activity_tools import (
    FindActivityTool,
    GetActivityDetailTool,
    GetRecentActivitiesTool,
)


def _make_repo():
    db = TinyDB(storage=MemoryStorage)
    return ActivityRepository(db)


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _activity(
    activity_id,
    *,
    start,
    type_key="running",
    distance_m=5000.0,
    avg_speed=3.0,
    duration_s=1500.0,
):
    return {
        "activityId": activity_id,
        "activityType": {"typeKey": type_key},
        "startTimeLocal": f"{start} 08:00:00",
        "distance": distance_m,
        "averageSpeed": avg_speed,
        "duration": duration_s,
        "averageHR": 150,
    }


# ── FindActivityTool ──────────────────────────────────────────────────────────


def test_find_activity_no_filters_returns_all_in_window():
    repo = _make_repo()
    repo.upsert(_activity("1", start=_days_ago(3)))
    repo.upsert(_activity("2", start=_days_ago(60)))
    tool = FindActivityTool(repo)
    result = tool.handle(days=30)
    assert result.error is None
    ids = {r["activityId"] for r in result.data}
    assert "1" in ids
    assert "2" not in ids


def test_find_activity_by_weekday():
    repo = _make_repo()
    # find a recent Friday
    today = date.today()
    days_back = (today.weekday() - 4) % 7 or 7
    friday = (today - timedelta(days=days_back)).isoformat()
    repo.upsert(_activity("fri", start=friday))
    repo.upsert(
        _activity(
            "other",
            start=_days_ago(3)
            if date.fromisoformat(_days_ago(3)).weekday() != 4
            else _days_ago(4),
        )
    )
    tool = FindActivityTool(repo)
    result = tool.handle(weekday="viernes", days=30)
    assert result.error is None
    ids = [r["activityId"] for r in result.data]
    assert "fri" in ids


def test_find_activity_unknown_weekday_returns_empty():
    repo = _make_repo()
    repo.upsert(_activity("1", start=_days_ago(1)))
    tool = FindActivityTool(repo)
    result = tool.handle(weekday="funday")
    assert result.data == []


def test_find_activity_by_date_iso():
    repo = _make_repo()
    target = _days_ago(5)
    repo.upsert(_activity("match", start=target))
    repo.upsert(_activity("other", start=_days_ago(6)))
    tool = FindActivityTool(repo)
    result = tool.handle(date_iso=target, days=30)
    ids = [r["activityId"] for r in result.data]
    assert ids == ["match"]


def test_find_activity_only_runs():
    repo = _make_repo()
    repo.upsert(_activity("run1", start=_days_ago(2), type_key="running"))
    repo.upsert(_activity("padel1", start=_days_ago(2), type_key="padel"))
    tool = FindActivityTool(repo)
    result = tool.handle(only_runs=True, days=10)
    types_found = {r.get("type") for r in result.data}
    assert "padel" not in types_found


def test_find_activity_by_min_distance():
    repo = _make_repo()
    repo.upsert(_activity("long", start=_days_ago(1), distance_m=21000.0))
    repo.upsert(_activity("short", start=_days_ago(1), distance_m=5000.0))
    tool = FindActivityTool(repo)
    result = tool.handle(min_distance_km=15.0, days=10)
    ids = [r["activityId"] for r in result.data]
    assert "long" in ids
    assert "short" not in ids


def test_find_activity_by_max_distance():
    repo = _make_repo()
    repo.upsert(_activity("long", start=_days_ago(1), distance_m=21000.0))
    repo.upsert(_activity("short", start=_days_ago(1), distance_m=5000.0))
    tool = FindActivityTool(repo)
    result = tool.handle(max_distance_km=10.0, days=10)
    ids = [r["activityId"] for r in result.data]
    assert "short" in ids
    assert "long" not in ids


def test_find_activity_by_type():
    repo = _make_repo()
    repo.upsert(_activity("cy1", start=_days_ago(1), type_key="cycling"))
    repo.upsert(_activity("ru1", start=_days_ago(1), type_key="running"))
    tool = FindActivityTool(repo)
    result = tool.handle(activity_type="cycling", days=10)
    ids = [r["activityId"] for r in result.data]
    assert "cy1" in ids
    assert "ru1" not in ids


# ── GetRecentActivitiesTool ───────────────────────────────────────────────────


def test_get_recent_activities_default_window():
    repo = _make_repo()
    repo.upsert(_activity("new", start=_days_ago(3)))
    repo.upsert(_activity("old", start=_days_ago(60)))
    tool = GetRecentActivitiesTool(repo)
    result = tool.handle(days=7)
    ids = [r["activityId"] for r in result.data]
    assert "new" in ids
    assert "old" not in ids


def test_get_recent_activities_respects_limit():
    repo = _make_repo()
    for i in range(10):
        repo.upsert(_activity(str(i), start=_days_ago(i % 5 + 1)))
    tool = GetRecentActivitiesTool(repo)
    result = tool.handle(days=30, limit=3)
    assert len(result.data) == 3


def test_get_recent_activities_only_runs():
    repo = _make_repo()
    repo.upsert(_activity("r1", start=_days_ago(1), type_key="running"))
    repo.upsert(_activity("p1", start=_days_ago(1), type_key="padel"))
    tool = GetRecentActivitiesTool(repo)
    result = tool.handle(days=7, only_runs=True)
    types = {r.get("type") for r in result.data}
    assert "padel" not in types


# ── GetActivityDetailTool ─────────────────────────────────────────────────────


def test_get_activity_detail_found():
    repo = _make_repo()
    repo.upsert(_activity("abc123", start=_days_ago(1)))
    tool = GetActivityDetailTool(repo)
    result = tool.handle(activity_id="abc123")
    assert result.error is None
    assert result.data is not None
    assert result.data["activityId"] == "abc123"


def test_get_activity_detail_not_found():
    repo = _make_repo()
    tool = GetActivityDetailTool(repo)
    result = tool.handle(activity_id="nonexistent")
    assert result.data is None
