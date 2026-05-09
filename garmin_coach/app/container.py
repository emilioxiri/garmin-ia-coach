"""
app/container.py
Dependency container.
Phase 1: Settings skeleton.
Phase 2: TinyDBFactory + repositories wired.
Phase 3: LLMClient + ToolRegistry + ContextBuilder + CoachService + BriefingService.
Phases 4-5 will complete the OOP wiring.
"""

from __future__ import annotations

from dataclasses import dataclass

from garmin_coach.app.config import Settings


@dataclass
class Repositories:
    """Holder for all repository instances."""

    activities: object
    sleep: object
    hrv: object
    body_battery: object
    training_status: object
    training_readiness: object
    respiration: object
    spo2: object
    stress: object
    fitness_metrics: object
    race_predictions: object
    lactate_threshold: object
    endurance_score: object
    memory: object
    sync_log: object


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repositories = self._build_repositories()
        self.llm_client = self._build_llm_client()
        self.tool_registry = self._build_tool_registry()
        self.context_builder = self._build_context_builder()
        self._system_prompt: str | None = None
        self.coach_service = self._build_coach_service()
        self.briefing_service = self._build_briefing_service()

    def _build_repositories(self) -> Repositories:
        from garmin_coach.infrastructure.db.activity_repository import (
            ActivityRepository,
        )
        from garmin_coach.infrastructure.db.fitness_repository import (
            EnduranceScoreRepository,
            FitnessMetricsRepository,
            LactateThresholdRepository,
            RacePredictionsRepository,
        )
        from garmin_coach.infrastructure.db.memory_repository import MemoryRepository
        from garmin_coach.infrastructure.db.sync_log_repository import SyncLogRepository
        from garmin_coach.infrastructure.db.tinydb_factory import TinyDBFactory
        from garmin_coach.infrastructure.db.wellness_repository import (
            BodyBatteryRepository,
            HRVRepository,
            RespirationRepository,
            SPO2Repository,
            SleepRepository,
            StressRepository,
            TrainingReadinessRepository,
            TrainingStatusRepository,
        )

        db = TinyDBFactory(self.settings.db_path).get()
        return Repositories(
            activities=ActivityRepository(db),
            sleep=SleepRepository(db),
            hrv=HRVRepository(db),
            body_battery=BodyBatteryRepository(db),
            training_status=TrainingStatusRepository(db),
            training_readiness=TrainingReadinessRepository(db),
            respiration=RespirationRepository(db),
            spo2=SPO2Repository(db),
            stress=StressRepository(db),
            fitness_metrics=FitnessMetricsRepository(db),
            race_predictions=RacePredictionsRepository(db),
            lactate_threshold=LactateThresholdRepository(db),
            endurance_score=EnduranceScoreRepository(db),
            memory=MemoryRepository(db),
            sync_log=SyncLogRepository(db),
        )

    def _build_llm_client(self):
        from garmin_coach.infrastructure.llm.groq_langchain import ChatGroqClient

        return ChatGroqClient(model=self.settings.llm_model)

    def _build_tool_registry(self):
        from garmin_coach.services.tools.activity_tools import (
            FindActivityTool,
            GetActivityDetailTool,
            GetRecentActivitiesTool,
        )
        from garmin_coach.services.tools.fitness_tools import (
            GetFitnessSnapshotTool,
            GetPersonalRecordsTool,
        )
        from garmin_coach.services.tools.memory_tools import SearchMemoryTool
        from garmin_coach.services.tools.registry import ToolRegistry
        from garmin_coach.services.tools.wellness_tools import (
            GetBodyBatteryWindowTool,
            GetHRVWindowTool,
            GetSleepWindowTool,
            GetTrainingReadinessWindowTool,
        )

        r = self.repositories
        registry = ToolRegistry()
        registry.register(FindActivityTool(r.activities))
        registry.register(GetRecentActivitiesTool(r.activities))
        registry.register(GetActivityDetailTool(r.activities))
        registry.register(GetSleepWindowTool(r.sleep))
        registry.register(GetHRVWindowTool(r.hrv))
        registry.register(GetBodyBatteryWindowTool(r.body_battery))
        registry.register(GetTrainingReadinessWindowTool(r.training_readiness))
        registry.register(
            GetFitnessSnapshotTool(
                r.fitness_metrics,
                r.race_predictions,
                r.lactate_threshold,
                r.endurance_score,
            )
        )
        registry.register(GetPersonalRecordsTool(r.activities))
        registry.register(SearchMemoryTool(r.memory))
        return registry

    def _build_context_builder(self):
        from garmin_coach.services.context_builder import ContextBuilder

        r = self.repositories
        return ContextBuilder(
            activity_repo=r.activities,
            sleep_repo=r.sleep,
            hrv_repo=r.hrv,
            body_battery_repo=r.body_battery,
            training_status_repo=r.training_status,
            training_readiness_repo=r.training_readiness,
            respiration_repo=r.respiration,
            spo2_repo=r.spo2,
            stress_repo=r.stress,
            fitness_metrics_repo=r.fitness_metrics,
            race_predictions_repo=r.race_predictions,
            lactate_repo=r.lactate_threshold,
            endurance_repo=r.endurance_score,
            memory_repo=r.memory,
        )

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            from garmin_coach.prompts import read_system_prompt

            self._system_prompt = read_system_prompt()
        return self._system_prompt

    def _build_coach_service(self):
        from garmin_coach.services.coach_service import CoachService
        from garmin_coach.services.coach_session import CoachSession
        from garmin_coach.services.session_manager import SessionManager

        llm = self.llm_client
        registry = self.tool_registry
        cb = self.context_builder
        prompt = self._get_system_prompt()

        def _session_factory() -> CoachSession:
            return CoachSession(llm, registry, cb, prompt)

        return CoachService(SessionManager(_session_factory))

    def _build_briefing_service(self):
        from garmin_coach.services.briefing_service import BriefingService

        return BriefingService(
            self.llm_client,
            self.context_builder,
            self._get_system_prompt(),
        )

    def run(self) -> None:
        """Start the application. Phases 1-3: delegates to legacy bot + scheduler."""
        from garmin_coach.app.legacy_bridge import start_scheduler
        from garmin_coach.bot import build_application
        from garmin_coach.garmin_sync import set_bot_app

        app = build_application()
        set_bot_app(app)

        start_scheduler(
            app,
            morning_time=self.settings.sync_time_morning,
            evening_time=self.settings.sync_time_evening,
        )

        app.run_polling(drop_pending_updates=True)
