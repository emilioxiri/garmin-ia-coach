# Refactor OOP Fase 4 — Garmin client + MFA handler + SyncService

## Objetivo

Encapsular la autenticación con Garmin Connect, el flujo MFA y la orquestación del sync en clases inyectables. Eliminar los cuatro globales mutables de `garmin_sync.py` (`_bot_app`, `_bot_loop`, `_mfa_event`, `_mfa_code`).

## Clases nuevas

### `infrastructure/garmin/mfa_handler.py` — `MFAHandler`

Encapsula el flujo MFA completo sin globales:

- `__init__(timeout_seconds=300)` — crea su propio `threading.Event` interno.
- `set_notifier(callable)` — registra el callback para notificar al usuario (inyectado por `garmin_sync.py` shim y en Fase 5 por `TelegramBotApp._on_startup`).
- `notify_user(message)` — invoca el notifier; swallows excepciones para no bloquear el hilo de sync.
- `provide_code(code)` — llamado por el comando `/mfa`; guarda el código y dispara el evento.
- `wait_for_code()` — bloquea hasta que hay código o expira el timeout; limpia el estado tras consumir; lanza `TimeoutError` en timeout.
- `clear()` — resetea evento y código (llamado al inicio de `authenticate()` para evitar códigos obsoletos).

### `infrastructure/garmin/client.py` — `GarminClient`

Envuelve `garminconnect.Garmin` con sesión persistida y MFA:

- `__init__(settings, mfa_handler)` — recibe ambas dependencias; no hace I/O en constructor.
- `authenticate()` — lazy: devuelve instancia cacheada si ya autenticada; intenta reutilizar sesión de disco; hace full login si no existe o ha expirado; persiste nueva sesión.
- `reset()` — invalida cache y borra fichero de sesión del disco.

### `infrastructure/garmin/data_fetcher.py` — `GarminDataFetcher`

Un método público por endpoint del API de Garmin. Sin upserts — sólo fetch.

- `__init__(garmin: Garmin)` — recibe instancia autenticada.
- Métodos: `fetch_activities`, `fetch_activity_detail`, `fetch_sleep`, `fetch_hrv`, `fetch_body_battery`, `fetch_training_status`, `fetch_training_readiness`, `fetch_respiration`, `fetch_spo2`, `fetch_stress`, `fetch_fitness_metrics`, `fetch_race_predictions`, `fetch_lactate_threshold`, `fetch_endurance_score`.
- Todos usan `_safe()` interno — cualquier excepción devuelve `None`/`[]` y loguea en DEBUG.

### `services/sync_service.py` — `SyncService` + `SyncSummary`

Orquesta el sync completo: auth → fetch → upsert → purge → log.

- `__init__(garmin_client, fetcher_factory, repositories, sync_log_repo, settings, purge_days=60)`
- `run() -> SyncSummary` — flujo:
  1. `garmin_client.authenticate()` → obtiene `Garmin` autenticado
  2. `fetcher_factory(garmin)` → crea `GarminDataFetcher`
  3. `compute_sync_window(repos, days_history)` → determina ventana temporal
  4. `_purge_wellness(purge_days)` → borra wellness antiguo (activities no se borran)
  5. Fetch + upsert de actividades con merge de detalles
  6. Fetch + upsert de wellness por día para cada tabla
  7. Fetch + replace de fitness snapshots (metrics/predictions/lactate/endurance)
  8. `sync_log.log(summary.as_dict())`
  9. Devuelve `SyncSummary` frozen dataclass

`SyncSummary` — dataclass frozen con contadores por tabla + `purged` dict + `started_at`/`finished_at` ISO timestamps + `as_dict()`.

### `services/sync_helpers.py` — funciones puras

- `daterange(start_iso, end_iso)` — generador de fechas YYYY-MM-DD inclusive.
- `compute_sync_window(repositories, default_days)` — si DB vacía → últimos N días; si no → desde la fecha más reciente en activities/sleep/hrv/body_battery hasta hoy.
- `merge_activity_details(activities, detail_fetcher)` — merge de detalles en cada actividad; flattea `summaryDTO`; no sobreescribe con None; non-fatal.

## Eliminación de globales

Los cuatro globales de `garmin_sync.py` original desaparecen del módulo de lógica:

| Global eliminado | Reemplazado por |
|---|---|
| `_mfa_event` (threading.Event) | `MFAHandler._event` |
| `_mfa_code` | `MFAHandler._code` |
| `_bot_app` | Referencia inyectada al notifier de `MFAHandler` |
| `_bot_loop` | Referencia inyectada al notifier de `MFAHandler` |

## Shim residual `garmin_sync.py` (Fase 5 lo eliminará)

`garmin_sync.py` se convirtió en shim delgado (~80 líneas). Mantiene la API pública que `bot.py` y `legacy_bridge.py` esperan pero delega internamente al `Container`:

- `set_bot_app(app)` → registra notifier en `container.mfa_handler`
- `set_event_loop(loop)` → captura loop para el notifier (Fase 5 lo hace en `TelegramBotApp._on_startup`)
- `provide_mfa_code(code)` → delega a `container.mfa_handler.provide_code()`
- `sync_all(email, password, days)` → delega a `container.sync_service.run()`

El `Container` se instancia lazily en `_get_container()` la primera vez que se llama cualquiera de estas funciones (evita doble inicialización si el Container ya fue creado por `app.container`).

## Container (`app/container.py`)

`_build_mfa_handler()`, `_build_garmin_client()`, `_build_sync_service()` añadidos. El `Container` ahora cablea:

```
MFAHandler → GarminClient(settings, mfa) → SyncService(client, fetcher_factory, repos, sync_log, settings)
```

## Tests

| Fichero | Tests |
|---|---|
| `tests/infrastructure/garmin/test_mfa_handler.py` | 7 tests (provide/wait, timeout, notifier, clear) |
| `tests/infrastructure/garmin/test_client.py` | 6 tests (cache, full login, session reuse, session expired, MFA flow, reset) |
| `tests/infrastructure/garmin/test_data_fetcher.py` | 28 tests (happy path + exception → None por cada endpoint) |
| `tests/services/test_sync_helpers.py` | 10 tests (daterange, compute_sync_window, merge_activity_details) |
| `tests/services/test_sync_service.py` | 15 tests (happy path, activities, wellness, purge, fitness, window) |

Tests legacy eliminados: `tests/test_garmin_sync.py` (15 tests que testeaban símbolos que ya no existen: `_mfa_event`, `Garmin`, `SESSION_PATH`, `get_garmin_client`, `get_db`).

El test `test_authenticate_mfa_flow` usa `threading.Event` de sincronización para evitar la race condition: el thread proveedor espera a que `_login_needs_mfa` empiece antes de llamar a `provide_code`.

**Resultado: 574 passed, 95.50% coverage.**

## Deuda restante para Fase 5

- `garmin_sync.py` sigue existiendo como shim (marcado para eliminación).
- `bot.py` legacy sigue usándolo (`set_bot_app`, `set_event_loop`, `provide_mfa_code`).
- `legacy_bridge.py` sigue en pie; el scheduler llama a `sync_all` del shim.
- Los globales `_bot_app` y `_bot_loop` en el shim desaparecen cuando `TelegramBotApp._on_startup` capture el asyncio loop y lo entregue directamente a `MFAHandler.set_notifier`.
- `bot.py`, `coach.py`, `coach_tools.py`, `context_builder.py`, `db.py` también se eliminan en Fase 5.
