"""Validation for shared CLI layout helpers."""

from src.frame_compare.layout_utils import sanitize_console_text


def test_sanitize_console_text_removes_ansi_and_newlines() -> None:
    payload = "\x1b[31mRed\x1b[0m Line\nSecond\x1b[0m"
    safe_value = sanitize_console_text(payload)

    assert "\x1b" not in safe_value
    assert "\n" not in safe_value
    assert "Red Line Second" in safe_value


def test_sanitize_console_text_filters_control_chars_but_preserves_tab() -> None:
    payload = "bad\0name\tok\nline"
    safe_value = sanitize_console_text(payload)

    assert "\x00" not in safe_value
    assert "\n" not in safe_value
    assert safe_value == "badname\tok line"


def test_sanitize_console_text_collapses_spaces_and_truncates() -> None:
    messy = "a" * 5 + "    " + "b" * 5
    cleaned = sanitize_console_text(messy)
    assert cleaned == "aaaaa bbbbb"

    truncated = sanitize_console_text("0123456789", max_len=5)
    assert truncated.endswith("…")
    assert len(truncated) <= 5
