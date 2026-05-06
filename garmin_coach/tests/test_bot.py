"""Unit tests for bot.py helpers."""

from garmin_coach.bot import format_for_telegram


def test_format_converts_double_asterisk_bold():
    assert format_for_telegram("**sueño**") == "<b>sueño</b>"


def test_format_converts_multiple_bold():
    result = format_for_telegram("**HRV**: 45 | **Body Battery**: 80")
    assert result == "<b>HRV</b>: 45 | <b>Body Battery</b>: 80"


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
    assert format_for_telegram(text) == "🏃 <b>Distancia</b>: 10 km"


def test_format_handles_empty_string():
    assert format_for_telegram("") == ""


def test_format_handles_no_markdown():
    text = "Entrena suave hoy. HRV bajo."
    assert format_for_telegram(text) == text


def test_format_multiline():
    text = "## Resumen\n**HRV**: 45\n- Duerme 8h\n- Ritmo suave"
    result = format_for_telegram(text)
    assert result == "Resumen\n<b>HRV</b>: 45\n- Duerme 8h\n- Ritmo suave"


def test_format_escapes_html_special_chars():
    """Caracteres `<`, `>`, `&` en texto LLM deben escaparse para HTML parse."""
    text = "Ritmo < 5 min/km & FC > 150"
    result = format_for_telegram(text)
    assert result == "Ritmo &lt; 5 min/km &amp; FC &gt; 150"


def test_format_bold_with_underscore_inside():
    """Underscore dentro de bold no debe romper HTML (legacy Markdown sí rompía)."""
    result = format_for_telegram("**vo2_max**: 55")
    assert result == "<b>vo2_max</b>: 55"


def test_format_bold_multiline_dotall():
    """Bold que cruza saltos de línea se convierte igualmente."""
    result = format_for_telegram("**linea1\nlinea2**")
    assert result == "<b>linea1\nlinea2</b>"
