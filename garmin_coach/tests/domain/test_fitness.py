"""Tests for domain/fitness.py dataclasses."""

from __future__ import annotations

import pytest

from garmin_coach.domain.fitness import (
    EnduranceScore,
    FitnessMetrics,
    LactateThreshold,
    PersonalRecord,
    RacePredictions,
)


@pytest.mark.parametrize(
    "cls",
    [FitnessMetrics, RacePredictions, LactateThreshold, EnduranceScore],
)
def test_from_dict_round_trip(cls):
    d = {"date": "2024-01-10", "value": 42, "extra": "preserved"}
    obj = cls.from_dict(d)
    assert obj.as_dict() == d


@pytest.mark.parametrize(
    "cls",
    [FitnessMetrics, RacePredictions, LactateThreshold, EnduranceScore],
)
def test_frozen(cls):
    obj = cls.from_dict({"date": "2024-01-10"})
    with pytest.raises((AttributeError, TypeError)):
        obj.payload = {}  # type: ignore[misc]


def test_personal_record_fields():
    pr = PersonalRecord(
        distance_label="5K",
        activity_id="123",
        date="2024-01-10",
        distance_km=5.0,
        duration_hms="25:00",
        pace_min_per_km="5:00",
        average_hr=155,
    )
    assert pr.distance_label == "5K"
    assert pr.distance_km == 5.0
    assert pr.pace_min_per_km == "5:00"


def test_personal_record_optional_fields():
    pr = PersonalRecord(
        distance_label="1K",
        activity_id="x",
        date="2024-01-01",
        distance_km=1.0,
        duration_hms="4:00",
        pace_min_per_km=None,
        average_hr=None,
    )
    assert pr.pace_min_per_km is None
    assert pr.average_hr is None


def test_personal_record_frozen():
    pr = PersonalRecord("5K", "1", "2024-01-01", 5.0, "25:00", "5:00", 150)
    with pytest.raises((AttributeError, TypeError)):
        pr.distance_label = "10K"  # type: ignore[misc]
