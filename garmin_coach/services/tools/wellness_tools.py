"""
services/tools/wellness_tools.py
Tool classes for wellness data queries (sleep, HRV, body battery, training readiness).
"""

from __future__ import annotations

from typing import Any, ClassVar

from garmin_coach.services.tools.base import Tool, ToolResult

DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 90


class GetSleepWindowTool(Tool):
    name: ClassVar[str] = "get_sleep_window"
    description: ClassVar[str] = (
        "Devuelve registros de sueño (total/deep/rem/light/awake en horas, score, restingHR) en los últimos `days` días."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {"days": {"type": "integer"}},
    }

    def __init__(self, sleep_repo: Any) -> None:
        self._repo = sleep_repo

    def handle(self, days: int = DEFAULT_WINDOW_DAYS) -> ToolResult:
        from garmin_coach.services.projections import slim_sleep

        rows = self._repo.window(max(1, min(int(days), MAX_WINDOW_DAYS)))
        return ToolResult(data=[slim_sleep(r) for r in rows])


class GetHRVWindowTool(Tool):
    name: ClassVar[str] = "get_hrv_window"
    description: ClassVar[str] = (
        "Devuelve HRV diaria (lastNight, weeklyAvg, status) en los últimos `days` días."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {"days": {"type": "integer"}},
    }

    def __init__(self, hrv_repo: Any) -> None:
        self._repo = hrv_repo

    def handle(self, days: int = DEFAULT_WINDOW_DAYS) -> ToolResult:
        from garmin_coach.services.projections import slim_hrv

        rows = self._repo.window(max(1, min(int(days), MAX_WINDOW_DAYS)))
        return ToolResult(data=[slim_hrv(r) for r in rows])


class GetBodyBatteryWindowTool(Tool):
    name: ClassVar[str] = "get_body_battery_window"
    description: ClassVar[str] = (
        "Devuelve Body Battery (max/min) diaria en los últimos `days` días."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {"days": {"type": "integer"}},
    }

    def __init__(self, body_battery_repo: Any) -> None:
        self._repo = body_battery_repo

    def handle(self, days: int = DEFAULT_WINDOW_DAYS) -> ToolResult:
        from garmin_coach.services.projections import slim_body_battery

        rows = self._repo.window(max(1, min(int(days), MAX_WINDOW_DAYS)))
        return ToolResult(data=[slim_body_battery(r) for r in rows])


class GetTrainingReadinessWindowTool(Tool):
    name: ClassVar[str] = "get_training_readiness_window"
    description: ClassVar[str] = (
        "Devuelve training readiness (score, level, feedback, sleepScore, hrvFactorPercent) en ventana."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {"days": {"type": "integer"}},
    }

    def __init__(self, training_readiness_repo: Any) -> None:
        self._repo = training_readiness_repo

    def handle(self, days: int = DEFAULT_WINDOW_DAYS) -> ToolResult:
        from garmin_coach.services.projections import slim_training_readiness

        rows = self._repo.window(max(1, min(int(days), MAX_WINDOW_DAYS)))
        return ToolResult(data=[slim_training_readiness(r) for r in rows])
