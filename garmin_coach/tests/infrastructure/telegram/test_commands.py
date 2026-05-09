"""Tests for CommandHandlers: one test per command handler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from garmin_coach.infrastructure.telegram.handlers.commands import CommandHandlers
from garmin_coach.infrastructure.telegram.auth import Authorizer
from garmin_coach.infrastructure.telegram.formatter import MessageFormatter


ALLOWED_USER_ID = 42


def _make_handlers(**overrides):
    defaults = dict(
        coach_service=MagicMock(),
        briefing_service=MagicMock(),
        sync_service=MagicMock(),
        mfa_handler=MagicMock(),
        memory_repo=MagicMock(),
        sync_log_repo=MagicMock(),
        context_builder=MagicMock(),
        formatter=MessageFormatter(),
        authorizer=Authorizer(ALLOWED_USER_ID),
        garmin_client=MagicMock(),
    )
    defaults.update(overrides)
    return CommandHandlers(**defaults)


def _make_update(user_id: int = ALLOWED_USER_ID, args=None):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 100
    ctx = MagicMock()
    ctx.args = args or []
    return update, ctx


def run(coro):
    return asyncio.run(coro)


# ── cmd_start ─────────────────────────────────────────────────────────────────


def test_cmd_start_replies_to_authorized():
    h = _make_handlers()
    update, ctx = _make_update()
    run(h.cmd_start(update, ctx))
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "entrenador" in text.lower()


def test_cmd_start_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_start(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


# ── cmd_sync ──────────────────────────────────────────────────────────────────


def test_cmd_sync_calls_sync_service():
    summary = MagicMock()
    summary.activities = 5
    summary.sleep = 3
    summary.hrv = 3
    summary.body_battery = 3

    sync_mock = MagicMock()

    h = _make_handlers(sync_service=sync_mock)
    update, ctx = _make_update()
    msg_mock = AsyncMock()
    update.message.reply_text.return_value = msg_mock

    async def _run():
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=summary)
            await h.cmd_sync(update, ctx)

    run(_run())
    update.message.reply_text.assert_called()


def test_cmd_sync_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_sync(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


# ── cmd_status ────────────────────────────────────────────────────────────────


def test_cmd_status_shows_data_counts():
    ctx_builder = MagicMock()
    ctx_builder.build_raw.return_value = {
        "activities": [1, 2],
        "sleep": [1],
        "hrv": [],
        "body_battery": [1, 2, 3],
        "memory": [],
    }
    sync_log = MagicMock()
    sync_log.last_sync.return_value = "2026-05-01T08:00:00"

    h = _make_handlers(context_builder=ctx_builder, sync_log_repo=sync_log)
    update, ctx = _make_update()
    run(h.cmd_status(update, ctx))

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "2026-05-01" in text
    assert "2" in text  # activities count


def test_cmd_status_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_status(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


# ── cmd_briefing ──────────────────────────────────────────────────────────────


def test_cmd_briefing_calls_briefing_service():
    briefing_mock = MagicMock()
    briefing_mock.generate.return_value = "Tu briefing de hoy."
    h = _make_handlers(briefing_service=briefing_mock)
    update, ctx = _make_update()
    msg_mock = AsyncMock()
    update.message.reply_text.return_value = msg_mock

    async def _run():
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value="Tu briefing de hoy."
            )
            await h.cmd_briefing(update, ctx)

    run(_run())
    update.message.reply_text.assert_called()


def test_cmd_briefing_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_briefing(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


# ── cmd_reset ─────────────────────────────────────────────────────────────────


def test_cmd_reset_resets_coach_session():
    coach_mock = MagicMock()
    h = _make_handlers(coach_service=coach_mock)
    update, ctx = _make_update()
    run(h.cmd_reset(update, ctx))
    coach_mock.reset.assert_called_once_with(ALLOWED_USER_ID)
    update.message.reply_text.assert_called()


def test_cmd_reset_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_reset(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


# ── cmd_resetsession ──────────────────────────────────────────────────────────


def test_cmd_resetsession_calls_garmin_reset():
    garmin_mock = MagicMock()
    h = _make_handlers(garmin_client=garmin_mock)
    update, ctx = _make_update()
    run(h.cmd_resetsession(update, ctx))
    garmin_mock.reset.assert_called_once()
    update.message.reply_text.assert_called()


def test_cmd_resetsession_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_resetsession(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


# ── cmd_mfa ───────────────────────────────────────────────────────────────────


def test_cmd_mfa_provides_code():
    mfa_mock = MagicMock()
    h = _make_handlers(mfa_handler=mfa_mock)
    update, ctx = _make_update(args=["123456"])
    run(h.cmd_mfa(update, ctx))
    mfa_mock.provide_code.assert_called_once_with("123456")


def test_cmd_mfa_missing_code_replies_usage():
    h = _make_handlers()
    update, ctx = _make_update(args=[])
    run(h.cmd_mfa(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "/mfa" in text


def test_cmd_mfa_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_mfa(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()


# ── cmd_memoria ───────────────────────────────────────────────────────────────


def test_cmd_memoria_saves_note():
    memory_mock = MagicMock()
    h = _make_handlers(memory_repo=memory_mock)
    update, ctx = _make_update(args=["rodilla", "derecha", "molesta"])
    run(h.cmd_memoria(update, ctx))
    memory_mock.add.assert_called_once_with("rodilla derecha molesta")


def test_cmd_memoria_missing_note_replies_usage():
    h = _make_handlers()
    update, ctx = _make_update(args=[])
    run(h.cmd_memoria(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "/memoria" in text


def test_cmd_memoria_blocks_unauthorized():
    h = _make_handlers()
    update, ctx = _make_update(user_id=999)
    run(h.cmd_memoria(update, ctx))
    text = update.message.reply_text.call_args[0][0]
    assert "autorizado" in text.lower()
