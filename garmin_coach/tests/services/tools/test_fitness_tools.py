"""Tests for services/tools/fitness_tools.py."""

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
from garmin_coach.services.tools.fitness_tools import (
    GetFitnessSnapshotTool,
    GetPersonalRecordsTool,
)


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _make_snapshot_repos(
    fm_record=None, rp_record=None, lt_record=None, es_record=None
):
    db = TinyDB(storage=MemoryStorage)
    fm = FitnessMetricsRepository(db)
    rp = RacePredictionsRepository(db)
    lt = LactateThresholdRepository(db)
    es = EnduranceScoreRepository(db)
    if fm_record:
        fm.replace(fm_record)
    if rp_record:
        rp.replace(rp_record)
    if lt_record:
        lt.replace(lt_record)
    if es_record:
        es.replace(es_record)
    return fm, rp, lt, es


def _make_activity_repo(activities: list[dict]):
    db = TinyDB(storage=MemoryStorage)
    repo = ActivityRepository(db)
    for a in activities:
        repo.upsert(a)
    return repo


def _run(activity_id, *, distance_m, duration_s, days_ago=5):
    return {
        "activityId": activity_id,
        "activityType": {"typeKey": "running"},
        "startTimeLocal": f"{_days_ago(days_ago)} 08:00:00",
        "distance": float(distance_m),
        "duration": float(duration_s),
        "averageHR": 155,
    }


# ── GetFitnessSnapshotTool ────────────────────────────────────────────────────


def test_fitness_snapshot_all_empty():
    fm, rp, lt, es = _make_snapshot_repos()
    tool = GetFitnessSnapshotTool(fm, rp, lt, es)
    result = tool.handle()
    assert result.error is None
    data = result.data
    assert data["fitness_metrics"] is None
    assert data["race_predictions"] is None
    assert data["lactate_threshold"] is None
    assert data["endurance_score"] is None


def test_fitness_snapshot_with_vo2max():
    fm, rp, lt, es = _make_snapshot_repos(
        fm_record={"date": _days_ago(1), "vo2max": 52.5}
    )
    tool = GetFitnessSnapshotTool(fm, rp, lt, es)
    result = tool.handle()
    assert result.data["fitness_metrics"]["vo2max"] == 52.5
    assert result.data["fitness_metrics"]["vo2max_running"] == 52.5


def test_fitness_snapshot_with_race_predictions():
    fm, rp, lt, es = _make_snapshot_repos(
        rp_record={
            "date": _days_ago(1),
            "predictions": {"time5K": 1500, "time10K": 3100},
        }
    )
    tool = GetFitnessSnapshotTool(fm, rp, lt, es)
    result = tool.handle()
    preds = result.data["race_predictions"]
    assert preds is not None
    assert preds["time5K"] == "0:25:00"


def test_fitness_snapshot_with_endurance_score():
    fm, rp, lt, es = _make_snapshot_repos(
        es_record={"date": _days_ago(1), "data": {"overallScore": 78}}
    )
    tool = GetFitnessSnapshotTool(fm, rp, lt, es)
    result = tool.handle()
    assert result.data["endurance_score"]["score"] == 78


# ── GetPersonalRecordsTool ────────────────────────────────────────────────────


def test_personal_records_empty_db():
    repo = _make_activity_repo([])
    tool = GetPersonalRecordsTool(repo)
    result = tool.handle()
    assert result.error is None
    assert result.data["records"]["5K"] is None
    assert result.data["activities_evaluated"] == 0


def test_personal_records_finds_5k():
    repo = _make_activity_repo([_run("r1", distance_m=5050, duration_s=1500)])
    tool = GetPersonalRecordsTool(repo)
    result = tool.handle()
    pr_5k = result.data["records"]["5K"]
    assert pr_5k is not None
    assert pr_5k["activityId"] == "r1"
    assert pr_5k["distance_km"] == 5.05


def test_personal_records_finds_best_5k():
    repo = _make_activity_repo(
        [
            _run("slow", distance_m=5000, duration_s=1800),
            _run("fast", distance_m=5000, duration_s=1200),
        ]
    )
    tool = GetPersonalRecordsTool(repo)
    result = tool.handle()
    assert result.data["records"]["5K"]["activityId"] == "fast"


def test_personal_records_ignores_non_runs():
    repo = _make_activity_repo(
        [
            {
                "activityId": "padel1",
                "activityType": {"typeKey": "padel"},
                "startTimeLocal": f"{_days_ago(3)} 10:00:00",
                "distance": 5000.0,
                "duration": 1200.0,
            }
        ]
    )
    tool = GetPersonalRecordsTool(repo)
    result = tool.handle()
    assert result.data["records"]["5K"] is None


def test_personal_records_has_pace():
    repo = _make_activity_repo([_run("r1", distance_m=10000, duration_s=3000)])
    tool = GetPersonalRecordsTool(repo)
    result = tool.handle()
    pr = result.data["records"]["10K"]
    assert pr is not None
    assert pr["pace_min_per_km"] is not None
    assert ":" in pr["pace_min_per_km"]


def test_personal_records_activities_count():
    repo = _make_activity_repo(
        [
            _run("r1", distance_m=5000, duration_s=1500),
            _run("r2", distance_m=10000, duration_s=3000),
        ]
    )
    tool = GetPersonalRecordsTool(repo)
    result = tool.handle()
    assert result.data["activities_evaluated"] == 2
