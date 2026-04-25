"""Unit tests for context_builder.py — slim_* projections, aggregations, build_context."""

import json
from garmin_coach.context_builder import (
    slim_activity,
    slim_sleep,
    slim_hrv,
    slim_body_battery,
    slim_respiration,
    slim_spo2,
    slim_stress,
    slim_training_status,
    slim_training_readiness,
    slim_fitness_metrics,
    slim_race_predictions,
    slim_lactate_threshold,
    slim_endurance_score,
    aggregate_series,
    build_context,
)


# ── slim_activity ─────────────────────────────────────────────────────────────


def test_slim_activity_keeps_relevant_fields():
    raw = {
        "activityId": "123",
        "activityName": "Morning Run",
        "startTimeLocal": "2026-04-25 08:00:00",
        "distance": 10000.5,
        "duration": 3000.0,
        "averageHR": 145.4,
        "maxHR": 175,
        "averageSpeed": 3.33,
        "calories": 700,
        "vO2MaxValue": 55.6,
        "splits": [{"distance": 1000} for _ in range(20)],
        "hrZones": [{"zone": 1}],
        "polyline": "x" * 5000,
    }
    slim = slim_activity(raw)
    assert slim["activityId"] == "123"
    assert slim["distance"] == 10000.5
    assert slim["averageHR"] == 145.4
    assert "splits" not in slim
    assert "hrZones" not in slim
    assert "polyline" not in slim


def test_slim_activity_extracts_type_key_from_dict():
    raw = {"activityId": "1", "activityType": {"typeKey": "running"}}
    assert slim_activity(raw)["type"] == "running"


def test_slim_activity_handles_string_activity_type():
    raw = {"activityId": "1", "activityType": "cycling"}
    assert slim_activity(raw)["type"] == "cycling"


def test_slim_activity_drops_none_fields():
    raw = {"activityId": "1", "distance": None, "averageHR": 140}
    slim = slim_activity(raw)
    assert "distance" not in slim
    assert slim["averageHR"] == 140


def test_slim_activity_rounds_floats():
    raw = {"activityId": "1", "averageSpeed": 3.333333333}
    assert slim_activity(raw)["averageSpeed"] == 3.33


# ── slim_sleep ────────────────────────────────────────────────────────────────


def test_slim_sleep_converts_seconds_to_hours():
    raw = {
        "date": "2026-04-25",
        "duration_s": 28800,
        "deep_s": 7200,
        "rem_s": 5400,
        "light_s": 14400,
        "awake_s": 1800,
        "score": 88,
        "restingHR": 48,
    }
    slim = slim_sleep(raw)
    assert slim["total_h"] == 8.0
    assert slim["deep_h"] == 2.0
    assert slim["rem_h"] == 1.5
    assert slim["score"] == 88
    assert slim["restingHR"] == 48


def test_slim_sleep_handles_missing_fields():
    slim = slim_sleep({"date": "2026-04-25"})
    assert slim["date"] == "2026-04-25"
    assert slim["total_h"] is None


# ── slim_hrv / bb ─────────────────────────────────────────────────────────────


def test_slim_hrv_keeps_only_useful():
    raw = {
        "date": "2026-04-25",
        "lastNight": 45,
        "weeklyAvg": 50,
        "status": "BALANCED",
        "feedbackPhrase": "noisy long phrase to drop",
    }
    slim = slim_hrv(raw)
    assert slim == {
        "date": "2026-04-25",
        "lastNight": 45,
        "weeklyAvg": 50,
        "status": "BALANCED",
    }


def test_slim_body_battery_keeps_min_max():
    raw = {"date": "2026-04-25", "max": 90, "min": 20, "extra": "drop"}
    assert slim_body_battery(raw) == {"date": "2026-04-25", "max": 90, "min": 20}


# ── slim_passthrough variants ─────────────────────────────────────────────────


def test_slim_respiration_drops_none_and_extras():
    raw = {"date": "2026-04-25", "avgWakingRespirationValue": 14, "extra": "x"}
    slim = slim_respiration(raw)
    assert slim == {"date": "2026-04-25", "avgWakingRespirationValue": 14}


def test_slim_spo2_keeps_relevant_fields():
    raw = {"date": "2026-04-25", "averageSpO2": 96, "lowestSpO2": 90, "ignored": True}
    slim = slim_spo2(raw)
    assert slim == {"date": "2026-04-25", "averageSpO2": 96, "lowestSpO2": 90}


def test_slim_stress():
    raw = {
        "date": "2026-04-25",
        "avgStressLevel": 25,
        "maxStressLevel": 70,
        "noise": [],
    }
    slim = slim_stress(raw)
    assert slim == {"date": "2026-04-25", "avgStressLevel": 25, "maxStressLevel": 70}


def test_slim_training_status():
    raw = {
        "date": "2026-04-25",
        "trainingStatus": "PRODUCTIVE",
        "fitness": 50,
        "fatigue": 30,
    }
    slim = slim_training_status(raw)
    assert slim["trainingStatus"] == "PRODUCTIVE"
    assert slim["fitness"] == 50


def test_slim_training_readiness():
    raw = {"date": "2026-04-25", "score": 75, "level": "HIGH", "feedback": "Ready"}
    slim = slim_training_readiness(raw)
    assert slim["score"] == 75
    assert slim["level"] == "HIGH"


# ── aggregate_series ──────────────────────────────────────────────────────────


def test_aggregate_series_basic():
    records = [{"x": 10}, {"x": 20}, {"x": 30}]
    agg = aggregate_series(records, "x")
    assert agg == {"last": 10, "mean": 20, "min": 10, "max": 30, "n": 3}


def test_aggregate_series_skips_non_numeric():
    records = [{"x": 10}, {"x": None}, {"x": "bad"}, {"x": 20}]
    agg = aggregate_series(records, "x")
    assert agg["n"] == 2
    assert agg["mean"] == 15


def test_aggregate_series_empty_returns_none():
    assert aggregate_series([], "x") is None
    assert aggregate_series([{"y": 1}], "x") is None


def test_aggregate_series_rounds_floats():
    records = [{"x": 1.111}, {"x": 2.222}]
    agg = aggregate_series(records, "x")
    assert agg["mean"] == 1.67


# ── slim_fitness/race/lactate/endurance ───────────────────────────────────────


def test_slim_fitness_metrics_drops_max_metrics():
    raw = {"date": "2026-04-25", "vo2max": 55, "maxMetrics": {"huge": "x" * 10000}}
    slim = slim_fitness_metrics(raw)
    assert slim == {"date": "2026-04-25", "vo2max": 55}


def test_slim_fitness_metrics_none_input():
    assert slim_fitness_metrics(None) is None


def test_slim_race_predictions_list_takes_latest():
    raw = {
        "date": "2026-04-25",
        "predictions": [
            {"time5K": 1500, "time10K": 3100},
            {
                "time5K": 1480,
                "time10K": 3050,
                "timeHalfMarathon": 6500,
                "timeMarathon": 13500,
            },
        ],
    }
    slim = slim_race_predictions(raw)
    assert slim["time5K"] == 1480
    assert slim["timeMarathon"] == 13500


def test_slim_race_predictions_dict_input():
    raw = {"date": "2026-04-25", "predictions": {"time5K": 1500}}
    assert slim_race_predictions(raw)["time5K"] == 1500


def test_slim_race_predictions_none():
    assert slim_race_predictions(None) is None


def test_slim_race_predictions_empty_list():
    raw = {"date": "2026-04-25", "predictions": []}
    assert slim_race_predictions(raw) == {"date": "2026-04-25"}


def test_slim_lactate_threshold_keeps_useful_fields():
    raw = {"date": "2026-04-25", "heartRateValue": 165, "speedValue": 4.2, "noise": "x"}
    slim = slim_lactate_threshold(raw)
    assert slim["heartRateValue"] == 165
    assert slim["speedValue"] == 4.2
    assert "noise" not in slim


def test_slim_lactate_threshold_none():
    assert slim_lactate_threshold(None) is None


def test_slim_endurance_score_extracts_overall():
    raw = {"date": "2026-04-25", "data": {"overallScore": 7000, "noise": "x"}}
    assert slim_endurance_score(raw) == {"date": "2026-04-25", "score": 7000}


def test_slim_endurance_score_none():
    assert slim_endurance_score(None) is None


# ── build_context ─────────────────────────────────────────────────────────────


def _raw_sample():
    return {
        "days_covered": 7,
        "activities": [
            {
                "activityId": str(i),
                "startTimeLocal": f"2026-04-{25 - i:02d} 08:00:00",
                "distance": 5000 + i,
                "averageHR": 140 + i,
                "splits": ["x"] * 50,
            }
            for i in range(15)
        ],
        "sleep": [
            {
                "date": f"2026-04-{25 - i:02d}",
                "duration_s": 28800 - i * 100,
                "score": 80 + i,
                "deep_s": 7200,
                "rem_s": 5400,
                "light_s": 14400,
                "awake_s": 1800,
                "restingHR": 50,
            }
            for i in range(7)
        ],
        "hrv": [
            {
                "date": f"2026-04-{25 - i:02d}",
                "lastNight": 50 + i,
                "weeklyAvg": 48,
                "status": "BALANCED",
                "feedbackPhrase": "long noisy text",
            }
            for i in range(7)
        ],
        "body_battery": [
            {"date": f"2026-04-{25 - i:02d}", "max": 90 - i, "min": 20 + i}
            for i in range(7)
        ],
        "respiration": [{"date": "2026-04-25", "avgWakingRespirationValue": 14}],
        "spo2": [{"date": "2026-04-25", "averageSpO2": 96}],
        "stress": [
            {
                "date": f"2026-04-{25 - i:02d}",
                "avgStressLevel": 30 + i,
                "maxStressLevel": 70,
            }
            for i in range(3)
        ],
        "training_status": [
            {
                "date": "2026-04-25",
                "trainingStatus": "PRODUCTIVE",
                "fitness": 50,
                "fatigue": 30,
            }
        ],
        "training_readiness": [{"date": "2026-04-25", "score": 75, "level": "HIGH"}],
        "fitness_metrics": {
            "date": "2026-04-25",
            "vo2max": 55,
            "maxMetrics": {"x": "y" * 5000},
        },
        "race_predictions": {
            "date": "2026-04-25",
            "predictions": [{"time5K": 1500, "time10K": 3100}],
        },
        "lactate_threshold": {
            "date": "2026-04-25",
            "heartRateValue": 165,
            "speedValue": 4.2,
        },
        "endurance_score": {"date": "2026-04-25", "data": {"overallScore": 7000}},
        "memory": [{"note": "rodilla derecha", "created_at": "2026-04-20"}],
    }


def test_build_context_caps_activities():
    ctx = build_context(_raw_sample(), max_activities=10)
    assert len(ctx["activities"]) == 10


def test_build_context_strips_activity_bloat():
    ctx = build_context(_raw_sample())
    for act in ctx["activities"]:
        assert "splits" not in act


def test_build_context_aggregates_sleep():
    ctx = build_context(_raw_sample())
    assert ctx["sleep"]["score_summary"]["n"] == 7
    assert ctx["sleep"]["score_summary"]["last"] == 80


def test_build_context_includes_all_keys():
    ctx = build_context(_raw_sample())
    expected = {
        "days_covered",
        "activities",
        "sleep",
        "hrv",
        "body_battery",
        "respiration",
        "spo2",
        "stress",
        "training_status",
        "training_readiness",
        "fitness_metrics",
        "race_predictions",
        "lactate_threshold",
        "endurance_score",
        "memory",
    }
    assert set(ctx.keys()) == expected


def test_build_context_drops_max_metrics():
    ctx = build_context(_raw_sample())
    assert "maxMetrics" not in ctx["fitness_metrics"]
    assert ctx["fitness_metrics"]["vo2max"] == 55


def test_build_context_passes_memory_through():
    ctx = build_context(_raw_sample())
    assert ctx["memory"][0]["note"] == "rodilla derecha"


def test_build_context_payload_smaller_than_raw():
    raw = _raw_sample()
    raw_size = len(json.dumps(raw, ensure_ascii=False))
    compact_size = len(json.dumps(build_context(raw), ensure_ascii=False))
    # debe reducir el payload al menos a la mitad
    assert compact_size < raw_size / 2


def test_build_context_handles_empty_input():
    ctx = build_context({"days_covered": 7})
    assert ctx["activities"] == []
    assert ctx["sleep"]["recent"] == []
    assert ctx["sleep"]["score_summary"] is None
    assert ctx["fitness_metrics"] is None


# ── integration: db.get_compact_context_for_ai ────────────────────────────────


def test_get_compact_context_for_ai_uses_builder():
    from tinydb import TinyDB
    from tinydb.storages import MemoryStorage
    from unittest.mock import patch
    from datetime import date

    import garmin_coach.db as db

    db_inst = TinyDB(storage=MemoryStorage)
    today = date.today().isoformat()
    db_inst.table("activities").insert(
        {
            "activityId": "1",
            "startTimeLocal": f"{today} 08:00:00",
            "distance": 5000,
            "splits": ["x"] * 50,
        }
    )
    with patch("garmin_coach.db._db_instance", db_inst):
        ctx = db.get_compact_context_for_ai(days=7)
    assert len(ctx["activities"]) == 1
    assert "splits" not in ctx["activities"][0]
    assert ctx["activities"][0]["distance"] == 5000
