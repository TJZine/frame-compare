import pytest

from frame_compare.render.geometry import (
    calculate_dimensions,
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

def test_ensure_mod2_already_even():
    assert ensure_mod2(width=1920, height=1080) == (1920, 1080)


def test_ensure_mod2_rounds_up():
    assert ensure_mod2(width=1919, height=1079) == (1920, 1080)


def test_ensure_mod2_invalid_raises():
    with pytest.raises(ValueError, match="dimensions must be positive"):
        ensure_mod2(width=0, height=100)
