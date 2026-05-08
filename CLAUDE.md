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

1. **Telegram bot** (`python-telegram-bot` async polling) — main thread
2. **Scheduler** (`schedule` lib) — daemon background thread, fires sync+briefing at configured times

The two subsystems share state via globals in `garmin_coach/garmin_sync.py` (`_bot_loop`, `_bot_app`) to allow the scheduler thread to post messages via the bot's asyncio loop using `asyncio.run_coroutine_threadsafe`.

### Package structure

All modules (except `main.py`) live in the `garmin_coach/` package. Tests are in `garmin_coach/tests/`.

### Data flow

```
Garmin Connect API → garmin_coach/garmin_sync.py → TinyDB (data/garmin_coach.json)
                                                         ↓
                                           garmin_coach/db.py → garmin_coach/coach.py (Groq/Llama) → garmin_coach/bot.py → Telegram
```

### Module responsibilities

| File | Role |
|------|------|
| `main.py` | Entry point; wires bot + scheduler; scheduler runs `sync_all` then `generate_daily_briefing` |
| `garmin_coach/bot.py` | All Telegram handlers; per-user `CoachSession` stored in `_sessions` dict |
| `garmin_coach/coach.py` | `CoachSession` class (in-memory conversation history, max 40 messages); `generate_daily_briefing` for scheduled messages; uses Groq API with `llama-3.3-70b-versatile` |
| `garmin_coach/garmin_sync.py` | Garmin auth with session persistence at `/data/garmin_session.json`; MFA flow via Telegram (`/mfa` command + threading.Event); `sync_all` fetches activities, sleep, HRV, body battery |
| `garmin_coach/db.py` | TinyDB singleton; tables: `activities`, `sleep`, `hrv`, `body_battery`, `memory`, `sync_log`; `get_context_for_ai` returns raw lists; `get_compact_context_for_ai` wraps it with `context_builder` for LLM use |
| `garmin_coach/context_builder.py` | `slim_*` projections + `aggregate_series` + `build_context` to compact TinyDB records before sending to Groq (avoids `context_length_exceeded`) |
| `garmin_coach/coach_tools.py` | Function-calling tools (find_activity, get_recent_activities, get_*_window, get_fitness_snapshot, search_memory) + `dispatch_tool_call`. Used by `CoachSession.chat` tool loop. |

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
python -m pytest garmin_coach/tests/ -v
```

## Active specs

All specs implemented. See `docs/implementations/` for technical details.

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

## Implemented: smart sync window + purge (`garmin_coach/db.py`, `garmin_coach/garmin_sync.py`)

- `purge_old_data(days)` — removes records older than N days from all tables at start of sync
- `is_db_empty()` — True if all four data tables empty
- `get_last_date_in_db()` — max date across activities (`startTimeLocal[:10]`) and sleep/hrv/body_battery (`date` field)
- `sync_all` uses empty-check to pick date window: empty → last 30d; not empty → last DB date to today
- Activities stored as full API dict + merged details from `get_activity(id)` (advanced metrics: vertical oscillation, ground contact time, step length, norm power, etc.). Detail fetch failure is non-fatal.
- `sync_all` summary now includes `purged` key with removed counts per table
