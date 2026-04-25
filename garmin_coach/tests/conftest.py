"""Set env vars before any module-level SDK clients are instantiated."""
import os

os.environ.setdefault("GROQ_API_KEY", "test-key-for-testing")
os.environ.setdefault("GARMIN_EMAIL", "test@test.com")
os.environ.setdefault("GARMIN_PASSWORD", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test")
os.environ.setdefault("TELEGRAM_ALLOWED_USER_ID", "12345")
