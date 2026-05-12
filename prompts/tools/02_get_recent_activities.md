# Test: get_recent_activities

Devuelve las actividades recientes de los últimos días, con filtros opcionales.

## Ejemplo 1: Actividades de esta semana
¿Qué he hecho esta semana?

## Ejemplo 2: Solo carreras del último mes
Muéstrame mis últimos entrenamientos de running en los últimos 30 días.

## Ejemplo 3: Actividades recientes, máximo 10
Dame mis 10 últimas sesiones.

## Ejemplo 4: Solo ciclismo
¿Cuántas sesiones de ciclismo hice los últimos 14 días?

## Ejemplo 5: Últimas actividades sin límite de tipo
Resúmeme qué he hecho en los últimos 3 días.

## Tool Schema
```
{
  "days": integer (default: 7, max: 90),
  "activity_type": "running|cycling|strength_training|padel",
  "only_runs": true|false,
  "limit": integer (default: 25, max: 25)
}
```
