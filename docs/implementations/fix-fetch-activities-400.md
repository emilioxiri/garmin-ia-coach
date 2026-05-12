# Fix `fetch_activities` 400 — "Activity type specified is invalid"

## Context

Sync runs emitían el warning:

```
WARNING garmin_coach.infrastructure.garmin.data_fetcher :: event=fetch_failed endpoint=activities
garminconnect.exceptions.GarminConnectConnectionError: API Error 400 - Activity type specified is invalid
```

`_safe()` capturaba la excepción y devolvía `None`, que `fetch_activities` convertía a `[]`. Resultado: regresión silenciosa donde `SyncService` registraba `event=sync_complete activities=0` y no persistía ninguna actividad nueva, sin alertar al usuario más allá de un WARNING en logs.

## Causa raíz

`GarminDataFetcher.fetch_activities` (`garmin_coach/infrastructure/garmin/data_fetcher.py:33-43`) llamaba:

```python
self._g.get_activities_by_date(start_date, end_date, limit)  # limit=200 default
```

Pero la firma real de `garminconnect.Garmin.get_activities_by_date` es:

```python
def get_activities_by_date(startdate, enddate, activitytype=None, sortorder=None)
```

El endpoint **no acepta un parámetro `limit`**. El entero `200` posicional caía en `activitytype`, Garmin lo recibía como `"200"` y respondía 400 porque no es un tipo de actividad válido (`"running"`, `"cycling"`, etc.).

El bug existía desde la introducción de `fetch_activities` con el parámetro `limit` hardcodeado a 200 — nunca llegó a usarse correctamente porque ningún caller sobreescribe el default.

## Fix

`garmin_coach/infrastructure/garmin/data_fetcher.py`

```python
def fetch_activities(self, start_date: str, end_date: str) -> list[dict]:
    result = _safe(
        "activities",
        self._g.get_activities_by_date,
        start_date,
        end_date,
    )
    return result if isinstance(result, list) else []
```

Eliminado el parámetro `limit`. El rango de fechas ya acota el resultado (Garmin devuelve todas las actividades del rango por defecto).

## Callers afectados

- `garmin_coach/services/sync_service.py:123` — ya invocaba con 2 argumentos, sin cambios.

## Tests

- `garmin_coach/tests/infrastructure/garmin/test_data_fetcher.py:27` — actualizado el `assert_called_once_with` para reflejar la nueva firma (2 args en vez de 3).
- Suite completa: 500 pasados.

## Verificación end-to-end

1. `make hard-restart` para reconstruir el contenedor.
2. Disparar `/sync` desde Telegram (o esperar a `SYNC_TIME_MORNING`/`SYNC_TIME_EVENING`).
3. Confirmar en `/data/logs/bot.log`:
   - ausencia de `event=fetch_failed endpoint=activities`.
   - `event=sync_complete activities=<N>` con N coherente con la actividad reciente.

## Lecciones

- El handler `_safe` enmascara errores 4xx persistentes como WARNINGs. Considerar elevar a ERROR (o métrica) los fallos repetidos para endpoints clave (activities, sleep). Fuera de scope de este fix.
- Llamadas con argumentos posicionales a librerías de terceros con kwargs opcionales: preferir keyword args (`activitytype=...`) cuando exista riesgo de confundir parámetros.
