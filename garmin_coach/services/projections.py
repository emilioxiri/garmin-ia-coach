"""
services/projections.py
Pure projection functions: slim_* and aggregate_series.
Replaces garmin_coach/context_builder.py (functional content moved here).
"""

from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any, Iterable

from garmin_coach.app.logging_setup import get_logger
from garmin_coach.domain.activity import NON_DISTANCE_TYPES, RUN_TYPES

logger = get_logger(__name__)

_WEEKDAYS_ES = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)

_NON_DISTANCE_DROP_FIELDS = (
    "distance",
    "averageSpeed",
    "maxSpeed",
    "avgStrideLength",
    "avgVerticalRatio",
    "avgVerticalOscillation",
    "avgGroundContactTime",
    "averageRunningCadenceInStepsPerMinute",
    "maxRunningCadenceInStepsPerMinute",
    "avgPower",
    "maxPower",
    "elevationGain",
    "elevationLoss",
    "minElevation",
    "maxElevation",
    "estimatedSweatLoss",
)

_FIELD_RENAMES = {
    "aerobicTrainingEffect": "aerobic_te",
    "anaerobicTrainingEffect": "anaerobic_te",
}

LONG_RUN_THRESHOLD_M = 15000

_ACTIVITY_FIELDS = (
    "activityId",
    "activityName",
    "startTimeLocal",
    "duration",
    "movingDuration",
    "elapsedDuration",
    "distance",
    "averageSpeed",
    "maxSpeed",
    "averageHR",
    "maxHR",
    "calories",
    "bmrCalories",
    "activeCalories",
    "elevationGain",
    "elevationLoss",
    "minElevation",
    "maxElevation",
    "aerobicTrainingEffect",
    "anaerobicTrainingEffect",
    "activityTrainingLoad",
    "trainingEffectLabel",
    "beginningPotentialStamina",
    "endPotentialStamina",
    "minAvailableStamina",
    "avgPower",
    "maxPower",
    "averageRunningCadenceInStepsPerMinute",
    "maxRunningCadenceInStepsPerMinute",
    "avgStrideLength",
    "avgVerticalRatio",
    "avgVerticalOscillation",
    "avgGroundContactTime",
    "estimatedSweatLoss",
    "avgTemperature",
    "minTemperature",
    "maxTemperature",
    "moderateIntensityMinutes",
    "vigorousIntensityMinutes",
)


def _coerce_number(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    return value


def _format_duration(seconds: Any) -> str | None:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return None
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def _parse_local_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace(" ", "T")[:19]
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def slim_activity(act: dict) -> dict:
    out: dict = {}
    for field in _ACTIVITY_FIELDS:
        if field in act and act[field] is not None:
            key = _FIELD_RENAMES.get(field, field)
            out[key] = _coerce_number(act[field])

    activity_type = act.get("activityType")
    type_key: str | None = None
    if isinstance(activity_type, dict):
        type_key = activity_type.get("typeKey")
    elif isinstance(activity_type, str):
        type_key = activity_type
    if type_key:
        out["type"] = type_key

    dt = _parse_local_datetime(act.get("startTimeLocal"))
    if dt is not None:
        out["date"] = dt.date().isoformat()
        out["weekday"] = _WEEKDAYS_ES[dt.weekday()]

    for raw_field, hms_field in (
        ("duration", "duration_hms"),
        ("movingDuration", "movingDuration_hms"),
        ("elapsedDuration", "elapsedDuration_hms"),
    ):
        if raw_field in out:
            hms = _format_duration(out[raw_field])
            if hms is not None:
                out[hms_field] = hms
            del out[raw_field]

    distance = out.get("distance")
    is_non_distance = type_key in NON_DISTANCE_TYPES

    if is_non_distance:
        for f in _NON_DISTANCE_DROP_FIELDS:
            out.pop(f, None)
    else:
        if isinstance(distance, (int, float)):
            out["distance_km"] = round(distance / 1000, 2)
        speed = out.get("averageSpeed")
        if isinstance(speed, (int, float)) and speed > 0:
            total_sec = 1000 / speed
            minutes = int(total_sec // 60)
            seconds = int(round(total_sec - minutes * 60))
            if seconds == 60:
                minutes += 1
                seconds = 0
            out["pace_min_per_km"] = f"{minutes}:{seconds:02d}"

    if type_key in RUN_TYPES:
        out["is_run"] = True
        if isinstance(distance, (int, float)) and distance >= LONG_RUN_THRESHOLD_M:
            out["is_long_run"] = True

    return out


def slim_sleep(record: dict) -> dict:
    def _to_hours(seconds: Any) -> Any:
        if isinstance(seconds, (int, float)):
            return round(seconds / 3600, 2)
        return None

    return {
        "date": record.get("date"),
        "total_h": _to_hours(record.get("duration_s")),
        "deep_h": _to_hours(record.get("deep_s")),
        "rem_h": _to_hours(record.get("rem_s")),
        "light_h": _to_hours(record.get("light_s")),
        "awake_h": _to_hours(record.get("awake_s")),
        "score": record.get("score"),
        "restingHR": record.get("restingHR"),
    }


def slim_hrv(record: dict) -> dict:
    return {
        "date": record.get("date"),
        "lastNight": record.get("lastNight"),
        "weeklyAvg": record.get("weeklyAvg"),
        "status": record.get("status"),
    }


def slim_body_battery(record: dict) -> dict:
    return {
        "date": record.get("date"),
        "max": record.get("max"),
        "min": record.get("min"),
    }


def _slim_passthrough(*fields: str):
    def _slim(record: dict) -> dict:
        out: dict = {"date": record.get("date")}
        for f in fields:
            if f in record and record[f] is not None:
                out[f] = _coerce_number(record[f])
        return out

    return _slim


slim_respiration = _slim_passthrough(
    "avgWakingRespirationValue",
    "avgSleepRespirationValue",
    "highestRespirationValue",
    "lowestRespirationValue",
)
slim_spo2 = _slim_passthrough("averageSpO2", "lowestSpO2", "lastSevenDaysAvgSpO2")
slim_stress = _slim_passthrough("avgStressLevel", "maxStressLevel")
slim_training_status = _slim_passthrough(
    "trainingStatus",
    "fitnessTrend",
    "loadTunnelMin",
    "loadTunnelMax",
    "fitness",
    "fatigue",
)
slim_training_readiness = _slim_passthrough(
    "score", "level", "feedback", "sleepScore", "hrvFactorPercent"
)


def aggregate_series(records: Iterable[dict], field: str) -> dict | None:
    values = [r[field] for r in records if isinstance(r.get(field), (int, float))]
    if not values:
        return None
    return {
        "last": _coerce_number(values[0]),
        "mean": _coerce_number(mean(values)),
        "min": _coerce_number(min(values)),
        "max": _coerce_number(max(values)),
        "n": len(values),
    }


def slim_fitness_metrics(record: dict | None) -> dict | None:
    if not record:
        return None
    vo2 = record.get("vo2max")
    return {
        "date": record.get("date"),
        "vo2max": vo2,
        "vo2max_running": vo2,
    }


def _seconds_to_hms(seconds: int | None) -> str | None:
    if seconds is None or not isinstance(seconds, (int, float)):
        return None
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"


def slim_race_predictions(record: dict | None) -> dict | None:
    if not record:
        return None
    predictions = record.get("predictions")
    if isinstance(predictions, list) and predictions:
        latest = predictions[-1]
        if isinstance(latest, dict):
            return {
                "date": record.get("date"),
                "time5K": _seconds_to_hms(latest.get("time5K")),
                "time10K": _seconds_to_hms(latest.get("time10K")),
                "timeHalfMarathon": _seconds_to_hms(latest.get("timeHalfMarathon")),
                "timeMarathon": _seconds_to_hms(latest.get("timeMarathon")),
            }
    if isinstance(predictions, dict):
        return {
            "date": record.get("date"),
            "time5K": _seconds_to_hms(predictions.get("time5K")),
            "time10K": _seconds_to_hms(predictions.get("time10K")),
            "timeHalfMarathon": _seconds_to_hms(predictions.get("timeHalfMarathon")),
            "timeMarathon": _seconds_to_hms(predictions.get("timeMarathon")),
        }
    return {"date": record.get("date")}


def slim_lactate_threshold(record: dict | None) -> dict | None:
    if not record:
        return None
    fields = ("date", "calendarDate", "heartRateValue", "speedValue", "userId")
    out = {f: record[f] for f in fields if f in record and record[f] is not None}
    return out or None


def slim_endurance_score(record: dict | None) -> dict | None:
    if not record:
        return None
    data = record.get("data")
    score = None
    if isinstance(data, dict):
        score = data.get("overallScore") or data.get("enduranceScore")
    return {"date": record.get("date"), "score": score}


def _pace_to_seconds(pace: str | None) -> float | None:
    """Parse 'M:SS' pace string into seconds-per-km. Returns None if malformed."""
    if not isinstance(pace, str) or ":" not in pace:
        return None
    try:
        m, s = pace.split(":", 1)
        return int(m) * 60 + int(s)
    except (ValueError, TypeError):
        return None


def compute_hrv_trend(hrv_records: list[dict], days: int = 14) -> dict | None:
    """Linear slope of `lastNight` HRV over the most recent `days` records.

    Records expected sorted desc by date. Returns slope ms/day + categorical
    direction ('subiendo', 'estable', 'descendiendo'). None if <3 valid points.
    """
    series = [
        r["lastNight"]
        for r in hrv_records[:days]
        if isinstance(r.get("lastNight"), (int, float))
    ]
    if len(series) < 3:
        return None
    series_chrono = list(reversed(series))
    n = len(series_chrono)
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(series_chrono) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, series_chrono))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return None
    slope = num / den
    if slope >= 0.2:
        direction = "subiendo"
    elif slope <= -0.2:
        direction = "descendiendo"
    else:
        direction = "estable"
    return {
        "slope_per_day": round(slope, 2),
        "direction": direction,
        "n": n,
        "first": _coerce_number(series_chrono[0]),
        "last": _coerce_number(series_chrono[-1]),
    }


def compute_weekly_load(slim_activities: list[dict]) -> dict | None:
    """Sum activityTrainingLoad (or duration_s fallback) for last 7 days +
    acute:chronic workload ratio (last 7d / mean of prior 28d)."""
    if not slim_activities:
        return None
    today = datetime.now().date()

    def _load(act: dict) -> float:
        v = act.get("activityTrainingLoad")
        if isinstance(v, (int, float)):
            return float(v)
        return 0.0

    def _date(act: dict):
        d = act.get("date")
        if not isinstance(d, str):
            return None
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            return None

    acute = 0.0
    chronic_buckets: list[float] = [0.0, 0.0, 0.0, 0.0]
    for act in slim_activities:
        d = _date(act)
        if d is None:
            continue
        delta_days = (today - d).days
        load = _load(act)
        if 0 <= delta_days < 7:
            acute += load
        for i in range(4):
            if 7 + i * 7 <= delta_days < 7 + (i + 1) * 7:
                chronic_buckets[i] += load
                break
    chronic_weeks = [w for w in chronic_buckets if w > 0]
    if not chronic_weeks:
        return {
            "weekly_load": round(acute, 1),
            "acwr": None,
            "chronic_avg": None,
        }
    chronic_avg = sum(chronic_weeks) / len(chronic_weeks)
    acwr = acute / chronic_avg if chronic_avg > 0 else None
    return {
        "weekly_load": round(acute, 1),
        "chronic_avg": round(chronic_avg, 1),
        "acwr": round(acwr, 2) if acwr is not None else None,
    }


def compute_resting_hr_trend(slim_sleep_records: list[dict]) -> dict | None:
    """Mean restingHR last 7d vs prior 7d (records sorted desc by date)."""
    rhrs = [
        r.get("restingHR")
        for r in slim_sleep_records
        if isinstance(r.get("restingHR"), (int, float))
    ]
    if len(rhrs) < 4:
        return None
    last_7 = rhrs[:7]
    prior_7 = rhrs[7:14]
    if not prior_7:
        return {"last_week_mean": round(sum(last_7) / len(last_7), 1), "delta": None}
    last_mean = sum(last_7) / len(last_7)
    prior_mean = sum(prior_7) / len(prior_7)
    return {
        "last_week_mean": round(last_mean, 1),
        "prior_week_mean": round(prior_mean, 1),
        "delta": round(last_mean - prior_mean, 1),
    }


def compute_fastest_runs(
    slim_activities: list[dict],
    *,
    min_distance_km: float = 3.0,
    top_n: int = 3,
) -> list[dict]:
    """Top-N runs by best `pace_min_per_km`, filtered by min distance."""
    candidates: list[tuple[float, dict]] = []
    for act in slim_activities:
        if not act.get("is_run"):
            continue
        dist = act.get("distance_km")
        if not isinstance(dist, (int, float)) or dist < min_distance_km:
            continue
        pace_s = _pace_to_seconds(act.get("pace_min_per_km"))
        if pace_s is None:
            continue
        candidates.append((pace_s, act))
    candidates.sort(key=lambda x: x[0])
    return [c[1] for c in candidates[:top_n]]
