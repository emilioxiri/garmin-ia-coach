# Telegram HTML formatting (bot.py)

## Problema

Las respuestas del LLM (chat libre, `/briefing` y briefings programados de mañana/noche) llegaban al usuario con los caracteres de markdown crudos visibles, p. ej. `**Recuperación**` en lugar de **Recuperación**.

Causas:

1. **Briefings programados sin formato**. `send_scheduled_message` enviaba el texto del LLM directamente con `app.bot.send_message(...)` sin aplicar `format_for_telegram` ni `parse_mode`. Como el modelo emite `**bold**` y `## headers`, el usuario veía los asteriscos y almohadillas literales.
2. **Legacy `Markdown` parse_mode frágil**. Telegram rechaza el mensaje si encuentra un `_`, `(`, `[` o `*` no balanceado (frecuente en fechas tipo `2026-05-06`, paréntesis aclaratorios o nombres como `vo2_max`). El bloque `try/except` caía al fallback sin parse y enseñaba el texto plano (con `*` o `**` visibles).

## Solución

Migración a `parse_mode="HTML"`, mucho más permisivo (los `*`, `_`, `(` sueltos se pasan tal cual, sólo se interpretan etiquetas `<b>`, `<i>`, `<code>`…).

### Cambios

`garmin_coach/bot.py`

- `format_for_telegram(text)` reescrito:
  - Elimina cabeceras `#{1,6}` al inicio de línea.
  - Escapa `<`, `>`, `&` con `html.escape(..., quote=False)` para evitar inyección/parse error.
  - Convierte `**bold**` (multilínea, `re.DOTALL`) en `<b>bold</b>`.
- Todas las salidas con texto generado por LLM pasan a `parse_mode="HTML"`:
  - `cmd_briefing` (mensaje único y troceado en chunks de 4000 chars).
  - `handle_message` (chat libre, mismo manejo de chunks).
  - `send_scheduled_message` ahora aplica `format_for_telegram` + chunking + `parse_mode="HTML"` con fallback sin `parse_mode` si Telegram rechaza el mensaje.
- Comandos con texto estático (`/start`, `/sync`, `/status`, `/memoria`) siguen usando `Markdown` legacy: son strings controlados sin riesgo de parse error.

### Tests

`garmin_coach/tests/test_bot.py` actualizado para validar la salida HTML:

- Conversión `**x**` → `<b>x</b>` (incluye múltiples ocurrencias y multilínea).
- Stripping de cabeceras `#`–`######`.
- Escape de `<`, `>`, `&`.
- Subrayados dentro de bold (`**vo2_max**`) ya no rompen.
- Preservación de emojis, code fences ` ``` `, asteriscos sueltos.

13 tests; todos pasan junto con la suite global (125 total).

## Notas

- HTML parse_mode no soporta `*italic*` ni `_italic_`. Si en el futuro queremos cursivas, habrá que añadir un patrón `*texto*` (cuidando bullets de lista que empiezan con `*`/`-`) o instruir al LLM a usar `<i>...</i>` directamente.
- El system prompt de `coach.py` ya no necesita pedir explícitamente "usa asterisco simple", pero se ha dejado intacto por ahora; el conversor tolera ambos estilos (`**...**` se convierte; `*...*` se queda como literal y Telegram lo muestra tal cual sin romper).
