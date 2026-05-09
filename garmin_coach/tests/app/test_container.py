"""Tests for garmin_coach.app.container and garmin_coach.prompts."""

from pathlib import Path
from unittest.mock import MagicMock

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


def test_container_has_all_phase5_attrs():
    settings = _make_settings()
    container = Container(settings)
    # Repos
    assert container.repositories is not None
    # LLM + services
    assert container.llm_client is not None
    assert container.tool_registry is not None
    assert container.context_builder is not None
    assert container.coach_service is not None
    assert container.briefing_service is not None
    # Garmin
    assert container.mfa_handler is not None
    assert container.garmin_client is not None
    assert container.sync_service is not None
    # Telegram
    assert container.formatter is not None
    assert container.authorizer is not None
    assert container.command_handlers is not None
    assert container.chat_handler is not None
    assert container.bot_app is not None
    # Scheduler
    assert container.scheduler is not None


def test_container_run_starts_scheduler_and_calls_bot():
    settings = _make_settings()
    container = Container(settings)

    scheduler_mock = MagicMock()
    bot_mock = MagicMock()
    container.scheduler = scheduler_mock
    container.bot_app = bot_mock

    container.run()

    scheduler_mock.start.assert_called_once()
    bot_mock.run.assert_called_once()
    scheduler_mock.stop.assert_called_once()


def test_container_run_stops_scheduler_on_exception():
    settings = _make_settings()
    container = Container(settings)

    scheduler_mock = MagicMock()
    bot_mock = MagicMock()
    bot_mock.run.side_effect = RuntimeError("bot crashed")
    container.scheduler = scheduler_mock
    container.bot_app = bot_mock

    try:
        container.run()
    except RuntimeError:
        pass

    scheduler_mock.stop.assert_called_once()


def test_read_system_prompt_returns_nonempty_string():
    prompt = read_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert "entrenador" in prompt
