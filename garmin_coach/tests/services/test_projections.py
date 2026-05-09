"""Tests for services/projections.py — pure projection functions."""

from garmin_coach.services.projections import (
    _format_duration,
    aggregate_series,
    slim_activity,
    slim_body_battery,
    slim_endurance_score,
    slim_fitness_metrics,
    slim_hrv,
    slim_lactate_threshold,
    slim_race_predictions,
    slim_sleep,
    slim_training_readiness,
)


# ── _format_duration ──────────────────────────────────────────────────────────


def test_format_duration_seconds_only():
    assert _format_duration(90) == "1:30"


def test_format_duration_with_hours():
    assert _format_duration(3661) == "1:01:01"


def test_format_duration_zero():
    assert _format_duration(0) == "0:00"


def test_format_duration_invalid():
    assert _format_duration("abc") is None
    assert _format_duration(-10) is None


def test_format_duration_carry():
    assert _format_duration(3600) == "1:00:00"


# ── slim_activity ─────────────────────────────────────────────────────────────


def _make_run(distance_m=10000.0, speed=2.5, duration_s=4000.0):
    return {
        "activityId": "r1",
        "activityType": {"typeKey": "running"},
        "startTimeLocal": "2025-05-01 08:00:00",
        "distance": distance_m,
        "averageSpeed": speed,
        "duration": duration_s,
        "aerobicTrainingEffect": 3.5,
        "anaerobicTrainingEffect": 0.5,
    }


def test_slim_activity_adds_date_and_weekday():
    out = slim_activity(_make_run())
    assert out["date"] == "2025-05-01"
    assert out["weekday"] == "jueves"


def test_slim_activity_converts_duration():
    out = slim_activity(_make_run(duration_s=3661))
    assert out["duration_hms"] == "1:01:01"
    assert "duration" not in out


def test_slim_activity_adds_distance_km():
    out = slim_activity(_make_run(distance_m=10000.0))
    assert out["distance_km"] == 10.0


def test_slim_activity_adds_pace():
    out = slim_activity(_make_run(speed=3.0))  # 3 m/s = 5:33 min/km
    assert "pace_min_per_km" in out
    assert ":" in out["pace_min_per_km"]


def test_slim_activity_renames_training_effect():
    out = slim_activity(_make_run())
    assert "aerobic_te" in out
    assert "anaerobic_te" in out
    assert "aerobicTrainingEffect" not in out


def test_slim_activity_is_run_flag():
    out = slim_activity(_make_run())
    assert out.get("is_run") is True


def test_slim_activity_is_long_run_above_threshold():
    out = slim_activity(_make_run(distance_m=16000.0))
    assert out.get("is_long_run") is True


def test_slim_activity_is_long_run_below_threshold():
    out = slim_activity(_make_run(distance_m=5000.0))
    assert "is_long_run" not in out


def test_slim_activity_non_distance_drops_distance_fields():
    padel = {
        "activityId": "p1",
        "activityType": {"typeKey": "padel"},
        "startTimeLocal": "2025-05-01 10:00:00",
        "distance": 200.0,
        "averageSpeed": 1.0,
        "duration": 3600.0,
    }
    out = slim_activity(padel)
    assert "distance_km" not in out
    assert "pace_min_per_km" not in out
    assert "averageSpeed" not in out


def test_slim_activity_type_string():
    act = {
        "activityId": "x1",
        "activityType": "running",
        "startTimeLocal": "2025-05-01 08:00:00",
        "distance": 5000.0,
        "duration": 1500.0,
    }
    out = slim_activity(act)
    assert out["type"] == "running"


# ── slim_sleep ────────────────────────────────────────────────────────────────


def test_slim_sleep_converts_to_hours():
    record = {"date": "2025-05-01", "duration_s": 28800, "deep_s": 7200, "score": 85}
    out = slim_sleep(record)
    assert out["total_h"] == 8.0
    assert out["deep_h"] == 2.0
    assert out["score"] == 85


def test_slim_sleep_none_for_missing():
    out = slim_sleep({"date": "2025-05-01"})
    assert out["total_h"] is None


# ── slim_hrv ──────────────────────────────────────────────────────────────────


def test_slim_hrv():
    record = {
        "date": "2025-05-01",
        "lastNight": 55,
        "weeklyAvg": 52,
        "status": "balanced",
    }
    out = slim_hrv(record)
    assert out == {
        "date": "2025-05-01",
        "lastNight": 55,
        "weeklyAvg": 52,
        "status": "balanced",
    }


# ── slim_body_battery ─────────────────────────────────────────────────────────


def test_slim_body_battery():
    record = {"date": "2025-05-01", "max": 90, "min": 20}
    out = slim_body_battery(record)
    assert out == {"date": "2025-05-01", "max": 90, "min": 20}


# ── aggregate_series ──────────────────────────────────────────────────────────


def test_aggregate_series_basic():
    records = [{"score": 80}, {"score": 60}, {"score": 70}]
    result = aggregate_series(records, "score")
    assert result["last"] == 80
    assert result["min"] == 60
    assert result["max"] == 80
    assert result["n"] == 3


def test_aggregate_series_empty():
    assert aggregate_series([], "score") is None


def test_aggregate_series_skips_non_numeric():
    records = [{"score": 80}, {"score": "bad"}, {"score": 60}]
    result = aggregate_series(records, "score")
    assert result["n"] == 2


# ── slim_fitness_metrics ──────────────────────────────────────────────────────


def test_slim_fitness_metrics_none():
    assert slim_fitness_metrics(None) is None


def test_slim_fitness_metrics_exposes_alias():
    out = slim_fitness_metrics({"date": "2025-05-01", "vo2max": 52.5})
    assert out["vo2max"] == 52.5
    assert out["vo2max_running"] == 52.5


# ── slim_race_predictions ─────────────────────────────────────────────────────


def test_slim_race_predictions_none():
    assert slim_race_predictions(None) is None


def test_slim_race_predictions_dict_format():
    record = {
        "date": "2025-05-01",
        "predictions": {"time5K": 1500, "time10K": 3100},
    }
    out = slim_race_predictions(record)
    assert out["time5K"] == 1500


def test_slim_race_predictions_list_format():
    record = {
        "date": "2025-05-01",
        "predictions": [{"time5K": 1600, "time10K": 3300}],
    }
    out = slim_race_predictions(record)
    assert out["time5K"] == 1600


# ── slim_lactate_threshold ────────────────────────────────────────────────────


def test_slim_lactate_threshold_none():
    assert slim_lactate_threshold(None) is None


def test_slim_lactate_threshold_extracts_fields():
    record = {
        "date": "2025-05-01",
        "heartRateValue": 170,
        "speedValue": 3.2,
        "userId": 42,
        "extra": "ignored",
    }
    out = slim_lactate_threshold(record)
    assert out["heartRateValue"] == 170
    assert "extra" not in out


# ── slim_training_readiness ───────────────────────────────────────────────────


def test_slim_training_readiness():
    record = {
        "date": "2025-05-01",
        "score": 75,
        "level": "good",
        "feedback": "ok",
        "extra": "x",
    }
    out = slim_training_readiness(record)
    assert out["score"] == 75
    assert "extra" not in out


# ── slim_endurance_score ──────────────────────────────────────────────────────


def test_slim_endurance_score_none():
    assert slim_endurance_score(None) is None


def test_slim_endurance_score_extracts_overall():
    record = {"date": "2025-05-01", "data": {"overallScore": 78}}
    out = slim_endurance_score(record)
    assert out["score"] == 78


# ── _pace_to_seconds ──────────────────────────────────────────────────────────


def test_pace_to_seconds_valid():
    from garmin_coach.services.projections import _pace_to_seconds

    assert _pace_to_seconds("5:30") == 330
    assert _pace_to_seconds("4:00") == 240


def test_pace_to_seconds_invalid():
    from garmin_coach.services.projections import _pace_to_seconds

    assert _pace_to_seconds(None) is None
    assert _pace_to_seconds("abc") is None
    assert _pace_to_seconds("5") is None
    assert _pace_to_seconds("a:b") is None


# ── compute_hrv_trend ─────────────────────────────────────────────────────────


def test_compute_hrv_trend_descending():
    from garmin_coach.services.projections import compute_hrv_trend

    records = [
        {"date": "2025-05-09", "lastNight": 50},
        {"date": "2025-05-08", "lastNight": 55},
        {"date": "2025-05-07", "lastNight": 60},
        {"date": "2025-05-06", "lastNight": 65},
    ]
    out = compute_hrv_trend(records, days=14)
    assert out["direction"] == "descendiendo"
    assert out["slope_per_day"] < 0
    assert out["n"] == 4


def test_compute_hrv_trend_ascending():
    from garmin_coach.services.projections import compute_hrv_trend

    records = [
        {"date": "2025-05-09", "lastNight": 70},
        {"date": "2025-05-08", "lastNight": 65},
        {"date": "2025-05-07", "lastNight": 60},
    ]
    out = compute_hrv_trend(records, days=14)
    assert out["direction"] == "subiendo"
    assert out["slope_per_day"] > 0


def test_compute_hrv_trend_stable():
    from garmin_coach.services.projections import compute_hrv_trend

    records = [
        {"date": "2025-05-09", "lastNight": 60},
        {"date": "2025-05-08", "lastNight": 60.05},
        {"date": "2025-05-07", "lastNight": 59.9},
    ]
    out = compute_hrv_trend(records, days=14)
    assert out["direction"] == "estable"


def test_compute_hrv_trend_too_few_records():
    from garmin_coach.services.projections import compute_hrv_trend

    assert compute_hrv_trend([], days=14) is None
    assert compute_hrv_trend([{"lastNight": 50}, {"lastNight": 55}], days=14) is None


def test_compute_hrv_trend_skips_non_numeric():
    from garmin_coach.services.projections import compute_hrv_trend

    records = [
        {"date": "2025-05-09", "lastNight": None},
        {"date": "2025-05-08", "lastNight": "bad"},
        {"date": "2025-05-07", "lastNight": 60},
    ]
    assert compute_hrv_trend(records, days=14) is None


# ── compute_weekly_load ───────────────────────────────────────────────────────


def test_compute_weekly_load_with_chronic_history():
    from datetime import datetime, timedelta

    from garmin_coach.services.projections import compute_weekly_load

    today = datetime.now().date()

    def _act(days_ago: int, load: float) -> dict:
        d = (today - timedelta(days=days_ago)).isoformat()
        return {"date": d, "activityTrainingLoad": load, "is_run": True}

    acts = [
        _act(1, 100),
        _act(3, 80),
        _act(8, 90),
        _act(15, 85),
        _act(22, 70),
    ]
    out = compute_weekly_load(acts)
    assert out["weekly_load"] == 180.0
    assert out["acwr"] is not None
    assert out["chronic_avg"] is not None


def test_compute_weekly_load_no_chronic():
    from datetime import datetime

    from garmin_coach.services.projections import compute_weekly_load

    today = datetime.now().date()
    acts = [{"date": today.isoformat(), "activityTrainingLoad": 50}]
    out = compute_weekly_load(acts)
    assert out["weekly_load"] == 50.0
    assert out["acwr"] is None


def test_compute_weekly_load_empty():
    from garmin_coach.services.projections import compute_weekly_load

    assert compute_weekly_load([]) is None


def test_compute_weekly_load_ignores_invalid_dates():
    from garmin_coach.services.projections import compute_weekly_load

    acts = [{"date": "not-a-date", "activityTrainingLoad": 50}]
    out = compute_weekly_load(acts)
    assert out["weekly_load"] == 0.0


# ── compute_resting_hr_trend ──────────────────────────────────────────────────


def test_compute_resting_hr_trend_full_window():
    from garmin_coach.services.projections import compute_resting_hr_trend

    records = [
        {"date": f"2025-05-{15 - i:02d}", "restingHR": 50 + i} for i in range(14)
    ]
    out = compute_resting_hr_trend(records)
    assert out["last_week_mean"] is not None
    assert out["prior_week_mean"] is not None
    assert out["delta"] is not None


def test_compute_resting_hr_trend_only_last_week():
    from garmin_coach.services.projections import compute_resting_hr_trend

    records = [{"date": f"2025-05-{9 - i:02d}", "restingHR": 55} for i in range(5)]
    out = compute_resting_hr_trend(records)
    assert out["last_week_mean"] == 55.0
    assert out["delta"] is None


def test_compute_resting_hr_trend_too_few():
    from garmin_coach.services.projections import compute_resting_hr_trend

    assert compute_resting_hr_trend([]) is None
    assert (
        compute_resting_hr_trend(
            [{"restingHR": 55}, {"restingHR": 56}, {"restingHR": 54}]
        )
        is None
    )


# ── compute_fastest_runs ──────────────────────────────────────────────────────


def test_compute_fastest_runs_orders_by_pace():
    from garmin_coach.services.projections import compute_fastest_runs

    acts = [
        {"is_run": True, "distance_km": 10, "pace_min_per_km": "4:30"},
        {"is_run": True, "distance_km": 5, "pace_min_per_km": "4:00"},
        {"is_run": True, "distance_km": 8, "pace_min_per_km": "4:15"},
    ]
    out = compute_fastest_runs(acts, top_n=3)
    assert [a["pace_min_per_km"] for a in out] == ["4:00", "4:15", "4:30"]


def test_compute_fastest_runs_filters_short():
    from garmin_coach.services.projections import compute_fastest_runs

    acts = [
        {"is_run": True, "distance_km": 1.5, "pace_min_per_km": "3:30"},
        {"is_run": True, "distance_km": 5, "pace_min_per_km": "4:30"},
    ]
    out = compute_fastest_runs(acts, min_distance_km=3.0)
    assert len(out) == 1
    assert out[0]["pace_min_per_km"] == "4:30"


def test_compute_fastest_runs_skips_non_runs():
    from garmin_coach.services.projections import compute_fastest_runs

    acts = [
        {"is_run": False, "distance_km": 30, "pace_min_per_km": "3:00"},
        {"is_run": True, "distance_km": 5, "pace_min_per_km": "5:00"},
    ]
    out = compute_fastest_runs(acts)
    assert len(out) == 1
    assert out[0]["pace_min_per_km"] == "5:00"


def test_compute_fastest_runs_empty():
    from garmin_coach.services.projections import compute_fastest_runs

    assert compute_fastest_runs([]) == []
