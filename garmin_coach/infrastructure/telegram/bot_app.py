"""
infrastructure/telegram/bot_app.py
TelegramBotApp: builds the Application, registers handlers, manages lifecycle.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from garmin_coach.app.logging_setup import get_logger

if TYPE_CHECKING:
    from garmin_coach.app.config import Settings
    from garmin_coach.infrastructure.garmin.mfa_handler import MFAHandler
    from garmin_coach.infrastructure.telegram.formatter import MessageFormatter
    from garmin_coach.infrastructure.telegram.handlers.chat import ChatMessageHandler
    from garmin_coach.infrastructure.telegram.handlers.commands import CommandHandlers

logger = get_logger(__name__)


class TelegramBotApp:
    """Wraps python-telegram-bot Application with injectable handlers."""

    def __init__(
        self,
        settings: "Settings",
        command_handlers: "CommandHandlers",
        chat_handler: "ChatMessageHandler",
        mfa_handler: "MFAHandler",
        formatter: "MessageFormatter",
    ) -> None:
        self._settings = settings
        self._commands = command_handlers
        self._chat = chat_handler
        self._mfa = mfa_handler
        self._formatter = formatter
        self._app: Application | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    def build(self) -> Application:
        app = (
            Application.builder()
            .token(self._settings.telegram_bot_token)
            .concurrent_updates(True)
            .post_init(self._on_startup)
            .build()
        )

        app.add_handler(CommandHandler("start", self._commands.cmd_start))
        app.add_handler(CommandHandler("sync", self._commands.cmd_sync))
        app.add_handler(CommandHandler("status", self._commands.cmd_status))
        app.add_handler(CommandHandler("briefing", self._commands.cmd_briefing))
        app.add_handler(CommandHandler("reset", self._commands.cmd_reset))
        app.add_handler(CommandHandler("resetsession", self._commands.cmd_resetsession))
        app.add_handler(CommandHandler("mfa", self._commands.cmd_mfa))
        app.add_handler(CommandHandler("memoria", self._commands.cmd_memoria))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._chat.handle)
        )

        self._app = app
        return app

    async def _on_startup(self, app: Application) -> None:
        self.loop = asyncio.get_running_loop()
        allowed_user_id = self._settings.telegram_allowed_user_id

        def _notifier(message: str) -> None:
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    app.bot.send_message(chat_id=allowed_user_id, text=message),
                    self.loop,
                )

        self._mfa.set_notifier(_notifier)
        logger.info("TelegramBotApp started, asyncio loop captured")

    def run(self) -> None:
        app = self.build()
        app.run_polling(drop_pending_updates=True)

    async def send_to_user(self, text: str) -> None:
        """Send a message to the configured allowed user (for scheduled messages)."""
        if self._app is None:
            logger.warning("event=send_to_user_skipped reason=app_not_built")
            return
        formatted = self._formatter.to_html(text)
        chunks = self._formatter.chunk(formatted)
        allowed_user_id = self._settings.telegram_allowed_user_id
        logger.info(
            "event=send_to_user chat_id=%d chunks=%d total_len=%d",
            allowed_user_id,
            len(chunks),
            len(formatted),
        )
        for chunk in chunks:
            try:
                await self._app.bot.send_message(
                    chat_id=allowed_user_id, text=chunk, parse_mode="HTML"
                )
            except Exception as exc:
                logger.warning(
                    "event=send_to_user_html_failed reason=parse_mode chat_id=%d: %s",
                    allowed_user_id,
                    exc,
                )
                try:
                    await self._app.bot.send_message(
                        chat_id=allowed_user_id, text=chunk
                    )
                except Exception:
                    logger.error(
                        "event=send_to_user_failed chat_id=%d",
                        allowed_user_id,
                        exc_info=True,
                    )
