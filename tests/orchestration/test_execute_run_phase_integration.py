"""Phase integration tests covered by execute_run fixtures."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from frame_compare.config.loader import load_config
from frame_compare.orchestration import phase_tasks
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.types import MetadataPrefetch, RenderArtifacts, RunArtifacts
from frame_compare.services.types import AlignmentResult, TmdbMetadata
from frame_compare.utils.types import WorkspacePaths

from .execute_run_helpers import (
    FakeFFmpegRunner,
    FakeVSLoader,
    clip_state,
    create_config,
    create_video_files,
)


def _workspace(tmp_path: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )


def test_execute_run_align_applies_trim_first_frame_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = true

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_ref.mkv", "b_comp1.mkv", "c_comp2.mkv")

    def _fake_align_clips(reference, comparisons, config, cache_dir, progress=None):
        return [
            AlignmentResult(
                reference_clip=reference.name,
                comparison_clip=comparisons[0].name,
                frame_offset=1,
                time_offset_seconds=0.041,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            ),
            AlignmentResult(
                reference_clip=reference.name,
                comparison_clip=comparisons[1].name,
                frame_offset=-1,
                time_offset_seconds=-0.041,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            ),
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    ffmpeg = FakeFFmpegRunner()
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=ffmpeg)
    request = RunRequest(
        root=tmp_path,
        frame_count=3,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )

    result = asyncio.run(execute_run(request, deps=deps))
    assert result.success is True
    assert result.frame_count == 3

    by_video: dict[str, list[int]] = {}
    for video_name, frame_num, _ in ffmpeg.calls:
        by_video.setdefault(video_name, []).append(frame_num)

    assert by_video["a_ref.mkv"] == [5, 50, 97]
    assert by_video["b_comp1.mkv"] == [4, 49, 96]
    assert by_video["c_comp2.mkv"] == [6, 51, 98]


def test_run_metadata_phase_uses_prefetched_metadata_without_client(tmp_path: Path) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = RunContext(
        config=config, workspace=_workspace(tmp_path), reference=reference, comparisons=[]
    )
    expected_metadata = TmdbMetadata(
        tmdb_id=789,
        title="Thief",
        original_title="Thief",
        year=1981,
        media_type="movie",
    )
    output = asyncio.run(
        phase_tasks.run_metadata_phase(
            ctx,
            client=None,
            metadata_prefetch=MetadataPrefetch(metadata=expected_metadata, was_attempted=True),
        )
    )

    assert output.resolved_metadata == expected_metadata


def test_run_publish_phase_without_client_clears_slowpics_url(tmp_path: Path) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = RunContext(
        config=config, workspace=_workspace(tmp_path), reference=reference, comparisons=[]
    )
    artifacts = RunArtifacts(slowpics_url="https://slow.pics/c/example")

    output = asyncio.run(
        phase_tasks.run_publish_phase(
            ctx,
            client=None,
            metadata=artifacts.resolved_metadata,
        )
    )

    assert output.slowpics_url is None
    assert artifacts.slowpics_url == "https://slow.pics/c/example"


def test_run_report_phase_clears_report_path_when_no_screenshots(tmp_path: Path) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = RunContext(
        config=config, workspace=_workspace(tmp_path), reference=reference, comparisons=[]
    )
    artifacts = RunArtifacts(report_path=tmp_path / "stale.html")

    output = phase_tasks.run_report_phase(
        ctx,
        frames=[1, 2],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    assert output.report_path is None
    assert artifacts.report_path == tmp_path / "stale.html"


def test_run_report_phase_builds_report_from_current_clip_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    comparison = clip_state(
        tmp_path / "comparison_videos" / "encode.mkv",
        label="Encode 1",
        num_frames=80,
    )
    ctx = RunContext(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[comparison],
    )
    metadata = TmdbMetadata(
        tmdb_id=321,
        title="Collateral",
        original_title="Collateral",
        year=2004,
        media_type="movie",
    )
    render = RenderArtifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "Reference_000001.png"],
            "Encode 1": [tmp_path / "screenshots" / "Encode_1_000001.png"],
        },
        screenshot_dir=tmp_path / "screenshots",
    )
    artifacts = RunArtifacts(
        render=render,
        resolved_metadata=metadata,
        slowpics_url="https://slow.pics/c/collateral",
    )
    captured: dict[str, Any] = {}
    expected_report_path = tmp_path / "report.html"

    def _fake_generate_report(report_data, report_config):
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        return expected_report_path

    monkeypatch.setattr(phase_tasks, "generate_report", _fake_generate_report)

    output = phase_tasks.run_report_phase(
        ctx,
        frames=[7, 11],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_report_path
    assert artifacts.report_path is None
    assert report_data.frames == [7, 11]
    assert report_data.clips[0].screenshots == render.screenshots_by_label["Reference"]
    assert report_data.clips[1].screenshots == render.screenshots_by_label["Encode 1"]
    assert report_data.metadata == metadata
    assert report_data.slowpics_url == "https://slow.pics/c/collateral"
    assert [(clip.name, clip.frame_count) for clip in report_data.clips] == [
        ("Reference", 100),
        ("Encode 1", 80),
    ]
    assert captured["report_config"] == config.report
