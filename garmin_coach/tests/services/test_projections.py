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
