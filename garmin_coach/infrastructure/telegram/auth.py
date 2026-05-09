"""
infrastructure/telegram/auth.py
Telegram user authorization check + decorator.
"""

from __future__ import annotations

import logging
from typing import Callable

from telegram import Update

logger = logging.getLogger(__name__)


class Authorizer:
    """Checks whether a Telegram update comes from the allowed user."""

    def __init__(self, allowed_user_id: int) -> None:
        self._allowed_user_id = allowed_user_id

    def is_authorized(self, update: Update) -> bool:
        if update.effective_user is None:
            return False
        return update.effective_user.id == self._allowed_user_id

    def require_auth(self, handler: Callable) -> Callable:
        """Decorator: replies 'No autorizado.' and returns early if not authorized."""

        async def wrapper(update: Update, context, *args, **kwargs):
            if not self.is_authorized(update):
                logger.warning(
                    "Unauthorized access attempt from user_id=%s",
                    update.effective_user.id if update.effective_user else "unknown",
                )
                if update.message:
                    await update.message.reply_text("No autorizado.")
                return

            return await handler(update, context, *args, **kwargs)

        wrapper.__name__ = handler.__name__
        wrapper.__doc__ = handler.__doc__
        return wrapper
