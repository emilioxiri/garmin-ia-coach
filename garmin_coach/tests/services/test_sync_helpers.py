"""Tests for services/sync_helpers.py."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock


from garmin_coach.services.sync_helpers import (
    compute_sync_window,
    daterange,
    merge_activity_details,
)


# ── daterange ─────────────────────────────────────────────────────────────────


def test_daterange_single_day():
    result = list(daterange("2024-01-05", "2024-01-05"))
    assert result == ["2024-01-05"]


def test_daterange_inclusive():
    result = list(daterange("2024-01-01", "2024-01-03"))
    assert result == ["2024-01-01", "2024-01-02", "2024-01-03"]


def test_daterange_empty_when_start_after_end():
    result = list(daterange("2024-01-05", "2024-01-01"))
    assert result == []


# ── compute_sync_window ───────────────────────────────────────────────────────


def _make_repos(
    activities_empty=True,
    sleep_empty=True,
    hrv_empty=True,
    body_battery_empty=True,
    last_activity_date: str | None = None,
    last_sleep_date: str | None = None,
):
    repos = MagicMock()

    repos.activities.is_empty.return_value = activities_empty
    repos.sleep.is_empty.return_value = sleep_empty
    repos.hrv.is_empty.return_value = hrv_empty
    repos.body_battery.is_empty.return_value = body_battery_empty

    acts = []
    if last_activity_date:
        acts = [{"startTimeLocal": last_activity_date + " 07:00:00"}]
    repos.activities.all.return_value = acts

    sleep_recs = []
    if last_sleep_date:
        sleep_recs = [{"date": last_sleep_date}]
    repos.sleep.all.return_value = sleep_recs
    repos.hrv.all.return_value = []
    repos.body_battery.all.return_value = []

    return repos


def test_compute_sync_window_empty_db_uses_default_days():
    repos = _make_repos()
    start, end = compute_sync_window(repos, default_days=30)
    expected_start = (date.today() - timedelta(days=30)).isoformat()
    assert start == expected_start
    assert end == date.today().isoformat()


def test_compute_sync_window_non_empty_db_uses_last_date():
    last = (date.today() - timedelta(days=5)).isoformat()
    repos = _make_repos(
        activities_empty=False,
        sleep_empty=True,
        hrv_empty=True,
        body_battery_empty=True,
        last_activity_date=last,
    )
    start, end = compute_sync_window(repos, default_days=30)
    assert start == last
    assert end == date.today().isoformat()


def test_compute_sync_window_uses_latest_across_tables():
    activity_date = (date.today() - timedelta(days=10)).isoformat()
    sleep_date = (date.today() - timedelta(days=3)).isoformat()
    repos = _make_repos(
        activities_empty=False,
        sleep_empty=False,
        hrv_empty=True,
        body_battery_empty=True,
        last_activity_date=activity_date,
        last_sleep_date=sleep_date,
    )
    start, end = compute_sync_window(repos, default_days=30)
    assert start == sleep_date


# ── merge_activity_details ────────────────────────────────────────────────────


def test_merge_activity_details_merges_top_level_keys():
    activities = [{"activityId": "1", "name": "Run", "normPower": None}]

    def fetcher(act_id):
        return {"normPower": 250, "intensityFactor": 0.9}

    result = merge_activity_details(activities, fetcher)
    assert result[0]["normPower"] == 250
    assert result[0]["intensityFactor"] == 0.9
    assert result[0]["name"] == "Run"


def test_merge_activity_details_flattens_summary_dto():
    activities = [{"activityId": "2", "verticalOscillation": None}]

    def fetcher(act_id):
        return {"summaryDTO": {"verticalOscillation": 8.5, "groundContactTime": 240}}

    result = merge_activity_details(activities, fetcher)
    assert result[0]["verticalOscillation"] == 8.5
    assert result[0]["groundContactTime"] == 240


def test_merge_activity_details_returns_original_when_fetcher_returns_none():
    activities = [{"activityId": "3", "name": "Bike"}]

    def fetcher(act_id):
        return None

    result = merge_activity_details(activities, fetcher)
    assert result == [{"activityId": "3", "name": "Bike"}]


def test_merge_activity_details_non_fatal_on_exception():
    activities = [{"activityId": "4", "name": "Swim"}]

    def fetcher(act_id):
        raise RuntimeError("API exploded")

    result = merge_activity_details(activities, fetcher)
    assert result == [{"activityId": "4", "name": "Swim"}]


def test_merge_activity_details_does_not_overwrite_with_none():
    activities = [{"activityId": "5", "averageHR": 145}]

    def fetcher(act_id):
        return {"averageHR": None, "newField": "value"}

    result = merge_activity_details(activities, fetcher)
    assert result[0]["averageHR"] == 145
    assert result[0]["newField"] == "value"


def test_merge_activity_details_multiple_activities():
    activities = [
        {"activityId": "10", "name": "Run"},
        {"activityId": "11", "name": "Bike"},
    ]
    calls: list[str] = []

    def fetcher(act_id):
        calls.append(act_id)
        return {"extra": f"data_{act_id}"}

    result = merge_activity_details(activities, fetcher)
    assert len(result) == 2
    assert result[0]["extra"] == "data_10"
    assert result[1]["extra"] == "data_11"
    assert calls == ["10", "11"]
