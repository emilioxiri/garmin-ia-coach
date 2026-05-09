"""
services/tools/fitness_tools.py
Tool classes for fitness snapshot and personal records queries.
"""

from __future__ import annotations

from typing import Any, ClassVar

from garmin_coach.services.tools.base import Tool, ToolResult


class GetFitnessSnapshotTool(Tool):
    name: ClassVar[str] = "get_fitness_snapshot"
    description: ClassVar[str] = (
        "Snapshot agregado: VO2max running, race predictions (5K/10K/HM/M), umbral de lactato y endurance score más recientes."
    )
    parameters: ClassVar[dict] = {"type": "object", "properties": {}}

    def __init__(
        self,
        fitness_metrics_repo: Any,
        race_predictions_repo: Any,
        lactate_repo: Any,
        endurance_repo: Any,
    ) -> None:
        self._fitness_metrics_repo = fitness_metrics_repo
        self._race_predictions_repo = race_predictions_repo
        self._lactate_repo = lactate_repo
        self._endurance_repo = endurance_repo

    def handle(self) -> ToolResult:
        from garmin_coach.services.projections import (
            slim_endurance_score,
            slim_fitness_metrics,
            slim_lactate_threshold,
            slim_race_predictions,
        )

        return ToolResult(
            data={
                "fitness_metrics": slim_fitness_metrics(
                    self._fitness_metrics_repo.latest()
                ),
                "race_predictions": slim_race_predictions(
                    self._race_predictions_repo.latest()
                ),
                "lactate_threshold": slim_lactate_threshold(
                    self._lactate_repo.latest()
                ),
                "endurance_score": slim_endurance_score(self._endurance_repo.latest()),
            }
        )


class GetPersonalRecordsTool(Tool):
    name: ClassVar[str] = "get_personal_records"
    description: ClassVar[str] = (
        "Devuelve marcas personales calculadas sobre TODA la tabla de actividades: "
        "mejor tiempo en 1K, 5K, 10K, media maratón y maratón (con tolerancia ±2-5%) "
        "y la carrera más larga registrada. Úsalo cuando el atleta pregunte por su PB, "
        "mejor marca, récord personal o tirada más larga."
    )
    parameters: ClassVar[dict] = {"type": "object", "properties": {}}

    def __init__(self, activity_repo: Any) -> None:
        self._repo = activity_repo

    def handle(self) -> ToolResult:
        prs = self._repo.compute_personal_records()
        serialized: dict[str, Any] = {}
        for label, pr in prs.items():
            if pr is None:
                serialized[label] = None
            elif label == "longest_run":
                # longest_run is a PersonalRecord — convert to slim activity via attrs
                serialized[label] = {
                    "activityId": pr.activity_id,
                    "date": pr.date,
                    "distance_km": pr.distance_km,
                    "duration_hms": pr.duration_hms,
                    "pace_min_per_km": pr.pace_min_per_km,
                    "averageHR": pr.average_hr,
                }
            else:
                serialized[label] = {
                    "activityId": pr.activity_id,
                    "date": pr.date,
                    "distance_km": pr.distance_km,
                    "duration_hms": pr.duration_hms,
                    "pace_min_per_km": pr.pace_min_per_km,
                    "averageHR": pr.average_hr,
                }

        all_activities = self._repo.all()
        return ToolResult(
            data={
                "records": serialized,
                "activities_evaluated": len(all_activities),
            }
        )
