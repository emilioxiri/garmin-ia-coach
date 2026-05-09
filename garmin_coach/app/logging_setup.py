"""
app/logging_setup.py
Logging configuration extracted from main.py.
"""

import logging

from garmin_coach.app.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure root logger with file and stream handlers."""
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.log_path),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
