"""Tests for garmin_coach.app.logging_setup."""

import logging
from pathlib import Path

from garmin_coach.app.config import Settings
from garmin_coach.app.logging_setup import configure_logging


def _make_settings(log_path: Path) -> Settings:
    return Settings(
        garmin_email="test@example.com",
        garmin_password="secret",
        telegram_bot_token="123:abc",
        telegram_allowed_user_id=42,
        groq_api_key="gsk_test",
        sync_time_morning="07:00",
        sync_time_evening="22:00",
        days_history=30,
        db_path=Path("/data/garmin_coach.json"),
        session_path=Path("/data/garmin_session.json"),
        log_path=log_path,
    )


def test_configure_logging_creates_log_dir(tmp_path):
    log_path = tmp_path / "logs" / "bot.log"
    assert not log_path.parent.exists()

    settings = _make_settings(log_path)
    configure_logging(settings)

    assert log_path.parent.exists()

    # Cleanup: remove FileHandler added to root logger to avoid polluting other tests
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == str(
            log_path
        ):
            handler.close()
            root.removeHandler(handler)


def test_configure_logging_attaches_handlers(tmp_path):
    log_path = tmp_path / "logs2" / "bot.log"
    settings = _make_settings(log_path)

    # Reset root handlers first so basicConfig takes effect
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    root.handlers.clear()

    try:
        configure_logging(settings)

        handler_types = {type(h) for h in root.handlers}
        assert logging.FileHandler in handler_types
        assert logging.StreamHandler in handler_types
    finally:
        # Restore original handlers
        for handler in list(root.handlers):
            if isinstance(handler, logging.FileHandler):
                handler.close()
        root.handlers = original_handlers
