# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. Use `\caveman` plugins always if it is possible.

## Self-maintenance

Update this file when you discover something non-obvious that would help future sessions: a new module added, a schema change, a tricky integration pattern, a spec moved to implemented, or an architectural decision made. Do not add things already derivable from reading the code.

## Commands

```bash
# Run locally (requires .env)
source .venv/bin/activate
python main.py

# Lint
ruff check .
ruff format .

# Docker (primary deployment method)
docker-compose up -d --build
docker-compose logs -f
docker-compose down

# Add/remove dependencies
poetry add <package>
poetry remove <package>
```

No test suite exists yet. When adding tests, use `pytest` and run with `python -m pytest`.

## Architecture

Single-process app with two concurrent subsystems:

1. **Telegram bot** (`python-telegram-bot` async polling) — main thread
2. **Scheduler** (`schedule` lib) — daemon background thread, fires sync+briefing at configured times

The two subsystems share state via globals in `garmin_sync.py` (`_bot_loop`, `_bot_app`) to allow the scheduler thread to post messages via the bot's asyncio loop using `asyncio.run_coroutine_threadsafe`.

### Data flow

```
Garmin Connect API → garmin_sync.py → TinyDB (data/garmin_coach.json)
                                           ↓
                                       db.py → coach.py (Groq/Llama) → bot.py → Telegram
```

### Module responsibilities

| File | Role |
|------|------|
| `main.py` | Entry point; wires bot + scheduler; scheduler runs `sync_all` then `generate_daily_briefing` |
| `bot.py` | All Telegram handlers; per-user `CoachSession` stored in `_sessions` dict |
| `coach.py` | `CoachSession` class (in-memory conversation history, max 40 messages); `generate_daily_briefing` for scheduled messages; uses Groq API with `llama-3.3-70b-versatile` |
| `garmin_sync.py` | Garmin auth with session persistence at `/data/garmin_session.json`; MFA flow via Telegram (`/mfa` command + threading.Event); `sync_all` fetches activities, sleep, HRV, body battery |
| `db.py` | TinyDB singleton; tables: `activities`, `sleep`, `hrv`, `body_battery`, `memory`, `sync_log`; `get_context_for_ai` is the main query used by the coach |

### TinyDB schema notes

- `activities`: keyed by `activityId` (string), upserted on sync
- `sleep`, `hrv`, `body_battery`: keyed by `date` (ISO string), upserted on sync
- `memory`: append-only notes saved via `/memoria` command
- `sync_log`: append-only log of sync runs with summary counts

### MFA handling

Garmin Connect sometimes requires MFA. Flow: sync thread blocks on `threading.Event` → bot sends Telegram message → user replies `/mfa <code>` → `provide_mfa_code()` unblocks the event. Timeout: 5 minutes.

### Data persistence

`/data/` is a Docker volume mounted at runtime. Contains the TinyDB JSON file, Garmin session tokens, and logs. Never exists locally unless running outside Docker.

## Environment variables

| Var | Purpose |
|-----|---------|
| `GARMIN_EMAIL` / `GARMIN_PASSWORD` | Garmin Connect credentials |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_ALLOWED_USER_ID` | Single authorized user (bot is single-user) |
| `GROQ_API_KEY` | Groq API key for Llama inference |
| `SYNC_TIME_MORNING` / `SYNC_TIME_EVENING` | Scheduler times (HH:MM, 24h, Europe/Madrid TZ) |
| `DAYS_HISTORY` | Days to sync on first run (default 30) |

## Documentation
- Finish the new implementations and bug fixes documenting everything on `docs`folder. 

## Testing
Minimun coverage allowed: 85%. Unit test are a MUST.

```bash
python -m pytest tests/ -v
```

pytest not in pyproject.toml yet — install with `pip install pytest` if missing in venv.

## Active specs

All specs implemented. See `docs/implementations/` for technical details.

## Implemented: smart sync window + purge (`db.py`, `garmin_sync.py`)

- `purge_old_data(days)` — removes records older than N days from all tables at start of sync
- `is_db_empty()` — True if all four data tables empty
- `get_last_date_in_db()` — max date across activities (`startTimeLocal[:10]`) and sleep/hrv/body_battery (`date` field)
- `sync_all` uses empty-check to pick date window: empty → last 30d; not empty → last DB date to today
- Activities stored as full API dict + merged details from `get_activity(id)` (advanced metrics: vertical oscillation, ground contact time, step length, norm power, etc.). Detail fetch failure is non-fatal.
- `sync_all` summary now includes `purged` key with removed counts per table
