# Test: get_sleep_window

Devuelve registros de sueño (total, deep, REM, light, awake en horas, score, HR en reposo).

## Ejemplo 1: Sueño de esta semana
¿Cómo ha sido mi sueño esta semana? Dame el resumen diario.

## Ejemplo 2: Últimas dos semanas
Quiero ver mi patrón de sueño de los últimos 14 días.

## Ejemplo 3: Sueño del último mes
¿Cuál es mi promedio de horas de sueño en el último mes?

## Ejemplo 4: Sueño profundo
¿Cuántas horas de sueño profundo he tenido los últimos 7 días?

## Ejemplo 5: Récord de sueño
¿Cuándo fue la noche que más dormí profundamente?

## Tool Schema
```
{
  "days": integer (default: 7, max: 90)
}
```

## Respuesta esperada
Array de registros con:
- date
- total_hours
- deep_hours
- rem_hours
- light_hours
- awake_hours
- score
- resting_hr
