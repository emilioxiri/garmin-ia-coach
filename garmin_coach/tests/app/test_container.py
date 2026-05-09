"""Tests for garmin_coach.app.container and garmin_coach.prompts."""

from pathlib import Path
from unittest.mock import MagicMock

import garmin_coach.app.legacy_bridge as _legacy_bridge_mod
import garmin_coach.bot as _bot_mod
import garmin_coach.garmin_sync as _garmin_sync_mod

from garmin_coach.app.config import Settings
from garmin_coach.app.container import Container
from garmin_coach.prompts import read_system_prompt


def _make_settings(**overrides) -> Settings:
    defaults = dict(
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
        log_path=Path("/data/logs/bot.log"),
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_container_stores_settings():
    settings = _make_settings()
    container = Container(settings)
    assert container.settings is settings


def test_container_run_delegates_to_legacy(monkeypatch):
    settings = _make_settings()
    container = Container(settings)

    fake_app = MagicMock()
    mock_set_bot = MagicMock()
    mock_scheduler = MagicMock()

    # Container.run() uses local `from X import Y`, so patch at source modules.
    monkeypatch.setattr(_bot_mod, "build_application", lambda: fake_app)
    monkeypatch.setattr(_garmin_sync_mod, "set_bot_app", mock_set_bot)
    monkeypatch.setattr(_legacy_bridge_mod, "start_scheduler", mock_scheduler)

    container.run()

    mock_set_bot.assert_called_once_with(fake_app)
    mock_scheduler.assert_called_once_with(
        fake_app,
        morning_time="07:00",
        evening_time="22:00",
    )
    fake_app.run_polling.assert_called_once_with(drop_pending_updates=True)


def test_read_system_prompt_returns_nonempty_string():
    prompt = read_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert "entrenador" in prompt
