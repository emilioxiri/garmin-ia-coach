"""
main.py
Punto de entrada: lanza el bot de Telegram y el scheduler de sincronización.
"""

import asyncio
import logging
import os
import threading
import schedule
import time
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/data/logs/bot.log"),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def scheduled_sync_and_briefing(app, moment: str):
    """
    Tarea programada: sincroniza Garmin y envía el briefing.
    Se ejecuta en un hilo separado, por eso usamos asyncio.run_coroutine_threadsafe.
    """
    import os
    from garmin_coach.garmin_sync import sync_all
    from garmin_coach.db import log_sync
    from garmin_coach.coach import generate_daily_briefing
    from garmin_coach.bot import send_scheduled_message

    logger.info(f"⏰ Sync programado ({moment}) iniciado")

    try:
        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        days = int(os.getenv("DAYS_HISTORY", "30"))
        summary = sync_all(email, password, days)
        log_sync(summary)
        logger.info(f"✅ Sync completado: {summary}")
    except Exception as e:
        logger.error(f"❌ Error en sync programado: {e}")

    try:
        from garmin_coach.garmin_sync import _bot_loop
        briefing = generate_daily_briefing(moment)
        if _bot_loop and _bot_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                send_scheduled_message(app, briefing), _bot_loop
            )
        else:
            logger.warning("No se pudo enviar el briefing: loop de asyncio no disponible")
    except Exception as e:
        logger.error(f"❌ Error enviando briefing programado: {e}")


def start_scheduler(app):
    """Configura y arranca el scheduler en un hilo dedicado."""
    morning_time = os.getenv("SYNC_TIME_MORNING", "07:00")
    evening_time = os.getenv("SYNC_TIME_EVENING", "21:00")

    schedule.every().day.at(morning_time).do(
        scheduled_sync_and_briefing, app=app, moment="morning"
    )
    schedule.every().day.at(evening_time).do(
        scheduled_sync_and_briefing, app=app, moment="evening"
    )

    logger.info(f"📅 Scheduler configurado: mañana {morning_time}, noche {evening_time}")

    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    from garmin_coach.bot import build_application
    from garmin_coach.garmin_sync import set_bot_app

    logger.info("🚀 Iniciando Garmin Coach Bot...")

    os.makedirs("/data/logs", exist_ok=True)

    app = build_application()
    set_bot_app(app)

    # Arrancar el scheduler en un hilo de fondo
    scheduler_thread = threading.Thread(
        target=start_scheduler, args=(app,), daemon=True
    )
    scheduler_thread.start()
    logger.info("⏰ Scheduler arrancado en hilo de fondo")

    # Arrancar el bot (blocking)
    logger.info("🤖 Bot de Telegram iniciado, esperando mensajes...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
