# Refactor OOP Fase 5 — Telegram OOP + Scheduler + cleanup final

## Summary

Phase 5 completes the 5-phase OOP/SOLID refactor by converting the remaining procedural Telegram bot
(`bot.py`) and legacy scheduler (`app/legacy_bridge.py`) into injectable classes, wiring them into
the `Container`, and deleting all backward-compat shims.

## New classes

### `infrastructure/telegram/formatter.py` — `MessageFormatter`

Extracted from `bot.format_for_telegram`. Two methods:
- `to_html(text)`: strips `#` headers, HTML-escapes `<>&`, converts `**bold**` to `<b>bold</b>`.
- `chunk(text, max_len=4000)`: splits on newlines when possible, hard-splits at limit.

### `infrastructure/telegram/auth.py` — `Authorizer`

- `is_authorized(update)`: compares `update.effective_user.id` to the injected `allowed_user_id`.
- `require_auth(handler)`: decorator that replies "No autorizado." and returns early if not authorized.

### `infrastructure/telegram/handlers/commands.py` — `CommandHandlers`

Eight async methods, one per Telegram command. All dependencies injected:
`coach_service`, `briefing_service`, `sync_service`, `mfa_handler`, `memory_repo`,
`sync_log_repo`, `context_builder`, `formatter`, `authorizer`, `garmin_client`.

Key behaviors:
- `/sync` — runs `sync_service.run()` in executor; replies with counts.
- `/status` — reads `context_builder.build_raw(days=7)` for counts + `sync_log_repo.last_sync()`.
- `/briefing` — runs `briefing_service.generate(moment)` in executor; formats + chunks reply.
- `/reset` — calls `coach_service.reset(user_id)`.
- `/resetsession` — calls `garmin_client.reset()` (removes persisted session file).
- `/mfa` — calls `mfa_handler.provide_code(code)`.
- `/memoria` — calls `memory_repo.add(note)`.

### `infrastructure/telegram/handlers/chat.py` — `ChatMessageHandler`

`handle(update, context)`:
1. Auth check via `authorizer.is_authorized`.
2. Sends typing action.
3. Calls `coach_service.chat(user_id, text)`.
4. Formats response with `formatter.to_html` + `formatter.chunk`.
5. Replies with `parse_mode="HTML"`, falls back to plain text on parse error.

### `infrastructure/telegram/bot_app.py` — `TelegramBotApp`

- `build()`: builds `Application`, registers all 9 handlers (8 CommandHandler + 1 MessageHandler).
- `_on_startup(app)`: captures `asyncio.get_running_loop()` into `self.loop`; injects a notifier
  callable into `MFAHandler.set_notifier(fn)` so MFA messages reach the user.
- `run()`: calls `build()` then `app.run_polling(drop_pending_updates=True)`.
- `send_to_user(text)`: used by `Scheduler` to deliver scheduled briefings via
  `asyncio.run_coroutine_threadsafe(bot_app.send_to_user(...), bot_app.loop)`.

### `app/scheduler.py` — `Scheduler`

- `start()`: configures `schedule.every().day.at(morning_time/evening_time)` jobs; launches daemon
  thread running `schedule.run_pending()` every `check_interval_seconds` (default 30).
- `stop()`: sets `threading.Event` and joins thread.
- `_run_job(moment)`: calls `sync_service.run()`, then `briefing_service.generate(moment)`, then
  posts result via `asyncio.run_coroutine_threadsafe(bot_app.send_to_user(briefing), bot_app.loop)`.
  Sync errors are caught and logged; briefing still fires.

## Updated: `app/container.py`

`Container.__init__` now builds the full chain in order:
repos → llm_client → tool_registry → context_builder → coach_service → briefing_service →
mfa_handler → garmin_client → sync_service → formatter → authorizer →
command_handlers → chat_handler → bot_app → scheduler.

`run()`:
```python
def run(self) -> None:
    self.scheduler.start()
    try:
        self.bot_app.run()
    finally:
        self.scheduler.stop()
```

Zero delegation to `legacy_bridge`. Zero shims.

## Files deleted

### Legacy shims
- `garmin_coach/bot.py`
- `garmin_coach/coach.py`
- `garmin_coach/coach_tools.py`
- `garmin_coach/context_builder.py`
- `garmin_coach/db.py`
- `garmin_coach/garmin_sync.py`
- `garmin_coach/app/legacy_bridge.py`

### Legacy tests
- `garmin_coach/tests/test_bot.py`
- `garmin_coach/tests/test_coach.py`
- `garmin_coach/tests/test_coach_tools.py`
- `garmin_coach/tests/test_context_builder.py`
- `garmin_coach/tests/test_db.py`

All behaviours tested in legacy suites are covered by the new OOP-layer tests.

## New tests (70)

| File | Tests | Coverage target |
|------|-------|-----------------|
| `tests/infrastructure/telegram/test_formatter.py` | 17 | `MessageFormatter` |
| `tests/infrastructure/telegram/test_auth.py` | 7 | `Authorizer` |
| `tests/infrastructure/telegram/test_commands.py` | 24 | `CommandHandlers` (3 per command) |
| `tests/infrastructure/telegram/test_chat_handler.py` | 6 | `ChatMessageHandler` |
| `tests/infrastructure/telegram/test_bot_app.py` | 8 | `TelegramBotApp` |
| `tests/app/test_scheduler.py` | 10 | `Scheduler` |
| `tests/app/test_container.py` | 5 | `Container` Phase 5 wiring |

All async handlers tested with `asyncio.run()` (no pytest-asyncio dependency).

## SOLID validations

```
grep -RnE "^_[a-z_]+ = " garmin_coach/ --include="*.py"  → empty
grep -rn "os.getenv|os.environ" garmin_coach/ --include="*.py"  → only app/config.py + tests/conftest.py
grep -rn "TinyDB(|ChatGroq(|Garmin(" garmin_coach/ --include="*.py"  → only tinydb_factory.py, groq_langchain.py, client.py
```

## Metrics

| Metric | Value |
|--------|-------|
| Tests | 459 passed |
| Coverage | 94.54% |
| Ruff | clean |
| Deleted files | 12 (7 shims + 5 test files) |
| New files | 7 (5 telegram + scheduler + updated container) |
| New tests | 70 |

## Architecture summary — 5/5 phases complete

All subsystems are now injectable classes behind explicit interfaces:

- **DB**: `TinyDBFactory` + 9 `Repository` subclasses
- **LLM**: `ChatGroqClient(LLMClient)` + `ToolRegistry` + 10 `Tool` subclasses
- **Garmin**: `GarminClient` + `MFAHandler` + `GarminDataFetcher`
- **Services**: `CoachService` (session mgmt) + `BriefingService` + `SyncService` + `ContextBuilder`
- **Telegram**: `MessageFormatter` + `Authorizer` + `CommandHandlers` + `ChatMessageHandler` + `TelegramBotApp`
- **App**: `Scheduler` + `Container` + `Settings`
