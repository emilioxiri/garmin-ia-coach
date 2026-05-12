# Logging strategy — unified observability for garmin-coach

## Context

The app previously had 6 of 53 files using `logging`, with 46 calls distributed unevenly. Entire layers were silent: `infrastructure/llm/`, `infrastructure/db/`, most services. Critical operations (Groq calls, TinyDB upserts, Garmin fetches, MFA flow, tool execution, Telegram commands) left no trace in production Docker logs, making diagnosis impossible.

## Changes

### `garmin_coach/app/logging_setup.py` (rewrite)

- `RotatingFileHandler(settings.log_path, maxBytes=5 MB, backupCount=5, encoding=utf-8)` + `StreamHandler`.
- Format: `%(asctime)s %(levelname)s %(name)s :: %(message)s` (separator `::` aids grepping).
- Level from `settings.log_level` (env `LOG_LEVEL`, default `INFO`).
- Silences: `httpx`, `garminconnect`, `urllib3`, `httpcore` → WARNING.
- Exports `get_logger(name) -> logging.Logger` — canonical import for all modules.
- Logs `event=logging_configured level=... path=...` on startup.

### `garmin_coach/app/config.py`

- Added `log_level: str = "INFO"` field to `Settings`.
- `load_settings()` reads `LOG_LEVEL` env var (`.upper()`, default `"INFO"`).

### Files with new/updated loggers

| File | What was added |
|------|----------------|
| `app/container.py` | `event=container_start` / `event=container_stop` (INFO) |
| `app/scheduler.py` | `event=scheduler_start/stop`, `event=job_start/end moment=... duration_ms=...` (INFO); job failures (ERROR, exc_info) |
| `infrastructure/llm/groq_langchain.py` | `event=llm_call_start/end/failed` + `event=llm_briefing_start/end/failed` with model, duration_ms (INFO/ERROR) |
| `infrastructure/llm/tool_use_recovery.py` | `event=tool_recovery strategy=salvage_plain_text` (WARNING) |
| `infrastructure/llm/message_helpers.py` | `event=serialize_assistant_message` (DEBUG) |
| `infrastructure/db/tinydb_factory.py` | `event=tinydb_init path=...` (INFO) |
| `infrastructure/db/base_repository.py` | `event=upsert_many count=...`, `event=delete_older_than removed=...` (DEBUG) |
| `infrastructure/garmin/data_fetcher.py` | `_safe()` promoted from DEBUG to WARNING: `event=fetch_failed endpoint=...` with exc_info |
| `infrastructure/garmin/client.py` | `event=auth_start email=em***@domain.com`, `event=auth_cache_hit` (INFO/DEBUG); `_mask_email()` helper added |
| `infrastructure/garmin/mfa_handler.py` | `event=mfa_notify`, `event=mfa_wait_start/complete/timeout`, `event=mfa_code_provided` (INFO/WARNING) |
| `infrastructure/telegram/bot_app.py` | `event=send_to_user chat_id=... chunks=... total_len=...` (INFO); HTML fallback (WARNING) |
| `infrastructure/telegram/handlers/commands.py` | Every command: `event=cmd_start/end command=/foo user=...` with duration_ms; failures ERROR exc_info |
| `infrastructure/telegram/handlers/chat.py` | `event=chat_msg user=... msg_len=...`, `event=chat_reply duration_ms=... resp_len=...` (INFO) |
| `infrastructure/telegram/formatter.py` | `event=chunk_split total_len=... chunks=...` (DEBUG) |
| `services/sync_service.py` | `event=sync_start`, `event=sync_window`, `event=sync_purged`, `event=sync_complete ... duration_ms=...` (INFO) |
| `services/briefing_service.py` | `event=briefing_start/end/failed moment=... duration_ms=...` (INFO/ERROR) |
| `services/coach_session.py` | `event=chat_round iter=... history_len=...`, `event=chat_round_result tool_calls=...` (INFO) |
| `services/coach_service.py` | `event=coach_chat`, `event=coach_reset` (DEBUG/INFO) |
| `services/context_builder.py` | `event=context_build days=... max_activities=...` (DEBUG) |
| `services/session_manager.py` | `event=session_create/reset user=...` (INFO) |
| `services/projections.py` | Logger added at module level |
| `services/tools/registry.py` | `event=tool_exec/error/crashed/bad_args/unknown name=...` (INFO/WARNING/ERROR) |
| `services/tools/activity_tools.py` | `event=find_activity matches=...` (DEBUG) |
| `services/tools/wellness_tools.py` | Logger at module level |
| `services/tools/fitness_tools.py` | Logger at module level |
| `services/tools/memory_tools.py` | Logger at module level |

### `CLAUDE.md`

- Added `LOG_LEVEL` row to env vars table.
- Added `## Logging` section between env vars and Documentation: setup, level table, hard rules, canonical pattern, mandatory sentence.

### `.claude/agents/` reviewers

- `telegram-handler-reviewer.md`: expanded invariant 6 + added Logging invariants section.
- `async-thread-safety-reviewer.md`: added Logging invariants section.
- `tinydb-schema-reviewer.md`: added Logging invariants section.

## Conventions

- Canonical import: `from garmin_coach.app.logging_setup import get_logger; logger = get_logger(__name__)`
- Message format: `event=<snake_case> key=val` — grepping `event=sync_complete` returns exactly the right lines.
- `%`-style lazy formatting in all `logger.*` calls.
- Secrets never logged: `password`, `groq_api_key`, Garmin tokens. Email masked via `_mask_email()`.

## Verification

```bash
ruff check .       # clean
ruff format .      # no changes
python -m pytest garmin_coach/tests/ -v  # suite green, coverage ≥ 85%
```

Smoke (Docker):
```
LOG_LEVEL=DEBUG  →  grep "event=container_start" /data/logs/bot.log
/sync             →  event=cmd_start command=/sync … event=sync_complete … event=cmd_end
/briefing         →  event=llm_briefing_start … event=llm_briefing_end duration_ms=…
```
