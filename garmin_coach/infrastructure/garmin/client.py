"""
infrastructure/garmin/client.py
Garmin Connect authentication with session persistence and pluggable MFA.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from garminconnect import Garmin

from garmin_coach.infrastructure.garmin.mfa_handler import MFAHandler

if TYPE_CHECKING:
    from garmin_coach.app.config import Settings

logger = logging.getLogger(__name__)


class GarminClient:
    """Wraps garminconnect.Garmin with session persistence and MFA support.

    Call authenticate() to get an authenticated Garmin instance.
    The result is cached; call reset() to force a new login.
    """

    def __init__(self, settings: Settings, mfa_handler: MFAHandler) -> None:
        self._settings = settings
        self._mfa = mfa_handler
        self._client: Garmin | None = None

    def authenticate(self) -> Garmin:
        if self._client is not None:
            return self._client

        self._mfa.clear()

        def _prompt_mfa() -> str:
            self._mfa.notify_user(
                "Garmin necesita verificación MFA.\n"
                "Revisa tu email o app de autenticación y responde con:\n"
                "/mfa <código>"
            )
            logger.info("Waiting for MFA code (timeout: %ds)...", self._mfa._timeout)
            return self._mfa.wait_for_code()

        client = Garmin(
            self._settings.garmin_email,
            self._settings.garmin_password,
            prompt_mfa=_prompt_mfa,
        )

        session_path = self._settings.session_path
        if session_path.exists():
            try:
                client.login(tokenstore=str(session_path))
                logger.info("Garmin session reused from disk")
                self._client = client
                return client
            except Exception as exc:
                logger.warning("Session expired or invalid, doing full login: %s", exc)
                session_path.unlink(missing_ok=True)

        try:
            client.login()
            session_path.parent.mkdir(parents=True, exist_ok=True)
            client.client.dump(str(session_path))
            logger.info("Full Garmin login completed, session persisted")
        except Exception as exc:
            raise RuntimeError(
                f"Could not authenticate with Garmin Connect: {exc}"
            ) from exc

        self._client = client
        return client

    def reset(self) -> None:
        """Invalidate the cached client and remove the persisted session file."""
        self._client = None
        self._settings.session_path.unlink(missing_ok=True)
        logger.info("Garmin session reset")
