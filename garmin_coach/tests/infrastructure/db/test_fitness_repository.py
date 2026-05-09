"""Tests for fitness snapshot repositories."""

from __future__ import annotations


def test_fitness_metrics_replace(memory_db):
    from garmin_coach.infrastructure.db.fitness_repository import (
        FitnessMetricsRepository,
    )

    repo = FitnessMetricsRepository(memory_db)
    repo.replace({"date": "2024-01-10", "vo2max": 50})
    repo.replace({"date": "2024-01-20", "vo2max": 52})
    assert repo.count() == 1
    assert repo.all()[0]["vo2max"] == 52


def test_fitness_metrics_latest(memory_db):
    from garmin_coach.infrastructure.db.fitness_repository import (
        FitnessMetricsRepository,
    )

    repo = FitnessMetricsRepository(memory_db)
    repo.insert({"date": "2024-01-10", "vo2max": 50})
    repo.insert({"date": "2024-01-20", "vo2max": 52})
    latest = repo.latest()
    assert latest["vo2max"] == 52


def test_fitness_metrics_latest_none_when_empty(memory_db):
    from garmin_coach.infrastructure.db.fitness_repository import (
        FitnessMetricsRepository,
    )

    repo = FitnessMetricsRepository(memory_db)
    assert repo.latest() is None


def test_race_predictions_replace(memory_db):
    from garmin_coach.infrastructure.db.fitness_repository import (
        RacePredictionsRepository,
    )

    repo = RacePredictionsRepository(memory_db)
    repo.replace({"date": "2024-01-10", "predictions": []})
    repo.replace({"date": "2024-01-20", "predictions": [{"time5K": 1200}]})
    assert repo.count() == 1
    assert repo.all()[0]["date"] == "2024-01-20"


def test_lactate_threshold_replace(memory_db):
    from garmin_coach.infrastructure.db.fitness_repository import (
        LactateThresholdRepository,
    )

    repo = LactateThresholdRepository(memory_db)
    repo.replace({"date": "2024-01-10", "heartRateValue": 165})
    repo.replace({"date": "2024-01-20", "heartRateValue": 168})
    assert repo.count() == 1
    assert repo.latest()["heartRateValue"] == 168


def test_endurance_score_replace(memory_db):
    from garmin_coach.infrastructure.db.fitness_repository import (
        EnduranceScoreRepository,
    )

    repo = EnduranceScoreRepository(memory_db)
    repo.replace({"date": "2024-01-10", "data": {"overallScore": 70}})
    assert repo.count() == 1
    assert repo.latest()["data"]["overallScore"] == 70


def test_replace_truncates_before_insert(memory_db):
    from garmin_coach.infrastructure.db.fitness_repository import (
        FitnessMetricsRepository,
    )

    repo = FitnessMetricsRepository(memory_db)
    for i in range(5):
        repo.insert({"date": f"2024-01-{i + 1:02d}", "vo2max": 50 + i})
    assert repo.count() == 5
    repo.replace({"date": "2024-02-01", "vo2max": 60})
    assert repo.count() == 1
