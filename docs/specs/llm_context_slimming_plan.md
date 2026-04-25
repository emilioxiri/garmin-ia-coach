# Fix `context_length_exceeded` en coach LLM

## Context

Tras enriquecer el sync con métricas avanzadas (detalles completos de actividades + `summaryDTO` + splits + hrZones, además de respiration, spo2, stress, training_status, training_readiness, fitness_metrics, race_predictions, lactate_threshold, endurance_score), `get_context_for_ai(days=14)` genera un JSON enorme. Al inyectarlo entero en `CoachSession.chat` (`garmin_coach/coach.py:50-56`), Groq devuelve:

```
Error code: 400 - context_length_exceeded
'Please reduce the length of the messages or completion.'
```

Llama 3.3 70B versatile tiene ventana de 128K, pero el dump JSON con `indent=2` de 14 días × 20 actividades enriquecidas + 14 días de cada métrica wellness + listas de splits/hrZones se la come. Hay que filtrar el contexto que pasamos al modelo según lo que el atleta pida.

Archivos clave:
- `garmin_coach/coach.py:39-78` — `CoachSession.chat`, inyecta contexto en primer turno
- `garmin_coach/coach.py:84-120` — `generate_daily_briefing`, mismo problema
- `garmin_coach/db.py:21-106` — `get_context_for_ai`, fuente del bloat
- `garmin_coach/garmin_sync.py:144-167` — bloat origin: merge de `get_activity` + `summaryDTO` + splits + hrZones por actividad

---

## Opción A — Slimming + projection (mínimo esfuerzo, alto impacto)

**Idea.** Mantener el patrón actual de "dump up-front" pero adelgazar lo que se serializa: proyectar solo campos relevantes por tabla, agregar series numéricas (medias, max, tendencia 7d) en lugar de todos los registros, recortar splits/hrZones de actividades.

**Cambios.**

1. Nuevo módulo `garmin_coach/context_builder.py` con funciones por tabla:
   - `slim_activity(act)` → keep `activityId`, `activityName`, `startTimeLocal`, `activityType.typeKey`, `distance`, `duration`, `averageHR`, `maxHR`, `averageSpeed`, `calories`, `aerobicTrainingEffect`, `anaerobicTrainingEffect`, `trainingStressScore`, `vO2MaxValue`, `normPower` si existen. Drop `splits`, `hrZones`, `summaryDTO` raw, geo, polylines, etc.
   - `slim_sleep(s)`, `slim_hrv(h)`, `slim_bb(b)`, etc. — solo campos numéricos clave + fecha.
   - `aggregate_series(records, fields)` → calcular `mean`, `min`, `max`, `last`, `trend_7d` para series largas.
2. Reemplazar `get_context_for_ai` por wrapper que llame al builder. Pasar `compact: bool = True`.
3. Bajar `days=14` → `days=7` en `CoachSession.chat`.
4. Preservar memoria del entrenador (notas) tal cual, son cortas.

**Pros.** No cambia arquitectura. No requiere clasificador. Reduce tokens ~80%. Sirve también para briefings.

**Contras.** Si el atleta pregunta por un dato muy específico que se quitó (ej. "¿qué cadencia tuve en el rodaje del martes?"), no estará en contexto. Hay que elegir bien la proyección.

**Esfuerzo.** ~1 sesión. Tests unitarios de proyección y agregación.

---

## Opción B — Routing por intent (medio esfuerzo, contexto adaptativo)

**Idea.** Antes de llamar al LLM principal, clasificar la intención del mensaje del atleta (regex/keywords o llamada barata a Groq con `llama-3.1-8b-instant`) y construir contexto solo con las tablas relevantes.

**Cambios.**

1. Nuevo `garmin_coach/intent_router.py`:
   - `classify_intent(message: str) -> set[str]` → categorías: `recovery` (sueño, hrv, bb, stress, spo2), `training` (actividades, training_status, readiness), `performance` (fitness_metrics, race_predictions, lactate, endurance, vO2), `general` (todo, fallback compacto).
   - Implementación: keywords ES (dormir, descansar, rodar, entrenar, ritmo, marca, vO2, etc.) + opcional fallback a LLM clasificador con `max_tokens=20`.
2. `get_context_for_ai(days, categories: set[str])` filtra qué tablas devuelve.
3. `CoachSession.chat` llama al clasificador antes de inyectar contexto. Cachea intent del primer turno; turnos sucesivos reutilizan o re-clasifican si cambia tema.
4. Combinable con Opción A para slimming dentro de cada categoría.

**Pros.** Contexto rico cuando se necesita, mínimo cuando no. Latencia extra solo si usamos LLM clasificador (~200ms).

**Contras.** Clasificador puede equivocarse → atleta pregunta por sueño y solo metemos sueño, pero quería correlacionar con entreno. Mitigación: solapamiento de categorías + fallback `general`.

**Esfuerzo.** ~1.5 sesiones. Tests del clasificador + integración.

---

## Opción C — Tool calling nativo (más limpio, mayor refactor)

**Idea.** No inyectar datos up-front. Exponer al modelo herramientas (`get_recent_activities`, `get_sleep_summary`, `get_hrv_trend`, `get_fitness_snapshot`, `get_activity_detail(id)`, `search_memory`) y dejar que pida lo que necesite vía Groq tool use.

**Cambios.**

1. Definir `tools` en `garmin_coach/coach.py` siguiendo schema OpenAI/Groq:
   ```python
   tools = [
       {"type": "function", "function": {
           "name": "get_recent_activities",
           "description": "Devuelve resumen de actividades de los últimos N días",
           "parameters": {"type": "object", "properties": {
               "days": {"type": "integer", "default": 7},
               "activity_type": {"type": "string", "description": "running, cycling, swimming, ..."}
           }}
       }},
       # ... una por tabla/agregación
   ]
   ```
2. Loop en `chat`: si `response.choices[0].message.tool_calls`, ejecutar y reinjectar como `role: tool`. Repetir hasta sin tool_calls (max ~5 iteraciones).
3. Implementar handlers en `garmin_coach/db.py` o nuevo `garmin_coach/coach_tools.py` que devuelvan dicts pequeños.
4. System prompt actualizado: "Tienes herramientas para consultar datos. Úsalas cuando necesites información concreta."
5. `generate_daily_briefing` puede seguir con dump compacto (Opción A) o también usar tools.

**Pros.** Solución correcta a largo plazo. Escala con cualquier nuevo tipo de dato sin tocar el flujo de chat. Solo se cargan los datos que el modelo realmente quiere ver. Costos bajan.

**Contras.** Más complejidad. Llama 3.3 70B soporta tool use pero a veces alucina o no las invoca. Latencia variable (1-3 round-trips). Necesita tests de loop de tools.

**Esfuerzo.** ~2-3 sesiones. Tests de cada tool + del loop con mocks.

---

## Recomendación

**A corto plazo (esta semana): Opción A.** Desbloquea ya. Bajo riesgo. Compatible con B/C después.

**A medio plazo: Opción C** sobre la base de A (las funciones de slimming se reutilizan como respuesta de las tools).

**Opción B** solo si tras A los tokens siguen rozando el límite y no quieres aún meterte con tool calling.

## Verificación

- Test unitario en `garmin_coach/tests/test_context_builder.py`: comprobar que `slim_activity` sólo devuelve campos esperados, agregación correcta de series.
- Medir tokens del payload antes/después con `tiktoken` o estimación `len(json) / 4`.
- Smoke test: `python main.py` → enviar mensaje al bot → verificar respuesta sin error 400.
- Cobertura ≥85% según `CLAUDE.md`.
