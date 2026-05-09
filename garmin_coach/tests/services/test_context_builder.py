"""Tests for services/context_builder.py — ContextBuilder class."""

from datetime import date, timedelta

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from garmin_coach.infrastructure.db.activity_repository import ActivityRepository
from garmin_coach.infrastructure.db.fitness_repository import (
    EnduranceScoreRepository,
    FitnessMetricsRepository,
    LactateThresholdRepository,
    RacePredictionsRepository,
)
from garmin_coach.infrastructure.db.memory_repository import MemoryRepository
from garmin_coach.infrastructure.db.wellness_repository import (
    BodyBatteryRepository,
    HRVRepository,
    RespirationRepository,
    SPO2Repository,
    SleepRepository,
    StressRepository,
    TrainingReadinessRepository,
    TrainingStatusRepository,
)
from garmin_coach.services.context_builder import ContextBuilder


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _make_builder() -> tuple[ContextBuilder, TinyDB]:
    db = TinyDB(storage=MemoryStorage)
    builder = ContextBuilder(
        activity_repo=ActivityRepository(db),
        sleep_repo=SleepRepository(db),
        hrv_repo=HRVRepository(db),
        body_battery_repo=BodyBatteryRepository(db),
        training_status_repo=TrainingStatusRepository(db),
        training_readiness_repo=TrainingReadinessRepository(db),
        respiration_repo=RespirationRepository(db),
        spo2_repo=SPO2Repository(db),
        stress_repo=StressRepository(db),
        fitness_metrics_repo=FitnessMetricsRepository(db),
        race_predictions_repo=RacePredictionsRepository(db),
        lactate_repo=LactateThresholdRepository(db),
        endurance_repo=EnduranceScoreRepository(db),
        memory_repo=MemoryRepository(db),
    )
    return builder, db


def test_build_returns_required_keys():
    builder, _ = _make_builder()
    result = builder.build(days=7)
    required = {
        "activities",
        "notable_runs",
        "sleep",
        "hrv",
        "body_battery",
        "fitness_metrics",
        "race_predictions",
        "memory",
    }
    assert required.issubset(result.keys())


def test_build_raw_returns_required_keys():
    builder, _ = _make_builder()
    raw = builder.build_raw(days=7)
    assert "activities" in raw
    assert "sleep" in raw
    assert "days_covered" in raw


def test_build_empty_db():
    builder, _ = _make_builder()
    result = builder.build(days=7)
    assert result["activities"] == []
    assert result["notable_runs"] == []
    assert result["memory"] == []


def test_build_filters_activities_by_window():
    builder, db = _make_builder()
    repo = ActivityRepository(db)
    repo.upsert(
        {
            "activityId": "recent",
            "activityType": {"typeKey": "running"},
            "startTimeLocal": f"{_days_ago(3)} 08:00:00",
            "distance": 10000.0,
            "duration": 3000.0,
        }
    )
    repo.upsert(
        {
            "activityId": "old",
            "activityType": {"typeKey": "running"},
            "startTimeLocal": f"{_days_ago(30)} 08:00:00",
            "distance": 5000.0,
            "duration": 1500.0,
        }
    )
    result = builder.build(days=7)
    ids = [a["activityId"] for a in result["activities"]]
    assert "recent" in ids
    assert "old" not in ids


def test_build_notable_runs_top3_longest():
    builder, db = _make_builder()
    repo = ActivityRepository(db)
    for i, dist in enumerate([5000, 10000, 21097, 15000]):
        repo.upsert(
            {
                "activityId": str(i),
                "activityType": {"typeKey": "running"},
                "startTimeLocal": f"{_days_ago(i + 1)} 08:00:00",
                "distance": float(dist),
                "duration": float(dist / 3),
            }
        )
    result = builder.build(days=14)
    notable = result["notable_runs"]
    assert len(notable) <= 3
    distances = [r["distance_km"] for r in notable]
    assert distances == sorted(distances, reverse=True)


def test_build_days_covered_default():
    builder, _ = _make_builder()
    result = builder.build()
    assert result["days_covered"] == 7


def test_build_with_custom_days():
    builder, _ = _make_builder()
    result = builder.build(days=14, max_activities=5)
    assert result["days_covered"] == 14


def test_build_includes_sleep_summary():
    builder, db = _make_builder()
    repo = SleepRepository(db)
    repo.upsert(
        {"date": _days_ago(1), "duration_s": 28800, "score": 82, "restingHR": 48}
    )
    result = builder.build(days=7)
    sleep = result["sleep"]
    assert len(sleep["recent"]) == 1
    assert sleep["score_summary"] is not None
    assert sleep["score_summary"]["last"] == 82


def test_build_includes_memory():
    builder, db = _make_builder()
    repo = MemoryRepository(db)
    repo.add("lesión leve rodilla")
    result = builder.build(days=7)
    assert any("lesión" in (r.get("note") or "") for r in result["memory"])
