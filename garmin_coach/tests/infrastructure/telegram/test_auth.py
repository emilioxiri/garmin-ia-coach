"""Tests for Authorizer: is_authorized and require_auth decorator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from garmin_coach.infrastructure.telegram.auth import Authorizer


def _make_update(user_id: int | None):
    update = MagicMock()
    if user_id is None:
        update.effective_user = None
    else:
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


# ── is_authorized ─────────────────────────────────────────────────────────────


def test_is_authorized_returns_true_for_allowed_user():
    auth = Authorizer(allowed_user_id=42)
    update = _make_update(42)
    assert auth.is_authorized(update) is True


def test_is_authorized_returns_false_for_different_user():
    auth = Authorizer(allowed_user_id=42)
    update = _make_update(99)
    assert auth.is_authorized(update) is False


def test_is_authorized_returns_false_when_no_user():
    auth = Authorizer(allowed_user_id=42)
    update = _make_update(None)
    assert auth.is_authorized(update) is False


# ── require_auth decorator ────────────────────────────────────────────────────


def test_require_auth_calls_handler_when_authorized():
    auth = Authorizer(allowed_user_id=42)
    called = []

    @auth.require_auth
    async def handler(update, context):
        called.append(True)

    update = _make_update(42)
    asyncio.run(handler(update, MagicMock()))
    assert called == [True]


def test_require_auth_blocks_unauthorized_user():
    auth = Authorizer(allowed_user_id=42)
    called = []

    @auth.require_auth
    async def handler(update, context):
        called.append(True)

    update = _make_update(99)
    asyncio.run(handler(update, MagicMock()))
    assert called == []


def test_require_auth_replies_no_autorizado():
    auth = Authorizer(allowed_user_id=42)

    @auth.require_auth
    async def handler(update, context):
        pass

    update = _make_update(99)
    asyncio.run(handler(update, MagicMock()))
    update.message.reply_text.assert_called_once_with("No autorizado.")


def test_require_auth_preserves_handler_name():
    auth = Authorizer(allowed_user_id=42)

    @auth.require_auth
    async def my_command(update, context):
        pass

    assert my_command.__name__ == "my_command"
