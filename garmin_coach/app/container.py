"""
app/container.py
Dependency container. Phase 1: delegates to legacy bot.
Phases 2-5 will replace run() with full OOP wiring.
"""

from garmin_coach.app.config import Settings


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self) -> None:
        """Start the application. Phase 1: delegates to legacy bot + scheduler."""
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
