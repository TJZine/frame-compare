"""Run-info persistence tests for run-folder orchestration."""

from __future__ import annotations

import asyncio
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from frame_compare.orchestration import preparation
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run

from .execute_run_helpers import (
    RUN_FOLDERS_CONFIG,
    FakeFFmpegRunner,
    FakeVSLoader,
    create_config,
    create_video_files,
)

TMDB_RUN_FOLDERS_CONFIG = (
    RUN_FOLDERS_CONFIG
    + """
[tmdb]
enabled = true
api_key = "test-key"
unattended = true
"""
)


def test_execute_prep_writes_run_info_with_clock_and_no_http_client_skip(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=TMDB_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv", "encode.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        no_upload=True,
    )
    deps = RunDependencies(
        vs_loader=FakeVSLoader(),
        ffmpeg_runner=FakeFFmpegRunner(),
        clock=lambda: datetime(2026, 6, 8, 15, 30, 45, tzinfo=UTC),
    )

    result = asyncio.run(preparation.execute_prep(request, deps=deps))

    assert result.workspace.run_dir is not None
    run_info_path = result.workspace.run_dir / "run_info.toml"
    run_info = tomllib.loads(run_info_path.read_text(encoding="utf-8"))
    assert run_info["created_at"] == "2026-06-08T15:30:45Z"
    assert run_info["source_filenames"] == ["encode.mkv", "source.mkv"]
    assert run_info["tmdb"] == {
        "enabled": True,
        "attempted": False,
        "resolved": False,
        "failed": False,
        "skip_reason": "no_http_client",
    }


def test_execute_run_writes_run_info_with_skip_metadata_facts(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=TMDB_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.screenshot_dir is not None
    run_info = tomllib.loads(
        (result.screenshot_dir.parent / "run_info.toml").read_text(encoding="utf-8")
    )
    assert run_info["tmdb"] == {
        "enabled": True,
        "attempted": False,
        "resolved": False,
        "failed": False,
        "skip_reason": "skip_metadata",
    }
