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

## Documentation
- Finish the new implementations and bug fixes documenting everything on `docs`folder. 

## Testing
Minimun coverage allowed: 85%. Unit test are a MUST.

```bash
python -m pytest garmin_coach/tests/ -v
```

## Active specs

All specs implemented. See `docs/implementations/` for technical details.

## Implemented: Refactor OOP Fase 1 — Settings + Container + estructura de carpetas (`garmin_coach/app/`, `garmin_coach/prompts/`)

- `Settings` frozen dataclass + `load_settings()` en `app/config.py` — único punto que toca `os.environ`. Lanza `RuntimeError` con lista de faltantes si falta alguna obligatoria.
- `configure_logging(settings)` en `app/logging_setup.py` — extraído de `main.py`, crea directorio del log automáticamente.
- `Container(settings).run()` en `app/container.py` — en Fase 1 delega a `bot.build_application()` legacy.
- `legacy_bridge.py` — pegamento temporal con scheduler y MFA bridge; se elimina en Fase 4-5.
- `prompts/coach_system.txt` — SYSTEM_PROMPT como recurso de texto; `read_system_prompt()` en `prompts/__init__.py`. CoachSession lo cargará en Fase 3.
- `main.py` reescrito a ≤20 líneas: load_dotenv → load_settings → configure_logging → Container.run().
- Deuda temporal: scheduler fuera del Container (hilo daemon en legacy_bridge) y SYSTEM_PROMPT duplicado en coach.py hasta Fase 3.
- Tests: `tests/app/test_config.py` (7), `test_container.py` (3), `test_logging_setup.py` (2). Suite: 210 passed, 90.44% coverage.
- Detalle: `docs/implementations/refactor_oop_phase_1.md`.

## Implemented: LLM context slimming (`garmin_coach/context_builder.py`, `garmin_coach/db.py`, `garmin_coach/coach.py`)

- `coach.py` ahora consume `get_compact_context_for_ai(days=7)` en `CoachSession.chat` y `generate_daily_briefing` para evitar `context_length_exceeded` de Groq tras enriquecer el sync.
- `context_builder.build_context` aplica `slim_*` por tabla (descarta `splits`, `hrZones`, `maxMetrics`, polylines) y `aggregate_series` para resumir series numéricas (last/mean/min/max/n).
- `db.get_context_for_ai` sigue devolviendo registros raw (lo usa `bot.cmd_status` para conteos).
- Detalle: `docs/implementations/llm_context_slimming.md`. Plan original con 3 opciones (incluida tool calling C como evolución futura): `docs/implementations/llm_context_slimming_plan.md`.

## Implemented: non-distance activity filtering (`garmin_coach/context_builder.py`, `garmin_coach/coach.py`)

- `_NON_DISTANCE_TYPES` (padel, tennis, strength_training, yoga, climbing, HIIT…) → `slim_activity` descarta distancia/velocidad/ritmo/cadencia/potencia/elevación/sweat-loss para esas actividades.
- `duration_hms` (HH:MM:SS o MM:SS) reemplaza `duration`/`movingDuration`/`elapsedDuration` en segundos en TODAS las actividades. El LLM ya no puede citar "5212.53 segundos".
- `SYSTEM_PROMPT` con regla explícita: usar `duration_hms`, no segundos; en padel/fuerza/yoga no mencionar distancia ni ritmo.
- Detalle: `docs/implementations/non_distance_activity_filtering.md`.

## Implemented: Telegram HTML formatting (`garmin_coach/bot.py`)

- `format_for_telegram` ahora produce HTML (`**x**` → `<b>x</b>`, escapa `<>&`, strip de cabeceras `#`).
- Todas las salidas LLM (`cmd_briefing`, `handle_message`, `send_scheduled_message`) usan `parse_mode="HTML"` con fallback sin parse.
- `send_scheduled_message` aplica el formateo + chunking; antes mandaba el texto crudo del LLM y los `**` aparecían en el chat.
- Detalle: `docs/implementations/telegram_html_formatting.md`.

## Implemented: coach quality Fase 1 (`garmin_coach/context_builder.py`, `garmin_coach/coach.py`)

- `slim_activity` añade `date`, `weekday` (es), `distance_km`, `pace_min_per_km`, `is_run`, `is_long_run` (≥15 km).
- TE renombrado: `aerobicTrainingEffect` → `aerobic_te`, `anaerobicTrainingEffect` → `anaerobic_te` (evita que el modelo los confunda con VO2max).
- `slim_fitness_metrics` expone alias `vo2max_running`.
- `build_context` añade `notable_runs` (top-3 carreras más largas de la ventana, calculado sobre TODAS las actividades, no sólo el cap). Default `max_activities` 10 → 15.
- `SYSTEM_PROMPT` con reglas estrictas: VO2max sólo en `fitness_metrics.vo2max_running`; preguntas referidas a una carrera concreta → buscar primero en `notable_runs` casando por `weekday`/`date`/`distance_km`; si no hay match, decirlo explícitamente, no inventar.
- Detalle: `docs/implementations/coach_quality_phase1.md`.

### Hotfixes Fase 1
- `pace_min_per_km` ahora string `"M:SS"` ya formateado (antes decimal causaba "5:79"). Carry de 60s incluido.
- Prompt de formato ahora pide `**doble asterisco**` para negrita (alineado con `format_for_telegram`, antes pedía `*simple*` que pasaba literal).
- Detalle: `docs/implementations/coach_quality_phase1_hotfixes.md`.

## Implemented: coach quality Fase 2 — tool calling (`garmin_coach/coach_tools.py`, `garmin_coach/coach.py`)

- Nuevo `coach_tools.py` con 9 tools (`find_activity`, `get_recent_activities`, `get_activity_detail`, `get_sleep_window`, `get_hrv_window`, `get_body_battery_window`, `get_training_readiness_window`, `get_fitness_snapshot`, `search_memory`) + `TOOLS_SPEC` (schema OpenAI/Groq) + `dispatch_tool_call(name, args)` con manejo de errores.
- `CoachSession.chat` ejecuta loop de function calling (max 5 iteraciones): manda `tools=TOOLS_SPEC`, ejecuta `tool_calls` vía dispatcher, reinjecta resultados como `role: tool` y vuelve a llamar al modelo hasta que devuelva texto.
- Helpers internos: `_serialize_assistant_message` (convierte respuesta SDK → dict), `_execute_tool_calls`, `_trim_history` (cap 40 + descarta `role: tool` huérfano).
- `SYSTEM_PROMPT` con sección "HERRAMIENTAS" listando cuándo usar cada tool; refuerzo "no inventes, llama a `find_activity` primero".
- `generate_daily_briefing` NO usa tools (un solo round-trip, dump sigue suficiente).
- Caps defensivos en handlers: `MAX_WINDOW_DAYS=90`, `MAX_ACTIVITIES_RESULT=25`.
- Tests: `test_coach_tools.py` (33) + tool-loop tests en `test_coach.py`. Suite 175 passed, 89.17% coverage.
- Hotfix `tool_use_failed`: Llama 3.3 a veces emite tags `<function=…>` literales y Groq devuelve 400 con la generación en `body.error.failed_generation`. Recovery dos pasos: (1) `_parse_function_tag` extrae `(name, args)` con regex (variantes con/sin paréntesis), inyecta assistant sintético con `tool_calls` + `role: tool` con resultado y continúa el loop; (2) si sólo hay prosa, `_salvage_tool_use_failed` strip-ea los tags y devuelve el texto. Otros 400 propagan al fallback "❌". Prompt reforzado con bloque "REGLAS DE TOOL USE" prohibiendo emitir texto + función en el mismo turno.
- Modelo cambiado a `meta-llama/llama-4-scout-17b-16e-instruct` (tool calling más fiable que `llama-3.3-70b-versatile`).
- Detalle: `docs/implementations/coach_tool_calling.md`.

## Implemented: coach quality Fase 3 — personal records (`garmin_coach/db.py`, `garmin_coach/coach_tools.py`, `garmin_coach/coach.py`)

- `purge_old_data` ya NO borra `activities` (sólo wellness). Garantiza que medias maratones, maratones y PRs históricos sobreviven indefinidamente. `removed["activities"]` siempre `0`.
- Nueva tool `get_personal_records()` calcula al vuelo desde la tabla activities: mejor tiempo en 1K, 5K, 10K, half_marathon (21097 m), marathon (42195 m) con tolerancias ±2-5%, y `longest_run` (carrera más larga). Sólo runs (`_RUN_TYPES`), ignora ciclismo. Devuelve `{activityId, date, distance_km, duration_hms, pace_min_per_km, averageHR}` por slot.
- `SYSTEM_PROMPT` instruye usar `get_personal_records` para PB / mejor marca / récord / tirada más larga.
- Tests: `test_purge_keeps_old_activities`, suite PRs (10 nuevos en `test_coach_tools.py`). Suite 200 passed, 89.81% coverage.
- Detalle: `docs/implementations/coach_quality_phase3.md`.

## Implemented: Refactor OOP Fase 1 — Settings + Container + estructura de carpetas (`garmin_coach/app/`)

- `app/config.py`: `Settings` frozen dataclass + `load_settings()` — único punto que lee `os.environ`.
- `app/container.py`: `Container` skeleton; Fase 1 delega a bot legacy.
- `app/logging_setup.py`: `configure_logging(settings)` extraído de `main.py`.
- `app/legacy_bridge.py`: pegamento temporal `start_scheduler()`. Se elimina en Fase 4-5.
- `prompts/coach_system.txt`: `SYSTEM_PROMPT` como recurso de texto plano; `prompts/__init__.read_system_prompt()` lo carga.
- `main.py` slim (≤20 líneas): `load_dotenv → load_settings → configure_logging → Container.run()`.
- Jerarquía de carpetas creada: `domain/`, `infrastructure/{db,llm,garmin,telegram}`, `services/`, `app/`, `tests/{domain,infrastructure,services,app}`.
- Detalle: `docs/implementations/refactor_oop_phase_1.md`.

## Implemented: Refactor OOP Fase 2 — Domain + Repositories (`garmin_coach/domain/`, `garmin_coach/infrastructure/db/`)

- Domain dataclasses frozen: `Activity` + `ActivityType(StrEnum)` (con `is_run()`/`is_distance_based()`), `Sleep`/`HRV`/`BodyBattery`/`TrainingReadiness`/`TrainingStatus`/`Respiration`/`SPO2`/`Stress`, `FitnessMetrics`/`RacePredictions`/`LactateThreshold`/`EnduranceScore`/`PersonalRecord`. Retrocompat: `RUN_TYPES`/`NON_DISTANCE_TYPES` como frozensets de strings.
- `TinyDBFactory(db_path)` — único punto de creación TinyDB. `BaseRepository` — operaciones genéricas (`upsert`, `upsert_many`, `find_by_date_range`, `delete_older_than`, `latest`, …).
- `ActivityRepository`: `find_runs_in_window`, `find_by_weekday`, `find_by_min_distance_km`, `find_by_type`, `compute_personal_records` (lógica de PRs migrada desde `coach_tools`).
- Wellness repos (`SleepRepository`, `HRVRepository`, …) con `window(days)`.
- Fitness repos (`FitnessMetricsRepository`, …) con `replace(record)` + `latest()` — replica patrón truncate+insert de `garmin_sync.py`.
- `MemoryRepository`: `add(note)`, `search(query, limit)`. `SyncLogRepository`: `log(summary)`, `last_sync()`.
- `db.py` convertido en shim delgado: misma API pública, delega a repos. `_db_instance` global conservado para seam de patch en tests legacy. Se elimina en Fase 3.
- `Container._build_repositories()` instancia todos los repos (preparado para Fase 3-5).
- 163 tests nuevos (363 total), 93.12% coverage. Detalle: `docs/implementations/refactor_oop_phase_2.md`.

## Implemented: Refactor OOP Fase 4 — Garmin client + MFA handler + SyncService

- `MFAHandler` (mfa_handler.py) — encapsula `threading.Event` + código MFA; cero globales; `set_notifier(fn)` inyectable.
- `GarminClient(settings, mfa_handler)` (client.py) — auth lazy con sesión persistida; `authenticate()` cacheado; `reset()`.
- `GarminDataFetcher(garmin)` (data_fetcher.py) — 14 métodos pure-fetch, uno por endpoint; todos usan `_safe()` (excepción → None/[]).
- `SyncService.run() -> SyncSummary` (sync_service.py) — orquesta completo: auth→window→purge→fetch→upsert→log. `SyncSummary` frozen dataclass.
- `sync_helpers.py` — `daterange`, `compute_sync_window`, `merge_activity_details` funciones puras.
- `garmin_sync.py` convertido en shim (~80 líneas): reexporta `set_bot_app`, `set_event_loop`, `provide_mfa_code`, `sync_all` delegando a `Container`. Marcado para eliminación en Fase 5.
- Globales eliminados de la lógica: `_mfa_event`, `_mfa_code`, `_bot_app`, `_bot_loop` — ahora encapsulados en `MFAHandler`.
- Tests legacy `tests/test_garmin_sync.py` eliminados (15); reemplazados por 66 tests nuevos en `tests/infrastructure/garmin/` y `tests/services/`.
- Race condition en `test_authenticate_mfa_flow` resuelta con `threading.Event` de sincronización entre hilo proveedor y el que llama `wait_for_code`.
- Suite: 574 passed, 95.50% coverage. Detalle: `docs/implementations/refactor_oop_phase_4.md`.

## Implemented: Refactor OOP Fase 5 — Telegram OOP + Scheduler + cleanup final

- `infrastructure/telegram/formatter.py`: `MessageFormatter` — `to_html()` (strip headers, escape HTML, `**x**`→`<b>x</b>`), `chunk(text, max_len=4000)`.
- `infrastructure/telegram/auth.py`: `Authorizer(allowed_user_id)` — `is_authorized(update)`, `require_auth(handler)` decorator.
- `infrastructure/telegram/bot_app.py`: `TelegramBotApp` — `build()` registra 9 handlers; `_on_startup` captura asyncio loop e inyecta notifier en `MFAHandler`; `run()` polling; `send_to_user(text)` para Scheduler.
- `infrastructure/telegram/handlers/commands.py`: `CommandHandlers(coach_service, briefing_service, sync_service, mfa_handler, memory_repo, sync_log_repo, context_builder, formatter, authorizer, garmin_client)` — 8 métodos async.
- `infrastructure/telegram/handlers/chat.py`: `ChatMessageHandler(coach_service, formatter, authorizer)` — `handle(update, context)`.
- `app/scheduler.py`: `Scheduler(sync_service, briefing_service, sync_log_repo, bot_app, settings)` — hilo daemon; `start()`/`stop()`; `_run_job(moment)` llama sync+briefing+`bot_app.send_to_user` vía `asyncio.run_coroutine_threadsafe(bot_app.loop)`.
- `app/container.py`: reescrito completo; `run()` hace `scheduler.start()` + `bot_app.run()` + `scheduler.stop()` en finally. Cero delegación a legacy_bridge.
- **Borrados**: `bot.py`, `coach.py`, `coach_tools.py`, `context_builder.py`, `db.py`, `garmin_sync.py`, `app/legacy_bridge.py`, `tests/test_bot.py`, `tests/test_coach.py`, `tests/test_coach_tools.py`, `tests/test_context_builder.py`, `tests/test_db.py`.
- **Tests nuevos** (70): `tests/infrastructure/telegram/test_formatter.py` (17), `test_auth.py` (7), `test_commands.py` (24), `test_chat_handler.py` (6+), `test_bot_app.py` (8), `tests/app/test_scheduler.py` (10), `test_container.py` (actualizado, 5).
- **SOLID validado**: cero globales mutables fuera de Container; cero `os.getenv` fuera de `app/config.py`; `TinyDB(`/`ChatGroq(`/`Garmin(` sólo en sus factories.
- Suite: 459 passed, 94.54% coverage. pyproject.toml omit limpiado: sólo `main.py` y `tests/*`.
- Detalle: `docs/implementations/refactor_oop_phase_5.md`.

## Implemented: smart sync window + purge (`garmin_coach/db.py`, `garmin_coach/garmin_sync.py`)

- `purge_old_data(days)` — removes records older than N days from all tables at start of sync
- `is_db_empty()` — True if all four data tables empty
- `get_last_date_in_db()` — max date across activities (`startTimeLocal[:10]`) and sleep/hrv/body_battery (`date` field)
- `sync_all` uses empty-check to pick date window: empty → last 30d; not empty → last DB date to today
- Activities stored as full API dict + merged details from `get_activity(id)` (advanced metrics: vertical oscillation, ground contact time, step length, norm power, etc.). Detail fetch failure is non-fatal.
- `sync_all` summary now includes `purged` key with removed counts per table
