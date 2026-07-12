"""Source and reference selection tests for orchestration preparation."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from frame_compare.orchestration import preparation
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.orchestration.errors import (
    DuplicateSourceStemError,
    SourceSelectionError,
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
    def __init__(self) -> None:
        self.loaded: list[Path] = []

    def load(self, path: Path) -> SourceInfo:
        self.loaded.append(path)
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24000, 1001),
            format=cast(Any, object()),
            frame_props={
                "_Transfer": 16,
                "DolbyVisionRPU": b"opaque-rpu",
                "Ignored": {"not": "toml-safe"},
            },
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> vs.Core:
        raise AssertionError("Preparation probing should not request the VS core directly")


def test_execute_prep_rejects_duplicate_explicit_labels_before_probe_or_generated_state(
    tmp_path: Path,
) -> None:
    _create_config(
        tmp_path,
        content=MINIMAL_CONFIG
        + """
[sources.overrides."a.mkv"]
label = "Same"

[sources.overrides."b.mkv"]
label = "Same"
""",
    )
    _create_video_files(tmp_path / "comparison_videos", "a.mkv", "b.mkv")

    class FailIfLoaded:
        def load(self, _path: Path) -> None:
            raise AssertionError("source probing must not start")

    with pytest.raises(SourceSelectionError, match="duplicate explicit source label"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, FailIfLoaded())),
            )
        )

    assert not (tmp_path / "generated").exists()


def test_execute_prep_preserves_deterministic_four_clip_order_and_labels(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(
        input_dir,
        "03-delta.mkv",
        "01-bravo.mkv",
        "04-charlie.ts",
        "00-alpha.mp4",
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in prep.clips] == [
        input_dir / "00-alpha.mp4",
        input_dir / "01-bravo.mkv",
        input_dir / "03-delta.mkv",
        input_dir / "04-charlie.ts",
    ]
    assert [clip.label for clip in prep.clips] == [
        "00-alpha",
        "01-bravo",
        "03-delta",
        "04-charlie",
    ]


def test_execute_prep_explicit_reference_moves_selected_source_to_front(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nreference = "03-delta.mkv"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(
        input_dir,
        "00-alpha.mp4",
        "01-bravo.mkv",
        "03-delta.mkv",
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in prep.clips] == [
        input_dir / "03-delta.mkv",
        input_dir / "00-alpha.mp4",
        input_dir / "01-bravo.mkv",
    ]
    assert [clip.label for clip in prep.clips] == ["03-delta", "00-alpha", "01-bravo"]


def test_execute_prep_reference_auto_behaves_like_omitted_reference(tmp_path: Path) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nreference = "auto"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-alpha.mp4", "01-bravo.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in prep.clips] == [
        input_dir / "00-alpha.mp4",
        input_dir / "01-bravo.mkv",
    ]


def test_execute_prep_analysis_source_reference_selects_selected_reference(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nreference = "01-reference.mkv"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-default.mkv", "01-reference.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.analysis_clip is prep.clips[0]
    assert prep.analysis_clip.path == input_dir / "01-reference.mkv"


def test_execute_prep_analysis_source_selector_does_not_reorder_clips(tmp_path: Path) -> None:
    config_content = (
        METRIC_CONFIG
        + """
[sources]
analysis_source = "02-analysis.mkv"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv", "02-analysis.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path.name for clip in prep.clips] == [
        "00-reference.mkv",
        "01-encode.mkv",
        "02-analysis.mkv",
    ]
    assert prep.analysis_clip is not None
    assert prep.analysis_clip.path.name == "02-analysis.mkv"


def test_execute_prep_analysis_selection_domain_differs_by_analysis_source(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-analysis.mkv")
    _create_config(tmp_path, content=METRIC_CONFIG)
    reference_prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    _create_config(
        tmp_path,
        content=METRIC_CONFIG + '\n[sources]\nanalysis_source = "01-analysis.mkv"\n',
    )
    configured_prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in reference_prep.clips] == [
        clip.path for clip in configured_prep.clips
    ]
    assert reference_prep.analysis_selection_domain != configured_prep.analysis_selection_domain
    assert (
        json.loads(reference_prep.analysis_selection_domain)["analysis_source_path"]
        == (input_dir / "00-reference.mkv").as_posix()
    )
    assert (
        json.loads(configured_prep.analysis_selection_domain)["analysis_source_path"]
        == (input_dir / "01-analysis.mkv").as_posix()
    )


def test_execute_prep_invalid_analysis_source_selector_fails_when_metrics_required(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "missing"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")

    with pytest.raises(SourceSelectionError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )

    assert exc_info.value.context.details["role"] == "sources.analysis_source"


def test_execute_prep_invalid_analysis_source_selector_is_ignored_when_analysis_skipped(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nanalysis_source = "missing"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.analysis_clip is None
    assert prep.analysis_selection_domain == ""


def test_execute_prep_applies_source_trim_and_active_rect_overrides(tmp_path: Path) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."01-encode.mkv"]
trim_start_frames = 12
trim_end_frames = 5
active_rect = { x = 240, y = 0, width = 1440, height = 1080 }
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.clips[0].trim.trim_start_frames == 0
    assert prep.clips[1].trim.trim_start_frames == 12
    assert prep.clips[1].trim.trim_end_frame_inclusive == 94
    assert prep.clips[1].active_rect == ClipActiveRect(
        x=240,
        y=0,
        width=1440,
        height=1080,
        source="explicit",
        detection_mode="aspect_ratio",
    )


def test_execute_prep_reference_source_trims_constrain_effective_frame_domain(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."00-reference.mkv"]
trim_start_frames = 10
trim_end_frames = 5
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.clips[0].trim.trim_start_frames == 10
    assert prep.clips[0].trim.trim_end_frame_inclusive == 94
    assert prep.clips[0].effective_num_frames() == 85


def test_execute_prep_rejects_source_trims_that_remove_every_frame(tmp_path: Path) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."01-encode.mkv"]
trim_start_frames = 100
trim_end_frames = 0
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    with pytest.raises(SourceSelectionError, match="source trims remove every frame"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )


def test_execute_prep_rejects_duplicate_source_stems_before_probe(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv", "source.mp4")
    loader = FakeVSLoader()

    with pytest.raises(DuplicateSourceStemError):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert loader.loaded == []
