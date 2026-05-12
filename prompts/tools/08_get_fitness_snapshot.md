# Test: get_fitness_snapshot

Devuelve un snapshot agregado de tu estado actual: VO2max, predicciones de carrera, lactato y endurance score.

## Ejemplo 1: Mi estado de forma actual
¿Cómo estoy de forma? Dame un resumen de mis métricas actuales.

## Ejemplo 2: Predicciones de carrera
¿Cuál es el mejor tiempo que podría hacer en una carrera de 5K según mis métricas?

## Ejemplo 3: VO2max
¿Cuál es mi VO2max actual? ¿Ha mejorado?

## Ejemplo 4: Umbrales
Dime mi umbral de lactato y cómo afecta mi rendimiento.

## Ejemplo 5: Resistencia
¿Qué tal está mi endurance score? ¿Estoy en buena forma para largas distancias?

## Tool Schema
```
{
  (sin parámetros)
}
```

## Respuesta esperada
Objeto con:
- fitness_metrics (VO2max, etc.)
- race_predictions (5K, 10K, media maratón, maratón)
- lactate_threshold
- endurance_score
