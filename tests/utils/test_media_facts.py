from dataclasses import FrozenInstanceError

import pytest

from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    RenderedGeometryFacts,
    normalize_picture_type,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(" i ", "I"), (b"p", "P"), ("IDR", "I"), ("?", None), (None, None)],
)
def test_normalize_picture_type(value: object, expected: str | None) -> None:
    assert normalize_picture_type(value) == expected


def test_geometry_contains_active_picture_and_is_immutable() -> None:
    active = ActivePictureFacts(0, 140, 1920, 800, "dolby_vision_l5", False)
    facts = RenderedGeometryFacts(
        source_size=(1920, 1080),
        active_picture=active,
        cropped_size=(1920, 800),
        scaled_size=(1920, 800),
        final_canvas_size=(1920, 800),
        is_noop=False,
    )
    assert facts.active_picture.provenance == "dolby_vision_l5"
    with pytest.raises(FrozenInstanceError):
        facts.is_noop = True  # type: ignore[misc]


def test_geometry_rejects_active_picture_outside_source() -> None:
    with pytest.raises(ValueError, match="contained"):
        RenderedGeometryFacts(
            source_size=(100, 100),
            active_picture=ActivePictureFacts(50, 0, 100, 100, "explicit", False),
            cropped_size=(100, 100),
            scaled_size=(100, 100),
            final_canvas_size=(100, 100),
            is_noop=False,
        )
