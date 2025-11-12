from __future__ import annotations

from src.frame_compare.render import encoders


def test_map_png_compression_level_clamps_values() -> None:
    assert encoders.map_png_compression_level(-5) == 0
    assert encoders.map_png_compression_level(0) == 0
    assert encoders.map_png_compression_level(1) == 6
    assert encoders.map_png_compression_level(2) == 9
    assert encoders.map_png_compression_level(99) == 9


def test_escape_drawtext_escapes_special_characters() -> None:
    result = encoders.escape_drawtext(r"\text:[]=, '")
    assert result == r"\\text\:\[\]\=\, \'"
