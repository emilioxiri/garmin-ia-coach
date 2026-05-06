"""
context_builder.py
Compacta los registros de TinyDB en estructuras pequeñas para enviárselas al LLM
sin saturar la ventana de contexto.

Cada `slim_*` proyecta sólo los campos relevantes de un registro.
`aggregate_series` calcula resumen estadístico (mean/min/max/last) de una serie diaria.
`build_context` orquesta la construcción del contexto completo en modo compacto.
"""

from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any, Iterable

_WEEKDAYS_ES = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)

_RUN_TYPES = {
    "running",
    "trail_running",
    "treadmill_running",
    "virtual_run",
    "track_running",
    "indoor_running",
    "street_running",
}

# Tipos de actividad sin distancia/ritmo significativos (deportes de raqueta,
# fuerza, gimnasio, escalada, yoga, etc). Para estos, slim_activity descarta
# distancia, velocidad, ritmo, dinámica de carrera, potencia y elevación —
# son datos de Garmin sin sentido para padel, pesas, etc.
_NON_DISTANCE_TYPES = {
    "padel",
    "tennis",
    "pickleball",
    "squash",
    "racquet_ball",
    "racquetball",
    "table_tennis",
    "badminton",
    "boxing",
    "mixed_martial_arts",
    "strength_training",
    "indoor_strength_training",
    "yoga",
    "pilates",
    "indoor_climbing",
    "bouldering",
    "rock_climbing",
    "hiit",
    "cardio",
    "stretching",
    "breathwork",
    "meditation",
    "mobility",
    "gym",
    "floor_climbing",
    "stair_climbing",
}

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

# Campos de carrera alineados con Garmin Connect "Carrera > Estadísticas".
_ACTIVITY_FIELDS = (
    # Identidad
    "activityId",
    "activityName",
    "startTimeLocal",
    # Tiempo
    "duration",
    "movingDuration",
    "elapsedDuration",
    # Distancia y velocidad
    "distance",
    "averageSpeed",
    "maxSpeed",
    # Frecuencia cardiaca
    "averageHR",
    "maxHR",
    # Calorías
    "calories",
    "bmrCalories",
    "activeCalories",
    # Elevación
    "elevationGain",
    "elevationLoss",
    "minElevation",
    "maxElevation",
    # Training Effect
    "aerobicTrainingEffect",
    "anaerobicTrainingEffect",
    "activityTrainingLoad",
    "trainingEffectLabel",
    # Stamina
    "beginningPotentialStamina",
    "endPotentialStamina",
    "minAvailableStamina",
    # Potencia de carrera
    "avgPower",
    "maxPower",
    # Dinámica de carrera
    "averageRunningCadenceInStepsPerMinute",
    "maxRunningCadenceInStepsPerMinute",
    "avgStrideLength",
    "avgVerticalRatio",
    "avgVerticalOscillation",
    "avgGroundContactTime",
    # Hidratación
    "estimatedSweatLoss",
    # Temperatura
    "avgTemperature",
    "minTemperature",
    "maxTemperature",
    # Minutos de intensidad
    "moderateIntensityMinutes",
    "vigorousIntensityMinutes",
)


def _coerce_number(value: Any) -> Any:
    """Redondea floats a 2 decimales para reducir bytes en el JSON dump."""
    if isinstance(value, float):
        return round(value, 2)
    return value


def _format_duration(seconds: Any) -> str | None:
    """Formatea segundos a `HH:MM:SS` o `MM:SS`. None si no es numérico válido."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return None
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def _parse_local_datetime(value: Any) -> datetime | None:
    """Parsea startTimeLocal de Garmin (`YYYY-MM-DD HH:MM:SS`) sin fallar."""
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace(" ", "T")[:19]
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def slim_activity(act: dict) -> dict:
    """Proyecta una actividad a sus campos relevantes para el coach.

    Añade campos derivados que el LLM consume mejor que el JSON crudo:
      - `date` y `weekday` (en español) extraídos de `startTimeLocal`
      - `duration_hms` / `movingDuration_hms` / `elapsedDuration_hms` (HH:MM:SS o MM:SS)
        en lugar de duración en segundos crudos para que el modelo nunca cite "5212 s"
      - `distance_km` y `pace_min_per_km` SÓLO para actividades con distancia real
      - `is_run` / `is_long_run` (≥ 15 km) para filtrar actividades clave
    Para actividades sin distancia significativa (padel, fuerza, yoga, escalada,
    HIIT…) descarta distancia, velocidad, ritmo, dinámica de carrera, potencia,
    elevación y sweat loss — son cero o ruido en Garmin para esos deportes.
    Renombra `aerobicTrainingEffect` → `aerobic_te` y `anaerobicTrainingEffect`
    → `anaerobic_te` para evitar que el modelo los confunda con VO2max.
    """
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

    # Duración: convertir SIEMPRE a HH:MM:SS y eliminar segundos crudos para que
    # el LLM no escriba cosas como "5212.53 segundos".
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
    is_non_distance = type_key in _NON_DISTANCE_TYPES

    if is_non_distance:
        for f in _NON_DISTANCE_DROP_FIELDS:
            out.pop(f, None)
    else:
        if isinstance(distance, (int, float)):
            out["distance_km"] = round(distance / 1000, 2)
        speed = out.get("averageSpeed")
        if isinstance(speed, (int, float)) and speed > 0:
            out["pace_min_per_km"] = round((1000 / speed) / 60, 2)

    if type_key in _RUN_TYPES:
        out["is_run"] = True
        if isinstance(distance, (int, float)) and distance >= LONG_RUN_THRESHOLD_M:
            out["is_long_run"] = True

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
    """fitness_metrics trae el `maxMetrics` raw enorme. Sólo conservamos vo2max y fecha.

    Expone también `vo2max_running` (alias del mismo valor) para que el modelo NO
    confunda el VO2max con `aerobic_te` (Training Effect, escala 0-5).
    """
    if not record:
        return None
    vo2 = record.get("vo2max")
    return {
        "date": record.get("date"),
        "vo2max": vo2,
        "vo2max_running": vo2,
    }


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


NOTABLE_RUNS_LIMIT = 3


def build_context(raw: dict, *, max_activities: int = 15) -> dict:
    """Construye el contexto compacto a partir del dict que devuelve `db.get_context_for_ai`.

    `raw` debe contener las listas tal como las devuelve TinyDB (ya ordenadas descendente).
    Devuelve un dict con:
      - `activities`: actividades recientes proyectadas (cap `max_activities`)
      - `notable_runs`: top-N (default 3) carreras más largas de la ventana, para que
        el coach localice rápido carreras de fondo aunque caigan fuera del cap
      - últimas N entradas de cada wellness diaria
      - agregados (mean/min/max/last) de los campos numéricos clave
      - snapshot de fitness/race/lactate/endurance proyectados
      - memoria del coach (sin tocar) y `days_covered`
    """
    slim_acts = [slim_activity(a) for a in raw.get("activities", [])]
    activities = slim_acts[:max_activities]
    notable_runs = sorted(
        (
            a
            for a in slim_acts
            if a.get("is_run") and isinstance(a.get("distance_km"), (int, float))
        ),
        key=lambda a: a["distance_km"],
        reverse=True,
    )[:NOTABLE_RUNS_LIMIT]

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
        "notable_runs": notable_runs,
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
