"""Lifecycle-level tests for execute_run."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.config.schema import ConfigSchema, OverlayMode, TonemapPreset
from frame_compare.orchestration import coordinator
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.types import MetadataPrefetch, PrepState, RunArtifacts
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.errors import TonemapRequiresVapourSynthError
from frame_compare.vs.types import SourceInfo

from .execute_run_helpers import (
    FakeFFmpegRunner,
    FakeHDRVSLoader,
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


def test_execute_run_returns_success_and_records_preflight_timing(
    tmp_path: Path,
) -> None:
    """Given valid workspace -> returns success and records preflight timing."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.warnings == []
    assert result.screenshot_dir == (tmp_path / "screenshots").resolve()
    assert result.frame_count == 10
    assert result.clips_processed == 1
    assert result.duration_seconds >= 0.0
    assert result.cache_hit is False
    assert result.slowpics_url is None
    assert result.report_path is None
    expected_keys = {
        "preflight",
        "load_sources",
        "frame_plan",
        "analyze",
        "align",
        "render",
        "metadata",
        "dovi",
        "publish",
        "report",
    }
    assert set(result.phase_timings.keys()) == expected_keys
    assert result.phase_timings["preflight"] >= 0.0
    assert result.phase_timings["load_sources"] >= 0.0
    assert result.phase_timings["analyze"] == 0.0
    assert result.phase_timings["align"] == 0.0
    assert result.phase_timings["metadata"] == 0.0
    assert result.phase_timings["dovi"] == 0.0
    assert result.phase_timings["publish"] == 0.0
    assert result.phase_timings["report"] == 0.0


def test_execute_run_returns_preflight_and_runtime_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prep = PrepState(
        workspace=_workspace(tmp_path),
        config=ConfigSchema(),
        input_videos=[tmp_path / "reference.mkv"],
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(warnings=["report: warned"]),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=["preflight: warned"],
        preflight_duration=0.0,
        load_sources_start=datetime.now(),
    )

    async def fake_execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    async def fake_execute_phases(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "execute_phases", fake_execute_phases)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda *a, **kw: None)

    result = asyncio.run(execute_run(RunRequest(root=tmp_path, quiet=True), deps=RunDependencies()))

    assert result.success is True
    assert result.warnings == ["preflight: warned", "report: warned"]


def test_execute_run_ffmpeg_render_rejects_hdr_when_tonemap_enabled(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeHDRVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(TonemapRequiresVapourSynthError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_propagates_config_not_found_error(tmp_path: Path) -> None:
    """Given missing config -> preflight error is raised."""
    request = RunRequest(root=tmp_path)

    with pytest.raises(ConfigNotFoundError):
        asyncio.run(execute_run(request))


def test_execute_run_creates_and_discards_http_client_when_missing(
    tmp_path: Path,
) -> None:
    """Given no injected http client, execute_run must not leak the temporary client."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(root=tmp_path, quiet=True)
    deps = RunDependencies(
        http_client=None,
        vs_loader=FakeVSLoader(),
        ffmpeg_runner=FakeFFmpegRunner(),
    )

    asyncio.run(execute_run(request, deps=deps))

    assert deps.http_client is None


def test_execute_run_emits_fps_report_after_load_sources_and_after_align(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FPS report is emitted after LoadSources and after Align, even if Align is skipped."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv", "comp.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    calls: list[str] = []

    def _record_emit(*, stage: str, **_kwargs: Any) -> None:
        calls.append(stage)

    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", _record_emit)

    asyncio.run(execute_run(request, deps=deps))

    assert calls == ["after_load_sources", "after_align"]


def test_execute_run_applies_cli_overrides_before_phase_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI overrides are applied to config before phase execution begins."""
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = false
force_interactive = false
use_vspreview = false

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv", "comp.mkv")

    request = RunRequest(
        root=tmp_path,
        tm_preset=TonemapPreset.FILMIC,
        tm_target_nits=203,
        overlay_mode=OverlayMode.DIAGNOSTIC,
        seed=123,
        no_upload=True,
        force_interactive_alignment=True,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    captured: dict[str, object] = {}

    async def _capture_execute_phases(_phases: object, context: object, _reporter: object) -> None:
        if "config" not in captured:
            captured["config"] = context.config

    monkeypatch.setattr(coordinator, "execute_phases", _capture_execute_phases)

    asyncio.run(execute_run(request, deps=deps))

    config = cast(ConfigSchema, captured["config"])
    assert config.color.preset == TonemapPreset.FILMIC
    assert config.color.target_nits == 203
    assert config.screenshots.overlay_mode == OverlayMode.DIAGNOSTIC
    assert config.analysis.random_seed == 123
    assert config.slowpics.auto_upload is False
    assert config.audio_alignment.force_interactive is True
    assert config.audio_alignment.use_vspreview is True


def test_execute_run_publish_skip_follows_effective_slowpics_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[slowpics]
auto_upload = false

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    async def _unexpected_publish(**_kwargs: object) -> object:
        raise AssertionError("publish should be skipped by effective slowpics config")

    from frame_compare.orchestration import phase_tasks

    monkeypatch.setattr(phase_tasks, "publish_to_slowpics", _unexpected_publish)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=False,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.slowpics_url is None
    assert result.phase_timings["publish"] == 0.0


def test_execute_run_uses_and_populates_probe_cache_without_reprobing(tmp_path: Path) -> None:
    """Prove that probe cache is populated on first run and reused on second run without reprobe calls."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )

    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())
    result = asyncio.run(execute_run(request, deps=deps))
    assert result.success is True

    cache_path = tmp_path / "generated" / "clip_probe.toml"
    assert cache_path.exists()
    cache_before = cache_path.read_text(encoding="utf-8")

    class RaisingFakeVSLoader:
        def load(self, path: Path) -> SourceInfo:
            raise AssertionError(f"Fake VS loader should not be called: {path}")

        def ensure_core(self) -> object:
            raise AssertionError("Fake VS core should not be requested when cache is warm")

    reuse_deps = RunDependencies(vs_loader=RaisingFakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())
    reuse_result = asyncio.run(execute_run(request, deps=reuse_deps))
    assert reuse_result.success is True

    cache_after = cache_path.read_text(encoding="utf-8")
    assert cache_after == cache_before
