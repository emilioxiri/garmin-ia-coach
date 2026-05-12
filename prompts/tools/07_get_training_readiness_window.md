# Test: get_training_readiness_window

Devuelve el indicador de disponibilidad para entrenar (score, nivel, feedback, influencia del sueño y HRV).

## Ejemplo 1: ¿Puedo entrenar hoy?
¿Cuál es mi training readiness hoy? ¿Puedo hacer un entrenamiento intenso?

## Ejemplo 2: Análisis de esta semana
Muéstrame mi readiness diaria esta semana. ¿Qué días eran mejores para entrenar?

## Ejemplo 3: Relación con sueño
Veo que mi readiness ha bajado, ¿cuánto influye mi sueño?

## Ejemplo 4: Historial
¿Cuáles fueron mis mejores días de readiness el mes pasado?

## Ejemplo 5: Comparativa
¿Cómo fue mi readiness hace dos semanas versus ahora?

## Tool Schema
```
{
  "days": integer (default: 7, max: 90)
}
```

## Respuesta esperada
Array de registros con:
- date
- score (0-100)
- level (Low/Medium/High)
- feedback (texto recomendación)
- sleepScore (influencia del sueño)
- hrvFactorPercent (influencia del HRV)
