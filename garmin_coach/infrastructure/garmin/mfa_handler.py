"""
infrastructure/garmin/mfa_handler.py
Encapsulates MFA flow: user notification + blocking wait for the code.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)


class MFAHandler:
    """Thread-safe MFA handler.

    The notifier callable is injected via set_notifier() and is called when
    Garmin requests a verification code.  If no notifier is registered the
    notification is silently skipped (useful in tests).
    """

    def __init__(self, timeout_seconds: int = 300) -> None:
        self._event = threading.Event()
        self._code: str | None = None
        self._timeout = timeout_seconds
        self._notifier: Callable[[str], None] | None = None

    def set_notifier(self, notifier: Callable[[str], None]) -> None:
        self._notifier = notifier

    def notify_user(self, message: str) -> None:
        if self._notifier is not None:
            try:
                self._notifier(message)
            except Exception:
                logger.exception("MFA notifier raised an exception")

    def provide_code(self, code: str) -> None:
        self._code = code
        self._event.set()

    def wait_for_code(self) -> str:
        """Block until a code is provided or the timeout expires.

        Clears internal state after consuming the code.
        Raises TimeoutError if the timeout elapses before a code arrives.
        """
        got_code = self._event.wait(timeout=self._timeout)
        code = self._code
        self.clear()
        if not got_code or code is None:
            raise TimeoutError(
                f"MFA code not received within {self._timeout}s. "
                "Send /mfa <code> within the time limit and retry /sync."
            )
        return code

    def clear(self) -> None:
        self._event.clear()
        self._code = None
