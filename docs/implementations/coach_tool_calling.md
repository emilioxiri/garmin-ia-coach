# Coach quality — Fase 2: Tool calling (MCP-style)

## Contexto

Tras la Fase 1 (`docs/implementations/coach_quality_phase1.md`) el dump compacto resolvía la mayoría de preguntas, pero seguía habiendo casos donde el coach inventaba datos: el atleta nombraba una sesión que estaba fuera del cap (`max_activities=15`) o más allá de la ventana de 7 días, y el modelo mezclaba métricas de otra actividad. La Opción C del plan original (`docs/specs/llm_context_slimming_plan.md`) propone exponer la base de datos como herramientas de function calling para que el LLM consulte sólo lo que necesita.

## Cambios

### `garmin_coach/coach_tools.py` (nuevo)

Nueve tools, todas backend en TinyDB y devolviendo dicts/listas pequeñas (a través de los `slim_*` ya existentes en `context_builder`).

| Tool | Argumentos | Para qué |
|------|------------|----------|
| `find_activity` | `weekday`, `date_iso`, `min_distance_km`, `max_distance_km`, `activity_type`, `only_runs`, `days` | Localizar sesiones concretas ("media maratón del viernes", "rodaje del 5 de mayo"). |
| `get_recent_activities` | `days`, `activity_type`, `only_runs`, `limit` | Listar entrenamientos recientes con filtros. |
| `get_activity_detail` | `activity_id` | Profundizar en una actividad por ID. |
| `get_sleep_window` | `days` | Sueño diario en horas + score + restingHR. |
| `get_hrv_window` | `days` | HRV diaria. |
| `get_body_battery_window` | `days` | Body Battery max/min. |
| `get_training_readiness_window` | `days` | Training readiness con score, level, feedback. |
| `get_fitness_snapshot` | (sin args) | VO2max running, race predictions (5K/10K/HM/M), umbral lactato, endurance score. |
| `search_memory` | `query`, `limit` | Notas guardadas con `/memoria` (lesiones, sensaciones). |

Defensivo:
- `MAX_WINDOW_DAYS = 90` y `MAX_ACTIVITIES_RESULT = 25` capean lo que el LLM puede pedir.
- `dispatch_tool_call(name, args)` envuelve cada handler con manejo de `TypeError` (args inválidos) y `Exception` genérico, devolviendo siempre un dict serializable a JSON.
- `_WEEKDAYS_ES_INDEX` acepta acentos y sin acento (`sábado`/`sabado`, `miércoles`/`miercoles`).

### `garmin_coach/coach.py`

`CoachSession.chat` ahora ejecuta un loop de tool calling:

1. Inyecta el dump compacto en el primer turno (sin cambios respecto a Fase 1).
2. Llama a Groq con `tools=TOOLS_SPEC` y `messages=[system] + history`.
3. Si la respuesta tiene `tool_calls`, serializa el mensaje del asistente en `history` (con sus `tool_calls`), ejecuta cada handler vía `dispatch_tool_call`, añade los resultados como `role: tool` y vuelve a llamar al modelo. Repite hasta `MAX_TOOL_ITERATIONS = 5`.
4. Cuando llega texto sin más `tool_calls`, lo devuelve como respuesta y trimea el historial.

Nuevos helpers:
- `_serialize_assistant_message(msg)` convierte el mensaje devuelto por el SDK de Groq a la forma `{"role": "assistant", "content", "tool_calls": [...]}` que admite el endpoint en turnos posteriores.
- `_execute_tool_calls(tool_calls)` parsea `arguments` (JSON), llama al dispatcher y serializa el resultado a string JSON antes de devolverlo como `role: tool`.
- `_trim_history(history, max_len=40)` mantiene el cap de 40 mensajes pero descarta `role: tool` huérfanos al inicio de la ventana (un `tool` sin su `assistant` previo rompe el endpoint).

`SYSTEM_PROMPT` actualizado con sección "HERRAMIENTAS (function calling)" que lista las tools y cuándo usarlas, y refuerza la regla "no inventes" remitiendo al uso de `find_activity` antes de decir "no tengo datos".

`generate_daily_briefing` NO usa tools: sigue el patrón de dump único (es un mensaje sin interacción posterior, no compensa el round-trip extra).

## Tests

`garmin_coach/tests/test_coach_tools.py` (33 tests):

- `find_activity`: filtros por weekday (con/sin acento, desconocido), distancia min/max, fecha exacta, tipo, only_runs, ventana, cap de resultados, proyección slim.
- `get_recent_activities`: orden, only_runs, limit.
- `get_activity_detail`: match y none.
- Window helpers (sleep/hrv/body_battery/training_readiness): filtro por cutoff, slim, orden.
- `get_fitness_snapshot`: pick latest + db vacía.
- `search_memory`: substring, query vacía, limit.
- `dispatch_tool_call`: routing, tool desconocida, args inválidos, excepción del handler, args None.
- `TOOLS_SPEC`: cada handler tiene spec, schema bien formado.

`garmin_coach/tests/test_coach.py` añade tests del loop:

- `test_chat_executes_tool_call_then_returns_final` — primera llamada devuelve tool_call, segunda devuelve texto.
- `test_chat_passes_tools_spec_to_groq`.
- `test_chat_appends_tool_messages_to_history` — `role: tool` con `tool_call_id` correcto.
- `test_chat_handles_invalid_tool_arguments_json` — JSON malformado fallback a `{}`.
- `test_chat_stops_after_max_tool_iterations` — corta el bucle, log de warning.
- `test_chat_serializes_assistant_tool_calls_in_history`.
- `test_chat_does_not_pass_tools_to_briefing`.
- `test_trim_history_drops_orphan_tool_messages`.

Helpers de mock (`make_tool_call`, `make_groq_with_responses`, `tool_response`, `final_response`) construyen secuencias de respuestas SDK-like.

Resultado suite: **175 tests passed, 89.17% coverage**.

## Verificación

```bash
source .venv/bin/activate
python -m pytest garmin_coach/tests/ --cov=garmin_coach
ruff check garmin_coach/coach.py garmin_coach/coach_tools.py
```

Smoke test recomendado:

```bash
make hard-restart
# Esperar al sync
# Preguntar: "¿qué hice el viernes pasado?"
#   → el modelo debería invocar find_activity(weekday="viernes")
# Preguntar: "¿cuál es mi VO2max actual?"
#   → get_fitness_snapshot
# Preguntar por una sesión de hace 20 días → find_activity con date_iso
```

## Hotfix: salvage `tool_use_failed`

Llama 3.3 versatile a veces emite la respuesta en texto y a continuación una llamada a función mal formada, p.ej.:

```
El jueves hiciste un rodaje de 8.31 km a 5:41 min/km.

<function=find_activity{"weekday": "jueves"}</function>
```

Groq rechaza esa respuesta con `400 tool_use_failed` y mete el texto en `body.error.failed_generation`. Antes el bot devolvía el 400 al usuario.

Aparecen dos variantes:

1. **Prosa + tag.** Modelo escribe respuesta y luego llama a la función.
2. **Sólo tag.** Modelo emite la llamada como texto plano sin prosa.

Solución dos pasos:

- `_failed_generation_payload(error)` valida que sea un `tool_use_failed` y devuelve el string `failed_generation`, o `None`.
- `_parse_function_tag(text)` con regex `<function=NAME(\(args\)|args)</function>` extrae `(name, args_dict)` cuando el JSON es válido. Acepta variante con paréntesis `<function=name({...})</function>` y sin (`<function=name{...}</function>`).
- `_salvage_tool_use_failed(error)` (fallback prosa): elimina los tags y devuelve el texto restante o `None`.
- En `CoachSession.chat`, la llamada a Groq dentro del loop está envuelta en `try/except BadRequestError`. Orden:
  1. Si `_parse_function_tag` extrae una tool call: se sintetiza un mensaje `assistant` con `tool_calls=[{id: "salvaged_<n>", ...}]`, se ejecuta vía `dispatch_tool_call`, se inyecta `role: tool` con el resultado y `continue` el loop. El siguiente turno el modelo recibe el resultado normalmente y produce la respuesta.
  2. Si no, intenta `_salvage_tool_use_failed` para recuperar prosa.
  3. Si nada, propaga al fallback "❌".
- `SYSTEM_PROMPT` añade bloque "REGLAS DE TOOL USE (CRÍTICAS)" prohibiendo emitir texto antes/después de una llamada y prohibiendo escribir tags `<function=…>` en el contenido. Reduce la frecuencia del bug a futuro.

Tests añadidos en `test_coach.py` (~13):
- `_salvage_tool_use_failed`: feliz path, código distinto, sin failed_generation, sólo tag.
- `_parse_function_tag`: con paréntesis, sin paréntesis, args vacíos, prosa alrededor, no match, JSON inválido.
- `chat`: recupera prosa, recupera tool call con paréntesis, recupera tool call sin paréntesis, propaga otros 400.

## Próximos pasos

Fase 3 (pendiente): excluir la tabla `activities` de `purge_old_data` para preservar marcas históricas más allá de 30 días, e introducir `personal_records` calculadas/sincronizadas. Con tool calling ya en su sitio, el coach podrá pedir directamente PRs vía un nuevo `get_personal_records` cuando exista.
