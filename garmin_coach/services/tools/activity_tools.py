"""
services/tools/activity_tools.py
Tool classes for activity-related queries.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, ClassVar

from garmin_coach.app.logging_setup import get_logger
from garmin_coach.domain.activity import RUN_TYPES
from garmin_coach.services.tools.base import Tool, ToolResult

logger = get_logger(__name__)

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
    if only_runs and raw_type not in RUN_TYPES:
        return False
    return True


class FindActivityTool(Tool):
    name: ClassVar[str] = "find_activity"
    description: ClassVar[str] = (
        "Busca actividades del atleta filtrando por día de la semana en español "
        "(lunes…domingo), fecha exacta YYYY-MM-DD, rango de distancia en km, tipo "
        "de actividad (running, cycling, padel, strength_training…) y/o solo "
        "carreras (only_runs). Úsalo cuando el atleta mencione una sesión "
        'concreta ("la media maratón del viernes", "el rodaje del 5 de mayo").'
    )
    parameters: ClassVar[dict] = {
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
    }

    def __init__(self, activity_repo: Any) -> None:
        self._repo = activity_repo

    def handle(
        self,
        weekday: str | None = None,
        date_iso: str | None = None,
        min_distance_km: float | None = None,
        max_distance_km: float | None = None,
        activity_type: str | None = None,
        only_runs: bool = False,
        days: int = DEFAULT_FIND_DAYS,
    ) -> ToolResult:
        from garmin_coach.services.projections import slim_activity

        weekday_idx: int | None = None
        if weekday:
            weekday_idx = _WEEKDAYS_ES_INDEX.get(weekday.strip().lower())
            if weekday_idx is None:
                return ToolResult(data=[])

        cutoff = _cutoff(days)
        activities = [
            a
            for a in self._repo.all()
            if bool(a.get("startTimeLocal")) and a.get("startTimeLocal", "") >= cutoff
        ]
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
        result = [slim_activity(a) for a in matches[:MAX_ACTIVITIES_RESULT]]
        logger.debug("event=find_activity matches=%d", len(result))
        return ToolResult(data=result)


class GetRecentActivitiesTool(Tool):
    name: ClassVar[str] = "get_recent_activities"
    description: ClassVar[str] = (
        "Devuelve actividades recientes (más nuevas primero) en una ventana de N días. Filtros opcionales por tipo o sólo carreras."
    )
    parameters: ClassVar[dict] = {
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
    }

    def __init__(self, activity_repo: Any) -> None:
        self._repo = activity_repo

    def handle(
        self,
        days: int = DEFAULT_WINDOW_DAYS,
        activity_type: str | None = None,
        only_runs: bool = False,
        limit: int = MAX_ACTIVITIES_RESULT,
    ) -> ToolResult:
        from garmin_coach.services.projections import slim_activity

        cutoff = _cutoff(days)
        rows = [
            a
            for a in self._repo.all()
            if bool(a.get("startTimeLocal")) and a.get("startTimeLocal", "") >= cutoff
        ]
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
        return ToolResult(data=[slim_activity(a) for a in rows[:cap]])


class GetActivityDetailTool(Tool):
    name: ClassVar[str] = "get_activity_detail"
    description: ClassVar[str] = (
        "Devuelve la actividad con `activityId` indicado. Útil tras find_activity para confirmar métricas avanzadas."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "activity_id": {"type": "string"},
        },
        "required": ["activity_id"],
    }

    def __init__(self, activity_repo: Any) -> None:
        self._repo = activity_repo

    def handle(self, activity_id: str) -> ToolResult:
        from tinydb import Query

        from garmin_coach.services.projections import slim_activity

        Q = Query()
        rows = self._repo._table.search(Q.activityId == str(activity_id))
        if not rows:
            rows = self._repo._table.search(Q.activityId == activity_id)
        if not rows:
            return ToolResult(data=None)
        return ToolResult(data=slim_activity(rows[0]))
