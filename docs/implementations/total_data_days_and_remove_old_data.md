# Implementation: Smart Sync Window & Old Data Purge

## Spec
`docs/specs/total_data_days_and_remove_old_data.md`

## Changes

### db.py — 3 new functions

**`is_db_empty() -> bool`**
Returns True if all four data tables (activities, sleep, hrv, body_battery) are empty.
Used by `sync_all` to decide the date window.

**`get_last_date_in_db() -> str | None`**
Returns the most recent date (YYYY-MM-DD) across all data tables.
Activities use `startTimeLocal[:10]`; sleep/hrv/body_battery use the `date` field.
Returns None if all tables are empty.

**`purge_old_data(days: int = 30) -> dict`**
Removes records older than `days` days from all data tables.
Returns a dict with removed counts per table.
Activities purged via `startTimeLocal[:10] < cutoff`; others via `date < cutoff`.
Cutoff date itself is kept (strict less-than).

### garmin_sync.py — sync_all rewrite

**Date window logic:**
- DB empty → fetch from `today - days` (default 30)
- DB not empty → fetch from `get_last_date_in_db()` to today

**Purge:**
Called at start of every sync, before fetching.

**Activity metrics:**
- Stores the full dict from `get_activities_by_date` (no cherry-picking).
- Additionally calls `get_activity(activityId)` per activity and merges in any fields not already present (adds advanced metrics: normPower, intensityFactor, verticalOscillation, groundContactTime, strideLength, avgRunCadence, trainingStressScore, etc.).
- Detail fetch failure is non-fatal (logged at DEBUG, sync continues).

**Summary dict:**
Now includes a `purged` key with removed counts per table.

## Tests
`tests/test_db.py` — 14 tests covering is_db_empty, get_last_date_in_db, purge_old_data edge cases.
`tests/test_garmin_sync.py` — 7 tests covering date window selection, purge ordering, full field storage, detail merge, and resilience to detail API failures.

All 21 tests pass.

## Running tests
```bash
python -m pytest tests/ -v
```
