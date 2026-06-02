import pytest

from frame_compare.render.geometry import (
    GeometryMargins,
    GeometryRect,
    SourceGeometry,
    calculate_dimensions,
    ensure_mod2,
    plan_render_geometry,
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


def test_plan_render_geometry_native_preserves_full_frame_for_multiple_sources():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1920, height=1080, label="reference"),
            SourceGeometry(width=1280, height=720, label="encode"),
        ),
        mode="native",
    )

    assert len(plans) == 2
    assert plans[0].active_rect == GeometryRect(0, 0, 1920, 1080)
    assert plans[0].crop == GeometryMargins()
    assert plans[0].scaled_size == (1920, 1080)
    assert plans[0].pad == GeometryMargins()
    assert plans[0].final_canvas_size == (1920, 1080)
    assert plans[0].overlay_origin == (10, 10)
    assert plans[0].is_noop

    assert plans[1].active_rect == GeometryRect(0, 0, 1280, 720)
    assert plans[1].final_canvas_size == (1280, 720)
    assert plans[1].is_noop


def test_plan_render_geometry_aligned_same_height_center_crops_wider_source():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1920, height=1080, label="pillarboxed"),
            SourceGeometry(width=1440, height=1080, label="active"),
        ),
        mode="aligned",
    )

    wider = plans[0]
    narrower = plans[1]
    assert wider.active_rect_source == "dimension-derived"
    assert wider.active_rect == GeometryRect(240, 0, 1440, 1080)
    assert wider.crop == GeometryMargins(left=240, right=240)
    assert wider.cropped_size == (1440, 1080)
    assert wider.final_canvas_size == (1440, 1080)
    assert wider.overlay_origin == (10, 10)
    assert wider.source_overlay_origin == (250, 10)

    assert narrower.crop == GeometryMargins()
    assert narrower.final_canvas_size == (1440, 1080)
    assert narrower.overlay_origin == (10, 10)


@pytest.mark.unit
def test_plan_render_geometry_aligned_three_sources_same_height_center_crops_wider_sources():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1920, height=1080, label="wide"),
            SourceGeometry(width=1600, height=1080, label="mid"),
            SourceGeometry(width=1440, height=1080, label="active"),
        ),
        mode="aligned",
    )

    assert [plan.active_rect for plan in plans] == [
        GeometryRect(240, 0, 1440, 1080),
        GeometryRect(80, 0, 1440, 1080),
        GeometryRect(0, 0, 1440, 1080),
    ]
    assert [plan.crop for plan in plans] == [
        GeometryMargins(left=240, right=240),
        GeometryMargins(left=80, right=80),
        GeometryMargins(),
    ]
    assert [plan.final_canvas_size for plan in plans] == [(1440, 1080)] * 3


def test_plan_render_geometry_aligned_same_width_center_crops_taller_source():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1920, height=1080, label="letterboxed"),
            SourceGeometry(width=1920, height=800, label="active"),
        ),
        mode="aligned",
    )

    taller = plans[0]
    shorter = plans[1]
    assert taller.active_rect_source == "dimension-derived"
    assert taller.active_rect == GeometryRect(0, 140, 1920, 800)
    assert taller.crop == GeometryMargins(top=140, bottom=140)
    assert taller.cropped_size == (1920, 800)
    assert taller.final_canvas_size == (1920, 800)
    assert taller.source_overlay_origin == (10, 150)

    assert shorter.crop == GeometryMargins()
    assert shorter.final_canvas_size == (1920, 800)


@pytest.mark.unit
def test_plan_render_geometry_aligned_three_sources_same_width_center_crops_taller_sources():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1920, height=1080, label="tall"),
            SourceGeometry(width=1920, height=900, label="mid"),
            SourceGeometry(width=1920, height=800, label="active"),
        ),
        mode="aligned",
    )

    assert [plan.active_rect for plan in plans] == [
        GeometryRect(0, 140, 1920, 800),
        GeometryRect(0, 50, 1920, 800),
        GeometryRect(0, 0, 1920, 800),
    ]
    assert [plan.crop for plan in plans] == [
        GeometryMargins(top=140, bottom=140),
        GeometryMargins(top=50, bottom=50),
        GeometryMargins(),
    ]
    assert [plan.final_canvas_size for plan in plans] == [(1920, 800)] * 3


def test_plan_render_geometry_aligned_crops_odd_full_frame_to_mod_safe_size():
    (plan,) = plan_render_geometry(
        (SourceGeometry(width=1921, height=1081, label="odd"),),
        mode="aligned",
    )

    assert plan.active_rect_source == "full-frame"
    assert plan.active_rect == GeometryRect(0, 0, 1921, 1081)
    assert plan.crop_rect == GeometryRect(0, 0, 1920, 1080)
    assert plan.crop == GeometryMargins(right=1, bottom=1)
    assert plan.final_canvas_size == (1920, 1080)


def test_plan_render_geometry_aligned_scales_proportionally_and_centers_padding():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1000, height=500, label="wide"),
            SourceGeometry(width=800, height=800, label="square"),
        ),
        mode="aligned",
    )

    wide = plans[0]
    square = plans[1]
    assert wide.scaled_size == (1600, 800)
    assert wide.pad == GeometryMargins()
    assert wide.final_canvas_size == (1600, 800)

    assert square.scaled_size == (800, 800)
    assert square.pad == GeometryMargins(left=400, right=400)
    assert square.content_origin == (400, 0)
    assert square.overlay_origin == (410, 10)
    assert square.final_canvas_size == (1600, 800)


def test_plan_render_geometry_clamps_overlay_origin_to_padded_content_bounds():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1000, height=500, label="wide"),
            SourceGeometry(width=800, height=800, label="square"),
        ),
        mode="aligned",
        overlay_margin=1000,
    )

    wide = plans[0]
    square = plans[1]
    assert wide.content_origin == (0, 0)
    assert wide.scaled_size == (1600, 800)
    assert wide.overlay_origin == (1000, 799)

    assert square.content_origin == (400, 0)
    assert square.scaled_size == (800, 800)
    assert square.overlay_origin == (1199, 799)


@pytest.mark.unit
def test_plan_render_geometry_aligned_three_sources_mixed_dimensions_with_explicit_active_rects():
    plans = plan_render_geometry(
        (
            SourceGeometry(
                width=1920,
                height=1080,
                active_rect=GeometryRect(240, 140, 1440, 800),
                active_rect_source="explicit",
                label="reference",
            ),
            SourceGeometry(
                width=1440,
                height=800,
                active_rect=GeometryRect(0, 0, 1440, 800),
                active_rect_source="explicit",
                label="encode-a",
            ),
            SourceGeometry(
                width=1280,
                height=720,
                active_rect=GeometryRect(0, 0, 1280, 720),
                active_rect_source="explicit",
                label="encode-b",
            ),
        ),
        mode="aligned",
    )

    assert [plan.active_rect_source for plan in plans] == ["explicit"] * 3
    assert plans[0].crop == GeometryMargins(left=240, top=140, right=240, bottom=140)
    assert plans[0].scaled_size == (1440, 800)
    assert plans[1].crop == GeometryMargins()
    assert plans[1].scaled_size == (1440, 800)
    assert plans[2].crop == GeometryMargins()
    assert plans[2].scaled_size == (1422, 800)
    assert [plan.final_canvas_size for plan in plans] == [(1440, 800)] * 3
    assert plans[2].pad == GeometryMargins(left=9, right=9)
    assert plans[0].source_overlay_origin == (250, 150)
    assert plans[0].overlay_origin == (10, 10)


def test_plan_render_geometry_prefers_safe_provided_active_rect_over_dimension_fallback():
    plans = plan_render_geometry(
        (
            SourceGeometry(
                width=1920,
                height=1080,
                active_rect=GeometryRect(160, 0, 1600, 1080),
                active_rect_source="metadata",
            ),
            SourceGeometry(width=1440, height=1080),
        ),
        mode="aligned",
    )

    provided = plans[0]
    derived = plans[1]
    assert provided.active_rect_source == "metadata"
    assert provided.crop == GeometryMargins(left=160, right=160)
    assert provided.final_canvas_size == (1600, 1080)
    assert provided.source_overlay_origin == (170, 10)

    assert derived.active_rect_source == "dimension-derived"
    assert derived.pad == GeometryMargins(left=80, right=80)
    assert derived.overlay_origin == (90, 10)


def test_plan_render_geometry_invalid_active_rect_falls_back_to_dimension_derived_rect():
    plans = plan_render_geometry(
        (
            SourceGeometry(width=1920, height=1080, active_rect=GeometryRect(0, 0, 0, 1080)),
            SourceGeometry(width=1440, height=1080),
        ),
        mode="aligned",
    )

    assert plans[0].active_rect_source == "dimension-derived"
    assert plans[0].active_rect == GeometryRect(240, 0, 1440, 1080)


def test_plan_render_geometry_invalid_active_rect_falls_back_to_full_frame_without_axis_match():
    (plan,) = plan_render_geometry(
        (SourceGeometry(width=1920, height=1080, active_rect=GeometryRect(-1, 0, 100, 100)),),
        mode="aligned",
    )

    assert plan.active_rect_source == "full-frame"
    assert plan.active_rect == GeometryRect(0, 0, 1920, 1080)
