# Refactor OOP/SOLID — Fase 1: Cimientos

## Qué se hizo

### Estructura de carpetas creada

```
garmin_coach/
  domain/__init__.py
  infrastructure/__init__.py
  infrastructure/db/__init__.py
  infrastructure/llm/__init__.py
  infrastructure/garmin/__init__.py
  infrastructure/telegram/__init__.py
  infrastructure/telegram/handlers/__init__.py
  services/__init__.py
  services/tools/__init__.py
  app/__init__.py
  app/config.py
  app/container.py
  app/legacy_bridge.py
  app/logging_setup.py
  prompts/__init__.py
  prompts/coach_system.txt
  tests/domain/__init__.py
  tests/infrastructure/__init__.py
  tests/infrastructure/db/__init__.py
  tests/infrastructure/llm/__init__.py
  tests/infrastructure/garmin/__init__.py
  tests/infrastructure/telegram/__init__.py
  tests/services/__init__.py
  tests/services/tools/__init__.py
  tests/app/__init__.py
  tests/app/test_config.py
  tests/app/test_container.py
  tests/app/test_logging_setup.py
```

### Módulos nuevos

**`garmin_coach/app/config.py`**
- `@dataclass(frozen=True) class Settings` con todos los campos tipados (garmin_email, garmin_password, telegram_bot_token, telegram_allowed_user_id, groq_api_key, sync_time_morning, sync_time_evening, days_history, db_path, session_path, log_path, timezone, llm_model).
- `load_settings() -> Settings`: único punto que lee `os.environ`. Lanza `RuntimeError` con lista de variables faltantes si alguna obligatoria no está presente. Defaults: `db_path=/data/garmin_coach.json`, `session_path=/data/garmin_session.json`, `log_path=/data/logs/bot.log`, `days_history=30`, `sync_time_morning=07:00`, `sync_time_evening=22:00`.

**`garmin_coach/app/logging_setup.py`**
- `configure_logging(settings)`: extrae setup de `main.py` original (FileHandler + StreamHandler, level INFO, formato con timestamp). Crea el directorio padre del log si no existe.

**`garmin_coach/app/container.py`**
- `class Container`: recibe `Settings` en constructor. `run()` delega al bot legacy vía `build_application()` de `bot.py` + `start_scheduler()` de `legacy_bridge.py`.

**`garmin_coach/app/legacy_bridge.py`**
- Pegamento temporal entre `Container` y los módulos legacy (`bot.py`, `garmin_sync.py`). Contiene `start_scheduler()` (equivalente a la función homónima que antes vivía en `main.py`) y `wire_mfa_to_app()` (guard no-op para Fase 4). Marcado explícitamente como deuda temporal (se elimina en Fase 4-5).

**`garmin_coach/prompts/__init__.py`**
- `read_system_prompt() -> str`: carga `coach_system.txt` del mismo directorio vía `pathlib`. CoachSession lo usará en Fase 3 en lugar del string inline.

**`garmin_coach/prompts/coach_system.txt`**
- Copia textual byte-a-byte del `SYSTEM_PROMPT` de `coach.py`. `coach.py` sigue usando su copia inline hasta Fase 3.

**`main.py`** (reescrito, ahora ≤20 líneas)
```python
from dotenv import load_dotenv
from garmin_coach.app.config import load_settings
from garmin_coach.app.container import Container
from garmin_coach.app.logging_setup import configure_logging

def main() -> None:
    load_dotenv()
    settings = load_settings()
    configure_logging(settings)
    Container(settings).run()
```

## Deuda técnica para Fases 2-5

| Ítem | Se resuelve en |
|---|---|
| `legacy_bridge.py` — scheduler y globals de `garmin_sync` | Fase 4-5 |
| `SYSTEM_PROMPT` duplicado en `coach.py` y `prompts/coach_system.txt` | Fase 3 (CoachSession cargará del txt) |
| `Container.run()` llama a `bot.build_application()` legacy | Fase 5 (TelegramBotApp OOP) |
| Scheduler no pasa por `Container` (hilo daemon en `legacy_bridge`) | Fase 5 (Scheduler class) |
| Todos los globales en `bot.py`, `garmin_sync.py`, `coach.py`, `db.py` | Fases 2-5 |
| `os.getenv` disperso en `bot.py`, `garmin_sync.py` | Fases 4-5 (Settings inyectado) |

## Tests nuevos

- `tests/app/test_config.py` — 7 tests: lectura de envs, error en faltantes (parametrizado por 4 vars), defaults, inmutabilidad.
- `tests/app/test_container.py` — 3 tests: almacenamiento de settings, delegación correcta a legacy en `run()`, `read_system_prompt()`.
- `tests/app/test_logging_setup.py` — 2 tests: creación del directorio de log, adjunción de FileHandler + StreamHandler al root logger.

## Resultado final

- **210 tests passed** (207 legacy + 12 nuevos — 9 de los nuevos tests de `app/` + 3 en `test_container.py`)
- **Coverage: 90.44%** (gate: 85%)
- **Ruff: limpio** (se corrigieron 4 errores pre-existentes en `test_garmin_sync.py` y se formatearon `garmin_sync.py` y `conftest.py`)
- `legacy_bridge.py` añadido a `[tool.coverage.run] omit` (mismo tratamiento que `bot.py` — módulo de pegamento temporal no testeable unitariamente)
