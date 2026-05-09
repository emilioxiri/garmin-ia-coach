"""
infrastructure/telegram/handlers/chat.py
ChatMessageHandler: routes free-text messages to CoachService.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from garmin_coach.infrastructure.telegram.auth import Authorizer
    from garmin_coach.infrastructure.telegram.formatter import MessageFormatter
    from garmin_coach.services.coach_service import CoachService

logger = logging.getLogger(__name__)


class ChatMessageHandler:
    """Handles free-text (non-command) Telegram messages."""

    def __init__(
        self,
        coach_service: "CoachService",
        formatter: "MessageFormatter",
        authorizer: "Authorizer",
    ) -> None:
        self._coach = coach_service
        self._formatter = formatter
        self._auth = authorizer

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return

        user_id = update.effective_user.id
        user_message = update.message.text

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )

        response = self._coach.chat(user_id, user_message)
        formatted = self._formatter.to_html(response)
        chunks = self._formatter.chunk(formatted)

        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(chunk)
