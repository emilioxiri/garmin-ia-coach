# Refactor OOP Phase 2 — Domain + Repositories

## Summary

Introduces domain dataclasses and TinyDB repository classes. `db.py` is converted to a thin backward-compatibility shim so all existing callers continue to work unchanged.

## New files

### Domain (`garmin_coach/domain/`)

| File | Contents |
|------|----------|
| `activity.py` | `ActivityType(StrEnum)` with `is_run()` / `is_distance_based()` methods; `Activity` frozen dataclass with `from_dict` / `as_dict` / `date_iso`; `RUN_TYPES` / `NON_DISTANCE_TYPES` frozensets for backward compat |
| `wellness.py` | `Sleep`, `HRV`, `BodyBattery`, `TrainingReadiness`, `TrainingStatus`, `Respiration`, `SPO2`, `Stress` — all frozen, all with `from_dict` / `as_dict` |
| `fitness.py` | `FitnessMetrics`, `RacePredictions`, `LactateThreshold`, `EnduranceScore` snapshot dataclasses; `PersonalRecord` value object |
| `session.py` | Reserved for Phase 3 |

### Infrastructure (`garmin_coach/infrastructure/db/`)

| File | Key class / methods |
|------|---------------------|
| `tinydb_factory.py` | `TinyDBFactory(db_path)` — lazy singleton `get()`, `close()` |
| `base_repository.py` | `BaseRepository(db, table_name, primary_key)` — `all`, `count`, `is_empty`, `insert`, `upsert`, `upsert_many`, `find_by_date_range`, `delete_older_than`, `latest` |
| `activity_repository.py` | `ActivityRepository` — `latest_date`, `find_runs_in_window`, `find_by_weekday`, `find_by_min_distance_km`, `find_by_type`, `compute_personal_records` |
| `wellness_repository.py` | `SleepRepository`, `HRVRepository`, `BodyBatteryRepository`, `TrainingReadinessRepository`, `TrainingStatusRepository`, `RespirationRepository`, `SPO2Repository`, `StressRepository` — all with `window(days)` |
| `fitness_repository.py` | `FitnessMetricsRepository`, `RacePredictionsRepository`, `LactateThresholdRepository`, `EnduranceScoreRepository` — `replace(record)` + `latest()` |
| `memory_repository.py` | `MemoryRepository` — `add(note, timestamp)`, `search(query, limit)` |
| `sync_log_repository.py` | `SyncLogRepository` — `log(summary, started_at)`, `last_sync()` |

### `compute_personal_records` location

Logic moved from `coach_tools.get_personal_records` into `ActivityRepository.compute_personal_records()`. The `coach_tools` function still calls `get_db().table("activities").all()` directly (untouched for now); the repository is the authoritative implementation going forward. Phase 3 will migrate the tools to use `ActivityRepository`.

## Modified files

### `garmin_coach/db.py` (shim — delete in Phase 3)

Identical public API. Internally creates a repo instance per call on top of `get_db()`:

```python
def _activity_repo():
    return ActivityRepository(get_db())
```

The global `_db_instance` is preserved so `patch("garmin_coach.db._db_instance", mock_tinydb)` in legacy tests keeps working.

`purge_old_data` delegates to `repo.delete_older_than("date", cutoff)` for each wellness table; activities remain unpurged.

### `garmin_coach/app/container.py`

`Container.__init__` now calls `_build_repositories()` which instantiates `TinyDBFactory(settings.db_path).get()` and creates all repos. Result stored in `self.repositories: Repositories` dataclass. `Container.run()` is unchanged (still delegates to legacy bot).

## Test strategy

All new tests live in `garmin_coach/tests/infrastructure/db/` and `garmin_coach/tests/domain/`, using `TinyDB(storage=MemoryStorage)` via the `memory_db` fixture — no patching required.

163 new tests added (363 total). All legacy tests pass against the shim.

## Metrics

- Tests: 363 passed (was 200)
- Coverage: 93.12% (was ~89.8%)
- ruff: clean

## Remaining debt (Phase 3+)

- `db.py` shim — delete once `coach.py`, `coach_tools.py`, `context_builder.py`, `garmin_sync.py`, `bot.py` migrate to repos directly.
- `coach_tools.py` calls `get_db()` directly — move to `ActivityRepository` / wellness repos in Phase 3.
- `context_builder._RUN_TYPES` / `_NON_DISTANCE_TYPES` — replace with `domain.activity.RUN_TYPES` / `NON_DISTANCE_TYPES` in Phase 3.
- `PersonalRecord` dataclass created but not yet consumed by `coach_tools` (returns plain dicts); migrate in Phase 3.
