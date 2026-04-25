"""
context_builder.py
Compacta los registros de TinyDB en estructuras pequeñas para enviárselas al LLM
sin saturar la ventana de contexto.

Cada `slim_*` proyecta sólo los campos relevantes de un registro.
`aggregate_series` calcula resumen estadístico (mean/min/max/last) de una serie diaria.
`build_context` orquesta la construcción del contexto completo en modo compacto.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Iterable

# Campos máximo a conservar de una actividad. Resto se descarta.
_ACTIVITY_FIELDS = (
    "activityId",
    "activityName",
    "startTimeLocal",
    "distance",
    "duration",
    "elapsedDuration",
    "movingDuration",
    "averageHR",
    "maxHR",
    "averageSpeed",
    "maxSpeed",
    "calories",
    "aerobicTrainingEffect",
    "anaerobicTrainingEffect",
    "trainingStressScore",
    "vO2MaxValue",
    "normPower",
    "averageRunningCadenceInStepsPerMinute",
    "averageBikingCadenceInRevPerMinute",
    "elevationGain",
    "elevationLoss",
)


def _coerce_number(value: Any) -> Any:
    """Redondea floats a 2 decimales para reducir bytes en el JSON dump."""
    if isinstance(value, float):
        return round(value, 2)
    return value


def slim_activity(act: dict) -> dict:
    """Proyecta una actividad a sus campos relevantes para el coach."""
    out: dict = {}
    for field in _ACTIVITY_FIELDS:
        if field in act and act[field] is not None:
            out[field] = _coerce_number(act[field])

    activity_type = act.get("activityType")
    if isinstance(activity_type, dict):
        type_key = activity_type.get("typeKey")
        if type_key:
            out["type"] = type_key
    elif isinstance(activity_type, str):
        out["type"] = activity_type

    return out


def slim_sleep(record: dict) -> dict:
    """Sueño: mantiene fecha + métricas clave en horas (más legibles para el LLM)."""

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
    """Helper: devuelve un slim que copia sólo los `fields` indicados + 'date'."""

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
    """Calcula mean/min/max/last de un campo numérico a través de una serie temporal.

    `records` debe venir ordenado de más reciente a más antiguo (como hace TinyDB tras sort
    descendente). El "last" es el valor más reciente disponible.
    """
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
    """fitness_metrics trae el `maxMetrics` raw enorme. Sólo conservamos vo2max y fecha."""
    if not record:
        return None
    return {"date": record.get("date"), "vo2max": record.get("vo2max")}


def slim_race_predictions(record: dict | None) -> dict | None:
    """Conserva sólo las predicciones por distancia estándar."""
    if not record:
        return None
    predictions = record.get("predictions")
    if isinstance(predictions, list) and predictions:
        latest = predictions[-1]
        if isinstance(latest, dict):
            return {
                "date": record.get("date"),
                "time5K": latest.get("time5K"),
                "time10K": latest.get("time10K"),
                "timeHalfMarathon": latest.get("timeHalfMarathon"),
                "timeMarathon": latest.get("timeMarathon"),
            }
    if isinstance(predictions, dict):
        return {
            "date": record.get("date"),
            "time5K": predictions.get("time5K"),
            "time10K": predictions.get("time10K"),
            "timeHalfMarathon": predictions.get("timeHalfMarathon"),
            "timeMarathon": predictions.get("timeMarathon"),
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


def build_context(raw: dict, *, max_activities: int = 10) -> dict:
    """Construye el contexto compacto a partir del dict que devuelve `db.get_context_for_ai`.

    `raw` debe contener las listas tal como las devuelve TinyDB (ya ordenadas descendente).
    Devuelve un dict con:
      - actividades recientes proyectadas
      - últimas N entradas de cada wellness diaria
      - agregados (mean/min/max/last) de los campos numéricos clave
      - snapshot de fitness/race/lactate/endurance proyectados
      - memoria del coach (sin tocar) y `days_covered`
    """
    activities = [slim_activity(a) for a in raw.get("activities", [])][:max_activities]

    sleep_records = [slim_sleep(s) for s in raw.get("sleep", [])]
    hrv_records = [slim_hrv(h) for h in raw.get("hrv", [])]
    bb_records = [slim_body_battery(b) for b in raw.get("body_battery", [])]
    resp_records = [slim_respiration(r) for r in raw.get("respiration", [])]
    spo2_records = [slim_spo2(s) for s in raw.get("spo2", [])]
    stress_records = [slim_stress(s) for s in raw.get("stress", [])]
    ts_records = [slim_training_status(t) for t in raw.get("training_status", [])]
    tr_records = [slim_training_readiness(t) for t in raw.get("training_readiness", [])]

    return {
        "days_covered": raw.get("days_covered"),
        "activities": activities,
        "sleep": {
            "recent": sleep_records[:7],
            "score_summary": aggregate_series(sleep_records, "score"),
            "total_h_summary": aggregate_series(sleep_records, "total_h"),
            "restingHR_summary": aggregate_series(sleep_records, "restingHR"),
        },
        "hrv": {
            "recent": hrv_records[:7],
            "lastNight_summary": aggregate_series(hrv_records, "lastNight"),
            "weeklyAvg_summary": aggregate_series(hrv_records, "weeklyAvg"),
        },
        "body_battery": {
            "recent": bb_records[:7],
            "max_summary": aggregate_series(bb_records, "max"),
            "min_summary": aggregate_series(bb_records, "min"),
        },
        "respiration": {
            "recent": resp_records[:7],
        },
        "spo2": {
            "recent": spo2_records[:7],
        },
        "stress": {
            "recent": stress_records[:7],
            "avg_summary": aggregate_series(stress_records, "avgStressLevel"),
        },
        "training_status": {
            "recent": ts_records[:5],
        },
        "training_readiness": {
            "recent": tr_records[:5],
            "score_summary": aggregate_series(tr_records, "score"),
        },
        "fitness_metrics": slim_fitness_metrics(raw.get("fitness_metrics")),
        "race_predictions": slim_race_predictions(raw.get("race_predictions")),
        "lactate_threshold": slim_lactate_threshold(raw.get("lactate_threshold")),
        "endurance_score": slim_endurance_score(raw.get("endurance_score")),
        "memory": raw.get("memory", []),
    }
