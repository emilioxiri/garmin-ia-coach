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
        "normPower": 300,
        "trainingStressScore": 80,
        "averageBikingCadenceInRevPerMinute": 90,
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
    # Fields removed from running profile
    assert "vO2MaxValue" not in slim
    assert "normPower" not in slim
    assert "trainingStressScore" not in slim
    assert "averageBikingCadenceInRevPerMinute" not in slim


def test_slim_activity_includes_running_dynamics():
    raw = {
        "activityId": "1",
        "avgStrideLength": 1.06,
        "avgVerticalRatio": 8.1,
        "avgVerticalOscillation": 8.5,
        "avgGroundContactTime": 245,
        "averageRunningCadenceInStepsPerMinute": 177,
        "maxRunningCadenceInStepsPerMinute": 192,
        "avgPower": 308,
        "maxPower": 417,
        "beginningPotentialStamina": 100,
        "endPotentialStamina": 59,
        "minAvailableStamina": 53,
        "activityTrainingLoad": 218,
        "trainingEffectLabel": "Umbral (Aeróbica alta)",
        "bmrCalories": 65,
        "activeCalories": 593,
        "estimatedSweatLoss": 798,
        "avgTemperature": 25,
        "minTemperature": 24,
        "maxTemperature": 29,
        "moderateIntensityMinutes": 2,
        "vigorousIntensityMinutes": 44,
        "minElevation": 27,
        "maxElevation": 43,
    }
    slim = slim_activity(raw)
    assert slim["avgStrideLength"] == 1.06
    assert slim["avgVerticalRatio"] == 8.1
    assert slim["avgVerticalOscillation"] == 8.5
    assert slim["avgGroundContactTime"] == 245
    assert slim["maxRunningCadenceInStepsPerMinute"] == 192
    assert slim["avgPower"] == 308
    assert slim["maxPower"] == 417
    assert slim["beginningPotentialStamina"] == 100
    assert slim["endPotentialStamina"] == 59
    assert slim["minAvailableStamina"] == 53
    assert slim["activityTrainingLoad"] == 218
    assert slim["trainingEffectLabel"] == "Umbral (Aeróbica alta)"
    assert slim["bmrCalories"] == 65
    assert slim["activeCalories"] == 593
    assert slim["estimatedSweatLoss"] == 798
    assert slim["avgTemperature"] == 25
    assert slim["minTemperature"] == 24
    assert slim["maxTemperature"] == 29
    assert slim["moderateIntensityMinutes"] == 2
    assert slim["vigorousIntensityMinutes"] == 44
    assert slim["minElevation"] == 27
    assert slim["maxElevation"] == 43


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


# ── slim_activity: duración en HH:MM:SS, sin segundos crudos ──────────────────


def test_slim_activity_replaces_duration_seconds_with_hms():
    """duration en segundos debe sustituirse por duration_hms (HH:MM:SS)."""
    raw = {"activityId": "1", "duration": 5212.53}
    slim = slim_activity(raw)
    assert "duration" not in slim, "los segundos crudos no deben llegar al LLM"
    assert slim["duration_hms"] == "1:26:53"


def test_slim_activity_short_duration_uses_mm_ss():
    raw = {"activityId": "1", "duration": 754}
    slim = slim_activity(raw)
    assert slim["duration_hms"] == "12:34"


def test_slim_activity_converts_all_duration_variants():
    raw = {
        "activityId": "1",
        "duration": 3600,
        "movingDuration": 3500,
        "elapsedDuration": 3700,
    }
    slim = slim_activity(raw)
    assert slim["duration_hms"] == "1:00:00"
    assert slim["movingDuration_hms"] == "58:20"
    assert slim["elapsedDuration_hms"] == "1:01:40"
    for f in ("duration", "movingDuration", "elapsedDuration"):
        assert f not in slim


# ── slim_activity: padel / fuerza / yoga sin distancia ni ritmo ───────────────


def test_slim_activity_padel_drops_distance_and_pace():
    raw = {
        "activityId": "1",
        "activityType": {"typeKey": "padel"},
        "duration": 5212.53,
        "distance": 190.0,
        "averageSpeed": 0.04,
        "averageHR": 111,
        "maxHR": 151,
        "calories": 600,
        "moderateIntensityMinutes": 40,
        "vigorousIntensityMinutes": 5,
        "activityTrainingLoad": 80,
    }
    slim = slim_activity(raw)
    assert slim["type"] == "padel"
    assert slim["duration_hms"] == "1:26:53"
    assert slim["averageHR"] == 111
    assert slim["maxHR"] == 151
    assert slim["moderateIntensityMinutes"] == 40
    assert slim["activityTrainingLoad"] == 80
    # Distancia / velocidad / ritmo no aplican a padel
    for forbidden in (
        "distance",
        "distance_km",
        "averageSpeed",
        "maxSpeed",
        "pace_min_per_km",
    ):
        assert forbidden not in slim, f"{forbidden} no debe aparecer en padel"


def test_slim_activity_strength_drops_running_dynamics_and_power():
    raw = {
        "activityId": "1",
        "activityType": {"typeKey": "strength_training"},
        "duration": 1800,
        "distance": 0,
        "averageHR": 120,
        "avgStrideLength": 0.5,
        "avgPower": 200,
        "elevationGain": 5,
        "estimatedSweatLoss": 100,
    }
    slim = slim_activity(raw)
    for forbidden in (
        "distance",
        "distance_km",
        "avgStrideLength",
        "avgPower",
        "elevationGain",
        "estimatedSweatLoss",
    ):
        assert forbidden not in slim
    assert slim["averageHR"] == 120
    assert slim["duration_hms"] == "30:00"


def test_slim_activity_running_keeps_distance_and_pace():
    """Running NO está en _NON_DISTANCE_TYPES → distancia y ritmo se conservan."""
    raw = {
        "activityId": "1",
        "activityType": {"typeKey": "running"},
        "distance": 10000,
        "averageSpeed": 3.33,
        "duration": 3000,
    }
    slim = slim_activity(raw)
    assert slim["distance_km"] == 10.0
    assert slim["pace_min_per_km"] == 5.01
    assert slim["is_run"] is True


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
    assert slim == {"date": "2026-04-25", "vo2max": 55, "vo2max_running": 55}


def test_slim_fitness_metrics_aliases_vo2max_running():
    raw = {"date": "2026-04-25", "vo2max": 60.5}
    slim = slim_fitness_metrics(raw)
    assert slim["vo2max_running"] == 60.5


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
        "notable_runs",
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
    assert ctx["notable_runs"] == []
    assert ctx["sleep"]["recent"] == []
    assert ctx["sleep"]["score_summary"] is None
    assert ctx["fitness_metrics"] is None


# ── slim_activity derived fields (Fase 1) ────────────────────────────────────


def test_slim_activity_extracts_date_and_weekday_es():
    # 2026-05-01 = viernes
    raw = {
        "activityId": "1",
        "startTimeLocal": "2026-05-01 08:30:00",
        "activityType": {"typeKey": "running"},
    }
    slim = slim_activity(raw)
    assert slim["date"] == "2026-05-01"
    assert slim["weekday"] == "viernes"


def test_slim_activity_handles_invalid_start_time():
    raw = {"activityId": "1", "startTimeLocal": "no-es-fecha"}
    slim = slim_activity(raw)
    assert "date" not in slim
    assert "weekday" not in slim


def test_slim_activity_computes_distance_km():
    raw = {"activityId": "1", "distance": 21097.5}
    assert slim_activity(raw)["distance_km"] == 21.1


def test_slim_activity_computes_pace_min_per_km():
    # 3.0 m/s → 1000m / 3 m/s = 333.33s = 5.55 min/km
    raw = {"activityId": "1", "averageSpeed": 3.0}
    slim = slim_activity(raw)
    assert slim["pace_min_per_km"] == 5.56


def test_slim_activity_pace_skipped_when_speed_zero():
    raw = {"activityId": "1", "averageSpeed": 0}
    assert "pace_min_per_km" not in slim_activity(raw)


def test_slim_activity_marks_run():
    raw = {
        "activityId": "1",
        "activityType": {"typeKey": "trail_running"},
        "distance": 8000,
    }
    slim = slim_activity(raw)
    assert slim["is_run"] is True
    assert "is_long_run" not in slim


def test_slim_activity_marks_long_run_at_threshold():
    raw = {
        "activityId": "1",
        "activityType": {"typeKey": "running"},
        "distance": 21097,
    }
    slim = slim_activity(raw)
    assert slim["is_run"] is True
    assert slim["is_long_run"] is True


def test_slim_activity_non_run_has_no_run_flags():
    raw = {
        "activityId": "1",
        "activityType": {"typeKey": "strength_training"},
        "distance": 0,
    }
    slim = slim_activity(raw)
    assert "is_run" not in slim
    assert "is_long_run" not in slim


def test_slim_activity_renames_training_effect_fields():
    raw = {
        "activityId": "1",
        "aerobicTrainingEffect": 4.2,
        "anaerobicTrainingEffect": 1.8,
    }
    slim = slim_activity(raw)
    assert slim["aerobic_te"] == 4.2
    assert slim["anaerobic_te"] == 1.8
    assert "aerobicTrainingEffect" not in slim
    assert "anaerobicTrainingEffect" not in slim


# ── build_context notable_runs / cap (Fase 1) ────────────────────────────────


def _runs_sample(distances):
    return {
        "days_covered": 30,
        "activities": [
            {
                "activityId": str(i),
                "startTimeLocal": f"2026-04-{20 - i:02d} 08:00:00",
                "activityType": {"typeKey": "running"},
                "distance": d,
            }
            for i, d in enumerate(distances)
        ],
    }


def test_build_context_notable_runs_picks_longest_three():
    raw = _runs_sample([5000, 21097, 10000, 15000, 8000])
    ctx = build_context(raw)
    distances = [a["distance_km"] for a in ctx["notable_runs"]]
    assert distances == [21.1, 15.0, 10.0]


def test_build_context_notable_runs_ignores_non_runs():
    raw = {
        "days_covered": 7,
        "activities": [
            {
                "activityId": "1",
                "startTimeLocal": "2026-04-25 08:00:00",
                "activityType": {"typeKey": "strength_training"},
                "distance": 9999,
            },
            {
                "activityId": "2",
                "startTimeLocal": "2026-04-24 08:00:00",
                "activityType": {"typeKey": "running"},
                "distance": 5000,
            },
        ],
    }
    ctx = build_context(raw)
    assert len(ctx["notable_runs"]) == 1
    assert ctx["notable_runs"][0]["activityId"] == "2"


def test_build_context_default_max_activities_is_15():
    raw = {
        "days_covered": 30,
        "activities": [
            {
                "activityId": str(i),
                "startTimeLocal": f"2026-04-{30 - i:02d} 08:00:00",
            }
            for i in range(20)
        ],
    }
    ctx = build_context(raw)
    assert len(ctx["activities"]) == 15


def test_build_context_notable_runs_can_include_activities_outside_cap():
    """notable_runs busca entre TODAS las actividades, no sólo el cap."""
    distances = [3000] * 14 + [21097]  # carrera larga en posición 15 (fuera del top-15)
    raw = _runs_sample(distances)
    ctx = build_context(raw, max_activities=10)
    assert len(ctx["activities"]) == 10
    assert any(a.get("distance_km") == 21.1 for a in ctx["notable_runs"])


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
