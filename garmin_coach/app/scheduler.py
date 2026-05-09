"""
app/scheduler.py
Scheduler: runs morning/evening sync+briefing jobs in a daemon thread.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING

import schedule

if TYPE_CHECKING:
    from garmin_coach.app.config import Settings
    from garmin_coach.infrastructure.db.sync_log_repository import SyncLogRepository
    from garmin_coach.infrastructure.telegram.bot_app import TelegramBotApp
    from garmin_coach.services.briefing_service import BriefingService
    from garmin_coach.services.sync_service import SyncService

logger = logging.getLogger(__name__)


class Scheduler:
    """Daemon thread that fires morning and evening sync+briefing jobs."""

    def __init__(
        self,
        sync_service: "SyncService",
        briefing_service: "BriefingService",
        sync_log_repo: "SyncLogRepository",
        bot_app: "TelegramBotApp",
        settings: "Settings",
        check_interval_seconds: int = 30,
    ) -> None:
        self._sync = sync_service
        self._briefing = briefing_service
        self._sync_log = sync_log_repo
        self._bot_app = bot_app
        self._settings = settings
        self._interval = check_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> threading.Thread:
        schedule.every().day.at(self._settings.sync_time_morning).do(self._morning_job)
        schedule.every().day.at(self._settings.sync_time_evening).do(self._evening_job)
        logger.info(
            "Scheduler configured: morning=%s, evening=%s",
            self._settings.sync_time_morning,
            self._settings.sync_time_evening,
        )

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            schedule.run_pending()
            time.sleep(self._interval)

    def _morning_job(self) -> None:
        self._run_job("morning")

    def _evening_job(self) -> None:
        self._run_job("evening")

    def _run_job(self, moment: str) -> None:
        logger.info("Scheduled job started: %s", moment)
        try:
            self._sync.run()
        except Exception as exc:
            logger.error("Scheduled sync error (%s): %s", moment, exc)

        try:
            briefing = self._briefing.generate(moment)
            loop = self._bot_app.loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._bot_app.send_to_user(briefing), loop
                )
            else:
                logger.warning("Briefing not sent: asyncio loop not available")
        except Exception as exc:
            logger.error("Scheduled briefing error (%s): %s", moment, exc)
