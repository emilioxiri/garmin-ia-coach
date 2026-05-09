"""Tests for domain/wellness.py dataclasses."""

from __future__ import annotations

import pytest

from garmin_coach.domain.wellness import (
    BodyBattery,
    HRV,
    Respiration,
    SPO2,
    Sleep,
    Stress,
    TrainingReadiness,
    TrainingStatus,
)


@pytest.mark.parametrize(
    "cls",
    [
        Sleep,
        HRV,
        BodyBattery,
        TrainingReadiness,
        TrainingStatus,
        Respiration,
        SPO2,
        Stress,
    ],
)
def test_from_dict_round_trip(cls):
    d = {"date": "2024-01-10", "score": 80, "extra": "preserved"}
    obj = cls.from_dict(d)
    assert obj.date == "2024-01-10"
    assert obj.as_dict() == d


@pytest.mark.parametrize(
    "cls",
    [
        Sleep,
        HRV,
        BodyBattery,
        TrainingReadiness,
        TrainingStatus,
        Respiration,
        SPO2,
        Stress,
    ],
)
def test_from_dict_missing_date(cls):
    obj = cls.from_dict({"score": 80})
    assert obj.date == ""


@pytest.mark.parametrize(
    "cls",
    [
        Sleep,
        HRV,
        BodyBattery,
        TrainingReadiness,
        TrainingStatus,
        Respiration,
        SPO2,
        Stress,
    ],
)
def test_frozen(cls):
    obj = cls.from_dict({"date": "2024-01-10"})
    with pytest.raises((AttributeError, TypeError)):
        obj.date = "changed"  # type: ignore[misc]
