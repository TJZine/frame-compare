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
        plan_render_geometry((SourceGeometry(width=width, height=height),), mode="native")


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
            SourceGeometry(width=1000, height=500, label="wide"),
            SourceGeometry(width=800, height=800, label="square"),
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


@pytest.mark.parametrize(
    "sources, mode, options, expected, bounded",
    [
        pytest.param(
            (
                SourceGeometry(width=1920, height=1080, label="reference"),
                SourceGeometry(width=1280, height=720, label="encode"),
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
                    active_rect_source="content-derived",
                    label="reference",
                ),
            ),
            "native",
            RenderGeometryOptions(),
            (
                {
                    "active_rect": GeometryRect(0, 140, 1920, 800),
                    "active_rect_source": "content-derived",
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
                SourceGeometry(width=1920, height=1080, label="pillarboxed"),
                SourceGeometry(width=1440, height=1080, label="active"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "active_rect_source": "dimension-derived",
                    "active_rect": GeometryRect(240, 0, 1440, 1080),
                    "crop": GeometryMargins(left=240, right=240),
                    "cropped_size": (1440, 1080),
                    "final_canvas_size": (1440, 1080),
                    "overlay_origin": (10, 10),
                    "source_overlay_origin": (250, 10),
                },
                {
                    "crop": GeometryMargins(),
                    "final_canvas_size": (1440, 1080),
                    "overlay_origin": (10, 10),
                },
            ),
            False,
            id="aligned_same_height_center_crops_wider_source",
        ),
        pytest.param(
            (
                SourceGeometry(width=1920, height=1080, label="wide"),
                SourceGeometry(width=1600, height=1080, label="mid"),
                SourceGeometry(width=1440, height=1080, label="active"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "active_rect": GeometryRect(240, 0, 1440, 1080),
                    "crop": GeometryMargins(left=240, right=240),
                    "final_canvas_size": (1440, 1080),
                },
                {
                    "active_rect": GeometryRect(80, 0, 1440, 1080),
                    "crop": GeometryMargins(left=80, right=80),
                    "final_canvas_size": (1440, 1080),
                },
                {
                    "active_rect": GeometryRect(0, 0, 1440, 1080),
                    "crop": GeometryMargins(),
                    "final_canvas_size": (1440, 1080),
                },
            ),
            False,
            id="aligned_three_sources_same_height_center_crops_wider_sources",
        ),
        pytest.param(
            (
                SourceGeometry(width=1920, height=1080, label="letterboxed"),
                SourceGeometry(width=1920, height=800, label="active"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "active_rect_source": "dimension-derived",
                    "active_rect": GeometryRect(0, 140, 1920, 800),
                    "crop": GeometryMargins(top=140, bottom=140),
                    "cropped_size": (1920, 800),
                    "final_canvas_size": (1920, 800),
                    "source_overlay_origin": (10, 150),
                },
                {"crop": GeometryMargins(), "final_canvas_size": (1920, 800)},
            ),
            False,
            id="aligned_same_width_center_crops_taller_source",
        ),
        pytest.param(
            (
                SourceGeometry(width=1920, height=1080, label="tall"),
                SourceGeometry(width=1920, height=900, label="mid"),
                SourceGeometry(width=1920, height=800, label="active"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "active_rect": GeometryRect(0, 140, 1920, 800),
                    "crop": GeometryMargins(top=140, bottom=140),
                    "final_canvas_size": (1920, 800),
                },
                {
                    "active_rect": GeometryRect(0, 50, 1920, 800),
                    "crop": GeometryMargins(top=50, bottom=50),
                    "final_canvas_size": (1920, 800),
                },
                {
                    "active_rect": GeometryRect(0, 0, 1920, 800),
                    "crop": GeometryMargins(),
                    "final_canvas_size": (1920, 800),
                },
            ),
            False,
            id="aligned_three_sources_same_width_center_crops_taller_sources",
        ),
    ],
)
def test_geometry_geometry_axis(
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
            (SourceGeometry(width=1921, height=1081, label="odd"),),
            "aligned",
            RenderGeometryOptions(),
            (
                {
                    "active_rect_source": "full-frame",
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
                    active_rect_source="content-derived",
                    label="odd-content",
                ),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="provided"),
            (
                {
                    "active_rect_source": "content-derived",
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
                    active_rect_source="content-derived",
                    label="tiny-odd-content",
                ),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="provided"),
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
                    active_rect_source="content-derived",
                    label="tiny-odd-content",
                ),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="provided"),
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
                SourceGeometry(width=1920, height=800, label="fhd-a"),
                SourceGeometry(width=1920, height=800, label="fhd-b"),
                SourceGeometry(width=3840, height=2160, label="uhd"),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="provided"),
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
                SourceGeometry(width=1920, height=800, label="fhd-a"),
                SourceGeometry(width=1920, height=800, label="fhd-b"),
                SourceGeometry(width=3840, height=2160, label="uhd"),
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
                SourceGeometry(width=1920, height=800, label="reference"),
                SourceGeometry(width=3840, height=2160, label="uhd"),
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
                SourceGeometry(width=1920, height=800, label="fhd"),
                SourceGeometry(width=3840, height=2160, label="uhd"),
            ),
            "aligned",
            RenderGeometryOptions(
                active_rect_detection="provided",
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
                SourceGeometry(width=1921, height=801, label="odd-wide"),
                SourceGeometry(width=1281, height=721, label="odd-small"),
            ),
            "aligned",
            RenderGeometryOptions(
                active_rect_detection="provided", aligned_scale_policy="largest_active"
            ),
            (
                {"final_canvas_size": (1920, 800)},
                {"final_canvas_size": (1920, 800)},
            ),
            True,
            id="aligned_reduces_odd_derived_targets_to_mod_safe_canvas",
        ),
        pytest.param(
            (
                SourceGeometry(width=2000, height=500, label="wide"),
                SourceGeometry(width=800, height=1000, label="tall"),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="provided"),
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
    "sources, mode, options, expected, bounded",
    [
        pytest.param(
            (
                SourceGeometry(width=1920, height=800, label="fhd-a"),
                SourceGeometry(width=1920, height=800, label="fhd-b"),
                SourceGeometry(width=3840, height=2160, label="uhd"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {"final_canvas_size": (3840, 1600), "scaled_size": (3840, 1600)},
                {"final_canvas_size": (3840, 1600), "scaled_size": (3840, 1600)},
                {
                    "active_rect_source": "aspect-ratio-derived",
                    "active_rect": GeometryRect(0, 280, 3840, 1600),
                    "final_canvas_size": (3840, 1600),
                    "scaled_size": (3840, 1600),
                },
            ),
            False,
            id="aligned_aspect_ratio_largest_active_fight_club_shape",
        ),
        pytest.param(
            (
                SourceGeometry(width=1920, height=800, label="fhd-a"),
                SourceGeometry(width=1920, height=800, label="fhd-b"),
                SourceGeometry(width=3840, height=2160, label="uhd"),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="auto"),
            (
                {},
                {},
                {
                    "active_rect_source": "aspect-ratio-derived",
                    "active_rect": GeometryRect(0, 280, 3840, 1600),
                },
            ),
            False,
            id="auto_uses_static_aspect_ratio_fallback",
        ),
        pytest.param(
            (
                SourceGeometry(
                    width=3840,
                    height=2160,
                    active_rect=GeometryRect(0, 280, 3840, 1600),
                    active_rect_source="content-derived",
                    label="uhd",
                ),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="provided"),
            (
                {
                    "active_rect_source": "content-derived",
                    "active_rect": GeometryRect(0, 280, 3840, 1600),
                },
            ),
            False,
            id="aligned_accepts_content_derived_active_rect",
        ),
        pytest.param(
            (
                SourceGeometry(
                    width=1920,
                    height=1080,
                    active_rect=GeometryRect(0, 140, 1920, 800),
                    active_rect_source="content-derived",
                ),
                SourceGeometry(
                    width=1440,
                    height=900,
                    active_rect=GeometryRect(0, 150, 1440, 600),
                    active_rect_source="content-derived",
                ),
                SourceGeometry(width=3840, height=2160),
            ),
            "aligned",
            RenderGeometryOptions(active_rect_detection="auto"),
            (
                {},
                {},
                {
                    "active_rect_source": "aspect-ratio-derived",
                    "active_rect": GeometryRect(0, 280, 3840, 1600),
                },
            ),
            False,
            id="uses_supported_content_derived_ratio",
        ),
        pytest.param(
            (SourceGeometry(width=3840, height=2160, label="single"),),
            "aligned",
            RenderGeometryOptions(),
            ({"active_rect_source": "full-frame"},),
            False,
            id="aspect_ratio_does_not_crop_single_or_ultrawide_outlier-0",
        ),
        pytest.param(
            (
                SourceGeometry(width=3000, height=1000, label="ultrawide"),
                SourceGeometry(width=3840, height=2160, label="uhd-a"),
                SourceGeometry(width=3840, height=2160, label="uhd-b"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {"active_rect_source": "full-frame"},
                {"active_rect_source": "full-frame"},
                {"active_rect_source": "full-frame"},
            ),
            False,
            id="aspect_ratio_does_not_crop_single_or_ultrawide_outlier-1",
        ),
        pytest.param(
            (
                SourceGeometry(
                    width=1920,
                    height=1080,
                    active_rect=GeometryRect(0, 140, 1920, 800),
                    active_rect_source="explicit",
                    label="explicit",
                ),
                SourceGeometry(width=3840, height=2160, label="uhd"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {"active_rect_source": "explicit"},
                {
                    "active_rect_source": "aspect-ratio-derived",
                    "active_rect": GeometryRect(0, 280, 3840, 1600),
                },
            ),
            False,
            id="aspect_ratio_uses_explicit_or_metadata_single_evidence",
        ),
        pytest.param(
            (
                SourceGeometry(width=3000, height=500, label="very-wide-a"),
                SourceGeometry(width=3000, height=500, label="very-wide-b"),
                SourceGeometry(width=1920, height=2160, label="tall"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {},
                {},
                {"active_rect_source": "full-frame"},
            ),
            False,
            id="aspect_ratio_respects_removal_limit",
        ),
        pytest.param(
            (
                SourceGeometry(width=2000, height=1000, label="ref-a"),
                SourceGeometry(width=2000, height=1000, label="ref-b"),
                SourceGeometry(width=2400, height=1000, label="wide-a"),
                SourceGeometry(width=2400, height=1000, label="wide-b"),
                SourceGeometry(width=3840, height=2160, label="uhd"),
            ),
            "aligned",
            RenderGeometryOptions(),
            (
                {},
                {},
                {},
                {},
                {
                    "active_rect_source": "aspect-ratio-derived",
                    "active_rect": GeometryRect(0, 120, 3840, 1920),
                },
            ),
            False,
            id="aspect_ratio_prefers_reference_ratio_on_tie",
        ),
    ],
)
def test_geometry_geometry_ratio(
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
