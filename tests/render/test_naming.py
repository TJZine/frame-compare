import pytest

from frame_compare.render.naming import generate_screenshot_name, generate_screenshot_path


def test_generate_name_simple():
    assert generate_screenshot_name("Source", 100) == "Source_00100.png"


def test_generate_name_zero_frame():
    assert generate_screenshot_name("Ref", 0) == "Ref_00000.png"


def test_generate_name_custom_extension():
    assert generate_screenshot_name("Test", 1, extension="jpg") == "Test_00001.jpg"


def test_generate_name_sanitizes_spaces():
    assert generate_screenshot_name("My Source", 50) == "My_Source_00050.png"


def test_generate_name_sanitizes_special_chars():
    assert generate_screenshot_name("$ource@123!", 10) == "ource_123_00010.png"


def test_generate_name_collapses_underscores():
    assert generate_screenshot_name("A___B", 1) == "A_B_00001.png"


def test_generate_name_strips_leading_trailing():
    assert generate_screenshot_name("_**Test**_", 1) == "Test_00001.png"


def test_generate_name_empty_becomes_unnamed():
    assert generate_screenshot_name("", 1) == "unnamed_00001.png"


def test_generate_name_all_special_becomes_unnamed():
    assert generate_screenshot_name("@#$%", 1) == "unnamed_00001.png"


def test_generate_name_preserves_hyphen():
    assert generate_screenshot_name("My-Source", 1) == "My-Source_00001.png"


def test_generate_name_negative_frame_raises():
    with pytest.raises(ValueError, match="frame_number must be non-negative"):
        generate_screenshot_name("Test", -1)


def test_generate_name_empty_extension_raises():
    with pytest.raises(ValueError, match="extension must not be empty"):
        generate_screenshot_name("Test", 1, extension="")


def test_generate_path_simple(tmp_path):
    assert generate_screenshot_path(tmp_path, "Ref", 100) == tmp_path / "Ref_00100.png"


def test_generate_path_sanitizes(tmp_path):
    assert generate_screenshot_path(tmp_path, "My Source", 1) == tmp_path / "My_Source_00001.png"
