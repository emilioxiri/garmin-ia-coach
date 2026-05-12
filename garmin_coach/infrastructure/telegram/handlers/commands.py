"""
infrastructure/telegram/handlers/commands.py
CommandHandlers class: one method per Telegram bot command.
"""

from __future__ import annotations

import asyncio
import html
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from garmin_coach.app.logging_setup import get_logger

if TYPE_CHECKING:
    from garmin_coach.infrastructure.db.memory_repository import MemoryRepository
    from garmin_coach.infrastructure.db.sync_log_repository import SyncLogRepository
    from garmin_coach.infrastructure.garmin.client import GarminClient
    from garmin_coach.infrastructure.garmin.mfa_handler import MFAHandler
    from garmin_coach.infrastructure.telegram.auth import Authorizer
    from garmin_coach.infrastructure.telegram.formatter import MessageFormatter
    from garmin_coach.services.briefing_service import BriefingService
    from garmin_coach.services.coach_service import CoachService
    from garmin_coach.services.context_builder import ContextBuilder
    from garmin_coach.services.sync_service import SyncService

logger = get_logger(__name__)


def _tail_file(path: Path, n: int) -> str:
    """Return last n lines of a text file without loading it all into memory."""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return "\n".join(deque(fh, maxlen=n))


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
        log_path: Path,
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
        self._log_path = log_path

    async def cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/start user=%d", user_id)
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
            "/memoria — Añadir nota de memoria\n"
            "/logs [N] — Ver últimas N líneas de log (máx 500)\n\n"
            "O simplemente escríbeme y te respondo como tu coach 🏃",
            parse_mode="Markdown",
        )

    async def cmd_sync(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/sync user=%d", user_id)
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        msg = await update.message.reply_text(
            "🔄 Sincronizando datos de Garmin... puede tardar un momento."
        )
        t0 = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            summary = await loop.run_in_executor(None, self._sync.run)
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "event=cmd_end command=/sync user=%d duration_ms=%d activities=%d",
                user_id,
                duration_ms,
                summary.activities,
            )
            text = (
                f"✅ *Sync completado*\n"
                f"🏃 Actividades: {summary.activities}\n"
                f"😴 Sueño: {summary.sleep} días\n"
                f"💓 HRV: {summary.hrv} días\n"
                f"🔋 Body Battery: {summary.body_battery} días"
            )
            await msg.edit_text(text, parse_mode="Markdown")
        except Exception as exc:
            logger.error(
                "event=cmd_failed command=/sync user=%d", user_id, exc_info=True
            )
            await msg.edit_text(f"❌ Error en sync: {exc}")

    async def cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/status user=%d", user_id)
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
            logger.info("event=cmd_end command=/status user=%d", user_id)
        except Exception as exc:
            logger.error(
                "event=cmd_failed command=/status user=%d", user_id, exc_info=True
            )
            await update.message.reply_text(f"❌ Error: {exc}")

    async def cmd_briefing(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/briefing user=%d", user_id)
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        hour = datetime.now().hour
        moment = "morning" if hour < 14 else "evening"
        msg = await update.message.reply_text(
            "🤔 Generando tu briefing personalizado..."
        )
        t0 = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            briefing = await loop.run_in_executor(None, self._briefing.generate, moment)
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "event=cmd_end command=/briefing user=%d moment=%s duration_ms=%d",
                user_id,
                moment,
                duration_ms,
            )
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
            logger.error(
                "event=cmd_failed command=/briefing user=%d", user_id, exc_info=True
            )
            await msg.edit_text(f"❌ Error generando briefing: {exc}")

    async def cmd_reset(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/reset user=%d", user_id)
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        self._coach.reset(user_id)
        logger.info("event=cmd_end command=/reset user=%d", user_id)
        await update.message.reply_text(
            "🔄 Conversación reiniciada. ¡Empezamos de nuevo!"
        )

    async def cmd_resetsession(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/resetsession user=%d", user_id)
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        try:
            self._garmin_client.reset()
            logger.info("event=cmd_end command=/resetsession user=%d", user_id)
            await update.message.reply_text(
                "🗑 Sesión de Garmin eliminada. El próximo /sync hará login completo."
            )
        except Exception as exc:
            logger.error(
                "event=cmd_failed command=/resetsession user=%d", user_id, exc_info=True
            )
            await update.message.reply_text(f"❌ Error: {exc}")

    async def cmd_mfa(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/mfa user=%d", user_id)
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return
        code = " ".join(context.args or []).strip()
        if not code:
            await update.message.reply_text("Uso: /mfa <código>")
            return
        self._mfa.provide_code(code)
        logger.info("event=cmd_end command=/mfa user=%d", user_id)
        await update.message.reply_text(
            "✅ Código MFA enviado, continuando login de Garmin..."
        )

    async def cmd_logs(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/logs user=%d", user_id)
        if not self._auth.is_authorized(update):
            await update.message.reply_text("No autorizado.")
            return

        raw_arg = (context.args or ["50"])[0]
        try:
            n_lines = max(1, min(int(raw_arg), 500))
        except ValueError:
            await update.message.reply_text("Uso: /logs [número de líneas] (máx 500)")
            return

        if not self._log_path.exists():
            await update.message.reply_text(
                f"⚠️ Archivo de log no encontrado: {self._log_path}"
            )
            return

        msg = await update.message.reply_text(
            f"📋 Obteniendo últimas {n_lines} líneas de log..."
        )
        loop = asyncio.get_running_loop()
        try:
            output = await loop.run_in_executor(
                None, _tail_file, self._log_path, n_lines
            )
            logger.info(
                "event=cmd_end command=/logs user=%d lines=%d", user_id, n_lines
            )
        except Exception as exc:
            logger.error(
                "event=cmd_failed command=/logs user=%d", user_id, exc_info=True
            )
            await msg.edit_text(f"❌ Error leyendo logs: {exc}")
            return

        if not output.strip():
            await msg.edit_text("⚠️ El archivo de log está vacío.")
            return

        # Chunk raw escaped text first, then wrap each chunk in <pre>.
        # This ensures Telegram always receives valid, self-contained HTML.
        escaped = html.escape(output)
        raw_chunks = self._formatter.chunk(escaped, max_len=3900)
        header = f"<b>Logs (últimas {n_lines} líneas):</b>\n"
        for i, raw_chunk in enumerate(raw_chunks):
            text = (header if i == 0 else "") + f"<pre>{raw_chunk}</pre>"
            try:
                if i == 0:
                    await msg.edit_text(text, parse_mode="HTML")
                else:
                    await update.message.reply_text(text, parse_mode="HTML")
            except Exception:
                if i == 0:
                    await msg.edit_text(text)
                else:
                    await update.message.reply_text(text)

    async def cmd_memoria(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        logger.info("event=cmd_start command=/memoria user=%d", user_id)
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
        logger.info(
            "event=cmd_end command=/memoria user=%d note_len=%d", user_id, len(note)
        )
        await update.message.reply_text(
            f"🧠 Guardado en memoria: _{note}_", parse_mode="Markdown"
        )
