"""
garmin_sync.py — TEMPORARY SHIM (Phase 4).
Exposes legacy API used by bot.py and legacy_bridge.py.
Will be deleted in Phase 5 when TelegramBotApp wires MFAHandler directly.

Real implementation lives in:
  infrastructure/garmin/client.py       (GarminClient)
  infrastructure/garmin/mfa_handler.py  (MFAHandler)
  services/sync_service.py              (SyncService)
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

# ── module-level compat refs (Phase 5 removes these) ──────────────────────────
_bot_app = None
_bot_loop = None

# ── lazy container ────────────────────────────────────────────────────────────
_container = None


def _get_container():
    global _container
    if _container is None:
        from garmin_coach.app.config import load_settings
        from garmin_coach.app.container import Container

        _container = Container(load_settings())
    return _container


# ── legacy setters called by bot.py / legacy_bridge.py ───────────────────────


def set_bot_app(app) -> None:
    global _bot_app
    _bot_app = app

    def _notifier(message: str) -> None:
        if _bot_app and _bot_loop and _bot_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _bot_app.bot.send_message(
                    chat_id=int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0")),
                    text=message,
                ),
                _bot_loop,
            )

    _get_container().mfa_handler.set_notifier(_notifier)


def set_event_loop(loop) -> None:
    global _bot_loop
    _bot_loop = loop


def provide_mfa_code(code: str) -> None:
    _get_container().mfa_handler.provide_code(code)


# ── legacy sync entry-point ───────────────────────────────────────────────────


def sync_all(email: str, password: str, days: int = 30) -> dict:
    """Delegates to SyncService.run(). email/password ignored (read from Settings)."""
    summary = _get_container().sync_service.run()
    return summary.as_dict()


# ── legacy auth helper (used by old test_garmin_sync.py) ─────────────────────


def get_garmin_client(email: str, password: str):
    """Returns an authenticated Garmin instance via GarminClient."""
    return _get_container().garmin_client.authenticate()
