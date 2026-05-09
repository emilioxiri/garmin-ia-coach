"""Tests for ActivityRepository."""

from __future__ import annotations

from datetime import date, timedelta

import pytest


def _run_act(activity_id, start_date, distance_m=10000.0, duration_s=3600.0, hr=150):
    return {
        "activityId": activity_id,
        "startTimeLocal": f"{start_date} 08:00:00",
        "activityType": {"typeKey": "running"},
        "distance": distance_m,
        "duration": duration_s,
        "averageHR": hr,
    }


def _cycling_act(activity_id, start_date, distance_m=30000.0):
    return {
        "activityId": activity_id,
        "startTimeLocal": f"{start_date} 10:00:00",
        "activityType": {"typeKey": "cycling"},
        "distance": distance_m,
        "duration": 5400.0,
        "averageHR": 130,
    }


def _strength_act(activity_id, start_date):
    return {
        "activityId": activity_id,
        "startTimeLocal": f"{start_date} 07:00:00",
        "activityType": {"typeKey": "strength_training"},
        "duration": 2700.0,
        "averageHR": 120,
    }


def _repo(memory_db):
    from garmin_coach.infrastructure.db.activity_repository import ActivityRepository

    return ActivityRepository(memory_db)


# ── Basic CRUD ────────────────────────────────────────────────────────────────


def test_upsert_and_all(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("1", "2024-01-10"))
    assert repo.count() == 1


def test_upsert_updates(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("1", "2024-01-10", distance_m=5000.0))
    repo.upsert({**_run_act("1", "2024-01-10"), "distance": 6000.0})
    assert repo.count() == 1
    assert repo.all()[0]["distance"] == 6000.0


def test_latest_date(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("1", "2024-01-10"))
    repo.upsert(_run_act("2", "2024-01-20"))
    assert repo.latest_date() == "2024-01-20"


def test_latest_date_none_when_empty(memory_db):
    assert _repo(memory_db).latest_date() is None


# ── find_runs_in_window ───────────────────────────────────────────────────────


def test_find_runs_in_window_returns_only_runs(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("r1", "2024-01-10"))
    repo.upsert(_cycling_act("c1", "2024-01-10"))
    repo.upsert(_strength_act("s1", "2024-01-10"))
    runs = repo.find_runs_in_window("2024-01-01", "2024-01-31")
    ids = {r["activityId"] for r in runs}
    assert ids == {"r1"}


def test_find_runs_in_window_respects_dates(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("in", "2024-01-15"))
    repo.upsert(_run_act("out", "2024-01-25"))
    runs = repo.find_runs_in_window("2024-01-01", "2024-01-20")
    assert len(runs) == 1
    assert runs[0]["activityId"] == "in"


def test_find_runs_in_window_sorted_desc(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("r1", "2024-01-05"))
    repo.upsert(_run_act("r2", "2024-01-10"))
    repo.upsert(_run_act("r3", "2024-01-15"))
    runs = repo.find_runs_in_window("2024-01-01", "2024-01-31")
    dates = [r["startTimeLocal"][:10] for r in runs]
    assert dates == sorted(dates, reverse=True)


# ── find_by_weekday ───────────────────────────────────────────────────────────


def _recent_weekday(target_weekday: int) -> str:
    """Return ISO date of the most recent occurrence of target_weekday (0=Mon)."""
    today = date.today()
    days_back = (today.weekday() - target_weekday) % 7
    if days_back == 0:
        days_back = 7  # go to last week so it's clearly in the past
    return (today - timedelta(days=days_back)).isoformat()


def test_find_by_weekday_lunes(memory_db):
    repo = _repo(memory_db)
    monday = _recent_weekday(0)  # Monday
    tuesday = _recent_weekday(1)  # Tuesday
    repo.upsert(_run_act("mon", monday))
    repo.upsert(_run_act("tue", tuesday))
    results = repo.find_by_weekday("lunes", days_back=30)
    ids = {r["activityId"] for r in results}
    assert "mon" in ids
    assert "tue" not in ids


def test_find_by_weekday_invalid_returns_empty(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("1", date.today().isoformat()))
    assert repo.find_by_weekday("notaday", days_back=90) == []


def test_find_by_weekday_sabado_no_accent(memory_db):
    repo = _repo(memory_db)
    saturday = _recent_weekday(5)  # Saturday
    repo.upsert(_run_act("sat", saturday))
    results = repo.find_by_weekday("sabado", days_back=30)
    ids = {r["activityId"] for r in results}
    assert "sat" in ids


# ── find_by_min_distance_km ───────────────────────────────────────────────────


def test_find_by_min_distance_km(memory_db):
    repo = _repo(memory_db)
    today = date.today().isoformat()
    repo.upsert(_run_act("short", today, distance_m=4000.0))
    repo.upsert(_run_act("long", today, distance_m=15000.0))
    results = repo.find_by_min_distance_km(min_km=10.0, days_back=1)
    ids = {r["activityId"] for r in results}
    assert "long" in ids
    assert "short" not in ids


def test_find_by_min_distance_km_respects_days_back(memory_db):
    repo = _repo(memory_db)
    old = (date.today() - timedelta(days=60)).isoformat()
    recent = date.today().isoformat()
    repo.upsert(_run_act("old", old, distance_m=20000.0))
    repo.upsert(_run_act("new", recent, distance_m=20000.0))
    results = repo.find_by_min_distance_km(min_km=10.0, days_back=7)
    ids = {r["activityId"] for r in results}
    assert "new" in ids
    assert "old" not in ids


# ── find_by_type ──────────────────────────────────────────────────────────────


def test_find_by_type_cycling(memory_db):
    repo = _repo(memory_db)
    today = date.today().isoformat()
    repo.upsert(_run_act("r1", today))
    repo.upsert(_cycling_act("c1", today))
    results = repo.find_by_type("cycling", days_back=1)
    ids = {r["activityId"] for r in results}
    assert ids == {"c1"}


def test_find_by_type_no_match_returns_empty(memory_db):
    repo = _repo(memory_db)
    today = date.today().isoformat()
    repo.upsert(_run_act("r1", today))
    assert repo.find_by_type("swimming", days_back=1) == []


# ── compute_personal_records ──────────────────────────────────────────────────


def test_compute_personal_records_5k(memory_db):
    repo = _repo(memory_db)
    # 5K in 25 min
    repo.upsert(_run_act("5k", "2024-01-01", distance_m=5000.0, duration_s=1500.0))
    bests = repo.compute_personal_records()
    assert bests["5K"] is not None
    assert bests["5K"].distance_km == 5.0
    assert bests["5K"].duration_hms == "25:00"


def test_compute_personal_records_10k(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("10k", "2024-01-01", distance_m=10000.0, duration_s=3000.0))
    bests = repo.compute_personal_records()
    assert bests["10K"] is not None
    assert bests["10K"].distance_km == 10.0


def test_compute_personal_records_half_marathon(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("hm", "2024-01-01", distance_m=21097.0, duration_s=6000.0))
    bests = repo.compute_personal_records()
    assert bests["half_marathon"] is not None
    assert bests["half_marathon"].distance_km == pytest.approx(21.097, abs=0.01)


def test_compute_personal_records_marathon(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("m", "2024-01-01", distance_m=42195.0, duration_s=14400.0))
    bests = repo.compute_personal_records()
    assert bests["marathon"] is not None
    assert bests["marathon"].duration_hms == "4:00:00"


def test_compute_personal_records_ignores_cycling(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_cycling_act("c1", "2024-01-01", distance_m=5000.0))
    bests = repo.compute_personal_records()
    assert bests["5K"] is None


def test_compute_personal_records_picks_fastest(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("slow", "2024-01-01", distance_m=5000.0, duration_s=2000.0))
    repo.upsert(_run_act("fast", "2024-01-05", distance_m=5000.0, duration_s=1500.0))
    bests = repo.compute_personal_records()
    assert bests["5K"].activity_id == "fast"


def test_compute_personal_records_longest_run(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_run_act("short", "2024-01-01", distance_m=5000.0))
    repo.upsert(_run_act("long", "2024-01-05", distance_m=25000.0))
    bests = repo.compute_personal_records()
    assert bests["longest_run"] is not None
    assert bests["longest_run"].activity_id == "long"
    assert bests["longest_run"].distance_km == 25.0


def test_compute_personal_records_longest_run_ignores_cycling(memory_db):
    repo = _repo(memory_db)
    repo.upsert(_cycling_act("big_bike", "2024-01-01", distance_m=100000.0))
    repo.upsert(_run_act("small_run", "2024-01-05", distance_m=5000.0))
    bests = repo.compute_personal_records()
    assert bests["longest_run"].activity_id == "small_run"


def test_compute_personal_records_all_none_when_empty(memory_db):
    repo = _repo(memory_db)
    bests = repo.compute_personal_records()
    assert all(v is None for v in bests.values())


def test_compute_personal_records_pace_format(memory_db):
    repo = _repo(memory_db)
    # 5K in exactly 25:00 → pace = 5:00 min/km
    repo.upsert(_run_act("5k", "2024-01-01", distance_m=5000.0, duration_s=1500.0))
    bests = repo.compute_personal_records()
    assert bests["5K"].pace_min_per_km == "5:00"
