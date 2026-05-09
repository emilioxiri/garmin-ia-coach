"""
main.py
Entry point: load config, configure logging, start container.
"""

from dotenv import load_dotenv

from garmin_coach.app.config import load_settings
from garmin_coach.app.container import Container
from garmin_coach.app.logging_setup import configure_logging


def main() -> None:
    load_dotenv()
    settings = load_settings()
    configure_logging(settings)
    Container(settings).run()


if __name__ == "__main__":
    main()
