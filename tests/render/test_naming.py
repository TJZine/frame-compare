import pytest

from frame_compare.render.naming import generate_screenshot_name, generate_screenshot_path


def test_generate_name_simple():
    assert generate_screenshot_name("Source", 100) == "100 - Source.png"


def test_generate_name_zero_frame():
    assert generate_screenshot_name("Ref", 0) == "0 - Ref.png"


def test_generate_name_custom_extension():
    assert generate_screenshot_name("Test", 1, extension="jpg") == "1 - Test.jpg"


def test_generate_name_preserves_spaces():
    assert generate_screenshot_name("My Source", 50) == "50 - My Source.png"


def test_generate_name_sanitizes_special_chars():
    assert generate_screenshot_name('Bad:Name?.mkv', 10) == "10 - Bad_Name_.mkv.png"


def test_generate_name_collapses_underscores():
    assert generate_screenshot_name("A:::B", 1) == "1 - A___B.png"


def test_generate_name_strips_leading_trailing():
    assert generate_screenshot_name(" **Test** ", 1) == "1 - __Test__.png"


def test_generate_name_empty_becomes_unnamed():
    assert generate_screenshot_name("", 1) == "1 - comparison.png"


def test_generate_name_all_special_becomes_unnamed():
    assert generate_screenshot_name("<>:/\\|?*", 1) == "1 - ________.png"


def test_generate_name_preserves_hyphen():
    assert generate_screenshot_name("My-Source", 1) == "1 - My-Source.png"


def test_generate_name_preserves_windows_reserved_name_stem():
    assert generate_screenshot_name("CON", 1) == "1 - CON.png"


def test_generate_name_negative_frame_raises():
    with pytest.raises(ValueError, match="frame_number must be non-negative"):
        generate_screenshot_name("Test", -1)


def test_generate_name_empty_extension_raises():
    with pytest.raises(ValueError, match="extension must not be empty"):
        generate_screenshot_name("Test", 1, extension="")


def test_generate_path_simple(tmp_path):
    assert generate_screenshot_path(tmp_path, "Ref", 100) == tmp_path / "100 - Ref.png"


def test_generate_path_sanitizes(tmp_path):
    assert generate_screenshot_path(tmp_path, "Bad:Name", 1) == tmp_path / "1 - Bad_Name.png"
