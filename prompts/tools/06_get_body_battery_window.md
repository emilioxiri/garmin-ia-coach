# Test: get_body_battery_window

Devuelve Body Battery diario (máximo y mínimo), indicador de energía.

## Ejemplo 1: Body Battery esta semana
¿Cómo está mi body battery? ¿Tengo energía suficiente para entrenar?

## Ejemplo 2: Días bajos de energía
¿Cuáles fueron mis días con body battery más bajo en el mes?

## Ejemplo 3: Recuperación
Ayer estaba agotado, ¿cuál fue mi body battery ese día?

## Ejemplo 4: Tendencia
¿Ha mejorado mi body battery en los últimos 14 días?

## Ejemplo 5: Planificación
Viendo mi body battery, ¿cuándo debería hacer un entrenamiento fuerte?

## Tool Schema
```
{
  "days": integer (default: 7, max: 90)
}
```

## Respuesta esperada
Array de registros con:
- date
- max (máxima energía del día)
- min (mínima energía del día)
