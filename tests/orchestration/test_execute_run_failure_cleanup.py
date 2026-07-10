"""Failure cleanup and containment tests for run-folder orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from frame_compare.orchestration import preparation
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.vs.types import SourceInfo

from .execute_run_helpers import (
    RUN_FOLDERS_CONFIG,
    FakeFFmpegRunner,
    create_config,
    create_video_files,
)


class NoProbeVSLoader:
    def load(self, path: Path) -> SourceInfo:
        del path
        raise AssertionError("run_info write failure should happen before probing")

    def ensure_core(self) -> object:
        raise AssertionError("run_info write failure should happen before VS core access")


def test_execute_run_run_info_write_failure_happens_before_probing_and_cleans_empty_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    generated_dir = preparation.prepare_preflight(root=tmp_path).workspace.generated_dir

    def _fail_write_run_info(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(preparation, "write_run_info", _fail_write_run_info)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=NoProbeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(OSError, match="disk full"):
        asyncio.run(execute_run(request, deps=deps))

    assert generated_dir.is_dir()
    assert not any(path.is_dir() for path in generated_dir.iterdir())
