# Test: get_hrv_window

Devuelve la variabilidad del ritmo cardíaco (HRV) diaria con status y promedio semanal.

## Ejemplo 1: HRV esta semana
¿Cómo está mi HRV esta semana? ¿Bajo qué valores tengo?

## Ejemplo 2: Tendencia de HRV
¿Cuál ha sido mi HRV promedio en los últimos 30 días?

## Ejemplo 3: Recuperación
Mi HRV ha estado bajo, ¿cuáles fueron los últimos 7 días?

## Ejemplo 4: Estado actual
¿Cuál es mi estado de HRV hoy? ¿Indica estrés o buena recuperación?

## Ejemplo 5: Historial largo
Dame el HRV de los últimos 3 meses para ver la tendencia.

## Tool Schema
```
{
  "days": integer (default: 7, max: 90)
}
```

## Respuesta esperada
Array de registros con:
- date
- lastNight (HRV de la noche anterior)
- weeklyAvg
- status (Low/Balanced/High)
