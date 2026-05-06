# Non-distance activity filtering (padel, fuerza, yoga…)

## Problema

Cuando el atleta registraba en Garmin una sesión de **padel** (o **strength training**, yoga, escalada…), el bot devolvía respuestas absurdas como:

> Te has entrenado hoy con una sesión de pádel, con una duración de **1 hora y 26 minutos (5212.53 segundos)**, y una **distancia recorrida de 0.19 km**. La intensidad ha sido moderada, con un **ritmo de 416.67 min/km**.

Tres cosas mal:

1. Distancia y ritmo no aplican a un deporte de raqueta — Garmin entrega 190 m / 0.04 m·s⁻¹ como ruido del GPS interior.
2. El modelo citaba la duración en **segundos crudos** ("5212.53 segundos") encima del HMS.
3. Cadencia/potencia/elevación/sweat-loss tampoco tienen sentido en padel o pesas.

## Solución

Filtrado a nivel de datos **antes** del LLM (no fiarse sólo del prompt) en `garmin_coach/context_builder.py`:

### `_NON_DISTANCE_TYPES`
Conjunto de `activityType.typeKey` de Garmin sin distancia significativa:

```
padel, tennis, pickleball, squash, racquet_ball, racquetball, table_tennis,
badminton, boxing, mixed_martial_arts, strength_training, indoor_strength_training,
yoga, pilates, indoor_climbing, bouldering, rock_climbing, hiit, cardio,
stretching, breathwork, meditation, mobility, gym, floor_climbing, stair_climbing
```

### `_NON_DISTANCE_DROP_FIELDS`
Campos eliminados de `slim_activity` cuando `type_key ∈ _NON_DISTANCE_TYPES`:

```
distance, averageSpeed, maxSpeed,
avgStrideLength, avgVerticalRatio, avgVerticalOscillation, avgGroundContactTime,
averageRunningCadenceInStepsPerMinute, maxRunningCadenceInStepsPerMinute,
avgPower, maxPower,
elevationGain, elevationLoss, minElevation, maxElevation,
estimatedSweatLoss
```

`distance_km` y `pace_min_per_km` tampoco se calculan para estos tipos.

### `duration_hms` siempre, segundos crudos nunca

`slim_activity` reemplaza `duration`/`movingDuration`/`elapsedDuration` en segundos por sus equivalentes `*_hms` (`HH:MM:SS` o `MM:SS` según corresponda). Helper `_format_duration(seconds)` calcula el formato; los campos en segundos se eliminan del JSON que ve el LLM, así no puede citarlos por error.

Aplica a TODAS las actividades (running incluido) — antes el running también exponía `duration: 3000.0` y el modelo a veces traducía mal.

### Prompt

`SYSTEM_PROMPT` (`garmin_coach/coach.py`) refuerza la regla:

- "Duración: usa SIEMPRE el campo `duration_hms`. NUNCA cites duración en segundos ni en decimales tipo '5212.53 segundos'."
- "Actividades sin distancia (padel, tenis, fuerza, yoga, escalada, HIIT, gimnasio…): NO menciones distancia, ritmo, velocidad, cadencia, potencia ni dinámica de carrera. Limítate a duración (`duration_hms`), frecuencia cardíaca (`averageHR`/`maxHR`) y carga/intensidad (`activityTrainingLoad`, `aerobic_te`, `trainingEffectLabel`, minutos moderados/vigorosos)."

## Tests añadidos (`garmin_coach/tests/test_context_builder.py`)

- `test_slim_activity_replaces_duration_seconds_with_hms` — duración 5212.53 s → `"1:26:53"`, sin segundos crudos.
- `test_slim_activity_short_duration_uses_mm_ss` — 754 s → `"12:34"`.
- `test_slim_activity_converts_all_duration_variants` — `duration`/`movingDuration`/`elapsedDuration` los tres convertidos.
- `test_slim_activity_padel_drops_distance_and_pace` — caso real del bug del usuario, comprueba que distancia/velocidad/ritmo desaparecen y duración/HR/intensidad se conservan.
- `test_slim_activity_strength_drops_running_dynamics_and_power` — fuerza también limpia stride/power/elevación/sweat.
- `test_slim_activity_running_keeps_distance_and_pace` — control: en running sigue calculándose `distance_km` y `pace_min_per_km`.

131 tests verde, 87.48 % cobertura.

## Notas y siguientes pasos

- Si Garmin introduce nuevos `typeKey` (p. ej. `paddle_tennis`), basta añadirlo a `_NON_DISTANCE_TYPES`.
- `cycling`/`swimming` NO están en el set: tienen distancia y ritmo legítimos.
- `other` ambiguo no se ha incluido para no perder datos en actividades sin clasificar.
