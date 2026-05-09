"""Tests for TelegramBotApp."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from garmin_coach.app.config import Settings
from garmin_coach.infrastructure.telegram.bot_app import TelegramBotApp
from garmin_coach.infrastructure.telegram.formatter import MessageFormatter


def _make_settings(**overrides):
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


def _make_bot_app(**overrides):
    defaults = dict(
        settings=_make_settings(),
        command_handlers=MagicMock(),
        chat_handler=MagicMock(),
        mfa_handler=MagicMock(),
        formatter=MessageFormatter(),
    )
    defaults.update(overrides)
    return TelegramBotApp(**defaults)


def run(coro):
    return asyncio.run(coro)


# ── build ─────────────────────────────────────────────────────────────────────


def test_build_registers_all_handlers():
    bot_app = _make_bot_app()
    fake_application = MagicMock()
    fake_builder = MagicMock()
    fake_builder.token.return_value = fake_builder
    fake_builder.concurrent_updates.return_value = fake_builder
    fake_builder.post_init.return_value = fake_builder
    fake_builder.build.return_value = fake_application

    with patch(
        "garmin_coach.infrastructure.telegram.bot_app.Application"
    ) as mock_app_class:
        mock_app_class.builder.return_value = fake_builder
        result = bot_app.build()

    assert result is fake_application
    # 8 CommandHandlers + 1 MessageHandler = 9 handlers
    assert fake_application.add_handler.call_count >= 9


# ── _on_startup ───────────────────────────────────────────────────────────────


def test_on_startup_captures_loop_and_sets_notifier():
    mfa_mock = MagicMock()
    bot_app = _make_bot_app(mfa_handler=mfa_mock)

    fake_app = MagicMock()
    fake_app.bot = AsyncMock()

    run(bot_app._on_startup(fake_app))

    assert bot_app.loop is not None
    mfa_mock.set_notifier.assert_called_once()


def test_on_startup_notifier_callable_is_set():
    mfa_mock = MagicMock()
    bot_app = _make_bot_app(mfa_handler=mfa_mock)

    fake_app = MagicMock()
    fake_app.bot = AsyncMock()

    run(bot_app._on_startup(fake_app))

    notifier = mfa_mock.set_notifier.call_args[0][0]
    assert callable(notifier)


# ── send_to_user ──────────────────────────────────────────────────────────────


def test_send_to_user_sends_formatted_message():
    bot_app = _make_bot_app()
    fake_app = MagicMock()
    fake_app.bot = AsyncMock()
    fake_app.bot.send_message = AsyncMock()
    bot_app._app = fake_app

    run(bot_app.send_to_user("**Briefing**: listo"))

    fake_app.bot.send_message.assert_called_once()
    call_kwargs = fake_app.bot.send_message.call_args[1]
    assert call_kwargs["chat_id"] == 42
    assert "<b>Briefing</b>" in call_kwargs["text"]
    assert call_kwargs["parse_mode"] == "HTML"


def test_send_to_user_skips_when_no_app():
    bot_app = _make_bot_app()
    bot_app._app = None
    # Should not raise
    run(bot_app.send_to_user("hello"))


def test_send_to_user_chunks_long_message():
    bot_app = _make_bot_app()
    fake_app = MagicMock()
    fake_app.bot = AsyncMock()
    fake_app.bot.send_message = AsyncMock()
    bot_app._app = fake_app

    long_text = "a\n" * 2500
    run(bot_app.send_to_user(long_text))

    assert fake_app.bot.send_message.await_count > 1


def test_send_to_user_fallback_on_parse_error():
    bot_app = _make_bot_app()
    fake_app = MagicMock()
    fake_app.bot = AsyncMock()

    call_count = []

    async def send_message_side_effect(chat_id, text, **kwargs):
        call_count.append(kwargs.get("parse_mode"))
        if kwargs.get("parse_mode") == "HTML":
            raise Exception("parse error")

    fake_app.bot.send_message.side_effect = send_message_side_effect
    bot_app._app = fake_app

    run(bot_app.send_to_user("Test message"))

    # Called twice: once with HTML, once without
    assert len(call_count) == 2
    assert "HTML" in call_count
