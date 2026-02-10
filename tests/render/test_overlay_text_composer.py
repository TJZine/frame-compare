from frame_compare.render.overlay_text import (
    compose_frame_info_lines,
    compose_overlay_text_lines,
)
from frame_compare.render.types import OverlayMode


def test_compose_frame_info_lines_standard_includes_frame_and_pict_type() -> None:
    lines = compose_frame_info_lines(
        mode=OverlayMode.STANDARD,
        label="Ref",
        display_frame_number=12,
        num_frames=100,
        picture_type="I",
        selection_label="Dark",
    )
    assert lines[0] == "Frame 12 of 100"
    assert lines[1] == "Picture type: I"
    assert lines[2] == "Ref"
    assert lines[3] == "Selection: Dark"


def test_compose_frame_info_lines_minimal_is_label_only() -> None:
    lines = compose_frame_info_lines(
        mode=OverlayMode.MINIMAL,
        label="Ref",
        display_frame_number=12,
        num_frames=100,
        picture_type="I",
        selection_label="Dark",
    )
    assert lines == ["Ref"]


def test_compose_overlay_text_lines_standard_order_matches_legacy_intent() -> None:
    lines = compose_overlay_text_lines(
        mode=OverlayMode.STANDARD,
        base_text=None,
        width=1920,
        height=1080,
        selection_type="Dark",
        diagnostic_lines=[],
    )
    assert lines[0] == "1920 × 1080  (native)"
    assert lines[1] == "Frame Selection Type: Dark"


def test_compose_overlay_text_lines_diagnostic_appends_lines_before_selection_type() -> None:
    lines = compose_overlay_text_lines(
        mode=OverlayMode.DIAGNOSTIC,
        base_text="Base",
        width=1920,
        height=1080,
        selection_type="Bright",
        diagnostic_lines=["MDL: ...", "HDR: ..."],
    )
    assert lines[:2] == ["Base", "1920 × 1080  (native)"]
    assert "MDL: ..." in lines
    assert "HDR: ..." in lines
    assert lines[-1] == "Frame Selection Type: Bright"
