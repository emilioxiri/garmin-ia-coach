# Test: find_activity

Busca actividades filtrando por día de la semana, fecha exacta, rango de distancia, tipo de actividad.

## Ejemplo 1: Actividad en día específico (español)
¿Cuál fue esa carrera que hice el viernes pasado? ¿Cuántos km fueron?

## Ejemplo 2: Actividad de cierta distancia
Busca mis carreras entre 5 y 10 km del último mes.

## Ejemplo 3: Actividad por tipo
Quiero ver mis entrenamientos de fuerza de la última semana.

## Ejemplo 4: Actividad en fecha específica
¿Qué corría el 15 de mayo de 2026?

## Ejemplo 5: Media maratón en fin de semana
¿Recuerdas cuando corría la media maratón? Creo que fue algún sábado...

## Tool Schema
```
{
  "weekday": "lunes|martes|miércoles|jueves|viernes|sábado|domingo",
  "date_iso": "YYYY-MM-DD",
  "min_distance_km": number,
  "max_distance_km": number,
  "activity_type": "running|trail_running|cycling|padel|strength_training",
  "only_runs": true|false,
  "days": integer (default: 30, max: 90)
}
```
