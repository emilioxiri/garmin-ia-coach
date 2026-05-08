# Coach quality — Fase 1 hotfixes

Tras desplegar la Fase 1 aparecieron dos bugs visibles en el chat:

## Bug 1 — Ritmo "5:79 min/km"

`slim_activity` emitía `pace_min_per_km` como decimal (`round(min, 2)`), p.ej. `5.79`. El LLM lo formateaba como `M:SS` y producía valores imposibles (segundos > 59).

**Fix.** `garmin_coach/context_builder.py` — `pace_min_per_km` ahora es string `"M:SS"` ya formateado, con redondeo entero de segundos y carry a la minutos siguiente cuando `seconds == 60`. El modelo solo tiene que copiarlo.

## Bug 2 — Asteriscos sueltos en negritas

`SYSTEM_PROMPT` pedía negrita con `*texto*` (estilo legacy Markdown de Telegram), pero `format_for_telegram` genera HTML y solo convierte `**texto**` → `<b>`. Con `parse_mode=HTML` los `*` simples pasan literales al chat.

**Fix.** `garmin_coach/coach.py` — la regla de formato ahora pide `**doble asterisco**`. Coincide con lo que el conversor entiende.

## Tests

- `test_slim_activity_computes_pace_min_per_km` actualizado a `"5:33"`.
- Nuevos: `test_slim_activity_pace_rolls_seconds_to_next_minute` (carry 60s → +1 min), `test_slim_activity_pace_pads_seconds_to_two_digits`.
- `test_slim_activity_running_keeps_distance_and_pace` actualizado a `"5:00"`.

Suite: **133 passed, 87.62% cov**.
