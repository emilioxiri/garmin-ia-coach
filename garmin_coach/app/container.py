"""
app/container.py
Dependency container.
Phase 1: Settings skeleton.
Phase 2: TinyDBFactory + repositories wired.
Phases 3-5 will complete the OOP wiring.
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

    def run(self) -> None:
        """Start the application. Phases 1-2: delegates to legacy bot + scheduler."""
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
