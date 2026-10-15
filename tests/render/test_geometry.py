import pytest

from frame_compare.render.geometry import (
    GeometryMargins,
    GeometryMode,
    GeometryRect,
    RenderGeometryOptions,
    SourceGeometry,
    plan_render_geometry,
)


@pytest.mark.parametrize(
    ("width", "height"),
    [(0, 1080), (1920, 0), (-1, 1080), (1920, -1)],
)
def test_plan_render_geometry_rejects_non_positive_source_dimensions(
    width: int, height: int
) -> None:
    with pytest.raises(ValueError, match="source dimensions must be positive"):
        plan_render_geometry(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, width, height),
                    provenance="full_frame",
                    width=width,
                    height=height,
                ),
            ),
            mode="native",
        )


def test_plan_render_geometry_aligned_scales_proportionally_and_centers_padding():
    plans = plan_render_geometry(
        (
            SourceGeometry(
                active_rect=GeometryRect(0, 0, 1000, 500),
                provenance="full_frame",
                width=1000,
                height=500,
                label="wide",
            ),
            SourceGeometry(
                active_rect=GeometryRect(0, 0, 800, 800),
                provenance="full_frame",
                width=800,
                height=800,
                label="square",
            ),
        ),
        mode="aligned",
    )

    wide = plans[0]
    square = plans[1]
    assert wide.scaled_size == (1000, 500)
    assert wide.pad == GeometryMargins(top=150, bottom=150)
    assert wide.final_canvas_size == (1000, 800)

    assert square.scaled_size == (800, 800)
    assert square.pad == GeometryMargins(left=100, right=100)
    assert square.content_origin == (100, 0)
    assert square.overlay_origin == (110, 10)
    assert square.final_canvas_size == (1000, 800)


def test_plan_render_geometry_clamps_overlay_origin_to_padded_content_bounds():
    plans = plan_render_geometry(
        (
            SourceGeometry(
                active_rect=GeometryRect(0, 0, 1000, 500),
                provenance="full_frame",
                width=1000,
                height=500,
                label="wide",
            ),
            SourceGeometry(
                active_rect=GeometryRect(0, 0, 800, 800),
                provenance="full_frame",
                width=800,
                height=800,
                label="square",
            ),
        ),
        mode="aligned",
        overlay_margin=1000,
    )

    wide = plans[0]
    square = plans[1]
    assert wide.content_origin == (0, 150)
    assert wide.scaled_size == (1000, 500)
    assert wide.overlay_origin == (999, 649)

    assert square.content_origin == (100, 0)
    assert square.scaled_size == (800, 800)
    assert square.overlay_origin == (899, 799)


@pytest.mark.unit
def test_plan_render_geometry_aligned_three_sources_mixed_dimensions_with_explicit_active_rects():
    plans = plan_render_geometry(
        (
            SourceGeometry(
                width=1920,
                height=1080,
                active_rect=GeometryRect(240, 140, 1440, 800),
                provenance="explicit",
                label="reference",
            ),
            SourceGeometry(
                width=1440,
                height=800,
                active_rect=GeometryRect(0, 0, 1440, 800),
                provenance="explicit",
                label="encode-a",
            ),
            SourceGeometry(
                width=1280,
                height=720,
                active_rect=GeometryRect(0, 0, 1280, 720),
                provenance="explicit",
                label="encode-b",
            ),
        ),
        mode="aligned",
    )

    assert [plan.provenance for plan in plans] == ["explicit"] * 3
    assert plans[0].crop == GeometryMargins(left=240, top=140, right=240, bottom=140)
    assert plans[0].scaled_size == (1440, 800)
    assert plans[1].crop == GeometryMargins()
    assert plans[1].scaled_size == (1440, 800)
    assert plans[2].crop == GeometryMargins()
    assert plans[2].scaled_size == (1422, 800)
    assert [plan.final_canvas_size for plan in plans] == [(1440, 800)] * 3
    assert plans[2].pad == GeometryMargins(left=9, right=9)
    assert plans[0].overlay_origin == (10, 10)


@pytest.mark.parametrize(
    "sources, mode, options, expected, bounded",
    [
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1920, 1080),
                    provenance="full_frame",
                    width=1920,
                    height=1080,
                    label="reference",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1280, 720),
                    provenance="full_frame",
                    width=1280,
                    height=720,
                    label="encode",
                ),
            ),
            "native",
            RenderGeometryOptions(),
            (
                {
                    "active_rect": GeometryRect(0, 0, 1920, 1080),
                    "crop": GeometryMargins(),
                    "scaled_size": (1920, 1080),
                    "pad": GeometryMargins(),
                    "final_canvas_size": (1920, 1080),
                    "overlay_origin": (10, 10),
                    "is_noop": True,
                },
                {
                    "active_rect": GeometryRect(0, 0, 1280, 720),
                    "final_canvas_size": (1280, 720),
                    "is_noop": True,
                },
            ),
            False,
            id="native_preserves_full_frame_for_multiple_sources",
        ),
        pytest.param(
            (
                SourceGeometry(
                    width=1920,
                    height=1080,
                    active_rect=GeometryRect(0, 140, 1920, 800),
                    provenance="content_derived",
                    label="reference",
                ),
            ),
            "native",
            RenderGeometryOptions(),
            (
                {
                    "active_rect": GeometryRect(0, 140, 1920, 800),
                    "provenance": "content_derived",
                    "crop_rect": GeometryRect(0, 0, 1920, 1080),
                    "crop": GeometryMargins(),
                    "cropped_size": (1920, 1080),
                    "scaled_size": (1920, 1080),
                    "pad": GeometryMargins(),
                    "final_canvas_size": (1920, 1080),
                    "is_noop": True,
                },
            ),
            False,
            id="native_preserves_active_picture_without_transform",
        ),
    ],
)
def test_geometry_native_geometry(
    sources: tuple[SourceGeometry, ...],
    mode: GeometryMode,
    options: RenderGeometryOptions,
    expected: tuple[dict[str, object], ...],
    bounded: bool,
) -> None:
    plans = plan_render_geometry(sources, mode=mode, options=options)
    assert len(plans) == len(expected)
    for plan, fields in zip(plans, expected, strict=True):
        for field, value in fields.items():
            assert getattr(plan, field) == value
    if bounded:
        assert all(
            plan.scaled_size[0] <= plan.final_canvas_size[0]
            and plan.scaled_size[1] <= plan.final_canvas_size[1]
            for plan in plans
        )


@pytest.mark.parametrize(
    "sources, mode, options, expected, bounded",
    [
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1921, 1081),
                    provenance="full_frame",
                    width=1921,
                    height=1081,
                    label="odd",
                ),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "provenance": "full_frame",
                    "active_rect": GeometryRect(0, 0, 1921, 1081),
                    "crop_rect": GeometryRect(0, 0, 1920, 1080),
                    "crop": GeometryMargins(right=1, bottom=1),
                    "final_canvas_size": (1920, 1080),
                },
            ),
            False,
            id="aligned_crops_odd_full_frame_to_mod_safe_size",
        ),
        pytest.param(
            (
                SourceGeometry(
                    width=100,
                    height=80,
                    active_rect=GeometryRect(0, 9, 100, 62),
                    provenance="content_derived",
                    label="odd-content",
                ),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "provenance": "content_derived",
                    "active_rect": GeometryRect(0, 9, 100, 62),
                    "crop_rect": GeometryRect(0, 10, 100, 60),
                    "crop": GeometryMargins(top=10, bottom=10),
                },
            ),
            False,
            id="aligned_mod_safes_odd_content_derived_crop",
        ),
        pytest.param(
            (
                SourceGeometry(
                    width=10,
                    height=10,
                    active_rect=GeometryRect(1, 1, 2, 2),
                    provenance="content_derived",
                    label="tiny-odd-content",
                ),
            ),
            "aligned",
            RenderGeometryOptions(),
            ({"active_rect": GeometryRect(1, 1, 2, 2), "crop_rect": GeometryRect(1, 1, 2, 2)},),
            False,
            id="aligned_preserves_tiny_odd_active_rect_when_no_even_crop_fits-0",
        ),
        pytest.param(
            (
                SourceGeometry(
                    width=10,
                    height=10,
                    active_rect=GeometryRect(1, 1, 1, 1),
                    provenance="content_derived",
                    label="tiny-odd-content",
                ),
            ),
            "aligned",
            RenderGeometryOptions(),
            ({"active_rect": GeometryRect(1, 1, 1, 1), "crop_rect": GeometryRect(1, 1, 1, 1)},),
            False,
            id="aligned_preserves_tiny_odd_active_rect_when_no_even_crop_fits-1",
        ),
    ],
)
def test_geometry_geometry_mod(
    sources: tuple[SourceGeometry, ...],
    mode: GeometryMode,
    options: RenderGeometryOptions,
    expected: tuple[dict[str, object], ...],
    bounded: bool,
) -> None:
    plans = plan_render_geometry(sources, mode=mode, options=options)
    assert len(plans) == len(expected)
    for plan, fields in zip(plans, expected, strict=True):
        for field, value in fields.items():
            assert getattr(plan, field) == value
    if bounded:
        assert all(
            plan.scaled_size[0] <= plan.final_canvas_size[0]
            and plan.scaled_size[1] <= plan.final_canvas_size[1]
            for plan in plans
        )


@pytest.mark.parametrize(
    "sources, mode, options, expected, bounded",
    [
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1920, 800),
                    provenance="full_frame",
                    width=1920,
                    height=800,
                    label="fhd-a",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1920, 800),
                    provenance="full_frame",
                    width=1920,
                    height=800,
                    label="fhd-b",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 3840, 2160),
                    provenance="full_frame",
                    width=3840,
                    height=2160,
                    label="uhd",
                ),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "final_canvas_size": (3840, 2160),
                    "scaled_size": (3840, 1600),
                    "pad": GeometryMargins(top=280, bottom=280),
                },
                {"final_canvas_size": (3840, 2160), "scaled_size": (3840, 1600)},
                {"final_canvas_size": (3840, 2160), "scaled_size": (3840, 2160)},
            ),
            False,
            id="aligned_largest_active_never_exceeds_target_without_aspect_crop",
        ),
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1920, 800),
                    provenance="full_frame",
                    width=1920,
                    height=800,
                    label="fhd-a",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1920, 800),
                    provenance="full_frame",
                    width=1920,
                    height=800,
                    label="fhd-b",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 280, 3840, 1600),
                    provenance="aspect_ratio_derived",
                    width=3840,
                    height=2160,
                    label="uhd",
                ),
            ),
            "aligned",
            RenderGeometryOptions(aligned_scale_policy="smallest_active"),
            (
                {"final_canvas_size": (1920, 800), "scaled_size": (1920, 800)},
                {"final_canvas_size": (1920, 800), "scaled_size": (1920, 800)},
                {"final_canvas_size": (1920, 800), "scaled_size": (1920, 800)},
            ),
            False,
            id="aligned_smallest_active_downscales_aspect_crop",
        ),
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1920, 800),
                    provenance="full_frame",
                    width=1920,
                    height=800,
                    label="reference",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 3840, 2160),
                    provenance="full_frame",
                    width=3840,
                    height=2160,
                    label="uhd",
                ),
            ),
            "aligned",
            RenderGeometryOptions(aligned_scale_policy="reference_active"),
            (
                {"final_canvas_size": (1920, 800)},
                {
                    "final_canvas_size": (1920, 800),
                    "scaled_size": (1422, 800),
                    "pad": GeometryMargins(left=249, right=249),
                },
            ),
            False,
            id="aligned_reference_active_uses_first_source_active_size",
        ),
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1920, 800),
                    provenance="full_frame",
                    width=1920,
                    height=800,
                    label="fhd",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 3840, 2160),
                    provenance="full_frame",
                    width=3840,
                    height=2160,
                    label="uhd",
                ),
            ),
            "aligned",
            RenderGeometryOptions(
                aligned_scale_policy="explicit_size",
                aligned_target_size=(3840, 2160),
            ),
            (
                {
                    "final_canvas_size": (3840, 2160),
                    "scaled_size": (3840, 1600),
                    "pad": GeometryMargins(top=280, bottom=280),
                },
                {"final_canvas_size": (3840, 2160)},
            ),
            False,
            id="aligned_explicit_size_preserves_exact_canvas",
        ),
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1921, 801),
                    provenance="full_frame",
                    width=1921,
                    height=801,
                    label="odd-wide",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 1281, 721),
                    provenance="full_frame",
                    width=1281,
                    height=721,
                    label="odd-small",
                ),
            ),
            "aligned",
            RenderGeometryOptions(aligned_scale_policy="largest_active"),
            (
                {"final_canvas_size": (1920, 800)},
                {"final_canvas_size": (1920, 800)},
            ),
            True,
            id="aligned_reduces_odd_derived_targets_to_mod_safe_canvas",
        ),
        pytest.param(
            (
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 2000, 500),
                    provenance="full_frame",
                    width=2000,
                    height=500,
                    label="wide",
                ),
                SourceGeometry(
                    active_rect=GeometryRect(0, 0, 800, 1000),
                    provenance="full_frame",
                    width=800,
                    height=1000,
                    label="tall",
                ),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {"final_canvas_size": (2000, 1000), "scaled_size": (2000, 500)},
                {"final_canvas_size": (2000, 1000), "scaled_size": (800, 1000)},
            ),
            False,
            id="aligned_mixed_envelope_policy_uses_max_width_and_height",
        ),
    ],
)
def test_geometry_geometry_target(
    sources: tuple[SourceGeometry, ...],
    mode: GeometryMode,
    options: RenderGeometryOptions,
    expected: tuple[dict[str, object], ...],
    bounded: bool,
) -> None:
    plans = plan_render_geometry(sources, mode=mode, options=options)
    assert len(plans) == len(expected)
    for plan, fields in zip(plans, expected, strict=True):
        for field, value in fields.items():
            assert getattr(plan, field) == value
    if bounded:
        assert all(
            plan.scaled_size[0] <= plan.final_canvas_size[0]
            and plan.scaled_size[1] <= plan.final_canvas_size[1]
            for plan in plans
        )


@pytest.mark.parametrize(
    "rect",
    [GeometryRect(0, 0, 0, 1080), GeometryRect(-1, 0, 100, 100), GeometryRect(1900, 0, 100, 100)],
)
@pytest.mark.parametrize("mode", ["native", "aligned"])
def test_invalid_active_rectangle_is_rejected(rect: GeometryRect, mode: GeometryMode) -> None:
    with pytest.raises(ValueError, match="active rectangle"):
        plan_render_geometry((SourceGeometry(1920, 1080, rect, "explicit"),), mode=mode)


def test_provided_fight_club_geometry_preserves_scale_and_canvas() -> None:
    plans = plan_render_geometry(
        (
            SourceGeometry(1920, 800, GeometryRect(0, 0, 1920, 800), "full_frame"),
            SourceGeometry(1920, 800, GeometryRect(0, 0, 1920, 800), "full_frame"),
            SourceGeometry(3840, 2160, GeometryRect(0, 280, 3840, 1600), "aspect_ratio_derived"),
        ),
        mode="aligned",
    )
    assert [plan.final_canvas_size for plan in plans] == [(3840, 1600)] * 3
    assert [plan.scaled_size for plan in plans] == [(3840, 1600)] * 3
    assert plans[2].crop == GeometryMargins(top=280, bottom=280)
