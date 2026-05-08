# Coach quality — Fase 3: Personal records + activities preserved

## Contexto

Fase 1 y 2 mejoraron contexto y trazabilidad pero quedaba un agujero: `purge_old_data(days=30)` borraba la tabla `activities` cada sync. Marcas históricas (mejor 10K del año pasado, primera media, maratón) se perdían. Además el coach no tenía forma directa de localizar el PB del atleta.

## Cambios

### `garmin_coach/db.py`

`purge_old_data` ya no toca `activities`. Sólo limpia las tablas wellness (`sleep`, `hrv`, `body_battery`, `training_status`, `training_readiness`, `respiration`, `spo2`, `stress`). El contador `removed["activities"]` queda en `0` y el log de sync sigue mostrando la entrada para preservar el shape del summary.

Justificación:
- Las actividades son pequeñas (~10-30 KB cada una con detalles) y un atleta serio no acumula más de 1-2 al día. 5 años de historial son <50 MB en TinyDB.
- Las wellness sí son redundantes (1 entrada/día/tabla) y el LLM nunca consulta sleep de hace 6 meses.

### `garmin_coach/coach_tools.py`

Nueva tool `get_personal_records()`. Sin tabla nueva: itera la tabla `activities` y calcula al vuelo.

Algoritmo:
- Para cada distancia canónica `_PR_DISTANCES` (1K, 5K, 10K, half_marathon=21097m, marathon=42195m), busca la actividad de tipo running con `distance ∈ [target ± tolerance]` y `duration > 0` mínima.
- Tolerancias asimétricas: 1K ±5%, 5K/10K ±3%, HM/M ±2%. Suficiente para absorber drift de Garmin sin contar una carrera de 19 km como media.
- Devuelve `{activityId, date, distance_km, duration_hms, pace_min_per_km, averageHR}` por distancia.
- Además calcula `longest_run` (carrera de mayor distancia en la tabla, ignorando ciclismo etc.) usando `slim_activity` para reutilizar la proyección.
- Resultado final: `{records: {1K, 5K, 10K, half_marathon, marathon}, longest_run, activities_evaluated}`.

`SYSTEM_PROMPT` añade una línea: cuando el atleta pregunte por PB / mejor marca / récord / tirada más larga, llamar `get_personal_records`.

### Schema spec

`TOOLS_SPEC` añade entrada para `get_personal_records` (sin parámetros). `HANDLERS` la registra. `dispatch_tool_call` la rutina sin cambios.

## Tests

`test_db.py`:
- `test_purge_keeps_old_activities` — dos actividades de hace 400 días y 29 días, ambas sobreviven.
- `test_purge_returns_removed_counts` actualizado: `removed["activities"] == 0`, las actividades quedan en DB.

`test_coach_tools.py` (10 nuevos):
- `_finds_best_5k` — entre dos 5K elige la más rápida.
- `_half_marathon_tolerance` — 21050 m cuenta como HM (dentro de ±2%).
- `_rejects_distance_outside_tolerance` — 19 km no es media maratón.
- `_ignores_non_runs` — un cycling de 5 km no llena el slot 5K.
- `_includes_pace` — `pace_min_per_km` formateado "M:SS".
- `_longest_run` — coge la carrera más larga, ignora ciclismo aunque sea mayor.
- `_empty_db` — todos los slots None, `activities_evaluated=0`.
- `_ignores_activities_with_no_distance_or_duration` — no rompe.
- `_zero_duration_skipped`.
- `_picks_lowest_duration_on_ties` — entre tres 5K elige el de menos duración.
- `_listed_in_handlers_and_spec` — handler y spec registrados.

Suite: **200 tests passed, 89.81% coverage**.

## Verificación

```bash
source .venv/bin/activate
python -m pytest garmin_coach/tests/ --cov=garmin_coach
ruff check garmin_coach/coach_tools.py garmin_coach/db.py
```

Smoke test:
```bash
make hard-restart
# Preguntar: "¿cuál es mi mejor 10K?"
#   → tool call get_personal_records → modelo cita el activityId, fecha, ritmo.
# Preguntar: "¿cuál ha sido mi tirada más larga?"
#   → mismo tool call, sección longest_run.
# Verificar: el siguiente sync NO borra actividades antiguas (ver counter activities=0
#   en el log JSON de sync_log).
```

## Próximos pasos (no urgente)

- Cachear PRs entre syncs si la tabla crece a >5000 actividades (ahora se recalcula en cada llamada).
- Añadir PRs específicos no estándar (ascenso máximo en una sesión, mejor segmento de 1 km dentro de carreras largas) — requiere splits crudos que ahora mismo se descartan en `slim_activity`. Decisión de coste/beneficio cuando el atleta lo pida.
