# Test: get_activity_detail

Obtiene los detalles completos de una actividad específica por su ID.

## Uso común
Después de usar `find_activity`, puedes pedir más detalles de una carrera específica.

## Ejemplo 1: Ver detalles de una carrera encontrada
Dime más detalles de la carrera del viernes, ¿cuál fue mi ritmo cardíaco medio?

## Ejemplo 2: Análisis profundo
Quiero revisar en detalle esa sesión de entrenamiento largo del mes pasado.

## Ejemplo 3: Confirmar métricas
Recuerdo esa carrera, pero necesito ver el ritmo exacto y elevación.

## Tool Schema
```
{
  "activity_id": "string" (required)
}
```

## Nota
El `activity_id` se obtiene de las respuestas de `find_activity` o `get_recent_activities`.
