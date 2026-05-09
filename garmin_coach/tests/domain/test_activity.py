"""Tests for domain/activity.py — ActivityType enum and Activity dataclass."""

from __future__ import annotations

import pytest

from garmin_coach.domain.activity import (
    NON_DISTANCE_TYPES,
    RUN_TYPES,
    Activity,
    ActivityType,
)


# ── ActivityType.is_run ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "type_key",
    [
        "running",
        "trail_running",
        "treadmill_running",
        "virtual_run",
        "track_running",
        "indoor_running",
        "street_running",
    ],
)
def test_is_run_true_for_run_types(type_key):
    assert ActivityType(type_key).is_run() is True


@pytest.mark.parametrize(
    "type_key",
    ["cycling", "swimming", "padel", "strength_training", "yoga", "walking"],
)
def test_is_run_false_for_non_run_types(type_key):
    assert ActivityType(type_key).is_run() is False


# ── ActivityType.is_distance_based ────────────────────────────────────────────


@pytest.mark.parametrize(
    "type_key",
    ["padel", "tennis", "strength_training", "yoga", "hiit", "indoor_climbing"],
)
def test_is_distance_based_false_for_non_distance(type_key):
    assert ActivityType(type_key).is_distance_based() is False


@pytest.mark.parametrize(
    "type_key",
    ["running", "cycling", "swimming", "walking", "hiking"],
)
def test_is_distance_based_true_for_distance_types(type_key):
    assert ActivityType(type_key).is_distance_based() is True


# ── RUN_TYPES / NON_DISTANCE_TYPES backward-compat constants ─────────────────


def test_run_types_is_frozenset_of_strings():
    assert isinstance(RUN_TYPES, frozenset)
    assert all(isinstance(t, str) for t in RUN_TYPES)
    assert "running" in RUN_TYPES
    assert "trail_running" in RUN_TYPES


def test_non_distance_types_is_frozenset_of_strings():
    assert isinstance(NON_DISTANCE_TYPES, frozenset)
    assert "padel" in NON_DISTANCE_TYPES
    assert "strength_training" in NON_DISTANCE_TYPES
    assert "running" not in NON_DISTANCE_TYPES


# ── Activity.from_dict ────────────────────────────────────────────────────────


def test_from_dict_basic():
    d = {
        "activityId": "123",
        "startTimeLocal": "2024-01-10 08:00:00",
        "activityType": {"typeKey": "running"},
        "distance": 10000.0,
        "duration": 3600.0,
        "averageHR": 150,
        "maxHR": 175,
    }
    act = Activity.from_dict(d)
    assert act.activity_id == "123"
    assert act.start_time_local == "2024-01-10 08:00:00"
    assert act.activity_type == "running"
    assert act.distance_m == 10000.0
    assert act.duration_s == 3600.0
    assert act.average_hr == 150
    assert act.max_hr == 175


def test_from_dict_string_activity_type():
    d = {"activityId": "1", "activityType": "cycling", "distance": 30000.0}
    act = Activity.from_dict(d)
    assert act.activity_type == "cycling"


def test_from_dict_missing_fields_defaults():
    act = Activity.from_dict({"activityId": "x"})
    assert act.distance_m is None
    assert act.duration_s is None
    assert act.average_hr is None
    assert act.max_hr is None
    assert act.activity_type == "other"


def test_from_dict_missing_activity_id_uses_empty_string():
    act = Activity.from_dict({})
    assert act.activity_id == ""


def test_from_dict_null_activity_type_dict():
    act = Activity.from_dict({"activityType": {"typeKey": None}})
    assert act.activity_type == "other"


def test_from_dict_integer_activity_id_coerced_to_str():
    act = Activity.from_dict({"activityId": 42})
    assert act.activity_id == "42"


# ── Activity.as_dict (round-trip) ─────────────────────────────────────────────


def test_as_dict_round_trip():
    d = {
        "activityId": "123",
        "startTimeLocal": "2024-01-10 08:00:00",
        "activityType": {"typeKey": "running"},
        "distance": 10000.0,
        "duration": 3600.0,
        "averageHR": 150,
        "custom_field": "preserved",
    }
    act = Activity.from_dict(d)
    result = act.as_dict()
    assert result == d


def test_as_dict_does_not_mutate_original():
    d = {"activityId": "1", "distance": 5000.0}
    act = Activity.from_dict(d)
    result = act.as_dict()
    result["distance"] = 9999.0
    assert act.payload["distance"] == 5000.0


# ── Activity.date_iso ─────────────────────────────────────────────────────────


def test_date_iso_from_start_time_local():
    act = Activity.from_dict({"startTimeLocal": "2024-01-10 08:00:00"})
    assert act.date_iso == "2024-01-10"


def test_date_iso_none_when_empty():
    act = Activity.from_dict({"startTimeLocal": ""})
    assert act.date_iso is None


def test_date_iso_none_when_missing():
    act = Activity.from_dict({})
    assert act.date_iso is None


# ── Frozen / immutability ─────────────────────────────────────────────────────


def test_activity_is_frozen():
    act = Activity.from_dict({"activityId": "1"})
    with pytest.raises((AttributeError, TypeError)):
        act.activity_id = "changed"  # type: ignore[misc]
