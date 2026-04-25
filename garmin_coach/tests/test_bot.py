"""Unit tests for bot.py helpers."""

from garmin_coach.bot import format_for_telegram


def test_format_converts_double_asterisk_bold():
    assert format_for_telegram("**sueño**") == "*sueño*"


def test_format_converts_multiple_bold():
    result = format_for_telegram("**HRV**: 45 | **Body Battery**: 80")
    assert result == "*HRV*: 45 | *Body Battery*: 80"


def test_format_strips_markdown_headers():
    result = format_for_telegram("## Recuperación\nDuerme bien.")
    assert result == "Recuperación\nDuerme bien."


def test_format_strips_all_header_levels():
    for level in range(1, 7):
        header = "#" * level + " Titulo"
        assert format_for_telegram(header) == "Titulo"


def test_format_preserves_single_asterisk():
    text = "*ya en negrita*"
    assert format_for_telegram(text) == "*ya en negrita*"


def test_format_preserves_code_blocks():
    text = "```python\nx = 1\n```"
    assert format_for_telegram(text) == text


def test_format_preserves_emojis():
    text = "🏃 **Distancia**: 10 km"
    assert format_for_telegram(text) == "🏃 *Distancia*: 10 km"


def test_format_handles_empty_string():
    assert format_for_telegram("") == ""


def test_format_handles_no_markdown():
    text = "Entrena suave hoy. HRV bajo."
    assert format_for_telegram(text) == text


def test_format_multiline():
    text = "## Resumen\n**HRV**: 45\n- Duerme 8h\n- Ritmo suave"
    result = format_for_telegram(text)
    assert result == "Resumen\n*HRV*: 45\n- Duerme 8h\n- Ritmo suave"
