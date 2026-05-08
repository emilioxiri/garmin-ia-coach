"""
coach_tools.py
Tool definitions (Groq/OpenAI function-calling schema) + handlers backed by TinyDB.

The LLM uses these to drill into specific data instead of receiving the whole
context dump up-front. Each handler returns a small, JSON-serializable dict
(or list) projected through `garmin_coach.context_builder` slim_* helpers.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Callable

from tinydb import Query

from garmin_coach.context_builder import (
    _RUN_TYPES,
    _format_duration,
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
from garmin_coach.db import get_db

logger = logging.getLogger(__name__)

# Cap result sizes so a misbehaving LLM cannot blow context back up.
MAX_ACTIVITIES_RESULT = 25
MAX_WINDOW_DAYS = 90
DEFAULT_FIND_DAYS = 30
DEFAULT_WINDOW_DAYS = 7

_WEEKDAYS_ES_INDEX = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _cutoff(days: int) -> str:
    days = max(1, min(int(days), MAX_WINDOW_DAYS))
    return (date.today() - timedelta(days=days)).isoformat()


def _activity_type_key(act: dict) -> str | None:
    t = act.get("activityType")
    if isinstance(t, dict):
        return t.get("typeKey")
    if isinstance(t, str):
        return t
    return None


def _activity_matches(
    act: dict,
    *,
    weekday_idx: int | None,
    date_str: str | None,
    min_km: float | None,
    max_km: float | None,
    type_key: str | None,
    only_runs: bool,
) -> bool:
    start = act.get("startTimeLocal", "")
    if not isinstance(start, str) or len(start) < 10:
        return False
    if date_str and start[:10] != date_str:
        return False
    if weekday_idx is not None:
        try:
            d = date.fromisoformat(start[:10])
        except ValueError:
            return False
        if d.weekday() != weekday_idx:
            return False
    distance_m = act.get("distance")
    if min_km is not None:
        if not isinstance(distance_m, (int, float)) or distance_m / 1000 < min_km:
            return False
    if max_km is not None:
        if not isinstance(distance_m, (int, float)) or distance_m / 1000 > max_km:
            return False
    raw_type = _activity_type_key(act) or ""
    if type_key and raw_type != type_key:
        return False
    if only_runs and raw_type not in _RUN_TYPES:
        return False
    return True


def _date_window(
    table_name: str, days: int, slimmer: Callable[[dict], dict]
) -> list[dict]:
    cutoff = _cutoff(days)
    Q = Query()
    rows = sorted(
        get_db().table(table_name).search(Q.date >= cutoff),
        key=lambda r: r.get("date", ""),
        reverse=True,
    )
    return [slimmer(r) for r in rows]


def _latest(table_name: str) -> dict | None:
    rows = get_db().table(table_name).all()
    if not rows:
        return None
    return max(rows, key=lambda r: r.get("date", ""))


# ── Handlers ──────────────────────────────────────────────────────────────────


def find_activity(
    weekday: str | None = None,
    date_iso: str | None = None,
    min_distance_km: float | None = None,
    max_distance_km: float | None = None,
    activity_type: str | None = None,
    only_runs: bool = False,
    days: int = DEFAULT_FIND_DAYS,
) -> list[dict]:
    """Find activities matching loose filters. Returns slim activities, newest first."""
    weekday_idx: int | None = None
    if weekday:
        weekday_idx = _WEEKDAYS_ES_INDEX.get(weekday.strip().lower())
        if weekday_idx is None:
            return []

    cutoff = _cutoff(days)
    Q = Query()
    activities = (
        get_db()
        .table("activities")
        .search(Q.startTimeLocal.test(lambda v: bool(v) and v >= cutoff))
    )
    matches = [
        a
        for a in activities
        if _activity_matches(
            a,
            weekday_idx=weekday_idx,
            date_str=date_iso,
            min_km=min_distance_km,
            max_km=max_distance_km,
            type_key=activity_type,
            only_runs=only_runs,
        )
    ]
    matches.sort(key=lambda a: a.get("startTimeLocal", ""), reverse=True)
    return [slim_activity(a) for a in matches[:MAX_ACTIVITIES_RESULT]]


def get_recent_activities(
    days: int = DEFAULT_WINDOW_DAYS,
    activity_type: str | None = None,
    only_runs: bool = False,
    limit: int = MAX_ACTIVITIES_RESULT,
) -> list[dict]:
    cutoff = _cutoff(days)
    Q = Query()
    rows = (
        get_db()
        .table("activities")
        .search(Q.startTimeLocal.test(lambda v: bool(v) and v >= cutoff))
    )
    if activity_type or only_runs:
        rows = [
            a
            for a in rows
            if _activity_matches(
                a,
                weekday_idx=None,
                date_str=None,
                min_km=None,
                max_km=None,
                type_key=activity_type,
                only_runs=only_runs,
            )
        ]
    rows.sort(key=lambda a: a.get("startTimeLocal", ""), reverse=True)
    cap = max(1, min(int(limit), MAX_ACTIVITIES_RESULT))
    return [slim_activity(a) for a in rows[:cap]]


def get_activity_detail(activity_id: str) -> dict | None:
    Q = Query()
    rows = get_db().table("activities").search(Q.activityId == str(activity_id))
    if not rows:
        rows = get_db().table("activities").search(Q.activityId == activity_id)
    if not rows:
        return None
    return slim_activity(rows[0])


def get_sleep_window(days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    return _date_window("sleep", days, slim_sleep)


def get_hrv_window(days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    return _date_window("hrv", days, slim_hrv)


def get_body_battery_window(days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    return _date_window("body_battery", days, slim_body_battery)


def get_training_readiness_window(days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    return _date_window("training_readiness", days, slim_training_readiness)


def get_fitness_snapshot() -> dict:
    return {
        "fitness_metrics": slim_fitness_metrics(_latest("fitness_metrics")),
        "race_predictions": slim_race_predictions(_latest("race_predictions")),
        "lactate_threshold": slim_lactate_threshold(_latest("lactate_threshold")),
        "endurance_score": slim_endurance_score(_latest("endurance_score")),
    }


# ── Personal records ──────────────────────────────────────────────────────────

# Distancias canónicas en metros con tolerancia para emparejar PRs.
# La tolerancia es asimétrica hacia arriba: una "media maratón" puede medir
# 21097 m exactos o 21450 m si hubo desvío de Garmin; pero NO debe contar como
# media una carrera de 19 km.
_PR_DISTANCES = (
    {"label": "1K", "meters": 1_000, "tolerance": 0.05},
    {"label": "5K", "meters": 5_000, "tolerance": 0.03},
    {"label": "10K", "meters": 10_000, "tolerance": 0.03},
    {"label": "half_marathon", "meters": 21_097, "tolerance": 0.02},
    {"label": "marathon", "meters": 42_195, "tolerance": 0.02},
)


def _pr_for_distance(
    activities: list[dict], target_m: int, tolerance: float
) -> dict | None:
    """Best (lowest duration) running activity within ±tolerance of target distance."""
    lo = target_m * (1 - tolerance)
    hi = target_m * (1 + tolerance)
    candidates = []
    for act in activities:
        type_key = _activity_type_key(act)
        if type_key not in _RUN_TYPES:
            continue
        distance = act.get("distance")
        duration = act.get("duration")
        if not isinstance(distance, (int, float)) or not isinstance(
            duration, (int, float)
        ):
            continue
        if duration <= 0 or not (lo <= distance <= hi):
            continue
        candidates.append((duration, act))
    if not candidates:
        return None
    duration, act = min(candidates, key=lambda x: x[0])
    distance = act["distance"]
    pace_sec = (1000 / distance) * duration if distance else None
    pace_str: str | None = None
    if isinstance(pace_sec, (int, float)) and pace_sec > 0:
        pace_minutes = int(pace_sec // 60)
        pace_seconds = int(round(pace_sec - pace_minutes * 60))
        if pace_seconds == 60:
            pace_minutes += 1
            pace_seconds = 0
        pace_str = f"{pace_minutes}:{pace_seconds:02d}"
    return {
        "activityId": act.get("activityId"),
        "date": (act.get("startTimeLocal") or "")[:10] or None,
        "distance_km": round(distance / 1000, 2),
        "duration_hms": _format_duration(duration),
        "pace_min_per_km": pace_str,
        "averageHR": act.get("averageHR"),
    }


def _longest_run(activities: list[dict]) -> dict | None:
    longest = None
    longest_distance = 0.0
    for act in activities:
        if _activity_type_key(act) not in _RUN_TYPES:
            continue
        distance = act.get("distance")
        if isinstance(distance, (int, float)) and distance > longest_distance:
            longest_distance = distance
            longest = act
    if longest is None:
        return None
    return slim_activity(longest)


def get_personal_records() -> dict:
    """Compute personal records from the full activities table.

    Returns best time per canonical distance (1K/5K/10K/HM/M) plus the longest
    run on record. Computed on-the-fly: no separate table to keep in sync.
    """
    activities = get_db().table("activities").all()
    bests: dict[str, dict | None] = {}
    for spec in _PR_DISTANCES:
        bests[spec["label"]] = _pr_for_distance(
            activities, spec["meters"], spec["tolerance"]
        )
    return {
        "records": bests,
        "longest_run": _longest_run(activities),
        "activities_evaluated": len(activities),
    }


def search_memory(query: str = "", limit: int = 10) -> list[dict]:
    rows = get_db().table("memory").all()
    needle = (query or "").strip().lower()
    if needle:
        rows = [r for r in rows if needle in (r.get("note") or "").lower()]
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    cap = max(1, min(int(limit), 50))
    return rows[:cap]


# ── Registry ──────────────────────────────────────────────────────────────────

HANDLERS: dict[str, Callable[..., Any]] = {
    "find_activity": find_activity,
    "get_recent_activities": get_recent_activities,
    "get_activity_detail": get_activity_detail,
    "get_sleep_window": get_sleep_window,
    "get_hrv_window": get_hrv_window,
    "get_body_battery_window": get_body_battery_window,
    "get_training_readiness_window": get_training_readiness_window,
    "get_fitness_snapshot": get_fitness_snapshot,
    "get_personal_records": get_personal_records,
    "search_memory": search_memory,
}


TOOLS_SPEC: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "find_activity",
            "description": (
                "Busca actividades del atleta filtrando por día de la semana en español "
                "(lunes…domingo), fecha exacta YYYY-MM-DD, rango de distancia en km, tipo "
                "de actividad (running, cycling, padel, strength_training…) y/o solo "
                "carreras (only_runs). Úsalo cuando el atleta mencione una sesión "
                'concreta ("la media maratón del viernes", "el rodaje del 5 de mayo").'
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "weekday": {
                        "type": "string",
                        "description": "lunes, martes, miércoles, jueves, viernes, sábado, domingo",
                    },
                    "date_iso": {
                        "type": "string",
                        "description": "Fecha exacta en formato YYYY-MM-DD",
                    },
                    "min_distance_km": {"type": "number"},
                    "max_distance_km": {"type": "number"},
                    "activity_type": {
                        "type": "string",
                        "description": "typeKey de Garmin: running, trail_running, cycling, padel, strength_training, etc.",
                    },
                    "only_runs": {
                        "type": "boolean",
                        "description": "Si true, sólo carreras (running, trail_running, treadmill_running…)",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Ventana hacia atrás. Default 30, max 90.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_activities",
            "description": "Devuelve actividades recientes (más nuevas primero) en una ventana de N días. Filtros opcionales por tipo o sólo carreras.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Default 7, max 90."},
                    "activity_type": {"type": "string"},
                    "only_runs": {"type": "boolean"},
                    "limit": {
                        "type": "integer",
                        "description": "Máximo a devolver (cap interno 25).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activity_detail",
            "description": "Devuelve la actividad con `activityId` indicado. Útil tras find_activity para confirmar métricas avanzadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_id": {"type": "string"},
                },
                "required": ["activity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sleep_window",
            "description": "Devuelve registros de sueño (total/deep/rem/light/awake en horas, score, restingHR) en los últimos `days` días.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hrv_window",
            "description": "Devuelve HRV diaria (lastNight, weeklyAvg, status) en los últimos `days` días.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_body_battery_window",
            "description": "Devuelve Body Battery (max/min) diaria en los últimos `days` días.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_training_readiness_window",
            "description": "Devuelve training readiness (score, level, feedback, sleepScore, hrvFactorPercent) en ventana.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fitness_snapshot",
            "description": "Snapshot agregado: VO2max running, race predictions (5K/10K/HM/M), umbral de lactato y endurance score más recientes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_personal_records",
            "description": (
                "Devuelve marcas personales calculadas sobre TODA la tabla de actividades: "
                "mejor tiempo en 1K, 5K, 10K, media maratón y maratón (con tolerancia ±2-5%) "
                "y la carrera más larga registrada. Úsalo cuando el atleta pregunte por su PB, "
                "mejor marca, récord personal o tirada más larga."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Busca en las notas que el atleta ha guardado con /memoria (lesiones, sensaciones, decisiones). Substring case-insensitive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
]


def dispatch_tool_call(name: str, arguments: dict) -> Any:
    """Run a tool by name with kwargs. Returns handler result or error dict.

    Caller should JSON-serialize the result before passing back to the LLM.
    """
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return handler(**(arguments or {}))
    except TypeError as e:
        logger.warning("tool %s rejected args %s: %s", name, arguments, e)
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:
        logger.exception("tool %s crashed", name)
        return {"error": f"{name} failed: {e}"}
