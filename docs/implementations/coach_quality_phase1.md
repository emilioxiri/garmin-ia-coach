# Coach quality — Fase 1 (quick wins)

## Contexto

Tras observar respuestas pobres del bot (ver `docs/bot-response-examples.md`), se detectaron tres bugs concretos:

1. **Selección de actividad equivocada.** El atleta preguntó por su media maratón del viernes (1:39:43, 21,1 km) y el bot respondió con métricas de un rodaje fácil de 5,5 km. El modelo no tenía forma de filtrar por fecha/distancia y cogió la primera actividad.
2. **Confusión `aerobicTrainingEffect` ↔ VO2max.** Briefing matinal habló de "VO2MAX de 5.0", confundiendo Training Effect (escala 0-5) con VO2max real.
3. **Sin fechas humanas.** Solo `startTimeLocal` ISO; el modelo no podía mapear "viernes" → fecha sin esfuerzo extra.

Plan global de mejoras en `docs/specs/llm_context_slimming_plan.md` (Opción C, tool calling). Esta entrega cubre **Fase 1**: quick wins sin refactor de arquitectura.

## Cambios

### `garmin_coach/context_builder.py`

#### `slim_activity` — campos derivados nuevos

- `date` (YYYY-MM-DD) y `weekday` (lunes…domingo) parseados desde `startTimeLocal`.
- `distance_km` (m → km, 2 decimales).
- `pace_min_per_km` calculado desde `averageSpeed` (m/s).
- Flags `is_run` (tipos de carrera) e `is_long_run` (≥ 15 km).
- Renombre `aerobicTrainingEffect` → `aerobic_te` y `anaerobicTrainingEffect` → `anaerobic_te` (vía `_FIELD_RENAMES`) para que el modelo no los etiquete como VO2max.

Nuevas constantes módulo: `_WEEKDAYS_ES`, `_RUN_TYPES`, `_FIELD_RENAMES`, `LONG_RUN_THRESHOLD_M = 15000`, `NOTABLE_RUNS_LIMIT = 3`.

Nuevo helper `_parse_local_datetime()` parsea formato Garmin (`YYYY-MM-DD HH:MM:SS`) sin lanzar excepciones.

#### `slim_fitness_metrics` — alias `vo2max_running`

Devuelve `{date, vo2max, vo2max_running}`. El alias es redundante semánticamente pero deja explícito al modelo que el VO2max real corre por aquí.

#### `build_context` — `notable_runs` + cap subido

- Default `max_activities` 10 → **15**.
- Nueva clave `notable_runs`: top-3 carreras por `distance_km`, calculadas sobre TODAS las actividades de la ventana (no solo las que pasan el cap), de modo que una media maratón aislada en el día 14 sigue presente aunque queden por delante 15+ rodajes cortos más recientes.

### `garmin_coach/coach.py`

`SYSTEM_PROMPT` ampliado con bloque "REGLAS ESTRICTAS":

- VO2max real solo en `fitness_metrics.vo2max_running` / `.vo2max`.
- `aerobic_te` / `anaerobic_te` son Training Effect (0-5), nunca VO2max.
- Para preguntas referidas a una carrera concreta (día semana, distancia, MMP, PB, half/maratón), buscar primero en `notable_runs`, después en `activities`, casando por `weekday` / `date` / `distance_km`. Verificar `duration` y `distance_km` antes de comentar.
- Si no hay coincidencia con la referencia del atleta, decirlo explícitamente. No inventar ni mezclar métricas.
- Duración en HH:MM:SS o MM:SS. Ritmo en `pace_min_per_km` (min/km), no m/s.

## Tests

`garmin_coach/tests/test_context_builder.py` añade 14 tests nuevos:

- `slim_activity`: extracción de `date`/`weekday`, manejo de timestamp inválido, `distance_km`, `pace_min_per_km`, ritmo omitido si speed=0, flags `is_run`/`is_long_run` en runs y no-runs, rename de TE.
- `slim_fitness_metrics`: alias `vo2max_running` correcto.
- `build_context`: `notable_runs` ordena descendente por distancia y top-3, ignora no-runs, default cap 15, `notable_runs` puede incluir actividades fuera del cap.

Resultado suite: **122 tests passed, 87.15% coverage** (umbral mínimo 85%, `pyproject.toml`).

## Verificación

```bash
source .venv/bin/activate
python -m pytest garmin_coach/tests/ --cov=garmin_coach
ruff check garmin_coach/context_builder.py garmin_coach/coach.py
```

Smoke test recomendado en Docker tras desplegar:

```bash
make hard-restart
# Esperar al sync y al briefing
# Repetir las preguntas de docs/bot-response-examples.md y comprobar:
#   - El bot NO llama VO2max al aerobic_te.
#   - "carrera del viernes" / "media maratón" → identifica la actividad
#     correcta por weekday/distance_km, no un rodaje aleatorio.
```

## Próximos pasos

Fase 2 (Opción C del plan original): tool calling nativo de Groq con handlers tipo MCP contra TinyDB (`get_activities`, `find_activity`, `get_sleep_window`, `get_fitness_snapshot`, etc.). Ver `docs/specs/llm_context_slimming_plan.md`.

Fase 3: dejar la tabla `activities` fuera de `purge_old_data` para que las marcas históricas (medias, maratones) no se borren tras 30 días.
