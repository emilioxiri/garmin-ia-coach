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

# Docker (primary deployment method — run from docker/ folder)
cd docker && docker-compose up -d --build
cd docker && docker-compose logs -f
cd docker && docker-compose down
make hard-restart # Turn off the current container, build a new one and turn on.

# Add/remove dependencies
poetry add <package>
poetry remove <package>
```

## Architecture

Single-process app with two concurrent subsystems:

1. **Telegram bot** (`python-telegram-bot` async polling) — main thread, managed by `TelegramBotApp`
2. **Scheduler** (`schedule` lib) — daemon background thread managed by `Scheduler`, fires sync+briefing at configured times

The two subsystems share state via `TelegramBotApp.loop` (captured in `_on_startup`) which is used by `Scheduler._run_job` via `asyncio.run_coroutine_threadsafe`. No module-level globals anywhere.

### Package structure

All modules (except `main.py`) live in the `garmin_coach/` package. Tests are in `garmin_coach/tests/`.

### Data flow

```
Garmin Connect API → SyncService → TinyDB (data/garmin_coach.json)
                                         ↓
                          ContextBuilder / ToolRegistry
                                         ↓
                        CoachService / BriefingService (Groq/Llama)
                                         ↓
                       TelegramBotApp (CommandHandlers + ChatMessageHandler) → Telegram
```

### Module responsibilities

| File | Role |
|------|------|
| `main.py` | Slim entry point (≤20 lines): load_dotenv → load_settings → configure_logging → Container.run() |
| `garmin_coach/app/config.py` | `Settings` frozen dataclass + `load_settings()` — único punto que lee `os.environ` |
| `garmin_coach/app/container.py` | `Container` — cablea todas las dependencias en orden; `run()` arranca Scheduler + TelegramBotApp |
| `garmin_coach/app/scheduler.py` | `Scheduler(sync_service, briefing_service, sync_log_repo, bot_app, settings)` — hilo daemon con `start()`/`stop()`; `_morning_job`/`_evening_job` llaman sync+briefing+send |
| `garmin_coach/app/logging_setup.py` | `configure_logging(settings)` — FileHandler + StreamHandler |
| `garmin_coach/prompts/coach_system.txt` | SYSTEM_PROMPT como recurso de texto plano. `prompts/__init__.read_system_prompt()` lo carga. |
| `garmin_coach/infrastructure/telegram/formatter.py` | `MessageFormatter` — `to_html(text)` (markdown→HTML, escape, strip headers), `chunk(text, max_len)` |
| `garmin_coach/infrastructure/telegram/auth.py` | `Authorizer(allowed_user_id)` — `is_authorized(update)`, `require_auth(handler)` decorator |
| `garmin_coach/infrastructure/telegram/bot_app.py` | `TelegramBotApp` — `build()` registra handlers; `_on_startup` captura asyncio loop + inyecta notifier en MFAHandler; `run()` arranca polling; `send_to_user(text)` para briefings programados |
| `garmin_coach/infrastructure/telegram/handlers/commands.py` | `CommandHandlers` — un método async por comando (/start, /sync, /status, /briefing, /reset, /resetsession, /mfa, /memoria) |
| `garmin_coach/infrastructure/telegram/handlers/chat.py` | `ChatMessageHandler` — `handle(update, context)` → coach_service.chat → formatter → reply |
| `garmin_coach/infrastructure/garmin/mfa_handler.py` | `MFAHandler` — encapsula `threading.Event` + código MFA; `provide_code()`, `wait_for_code(timeout)`, `notify_user(msg)`, `set_notifier(fn)`, `clear()`. Cero globales. |
| `garmin_coach/infrastructure/garmin/client.py` | `GarminClient(settings, mfa_handler)` — auth con sesión persistida; `authenticate()` lazy + cache; `reset()`. |
| `garmin_coach/infrastructure/garmin/data_fetcher.py` | `GarminDataFetcher(garmin)` — un método por endpoint (activities/sleep/hrv/body_battery/training_status/training_readiness/respiration/spo2/stress/fitness_metrics/race_predictions/lactate_threshold/endurance_score). Pure fetch, sin upserts. |
| `garmin_coach/services/sync_service.py` | `SyncService(garmin_client, fetcher_factory, repositories, sync_log_repo, settings)` — `run() -> SyncSummary`; orquesta auth→fetch→merge→upsert→purge→log. `SyncSummary` frozen dataclass con contadores + `as_dict()`. |
| `garmin_coach/services/sync_helpers.py` | Funciones puras: `daterange(start, end)`, `compute_sync_window(repos, default_days)`, `merge_activity_details(activities, detail_fetcher)`. |
| `garmin_coach/domain/activity.py` | `ActivityType(StrEnum)` con `is_run()`/`is_distance_based()`; `Activity` frozen dataclass; `RUN_TYPES`/`NON_DISTANCE_TYPES` frozensets |
| `garmin_coach/domain/wellness.py` | `Sleep`, `HRV`, `BodyBattery`, `TrainingReadiness`, `TrainingStatus`, `Respiration`, `SPO2`, `Stress` — frozen dataclasses |
| `garmin_coach/domain/fitness.py` | `FitnessMetrics`, `RacePredictions`, `LactateThreshold`, `EnduranceScore`, `PersonalRecord` frozen dataclasses |
| `garmin_coach/infrastructure/db/tinydb_factory.py` | `TinyDBFactory(db_path)` — lazy singleton, un único punto de creación de TinyDB |
| `garmin_coach/infrastructure/db/base_repository.py` | `BaseRepository` — `upsert`, `upsert_many`, `insert`, `find_by_date_range`, `delete_older_than`, `latest`, `count`, `is_empty` |
| `garmin_coach/infrastructure/db/activity_repository.py` | `ActivityRepository` — `find_runs_in_window`, `find_by_weekday`, `find_by_min_distance_km`, `find_by_type`, `compute_personal_records`, `latest_date` |
| `garmin_coach/infrastructure/db/wellness_repository.py` | `SleepRepository`, `HRVRepository`, `BodyBatteryRepository`, `TrainingReadinessRepository`, `TrainingStatusRepository`, `RespirationRepository`, `SPO2Repository`, `StressRepository` — todas con `window(days)` |
| `garmin_coach/infrastructure/db/fitness_repository.py` | `FitnessMetricsRepository`, `RacePredictionsRepository`, `LactateThresholdRepository`, `EnduranceScoreRepository` — `replace(record)` + `latest()` |
| `garmin_coach/infrastructure/db/memory_repository.py` | `MemoryRepository` — `add(note, timestamp)`, `search(query, limit)` |
| `garmin_coach/infrastructure/db/sync_log_repository.py` | `SyncLogRepository` — `log(summary, started_at)`, `last_sync()` |

### TinyDB schema notes

- `activities`: keyed by `activityId` (string), upserted on sync
- `sleep`, `hrv`, `body_battery`: keyed by `date` (ISO string), upserted on sync
- `memory`: append-only notes saved via `/memoria` command
- `sync_log`: append-only log of sync runs with summary counts

### MFA handling

Garmin Connect sometimes requires MFA. Flow: `GarminClient.authenticate()` passes `prompt_mfa` callback to `Garmin()`; callback calls `MFAHandler.notify_user()` + `MFAHandler.wait_for_code()` (blocks up to 300s). Bot's `/mfa <code>` handler calls `MFAHandler.provide_code()` which unblocks the wait. The notifier callable is injected in `TelegramBotApp._on_startup` via `mfa_handler.set_notifier(fn)` — no globals involved.

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
| `LOG_LEVEL` | Logging verbosity: DEBUG / INFO / WARNING / ERROR (default INFO) |

## Logging

Setup central en `garmin_coach/app/logging_setup.py`:
- `RotatingFileHandler` 5 MB × 5 backups en `settings.log_path` (`/data/logs/bot.log` por defecto).
- `StreamHandler` para `docker logs`.
- Nivel configurable vía `LOG_LEVEL` env var (default INFO).
- Silencios: `httpx`, `garminconnect`, `urllib3`, `httpcore` → WARNING.

Patrón canónico (TODOS los módulos con I/O o lógica de negocio):

```python
from garmin_coach.app.logging_setup import get_logger
logger = get_logger(__name__)
```

Convención de mensajes: `event=<snake_case> key1=val1 key2=val2`

Ejemplo: `logger.info("event=sync_complete activities=%d sleep=%d duration_ms=%d", a, s, d)`

| Nivel | Cuándo |
|-------|--------|
| `DEBUG` | Flujo interno detallado (upserts, iteraciones de tool loop, payloads). Off en prod. |
| `INFO` | Eventos de negocio: arranque/parada, comandos Telegram, sync start/end con totales, LLM call start/end con duración, briefing enviado, MFA solicitado/recibido. |
| `WARNING` | Degradaciones: fetch Garmin endpoint vacío, fallback HTML→texto plano, retry de tool call, recovery de `<function=...>`. |
| `ERROR` | Excepciones controladas (siempre `exc_info=True`). I/O fallido que aborta una operación. |
| `CRITICAL` | App no puede continuar (init failure). |

Reglas duras:
- Nunca usar `print()`.
- Nunca `except: pass` sin `logger.exception(...)` antes.
- Operaciones externas (Garmin API, Telegram send, Groq invoke, TinyDB write) → SIEMPRE log INFO entrada+salida con duración, ERROR en fallo.
- Nunca loguear `password`, `groq_api_key`, ni tokens de sesión Garmin. Email solo enmascarado (`em***@domain.com`).
- Loggers a nivel de módulo, no de instancia.

**"Los logs son tan importantes como los tests. Toda I/O externa o decisión de negocio debe quedar trazada. PRs sin logs en operaciones nuevas son tan inválidas como PRs sin tests."**

## Documentation
- Finish the new implementations and bug fixes documenting everything on `docs`folder. 

## Testing
Minimun coverage allowed: 85%. Unit test are a MUST.

```bash
python -m pytest garmin_coach/tests/ -v
```

## Guidelines
After finish an implementation successfully, run the following command to refresh the docker currently running:
```bash
make hard-restart
```
