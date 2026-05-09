"""Tests for MessageFormatter: to_html and chunk."""

from garmin_coach.infrastructure.telegram.formatter import MessageFormatter


def make_fmt():
    return MessageFormatter()


# ── to_html ───────────────────────────────────────────────────────────────────


def test_to_html_converts_bold():
    assert make_fmt().to_html("**sueño**") == "<b>sueño</b>"


def test_to_html_multiple_bold():
    result = make_fmt().to_html("**HRV**: 45 | **Body Battery**: 80")
    assert result == "<b>HRV</b>: 45 | <b>Body Battery</b>: 80"


def test_to_html_strips_h1():
    assert make_fmt().to_html("# Titulo") == "Titulo"


def test_to_html_strips_all_header_levels():
    fmt = make_fmt()
    for level in range(1, 7):
        header = "#" * level + " Titulo"
        assert fmt.to_html(header) == "Titulo"


def test_to_html_escapes_lt_gt_amp():
    result = make_fmt().to_html("Ritmo < 5 min/km & FC > 150")
    assert result == "Ritmo &lt; 5 min/km &amp; FC &gt; 150"


def test_to_html_preserves_emojis():
    result = make_fmt().to_html("🏃 **Distancia**: 10 km")
    assert result == "🏃 <b>Distancia</b>: 10 km"


def test_to_html_handles_empty_string():
    assert make_fmt().to_html("") == ""


def test_to_html_handles_no_markdown():
    text = "Entrena suave hoy. HRV bajo."
    assert make_fmt().to_html(text) == text


def test_to_html_multiline():
    text = "## Resumen\n**HRV**: 45\n- Duerme 8h"
    result = make_fmt().to_html(text)
    assert result == "Resumen\n<b>HRV</b>: 45\n- Duerme 8h"


def test_to_html_bold_with_underscore():
    result = make_fmt().to_html("**vo2_max**: 55")
    assert result == "<b>vo2_max</b>: 55"


def test_to_html_bold_multiline_dotall():
    result = make_fmt().to_html("**linea1\nlinea2**")
    assert result == "<b>linea1\nlinea2</b>"


def test_to_html_preserves_single_asterisk():
    text = "*ya en negrita*"
    assert make_fmt().to_html(text) == "*ya en negrita*"


# ── chunk ─────────────────────────────────────────────────────────────────────


def test_chunk_short_text_returns_single():
    fmt = make_fmt()
    result = fmt.chunk("hola mundo")
    assert result == ["hola mundo"]


def test_chunk_respects_max_len():
    fmt = make_fmt()
    text = "a" * 10
    chunks = fmt.chunk(text, max_len=5)
    for c in chunks:
        assert len(c) <= 5


def test_chunk_preserves_newlines():
    fmt = make_fmt()
    text = "linea1\nlinea2\nlinea3"
    chunks = fmt.chunk(text, max_len=15)
    reconstructed = "\n".join(chunks)
    # All original words preserved
    assert "linea1" in reconstructed
    assert "linea2" in reconstructed
    assert "linea3" in reconstructed


def test_chunk_exact_limit_returns_single():
    fmt = make_fmt()
    text = "a" * 4000
    assert fmt.chunk(text) == [text]


def test_chunk_over_limit_splits():
    fmt = make_fmt()
    text = "x" * 4001
    chunks = fmt.chunk(text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= fmt.MAX_CHUNK_LEN


def test_chunk_custom_max_len():
    fmt = make_fmt()
    text = "hello world\nfoo bar"
    chunks = fmt.chunk(text, max_len=12)
    assert all(len(c) <= 12 for c in chunks)
