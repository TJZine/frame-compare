"""Effective-FPS policy tests for orchestration preparation."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from frame_compare.orchestration import preparation
from frame_compare.orchestration.errors import (
    MixedSourceFpsError,
)
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.vs.types import SourceInfo
from tests.orchestration.preparation_test_support import (
    METRIC_CONFIG,
    MINIMAL_CONFIG,
)
from tests.orchestration.preparation_test_support import (
    create_config as _create_config,
)
from tests.orchestration.preparation_test_support import (
    create_video_files as _create_video_files,
)

if TYPE_CHECKING:
    import vapoursynth as vs


class FakeVSLoader:
    def __init__(
        self,
        *,
        fps_by_name: dict[str, Fraction] | None = None,
        dimensions_by_name: dict[str, tuple[int, int]] | None = None,
        frame_props_by_name: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.loaded: list[Path] = []
        self._fps_by_name = fps_by_name or {}
        self._dimensions_by_name = dimensions_by_name or {}
        self._frame_props_by_name = frame_props_by_name or {}

    def load(self, path: Path) -> SourceInfo:
        self.loaded.append(path)
        width, height = self._dimensions_by_name.get(path.name, (1920, 1080))
        return SourceInfo(
            clip=cast(Any, object()),
            width=width,
            height=height,
            num_frames=100,
            fps=self._fps_by_name.get(path.name, Fraction(24000, 1001)),
            format=cast(Any, object()),
            frame_props=self._frame_props_by_name.get(
                path.name,
                {
                    "_Transfer": 16,
                    "DolbyVisionRPU": b"opaque-rpu",
                    "Ignored": {"not": "toml-safe"},
                },
            ),
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> vs.Core:
        raise AssertionError("Preparation probing should not request the VS core directly")


@pytest.mark.parametrize(
    ("config_content", "fps_by_name", "source_fps", "effective_fps", "reference", "domain_fps"),
    [
        pytest.param(
            MINIMAL_CONFIG
            + '\n[sources.overrides."01-encode.mkv"]\neffective_fps = "24000/1001"\n',
            {"00-reference.mkv": Fraction(24000, 1001), "01-encode.mkv": Fraction(30000, 1001)},
            [Fraction(24000, 1001), Fraction(30000, 1001)],
            [Fraction(24000, 1001), Fraction(24000, 1001)],
            None,
            None,
            id="applies_effective_fps_overrides_without_changing_source_fps",
        ),
        pytest.param(
            MINIMAL_CONFIG
            + '\n[sources]\nreference = "00-reference.mkv"\nmatch_fps = "assume_reference"\n',
            {
                "00-reference.mkv": Fraction(24000, 1001),
                "01-source-24.mkv": Fraction(24, 1),
                "02-source-ntsc-ish.mkv": Fraction(13978, 583),
            },
            [Fraction(24000, 1001), Fraction(24, 1), Fraction(13978, 583)],
            [Fraction(24000, 1001), Fraction(24000, 1001), Fraction(24000, 1001)],
            None,
            None,
            id="match_fps_assumes_reference_for_unoverridden_comparisons",
        ),
        pytest.param(
            METRIC_CONFIG
            + '\n[sources]\nreference = "02-reference-ntsc.mkv"\nmatch_fps = "assume_reference"\n',
            {"00-default-24.mkv": Fraction(24, 1), "02-reference-ntsc.mkv": Fraction(30000, 1001)},
            [Fraction(30000, 1001), Fraction(24, 1)],
            [Fraction(30000, 1001), Fraction(30000, 1001)],
            "02-reference-ntsc.mkv",
            [{"numerator": 30000, "denominator": 1001}, {"numerator": 30000, "denominator": 1001}],
            id="match_fps_uses_selected_reference_before_matching",
        ),
    ],
)
def test_execute_prep_effective_fps(
    config_content: str,
    fps_by_name: dict[str, Fraction],
    source_fps: list[Fraction],
    effective_fps: list[Fraction],
    reference: str | None,
    domain_fps: list[dict[str, int]] | None,
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, *fps_by_name)
    loader = FakeVSLoader(fps_by_name=fps_by_name)
    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path), RunDependencies(vs_loader=cast(Any, loader))
        )
    )
    assert [clip.source_fps for clip in prep.clips] == source_fps
    assert [clip.effective_fps for clip in prep.clips] == effective_fps
    if reference is not None:
        selection_domain = json.loads(prep.analysis_selection_domain)
        assert selection_domain["reference_path"] == (input_dir / reference).as_posix()
        assert [clip["effective_fps"] for clip in selection_domain["clips"]] == domain_fps


def test_execute_prep_match_fps_preserves_explicit_comparison_effective_fps(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources]
match_fps = "assume_reference"

[sources.overrides."01-source-25.mkv"]
effective_fps = "25/1"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-source-25.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-source-25.mkv": Fraction(25, 1),
        }
    )

    with pytest.raises(MixedSourceFpsError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details["comparison_fps"] == "25"


@pytest.mark.parametrize(
    (
        "names",
        "fps_by_name",
        "source_fps",
        "effective_fps",
        "diagnostic",
        "no_diagnostics",
        "warning_fragment",
        "no_warnings",
    ),
    [
        pytest.param(
            ["00-reference.mkv", "01-majority.mkv", "02-outlier.mkv"],
            {
                "00-reference.mkv": Fraction(24000, 1001),
                "01-majority.mkv": Fraction(24000, 1001),
                "02-outlier.mkv": Fraction(24, 1),
            },
            [Fraction(24000, 1001), Fraction(24000, 1001), Fraction(24, 1)],
            [Fraction(24000, 1001)] * 3,
            "FPS target: 24000/1001 (majority)",
            False,
            None,
            True,
            id="_matches_outlier_and_preserves_source_fps",
        ),
        pytest.param(
            ["00-reference.mkv", "01-a.mkv", "02-b.mkv"],
            {
                "00-reference.mkv": Fraction(24000, 1001),
                "01-a.mkv": Fraction(24, 1),
                "02-b.mkv": Fraction(25, 1),
            },
            None,
            [Fraction(24000, 1001)] * 3,
            "FPS target: 24000/1001 (reference fallback; no FPS majority)",
            False,
            "reference fallback; no FPS majority",
            None,
            id="_falls_back_to_reference_without_majority",
        ),
        pytest.param(
            ["00-reference.mkv", "01-encode.mkv"],
            {},
            None,
            None,
            None,
            True,
            None,
            True,
            id="_noop_has_no_diagnostic_noise",
        ),
        pytest.param(
            ["00-reference-outlier.mkv", "01-majority.mkv", "02-majority.mkv"],
            {
                "00-reference-outlier.mkv": Fraction(24, 1),
                "01-majority.mkv": Fraction(24000, 1001),
                "02-majority.mkv": Fraction(24000, 1001),
            },
            [Fraction(24, 1), Fraction(24000, 1001), Fraction(24000, 1001)],
            [Fraction(24000, 1001)] * 3,
            None,
            False,
            None,
            None,
            id="_can_change_reference_outlier",
        ),
    ],
)
def test_execute_prep_majority_fps(
    names: list[str],
    fps_by_name: dict[str, Fraction],
    source_fps: list[Fraction] | None,
    effective_fps: list[Fraction] | None,
    diagnostic: str | None,
    no_diagnostics: bool,
    warning_fragment: str | None,
    no_warnings: bool | None,
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=MINIMAL_CONFIG + '\n[sources]\nmatch_fps = "majority"\n')
    _create_video_files(tmp_path / "comparison_videos", *names)
    loader = FakeVSLoader(fps_by_name=fps_by_name)
    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path), RunDependencies(vs_loader=cast(Any, loader))
        )
    )
    if source_fps is not None:
        assert [clip.source_fps for clip in prep.clips] == source_fps
    if effective_fps is not None:
        assert [clip.effective_fps for clip in prep.clips] == effective_fps
    if diagnostic is not None:
        assert diagnostic in prep.load_source_diagnostics
    if no_diagnostics:
        assert prep.load_source_diagnostics == []
    if warning_fragment is not None:
        assert any(warning_fragment in warning for warning in prep.preflight_warnings)
    if no_warnings:
        assert prep.preflight_warnings == []


def test_execute_prep_match_fps_majority_preserves_explicit_override_and_can_still_fail(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources]
match_fps = "majority"

[sources.overrides."02-explicit.mkv"]
effective_fps = "25/1"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-majority.mkv", "02-explicit.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-majority.mkv": Fraction(24000, 1001),
            "02-explicit.mkv": Fraction(24, 1),
        }
    )

    with pytest.raises(MixedSourceFpsError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details["comparison_fps"] == "25"


def test_execute_prep_rejects_mixed_source_fps_before_downstream_work(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a_reference.mkv", "b_comparison.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "a_reference.mkv": Fraction(24000, 1001),
            "b_comparison.mkv": Fraction(30000, 1001),
        }
    )

    with pytest.raises(MixedSourceFpsError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    error = exc_info.value
    assert error.code == "FC-3011"
    assert "Mixed source FPS is not supported" in error.context.message
    assert error.context.details == {
        "reference_path": str(input_dir / "a_reference.mkv"),
        "reference_fps": "24000/1001",
        "comparison_label": "b_comparison",
        "comparison_path": str(input_dir / "b_comparison.mkv"),
        "comparison_fps": "30000/1001",
    }
