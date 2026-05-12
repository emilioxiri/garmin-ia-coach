# Test Prompts para Tools

Esta carpeta contiene ejemplos de prompts para invocar cada tool desde el bot Telegram y probarlos.

## Tools Disponibles (10)

### 1. **find_activity** — Búsqueda avanzada
Busca actividades filtrando por día semana (lunes-domingo), fecha exacta, rango distancia, tipo actividad.
- Archivo: `01_find_activity.md`
- Caso: "¿Cuál fue esa carrera que hice el viernes pasado?"

### 2. **get_recent_activities** — Últimas sesiones
Devuelve actividades recientes (últimos N días) con filtros opcionales.
- Archivo: `02_get_recent_activities.md`
- Caso: "¿Qué he hecho esta semana?"

### 3. **get_activity_detail** — Detalles completos
Obtiene toda la información de una actividad específica por ID.
- Archivo: `03_get_activity_detail.md`
- Caso: Después de `find_activity`, pedir más detalles

### 4. **get_sleep_window** — Sueño
Registros diarios: total, deep, REM, light, awake (horas), score, HR reposo.
- Archivo: `04_get_sleep_window.md`
- Caso: "¿Cómo ha sido mi sueño esta semana?"

### 5. **get_hrv_window** — Variabilidad cardíaca
HRV diaria + status + promedio semanal. Indicador de recuperación.
- Archivo: `05_get_hrv_window.md`
- Caso: "¿Cómo está mi HRV esta semana?"

### 6. **get_body_battery_window** — Energía
Body Battery diario (máx/mín). Indicador energía disponible.
- Archivo: `06_get_body_battery_window.md`
- Caso: "¿Tengo energía para entrenar hoy?"

### 7. **get_training_readiness_window** — Disponibilidad entrenar
Score, nivel, feedback, influencia sueño/HRV.
- Archivo: `07_get_training_readiness_window.md`
- Caso: "¿Puedo hacer un entrenamiento intenso hoy?"

### 8. **get_fitness_snapshot** — Estado forma actual
Agregado: VO2max, predicciones carrera, lactato, endurance score.
- Archivo: `08_get_fitness_snapshot.md`
- Caso: "¿Cómo estoy de forma? ¿Cuál es mi VO2max?"

### 9. **get_personal_records** — Marcas personales
PBs en 1K, 5K, 10K, media maratón, maratón, carrera más larga.
- Archivo: `09_get_personal_records.md`
- Caso: "¿Cuál es mi PB en 5K?"

### 10. **search_memory** — Notas guardadas
Búsqueda en notas de /memoria (lesiones, sensaciones, decisiones).
- Archivo: `10_search_memory.md`
- Caso: "¿Tengo registrada alguna lesión?"

---

## Cómo probar

1. **Elige un tool** de los 10 disponibles
2. **Abre el archivo** correspondiente
3. **Copia uno de los ejemplos** (está redactado como pregunta natural)
4. **Envía al bot** en Telegram como mensaje normal
5. **El bot invocará automáticamente el tool** que necesita responder

## Notas

- Todos los ejemplos están en **español** (idioma nativo del sistema)
- Los parámetros se extraen automáticamente del mensaje
- Si el mensaje no tieneparámetros, se usan los defaults
- Rango máximo de días: **90 días** (algunos tools)

## Archivos

```
prompts/tools/
├── 01_find_activity.md
├── 02_get_recent_activities.md
├── 03_get_activity_detail.md
├── 04_get_sleep_window.md
├── 05_get_hrv_window.md
├── 06_get_body_battery_window.md
├── 07_get_training_readiness_window.md
├── 08_get_fitness_snapshot.md
├── 09_get_personal_records.md
├── 10_search_memory.md
└── README.md (este archivo)
```
