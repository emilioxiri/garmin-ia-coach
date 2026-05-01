"""
bot.py
Bot de Telegram con conversación libre, comandos y memoria.
"""

import logging
import os
import re
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from garmin_coach.coach import CoachSession, generate_daily_briefing
from garmin_coach.garmin_sync import sync_all, provide_mfa_code, set_event_loop
from garmin_coach.db import get_last_sync, log_sync, save_memory, get_context_for_ai
import json

logger = logging.getLogger(__name__)


def format_for_telegram(text: str) -> str:
    """Convert LLM markdown output to Telegram legacy Markdown.

    LLMs emit **bold** and ## headers which Telegram does not render.
    Converts to Telegram-compatible *bold* and strips heading symbols.
    """
    text = text.replace("**", "*")
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return text


# Sesiones activas por usuario
_sessions: dict[int, CoachSession] = {}

ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))


def get_session(user_id: int) -> CoachSession:
    if user_id not in _sessions:
        _sessions[user_id] = CoachSession()
    return _sessions[user_id]


def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


# ── Comandos ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
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


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    import asyncio
    msg = await update.message.reply_text("🔄 Sincronizando datos de Garmin... puede tardar un momento.")
    try:
        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        days = int(os.getenv("DAYS_HISTORY", "30"))
        loop = asyncio.get_running_loop()
        set_event_loop(loop)
        summary = await loop.run_in_executor(None, sync_all, email, password, days)
        log_sync(summary)
        text = (
            f"✅ *Sync completado*\n"
            f"🏃 Actividades: {summary['activities']}\n"
            f"😴 Sueño: {summary['sleep']} días\n"
            f"💓 HRV: {summary['hrv']} días\n"
            f"🔋 Body Battery: {summary['body_battery']} días"
        )
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Error en sync: {str(e)}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    last_sync = get_last_sync()
    ctx = get_context_for_ai(days=7)
    text = (
        f"📊 *Estado de datos*\n"
        f"🕐 Último sync: {last_sync or 'Nunca'}\n"
        f"🏃 Actividades (7d): {len(ctx['activities'])}\n"
        f"😴 Registros de sueño (7d): {len(ctx['sleep'])}\n"
        f"💓 Registros HRV (7d): {len(ctx['hrv'])}\n"
        f"🔋 Body Battery (7d): {len(ctx['body_battery'])}\n"
        f"🧠 Notas de memoria: {len(ctx['memory'])}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    import asyncio
    from datetime import datetime
    hour = datetime.now().hour
    moment = "morning" if hour < 14 else "evening"
    msg = await update.message.reply_text("🤔 Generando tu briefing personalizado...")
    loop = asyncio.get_event_loop()
    briefing = await loop.run_in_executor(None, generate_daily_briefing, moment)
    formatted = format_for_telegram(briefing)
    try:
        await msg.edit_text(formatted, parse_mode="Markdown")
    except Exception:
        await msg.edit_text(briefing)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    user_id = update.effective_user.id
    if user_id in _sessions:
        _sessions[user_id].reset()
    await update.message.reply_text("🔄 Conversación reiniciada. ¡Empezamos de nuevo!")


async def cmd_resetsession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    from garmin_coach.garmin_sync import SESSION_PATH
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()
        await update.message.reply_text("🗑 Sesión de Garmin eliminada. El próximo /sync hará login completo.")
    else:
        await update.message.reply_text("ℹ️ No había sesión guardada.")


async def cmd_mfa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    code = " ".join(context.args).strip()
    if not code:
        await update.message.reply_text("Uso: /mfa <código>")
        return
    provide_mfa_code(code)
    await update.message.reply_text("✅ Código MFA enviado, continuando login de Garmin...")


async def cmd_memoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    note = " ".join(context.args)
    if not note:
        await update.message.reply_text(
            "✍️ Uso: /memoria <texto a recordar>\nEjemplo: /memoria Tengo molestia en rodilla derecha"
        )
        return
    save_memory(note)
    await update.message.reply_text(f"🧠 Guardado en memoria: _{note}_", parse_mode="Markdown")


# ── Mensajes de texto libre ────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    user_message = update.message.text
    session = get_session(update.effective_user.id)

    # Indicador de escritura
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    response = session.chat(user_message)
    formatted = format_for_telegram(response)

    # Telegram tiene límite de 4096 chars por mensaje
    if len(formatted) > 4000:
        parts = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
        for part in parts:
            try:
                await update.message.reply_text(part, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(part)
    else:
        try:
            await update.message.reply_text(formatted, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(response)


# ── Setup del bot ──────────────────────────────────────────────────────────────

async def _on_startup(app: Application) -> None:
    import asyncio
    set_event_loop(asyncio.get_event_loop())


def build_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).concurrent_updates(True).post_init(_on_startup).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("resetsession", cmd_resetsession))
    app.add_handler(CommandHandler("memoria", cmd_memoria))
    app.add_handler(CommandHandler("mfa", cmd_mfa))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


async def send_scheduled_message(app: Application, text: str):
    """Envía un mensaje programado al usuario autorizado."""
    try:
        await app.bot.send_message(chat_id=ALLOWED_USER_ID, text=text)
    except Exception as e:
        logger.error(f"Error enviando mensaje programado: {e}")
