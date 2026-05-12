"""
app/container.py
Dependency container — Phase 5 final: wires all layers end-to-end.
No delegation to legacy_bridge. No shims.
"""

from __future__ import annotations

from dataclasses import dataclass

from garmin_coach.app.config import Settings
from garmin_coach.app.logging_setup import get_logger

logger = get_logger(__name__)


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
        self.mfa_handler = self._build_mfa_handler()
        self.garmin_client = self._build_garmin_client()
        self.sync_service = self._build_sync_service()
        self.formatter = self._build_formatter()
        self.authorizer = self._build_authorizer()
        self.command_handlers = self._build_command_handlers()
        self.chat_handler = self._build_chat_handler()
        self.bot_app = self._build_bot_app()
        self.scheduler = self._build_scheduler()

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

    def _build_mfa_handler(self):
        from garmin_coach.infrastructure.garmin.mfa_handler import MFAHandler

        return MFAHandler(timeout_seconds=300)

    def _build_garmin_client(self):
        from garmin_coach.infrastructure.garmin.client import GarminClient

        return GarminClient(self.settings, self.mfa_handler)

    def _build_sync_service(self):
        from garmin_coach.infrastructure.garmin.data_fetcher import GarminDataFetcher
        from garmin_coach.services.sync_service import SyncService

        return SyncService(
            garmin_client=self.garmin_client,
            fetcher_factory=lambda g: GarminDataFetcher(g),
            repositories=self.repositories,
            sync_log_repo=self.repositories.sync_log,
            settings=self.settings,
        )

    def _build_formatter(self):
        from garmin_coach.infrastructure.telegram.formatter import MessageFormatter

        return MessageFormatter()

    def _build_authorizer(self):
        from garmin_coach.infrastructure.telegram.auth import Authorizer

        return Authorizer(self.settings.telegram_allowed_user_id)

    def _build_command_handlers(self):
        from garmin_coach.infrastructure.telegram.handlers.commands import (
            CommandHandlers,
        )

        return CommandHandlers(
            coach_service=self.coach_service,
            briefing_service=self.briefing_service,
            sync_service=self.sync_service,
            mfa_handler=self.mfa_handler,
            memory_repo=self.repositories.memory,
            sync_log_repo=self.repositories.sync_log,
            context_builder=self.context_builder,
            formatter=self.formatter,
            authorizer=self.authorizer,
            garmin_client=self.garmin_client,
            log_path=self.settings.log_path,
        )

    def _build_chat_handler(self):
        from garmin_coach.infrastructure.telegram.handlers.chat import (
            ChatMessageHandler,
        )

        return ChatMessageHandler(
            coach_service=self.coach_service,
            formatter=self.formatter,
            authorizer=self.authorizer,
        )

    def _build_bot_app(self):
        from garmin_coach.infrastructure.telegram.bot_app import TelegramBotApp

        return TelegramBotApp(
            settings=self.settings,
            command_handlers=self.command_handlers,
            chat_handler=self.chat_handler,
            mfa_handler=self.mfa_handler,
            formatter=self.formatter,
        )

    def _build_scheduler(self):
        from garmin_coach.app.scheduler import Scheduler

        return Scheduler(
            sync_service=self.sync_service,
            briefing_service=self.briefing_service,
            sync_log_repo=self.repositories.sync_log,
            bot_app=self.bot_app,
            settings=self.settings,
        )

    def run(self) -> None:
        logger.info("event=container_start")
        self.scheduler.start()
        try:
            self.bot_app.run()
        finally:
            self.scheduler.stop()
            logger.info("event=container_stop")
