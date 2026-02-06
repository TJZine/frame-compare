import pytest

from frame_compare.render.geometry import (
    calculate_dimensions,
    calculate_overlay_position,
    ensure_mod2,
)


def test_calculate_dimensions_no_constraints():
    assert calculate_dimensions(1920, 1080, max_width=None, max_height=None) == (
        1920,
        1080,
    )


def test_calculate_dimensions_max_width_constrains():
    assert calculate_dimensions(1920, 1080, max_width=960, max_height=None) == (960, 540)


def test_calculate_dimensions_max_height_constrains():
    assert calculate_dimensions(1920, 1080, max_width=None, max_height=540) == (960, 540)


def test_calculate_dimensions_both_constraints():
    # Aspect ratio 16/9. 1280x720 is 16/9.
    # 1920 limit for width, 720 limit for height.
    # 1280x720 fits in both.
    assert calculate_dimensions(3840, 2160, max_width=1920, max_height=720) == (
        1280,
        720,
    )


def test_calculate_dimensions_constraint_exceeds_source():
    assert calculate_dimensions(1280, 720, max_width=1920, max_height=None) == (
        1280,
        720,
    )


def test_calculate_dimensions_invalid_source_raises():
    with pytest.raises(ValueError, match="source dimensions must be positive"):
        calculate_dimensions(0, 100)


def test_calculate_dimensions_invalid_max_raises():
    with pytest.raises(ValueError, match="max dimensions must be positive"):
        calculate_dimensions(100, 100, max_width=-1)


def test_calculate_dimensions_never_returns_zero_dimensions():
    assert calculate_dimensions(1, 1000, max_width=None, max_height=1) == (1, 1)


def test_overlay_position_top_left():
    assert calculate_overlay_position(
        image_size=(1920, 1080), overlay_size=(200, 50), position="top-left", margin=10
    ) == (10, 10)


def test_overlay_position_top_right():
    assert calculate_overlay_position(
        image_size=(1920, 1080), overlay_size=(200, 50), position="top-right", margin=10
    ) == (1710, 10)


def test_overlay_position_bottom_left():
    assert calculate_overlay_position(
        image_size=(1920, 1080),
        overlay_size=(200, 50),
        position="bottom-left",
        margin=10,
    ) == (10, 1020)


def test_overlay_position_bottom_right():
    assert calculate_overlay_position(
        image_size=(1920, 1080),
        overlay_size=(200, 50),
        position="bottom-right",
        margin=10,
    ) == (1710, 1020)


def test_overlay_position_invalid_raises():
    with pytest.raises(ValueError, match="invalid position: center"):
        calculate_overlay_position(
            image_size=(1920, 1080), overlay_size=(100, 50), position="center", margin=10
        )


def test_overlay_position_clamps_when_too_large():
    assert calculate_overlay_position(
        image_size=(1920, 1080),
        overlay_size=(1900, 1060),
        position="bottom-right",
        margin=50,
    ) == (0, 0)


def test_overlay_position_invalid_dims_raises():
    with pytest.raises(ValueError, match="dimensions must be positive"):
        calculate_overlay_position(
            image_size=(0, 100), overlay_size=(10, 10), position="top-left", margin=10
        )


def test_overlay_position_negative_margin_raises():
    with pytest.raises(ValueError, match="margin must be >= 0"):
        calculate_overlay_position(
            image_size=(1920, 1080), overlay_size=(100, 50), position="top-left", margin=-1
        )


def test_ensure_mod2_already_even():
    assert ensure_mod2(width=1920, height=1080) == (1920, 1080)


def test_ensure_mod2_rounds_up():
    assert ensure_mod2(width=1919, height=1079) == (1920, 1080)


def test_ensure_mod2_invalid_raises():
    with pytest.raises(ValueError, match="dimensions must be positive"):
        ensure_mod2(width=0, height=100)
