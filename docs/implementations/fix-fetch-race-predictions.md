# Fix `fetch_race_predictions` ValueError — "you must either provide all parameters or no parameters"

## Context

Tras el fix del 400 en `fetch_activities`, el sync seguía emitiendo:

```
WARNING garmin_coach.infrastructure.garmin.data_fetcher :: event=fetch_failed endpoint=race_predictions
ValueError: you must either provide all parameters or no parameters
```

`_safe()` capturaba la excepción y devolvía `None`, así que el sync nunca actualizaba `race_predictions` en TinyDB.

## Causa raíz

`GarminDataFetcher.fetch_race_predictions` llamaba `self._g.get_race_predictions(start, today)` con **dos** argumentos. La firma real es:

```python
def get_race_predictions(startdate=None, enddate=None, _type=None) -> dict
```

Y exige explícitamente 0 argumentos (devuelve las predicciones más recientes) o **los 3** (`startdate`, `enddate`, `_type` ∈ `{"daily", "monthly"}`). Con 2 argumentos cae en el `raise ValueError(...)` final.

## Fix

`garmin_coach/infrastructure/garmin/data_fetcher.py`

```python
def fetch_race_predictions(self) -> dict | None:
    return _safe("race_predictions", self._g.get_race_predictions)
```

Llamada sin argumentos → endpoint `/latest/<displayName>` → predicción actual (5k, 10k, half, marathon). El sync ya guarda el blob bajo `date=today_str`, así que la "latest" prediction encaja sin cambios en `SyncService` ni en `RacePredictionsRepository.replace()`.

Se eliminaron también los imports locales `from datetime import date, timedelta` que ya no son necesarios.

## Tests

- `garmin_coach/tests/infrastructure/garmin/test_data_fetcher.py` — los tests existentes no asertaban argumentos, siguen pasando.
- Suite completa: 500/500.

## Verificación end-to-end

1. `make hard-restart`.
2. `/sync` desde Telegram.
3. En `/data/logs/bot.log`:
   - sin `event=fetch_failed endpoint=race_predictions`.
   - `Race predictions updated` y `race_predictions=1` en el summary del sync.
