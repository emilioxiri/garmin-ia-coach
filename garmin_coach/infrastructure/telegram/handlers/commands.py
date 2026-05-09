"""
infrastructure/telegram/handlers/commands.py
CommandHandlers class: one method per Telegram bot command.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from garmin_coach.infrastructure.garmin.mfa_handler import MFAHandler
    from garmin_coach.infrastructure.telegram.auth import Authorizer
    from garmin_coach.infrastructure.telegram.formatter import MessageFormatter
    from garmin_coach.services.briefing_service import BriefingService
    from garmin_coach.services.coach_service import CoachService
    from garmin_coach.services.context_builder import ContextBuilder
    from garmin_coach.services.sync_service import SyncService
    from garmin_coach.infrastructure.db.memory_repository import MemoryRepository
    from garmin_coach.infrastructure.db.sync_log_repository import SyncLogRepository
    from garmin_coach.infrastructure.garmin.client import GarminClient

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handles all /command messages from Telegram."""

    def __init__(
        self,
        coach_service: "CoachService",
        briefing_service: "BriefingService",
        sync_service: "SyncService",
        mfa_handler: "MFAHandler",
        memory_repo: "MemoryRepository",
        sync_log_repo: "SyncLogRepository",
        context_builder: "ContextBuilder",
        formatter: "MessageFormatter",
        authorizer: "Authorizer",
        garmin_client: "GarminClient",
    ) -> None:
        self._coach = coach_service
        self._briefing = briefing_service
        self._sync = sync_service
        self._mfa = mfa_handler
        self._memory_repo = memory_repo
        self._sync_log_repo = sync_log_repo
        self._context_builder = context_builder
        self._formatter = formatter
        self._auth = authorizer
        self._garmin_client = garmin_client

    async def cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        await update.message.reply_text(
            "👋 ¡Hola! Soy tu entrenador personal con acceso a tus datos de Garmin.\n\n"
            "📋 *Comandos disponibles:*\n"
            "/sync — Sincronizar datos de Garmin ahora\n"
            "/status — Ver estado de los datos\n"
            "/briefing — Briefing del día\n"
            "/reset — Reiniciar conversación\n"
            "/memoria — Añadir nota de memoria\n\n"
            "O simplemente escríbeme y te respondo como tu coach 🏃",
            parse_mode="Markdown",
        )

    async def cmd_sync(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        msg = await update.message.reply_text(
            "🔄 Sincronizando datos de Garmin... puede tardar un momento."
        )
        try:
            loop = asyncio.get_running_loop()
            summary = await loop.run_in_executor(None, self._sync.run)
            text = (
                f"✅ *Sync completado*\n"
                f"🏃 Actividades: {summary.activities}\n"
                f"😴 Sueño: {summary.sleep} días\n"
                f"💓 HRV: {summary.hrv} días\n"
                f"🔋 Body Battery: {summary.body_battery} días"
            )
            await msg.edit_text(text, parse_mode="Markdown")
        except Exception as exc:
            logger.error("Error en sync: %s", exc)
            await msg.edit_text(f"❌ Error en sync: {exc}")

    async def cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        try:
            last_sync = self._sync_log_repo.last_sync()
            raw = self._context_builder.build_raw(days=7)
            text = (
                f"📊 *Estado de datos*\n"
                f"🕐 Último sync: {last_sync or 'Nunca'}\n"
                f"🏃 Actividades (7d): {len(raw['activities'])}\n"
                f"😴 Registros de sueño (7d): {len(raw['sleep'])}\n"
                f"💓 Registros HRV (7d): {len(raw['hrv'])}\n"
                f"🔋 Body Battery (7d): {len(raw['body_battery'])}\n"
                f"🧠 Notas de memoria: {len(raw['memory'])}"
            )
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception as exc:
            logger.error("Error en status: %s", exc)
            await update.message.reply_text(f"❌ Error: {exc}")

    async def cmd_briefing(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        hour = datetime.now().hour
        moment = "morning" if hour < 14 else "evening"
        msg = await update.message.reply_text(
            "🤔 Generando tu briefing personalizado..."
        )
        try:
            loop = asyncio.get_running_loop()
            briefing = await loop.run_in_executor(None, self._briefing.generate, moment)
            formatted = self._formatter.to_html(briefing)
            chunks = self._formatter.chunk(formatted)
            try:
                await msg.edit_text(chunks[0], parse_mode="HTML")
            except Exception:
                await msg.edit_text(chunks[0])
            for chunk in chunks[1:]:
                try:
                    await update.message.reply_text(chunk, parse_mode="HTML")
                except Exception:
                    await update.message.reply_text(chunk)
        except Exception as exc:
            logger.error("Error en briefing: %s", exc)
            await msg.edit_text(f"❌ Error generando briefing: {exc}")

    async def cmd_reset(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        user_id = update.effective_user.id
        self._coach.reset(user_id)
        await update.message.reply_text(
            "🔄 Conversación reiniciada. ¡Empezamos de nuevo!"
        )

    async def cmd_resetsession(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        try:
            self._garmin_client.reset()
            await update.message.reply_text(
                "🗑 Sesión de Garmin eliminada. El próximo /sync hará login completo."
            )
        except Exception as exc:
            logger.error("Error en resetsession: %s", exc)
            await update.message.reply_text(f"❌ Error: {exc}")

    async def cmd_mfa(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        code = " ".join(context.args or []).strip()
        if not code:
            await update.message.reply_text("Uso: /mfa <código>")
            return
        self._mfa.provide_code(code)
        await update.message.reply_text(
            "✅ Código MFA enviado, continuando login de Garmin..."
        )

    async def cmd_memoria(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        note = " ".join(context.args or [])
        if not note:
            await update.message.reply_text(
                "✍️ Uso: /memoria <texto a recordar>\n"
                "Ejemplo: /memoria Tengo molestia en rodilla derecha"
            )
            return
        self._memory_repo.add(note)
        await update.message.reply_text(
            f"🧠 Guardado en memoria: _{note}_", parse_mode="Markdown"
        )
