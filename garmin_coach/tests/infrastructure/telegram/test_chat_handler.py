"""Tests for ChatMessageHandler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from garmin_coach.infrastructure.telegram.handlers.chat import ChatMessageHandler
from garmin_coach.infrastructure.telegram.auth import Authorizer
from garmin_coach.infrastructure.telegram.formatter import MessageFormatter

ALLOWED_USER_ID = 42


def _make_handler(**overrides):
    defaults = dict(
        coach_service=MagicMock(),
        formatter=MessageFormatter(),
        authorizer=Authorizer(ALLOWED_USER_ID),
    )
    defaults.update(overrides)
    return ChatMessageHandler(**defaults)


def _make_update(user_id: int = ALLOWED_USER_ID, text: str = "hola"):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 100
    ctx = MagicMock()
    ctx.bot = AsyncMock()
    ctx.bot.send_chat_action = AsyncMock()
    return update, ctx


def run(coro):
    return asyncio.run(coro)


# ── handle ────────────────────────────────────────────────────────────────────


def test_handle_calls_coach_service():
    coach_mock = MagicMock()
    coach_mock.chat.return_value = "Entrena suave."
    h = _make_handler(coach_service=coach_mock)
    update, ctx = _make_update(text="¿cómo estoy?")
    run(h.handle(update, ctx))
    coach_mock.chat.assert_called_once_with(ALLOWED_USER_ID, "¿cómo estoy?")


def test_handle_sends_formatted_reply():
    coach_mock = MagicMock()
    coach_mock.chat.return_value = "**VO2max**: 52"
    h = _make_handler(coach_service=coach_mock)
    update, ctx = _make_update()
    run(h.handle(update, ctx))
    update.message.reply_text.assert_called()
    call_kwargs = update.message.reply_text.call_args
    text = call_kwargs[0][0]
    assert "<b>VO2max</b>" in text


def test_handle_blocks_unauthorized():
    coach_mock = MagicMock()
    h = _make_handler(coach_service=coach_mock)
    update, ctx = _make_update(user_id=999)
    run(h.handle(update, ctx))
    coach_mock.chat.assert_not_called()
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


def test_handle_sends_typing_action():
    coach_mock = MagicMock()
    coach_mock.chat.return_value = "ok"
    h = _make_handler(coach_service=coach_mock)
    update, ctx = _make_update()
    run(h.handle(update, ctx))
    ctx.bot.send_chat_action.assert_called_once()


def test_handle_chunks_long_response():
    coach_mock = MagicMock()
    coach_mock.chat.return_value = "x" * 5000
    h = _make_handler(coach_service=coach_mock)
    update, ctx = _make_update()
    run(h.handle(update, ctx))
    assert update.message.reply_text.await_count > 1


def test_handle_fallback_when_parse_fails():
    coach_mock = MagicMock()
    coach_mock.chat.return_value = "Mensaje normal"
    h = _make_handler(coach_service=coach_mock)
    update, ctx = _make_update()

    call_count = []

    async def reply_side_effect(text, **kwargs):
        call_count.append(kwargs.get("parse_mode"))
        if kwargs.get("parse_mode") == "HTML":
            raise Exception("parse error")

    update.message.reply_text.side_effect = reply_side_effect
    run(h.handle(update, ctx))
    # Called twice: HTML attempt + fallback
    assert len(call_count) == 2
    assert "HTML" in call_count
