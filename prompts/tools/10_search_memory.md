# Test: search_memory

Busca en las notas guardadas con /memoria (lesiones, sensaciones, decisiones del entrenamiento).

## Ejemplo 1: Lesiones previas
¿Tengo registrada alguna lesión en mis notas?

## Ejemplo 2: Notas sobre sensaciones
¿Qué sensaciones registré sobre mi pierna la última vez que me dolió?

## Ejemplo 3: Decisiones de entrenamiento
Busca en mis notas qué decisiones tomé sobre entrenamientos intensos.

## Ejemplo 4: Específica
¿Hay algo anotado sobre mis rodillas?

## Ejemplo 5: Reciente
¿Cuáles fueron mis últimas anotaciones en memoria?

## Tool Schema
```
{
  "query": "string (búsqueda substring)",
  "limit": integer (default: 10, max: 50)
}
```

## Respuesta esperada
Array de notas con:
- note (texto de la nota)
- created_at (timestamp)

## Cómo crear notas
En el bot Telegram:
`/memoria <texto>` — guarda una nota con la fecha

Ejemplo:
`/memoria Sentí molestia en rodilla derecha después de la carrera`
