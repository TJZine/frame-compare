"""Tests for orchestration active-picture rectangle resolution."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.active_rect import (
    ACTIVE_RECT_RESOLUTION_ALGORITHM,
    active_rect_identity,
    active_rect_policy_identity,
    resolve_active_rects_for_clips,
)
from frame_compare.orchestration.context import (
    ClipActiveRect,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.errors import SourceSelectionError


def _clip(
    name: str,
    *,
    width: int,
    height: int,
    props: dict[str, str | int | float] | None = None,
) -> ClipState:
    path = Path(name)
    return ClipState(
        path=path,
        label=name,
        probe=ClipProbeSnapshot(
            fingerprint=ClipFingerprint(path=path, size_bytes=100, mtime_ns=1),
            width=width,
            height=height,
            num_frames=100,
            fps=Fraction(24, 1),
            is_hdr=False,
            preserved_frame_props=props or {},
        ),
        source_fps=Fraction(24, 1),
        effective_fps=Fraction(24, 1),
    )


def _resolve(
    clips: list[ClipState],
    *,
    detection: ScreenshotActiveRectDetection = ScreenshotActiveRectDetection.ASPECT_RATIO,
    overrides_by_path: dict[Path, SourceOverrideConfig] | None = None,
) -> list[ClipState]:
    return resolve_active_rects_for_clips(
        clips=clips,
        overrides_by_path=overrides_by_path or {},
        detection=detection,
    )


def test_provided_without_explicit_or_metadata_resolves_full_frame() -> None:
    clips = [_clip("ref.mkv", width=1920, height=1080), _clip("enc.mkv", width=1280, height=720)]

    resolved = _resolve(clips, detection=ScreenshotActiveRectDetection.PROVIDED)

    assert [clip.active_rect for clip in resolved] == [
        ClipActiveRect(
            x=0,
            y=0,
            width=1920,
            height=1080,
            source="full-frame",
            detection_mode="provided",
        ),
        ClipActiveRect(
            x=0,
            y=0,
            width=1280,
            height=720,
            source="full-frame",
            detection_mode="provided",
        ),
    ]


def test_explicit_override_wins_over_metadata_and_dimension_inference() -> None:
    ref = _clip(
        "ref.mkv",
        width=1920,
        height=1080,
        props={
            "DolbyVision_L5_Left": 100,
            "DolbyVision_L5_Right": 100,
            "DolbyVision_L5_Top": 0,
            "DolbyVision_L5_Bottom": 0,
        },
    )
    enc = _clip("enc.mkv", width=1440, height=1080)
    override = SourceOverrideConfig.model_validate(
        {"active_rect": {"x": 240, "y": 0, "width": 1440, "height": 1080}}
    )

    resolved = _resolve([ref, enc], overrides_by_path={ref.path: override})

    assert resolved[0].active_rect == ClipActiveRect(
        x=240,
        y=0,
        width=1440,
        height=1080,
        source="explicit",
        detection_mode="aspect_ratio",
    )


def test_invalid_explicit_override_raises_source_selection_error() -> None:
    clip = _clip("ref.mkv", width=1920, height=1080)
    override = SourceOverrideConfig.model_validate(
        {"active_rect": {"x": 1800, "y": 0, "width": 400, "height": 1080}}
    )

    with pytest.raises(SourceSelectionError, match="active_rect is outside source dimensions"):
        _resolve([clip], overrides_by_path={clip.path: override})


@pytest.mark.parametrize(
    "props",
    [
        {
            "DolbyVision_L5_Left": 100,
            "DolbyVision_L5_Right": 100,
            "DolbyVision_L5_Top": 40,
        },
        {
            "DolbyVision_L5_Left": -1,
            "DolbyVision_L5_Right": 100,
            "DolbyVision_L5_Top": 40,
            "DolbyVision_L5_Bottom": 40,
        },
        {
            "DolbyVision_L5_Left": 1000,
            "DolbyVision_L5_Right": 1000,
            "DolbyVision_L5_Top": 0,
            "DolbyVision_L5_Bottom": 0,
        },
        {
            "DolbyVision_L5_Left": 0,
            "DolbyVision_L5_Right": 0,
            "DolbyVision_L5_Top": 0,
            "DolbyVision_L5_Bottom": 0,
        },
    ],
)
def test_unsafe_metadata_falls_back_to_full_frame(props: dict[str, int]) -> None:
    clip = _clip("ref.mkv", width=1920, height=1080, props=props)

    resolved = _resolve([clip], detection=ScreenshotActiveRectDetection.PROVIDED)

    assert resolved[0].active_rect == ClipActiveRect(
        x=0,
        y=0,
        width=1920,
        height=1080,
        source="full-frame",
        detection_mode="provided",
    )


@pytest.mark.parametrize(
    "props",
    [
        {
            "DolbyVision_L5_Left": 100,
            "DolbyVision_L5_Right": 120,
            "DolbyVision_L5_Top": 40,
            "DolbyVision_L5_Bottom": 60,
        },
        {
            "_DolbyVision_L5_Left": 100,
            "_DolbyVision_L5_Right": 120,
            "_DolbyVision_L5_Top": 40,
            "_DolbyVision_L5_Bottom": 60,
        },
        {
            "DolbyVision_L5_Left": "100",
            "DolbyVision_L5_Right": "120",
            "DolbyVision_L5_Top": "40",
            "DolbyVision_L5_Bottom": "60",
        },
    ],
)
def test_metadata_l5_margins_resolve_active_rect(
    props: dict[str, str | int | float],
) -> None:
    clip = _clip(
        "ref.mkv",
        width=1920,
        height=1080,
        props=props,
    )

    resolved = _resolve([clip], detection=ScreenshotActiveRectDetection.PROVIDED)

    assert resolved[0].active_rect == ClipActiveRect(
        x=100,
        y=40,
        width=1700,
        height=980,
        source="metadata",
        detection_mode="provided",
    )


@pytest.mark.parametrize(
    "props",
    [
        {
            "DolbyVision_L50_Left": 100,
            "DolbyVision_L50_Right": 120,
            "DolbyVision_L50_Top": 40,
            "DolbyVision_L50_Bottom": 60,
        },
        {
            "DolbyVision_L5_LeftMargin": 100,
            "DolbyVision_L5_RightMargin": 120,
            "DolbyVision_L5_TopMargin": 40,
            "DolbyVision_L5_BottomMargin": 60,
        },
        {
            "DolbyVision_L5_Left": 100,
            "_DolbyVision_L5_Left": 101,
            "DolbyVision_L5_Right": 120,
            "DolbyVision_L5_Top": 40,
            "DolbyVision_L5_Bottom": 60,
        },
        {
            "_DolbyVision_L5_Left": 101,
            "DolbyVision_L5_Left": 100,
            "DolbyVision_L5_Right": 120,
            "DolbyVision_L5_Top": 40,
            "DolbyVision_L5_Bottom": 60,
        },
        {
            "DolbyVision_L5_Left": 100,
            "_DolbyVision_L5_Left": 100,
            "DolbyVision_L5_Right": 120,
            "DolbyVision_L5_Top": 40,
            "DolbyVision_L5_Bottom": 60,
        },
    ],
)
def test_near_miss_or_duplicate_l5_metadata_falls_back_to_full_frame(
    props: dict[str, str | int | float],
) -> None:
    clip = _clip("ref.mkv", width=1920, height=1080, props=props)

    resolved = _resolve([clip], detection=ScreenshotActiveRectDetection.PROVIDED)

    assert resolved[0].active_rect == ClipActiveRect(
        x=0,
        y=0,
        width=1920,
        height=1080,
        source="full-frame",
        detection_mode="provided",
    )


def test_dimension_detection_derives_centered_horizontal_crop() -> None:
    resolved = _resolve(
        [_clip("ref.mkv", width=1920, height=1080), _clip("enc.mkv", width=1440, height=1080)],
        detection=ScreenshotActiveRectDetection.DIMENSION,
    )

    assert [clip.active_rect for clip in resolved] == [
        ClipActiveRect(240, 0, 1440, 1080, "dimension-derived", "dimension"),
        ClipActiveRect(0, 0, 1440, 1080, "dimension-derived", "dimension"),
    ]


def test_dimension_detection_derives_centered_vertical_crop() -> None:
    resolved = _resolve(
        [_clip("ref.mkv", width=1920, height=1080), _clip("enc.mkv", width=1920, height=800)],
        detection=ScreenshotActiveRectDetection.DIMENSION,
    )

    assert [clip.active_rect for clip in resolved] == [
        ClipActiveRect(0, 140, 1920, 800, "dimension-derived", "dimension"),
        ClipActiveRect(0, 0, 1920, 800, "dimension-derived", "dimension"),
    ]


def test_dimension_detection_does_nothing_when_no_axis_matches() -> None:
    resolved = _resolve(
        [_clip("ref.mkv", width=1920, height=1080), _clip("enc.mkv", width=1440, height=800)],
        detection=ScreenshotActiveRectDetection.DIMENSION,
    )

    assert [clip.active_rect for clip in resolved] == [
        ClipActiveRect(0, 0, 1920, 1080, "full-frame", "dimension"),
        ClipActiveRect(0, 0, 1440, 800, "full-frame", "dimension"),
    ]


def test_aspect_ratio_detection_crops_letterboxed_source_with_two_source_evidence() -> None:
    resolved = _resolve(
        [
            _clip("ref.mkv", width=3840, height=2160),
            _clip("enc-a.mkv", width=1920, height=800),
            _clip("enc-b.mkv", width=1920, height=800),
        ]
    )

    assert resolved[0].active_rect == ClipActiveRect(
        0,
        280,
        3840,
        1600,
        "aspect-ratio-derived",
        "aspect_ratio",
    )


def test_auto_static_resolution_preserves_aspect_ratio_behavior_before_content_refinement() -> None:
    resolved = _resolve(
        [
            _clip("ref.mkv", width=3840, height=2160),
            _clip("enc-a.mkv", width=1920, height=800),
            _clip("enc-b.mkv", width=1920, height=800),
        ],
        detection=ScreenshotActiveRectDetection.AUTO,
    )

    assert resolved[0].active_rect == ClipActiveRect(
        0,
        280,
        3840,
        1600,
        "aspect-ratio-derived",
        "auto",
    )


def test_aspect_ratio_detection_uses_one_explicit_source_as_evidence() -> None:
    ref = _clip("ref.mkv", width=3840, height=2160)
    enc = _clip("enc.mkv", width=1920, height=1080)
    override = SourceOverrideConfig.model_validate(
        {"active_rect": {"x": 0, "y": 140, "width": 1920, "height": 800}}
    )

    resolved = _resolve([ref, enc], overrides_by_path={enc.path: override})

    assert resolved[0].active_rect == ClipActiveRect(
        0,
        280,
        3840,
        1600,
        "aspect-ratio-derived",
        "aspect_ratio",
    )


def test_aspect_ratio_detection_uses_one_metadata_source_as_evidence() -> None:
    ref = _clip("ref.mkv", width=3840, height=2160)
    enc = _clip(
        "enc.mkv",
        width=1920,
        height=1080,
        props={
            "DolbyVision_L5_Left": 0,
            "DolbyVision_L5_Right": 0,
            "DolbyVision_L5_Top": 140,
            "DolbyVision_L5_Bottom": 140,
        },
    )

    resolved = _resolve([ref, enc])

    assert resolved[0].active_rect == ClipActiveRect(
        0,
        280,
        3840,
        1600,
        "aspect-ratio-derived",
        "aspect_ratio",
    )


def test_aspect_ratio_detection_does_not_crop_single_source_or_large_removal() -> None:
    single = _resolve([_clip("single.mkv", width=3840, height=2160)])
    assert single[0].active_rect == ClipActiveRect(
        0,
        0,
        3840,
        2160,
        "full-frame",
        "aspect_ratio",
    )

    extreme = _resolve(
        [
            _clip("ref.mkv", width=3840, height=2160),
            _clip("wide-a.mkv", width=1920, height=400),
            _clip("wide-b.mkv", width=1920, height=400),
        ]
    )
    assert extreme[0].active_rect == ClipActiveRect(
        0,
        0,
        3840,
        2160,
        "full-frame",
        "aspect_ratio",
    )


def test_aspect_ratio_candidate_tie_is_reference_biased_and_identity_is_stable() -> None:
    resolved = _resolve(
        [
            _clip("ref.mkv", width=2400, height=1000),
            _clip("near-ref.mkv", width=1200, height=500),
            _clip("other-a.mkv", width=1920, height=800),
            _clip("other-b.mkv", width=1920, height=800),
        ]
    )

    assert resolved[0].active_rect == ClipActiveRect(
        0,
        0,
        2400,
        1000,
        "full-frame",
        "aspect_ratio",
    )
    rect = resolved[0].active_rect
    assert rect is not None
    assert active_rect_identity(rect) == {
        "x": 0,
        "y": 0,
        "width": 2400,
        "height": 1000,
        "source": "full-frame",
        "detection_mode": "aspect_ratio",
        "algorithm_id": ACTIVE_RECT_RESOLUTION_ALGORITHM,
    }
    assert active_rect_policy_identity(ScreenshotActiveRectDetection.ASPECT_RATIO) == {
        "detection_mode": "aspect_ratio",
        "algorithm_id": ACTIVE_RECT_RESOLUTION_ALGORITHM,
    }


def test_auto_policy_identity_is_stable() -> None:
    assert active_rect_policy_identity(ScreenshotActiveRectDetection.AUTO) == {
        "detection_mode": "auto",
        "algorithm_id": ACTIVE_RECT_RESOLUTION_ALGORITHM,
    }
