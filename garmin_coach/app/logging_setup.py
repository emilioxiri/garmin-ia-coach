"""
app/logging_setup.py
Unified logging configuration: RotatingFileHandler + StreamHandler.
Exports get_logger() for use across all modules.
"""

import logging
from logging.handlers import RotatingFileHandler

from garmin_coach.app.config import Settings

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s :: %(message)s"

_logger = logging.getLogger(__name__)


def configure_logging(settings: Settings) -> None:
    """Configure root logger with rotating file + stream handlers.

    Level is read from settings.log_level (defaults to INFO).
    Noisy third-party loggers are silenced to WARNING.
    """
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    level_name = logging.getLevelName(level)

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(
        settings.log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "garminconnect", "urllib3", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _logger.info(
        "event=logging_configured level=%s path=%s", level_name, settings.log_path
    )


def get_logger(name: str) -> logging.Logger:
    """Return a stdlib logger for the given module name.

    Usage::

        from garmin_coach.app.logging_setup import get_logger
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
