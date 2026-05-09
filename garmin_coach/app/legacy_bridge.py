"""
app/legacy_bridge.py
Temporary glue between the new Container and the legacy bot/garmin_sync modules.
DEBT: This module is removed in Phase 4-5 once TelegramBotApp and MFAHandler exist.
"""

import asyncio
import logging
import os
import threading
import time

import schedule

logger = logging.getLogger(__name__)


def wire_mfa_to_app(app) -> None:
    """Register _on_startup hook so garmin_sync captures the running asyncio loop."""
    from garmin_coach.garmin_sync import set_bot_app, set_event_loop

    set_bot_app(app)

    async def _on_startup(application) -> None:
        set_event_loop(asyncio.get_running_loop())

    # post_init is already registered inside build_application; replicate here only
    # if called outside of bot.build_application(). In practice Container calls
    # build_application() which already sets _on_startup, so this is a no-op guard.


def start_scheduler(app, morning_time: str, evening_time: str) -> threading.Thread:
    """Configure and start the legacy scheduler in a daemon thread."""
    from garmin_coach.coach import generate_daily_briefing
    from garmin_coach.db import log_sync
    from garmin_coach.garmin_sync import sync_all
    from garmin_coach.bot import send_scheduled_message

    def _run(moment: str) -> None:
        logger.info(f"Sync programado ({moment}) iniciado")
        try:
            email = os.getenv("GARMIN_EMAIL")
            password = os.getenv("GARMIN_PASSWORD")
            days = int(os.getenv("DAYS_HISTORY", "30"))
            summary = sync_all(email, password, days)
            log_sync(summary)
            logger.info(f"Sync completado: {summary}")
        except Exception as exc:
            logger.error(f"Error en sync programado: {exc}")

        try:
            import garmin_coach.garmin_sync as gs

            briefing = generate_daily_briefing(moment)
            loop = gs._bot_loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    send_scheduled_message(app, briefing), loop
                )
            else:
                logger.warning("Briefing no enviado: loop asyncio no disponible")
        except Exception as exc:
            logger.error(f"Error enviando briefing programado: {exc}")

    schedule.every().day.at(morning_time).do(_run, moment="morning")
    schedule.every().day.at(evening_time).do(_run, moment="evening")
    logger.info(f"Scheduler configurado: mañana {morning_time}, noche {evening_time}")

    def _loop() -> None:
        while True:
            schedule.run_pending()
            time.sleep(30)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
