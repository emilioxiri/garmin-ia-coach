"""
app/config.py
Settings dataclass + factory. Single point that reads os.environ.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    garmin_email: str
    garmin_password: str
    telegram_bot_token: str
    telegram_allowed_user_id: int
    groq_api_key: str
    sync_time_morning: str
    sync_time_evening: str
    days_history: int
    db_path: Path
    session_path: Path
    log_path: Path
    timezone: str = "Europe/Madrid"
    llm_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"


def load_settings() -> Settings:
    """Read environment variables and return a validated Settings instance.

    Raises RuntimeError if any required variable is missing.
    """
    missing = []

    def require(name: str) -> str:
        value = os.getenv(name)
        if not value:
            missing.append(name)
            return ""
        return value

    garmin_email = require("GARMIN_EMAIL")
    garmin_password = require("GARMIN_PASSWORD")
    telegram_bot_token = require("TELEGRAM_BOT_TOKEN")
    groq_api_key = require("GROQ_API_KEY")

    raw_user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "")
    if not raw_user_id:
        missing.append("TELEGRAM_ALLOWED_USER_ID")

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return Settings(
        garmin_email=garmin_email,
        garmin_password=garmin_password,
        telegram_bot_token=telegram_bot_token,
        telegram_allowed_user_id=int(raw_user_id),
        groq_api_key=groq_api_key,
        sync_time_morning=os.getenv("SYNC_TIME_MORNING", "07:00"),
        sync_time_evening=os.getenv("SYNC_TIME_EVENING", "22:00"),
        days_history=int(os.getenv("DAYS_HISTORY", "30")),
        db_path=Path(os.getenv("DB_PATH", "/data/garmin_coach.json")),
        session_path=Path(os.getenv("SESSION_PATH", "/data/garmin_session.json")),
        log_path=Path(os.getenv("LOG_PATH", "/data/logs/bot.log")),
        timezone=os.getenv("TIMEZONE", "Europe/Madrid"),
        llm_model=os.getenv("LLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
    )
