# Test: get_personal_records

Devuelve tus marcas personales calculadas en todas tus carreras: PBs en 1K, 5K, 10K, media maratón, maratón, y carrera más larga.

## Ejemplo 1: ¿Cuál es mi PB en 5K?
Dime mi mejor tiempo en 5K.

## Ejemplo 2: Todas mis marcas
Resúmeme todas mis marcas personales de running.

## Ejemplo 3: Carrera más larga
¿Cuál es la tirada más larga que he hecho? ¿Cuándo fue?

## Ejemplo 4: Media maratón
¿Cuál es mi PB en media maratón? ¿Cómo fue ese día?

## Ejemplo 5: Progresión
¿Cuándo logré mi mejor maratón? ¿Cuál fue mi ritmo?

## Tool Schema
```
{
  (sin parámetros)
}
```

## Respuesta esperada
Objeto con records:
- pb_1k (mejor 1K)
- pb_5k (mejor 5K)
- pb_10k (mejor 10K)
- pb_half_marathon (mejor media maratón)
- pb_marathon (mejor maratón)
- longest_run (carrera más larga)

Cada uno contiene:
- activityId
- date
- distance_km
- duration_hms
- pace_min_per_km
- averageHR
