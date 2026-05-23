"""Unit tests for execute_run orchestration entry point."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from PIL import Image

import frame_compare.analysis.cache_io as cache_io
from frame_compare.config import ConfigSchema, OverlayMode, TonemapPreset, load_config
from frame_compare.errors import (
    AudioAlignmentError,
    CacheCorruptionError,
    CacheVersionMismatchError,
    ConfigNotFoundError,
    MetricsCalculationError,
    TmdbError,
    TonemapRequiresVapourSynthError,
)
from frame_compare.orchestration import coordinator, phase_tasks, preparation
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.execution import build_execution_phase_plan
from frame_compare.orchestration.types import ExecutionState, PrepState, RunArtifacts
from frame_compare.services.alignment import CACHE_FILE_NAME
from frame_compare.services.run_folder import derive_run_folder_name
from frame_compare.services.types import AlignmentResult, MetadataConfig, TmdbMetadata
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.types import HDRMetadata, SourceInfo

# Minimal valid TOML config content
MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""

RUN_FOLDERS_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def _create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    """Create a config file in the standard location."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(content)
    return config_file


def _create_video_files(input_dir: Path, *filenames: str) -> None:
    """Create empty video files for testing."""
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (input_dir / name).touch()


def _write_metrics_cache(cache_dir: Path, *, source_path: Path, config: ConfigSchema) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = cache_io.compute_cache_key([source_path], config.analysis)
    cache_payload = {
        "version": cache_io.CACHE_VERSION,
        "fingerprint": fingerprint,
        "luminance": [0.1] * 100,
        "motion": [0.2] * 100,
        "metadata": {
            "frame_count": 100,
            "fps": "24",
            "config_fingerprint": fingerprint,
            "clips": [
                {
                    "path": str(source_path),
                    "size": 0,
                    "mtime": 0.0,
                    "sha1": None,
                }
            ],
            "version": cache_io.CACHE_VERSION,
        },
    }
    (cache_dir / cache_io.CACHE_FILENAME).write_text(json.dumps(cache_payload), encoding="utf-8")


def _clip_state(path: Path, *, label: str, num_frames: int = 100) -> ClipState:
    probe = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path=path, size_bytes=0, mtime_ns=0),
        width=1920,
        height=1080,
        num_frames=num_frames,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    return ClipState(
        path=path,
        label=label,
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
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


def test_build_execution_phase_plan_preserves_align_boundary_and_progress_total(
    tmp_path: Path,
) -> None:
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )

    prep = PrepState(
        workspace=workspace,
        config=ConfigSchema(),
        input_videos=[
            tmp_path / "ref.mkv",
            tmp_path / "comp_a.mkv",
            tmp_path / "comp_b.mkv",
        ],
        clips=[
            _clip_state(tmp_path / "ref.mkv", label="Reference"),
            _clip_state(tmp_path / "comp_a.mkv", label="Encode 1"),
            _clip_state(tmp_path / "comp_b.mkv", label="Encode 2"),
        ],
        artifacts=RunArtifacts(),
        metadata_prefetched=False,
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=datetime.now(),
    )

    plan = build_execution_phase_plan(
        request=RunRequest(root=tmp_path),
        deps=RunDependencies(ffmpeg_runner=FakeFFmpegRunner()),
        prep=prep,
        state=ExecutionState(artifacts=prep.artifacts),
    )

    assert [phase.name for phase in plan.before_align] == ["frame_plan", "analyze", "align"]
    assert [phase.name for phase in plan.after_align] == [
        "render",
        "metadata",
        "dovi",
        "publish",
        "report",
    ]

    align_phase = next(phase for phase in plan.before_align if phase.name == "align")
    assert align_phase.progress_total == 1


def test_run_request_cli_override_args_capture_runtime_override_contract(tmp_path: Path) -> None:
    request = RunRequest(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        tm_preset=TonemapPreset.FILMIC,
        tm_target_nits=203,
        overlay_mode=OverlayMode.DIAGNOSTIC,
        frame_count=12,
        seed=123,
        no_upload=True,
        force_interactive_alignment=True,
    )

    assert request.cli_override_args() == {
        "tm_preset": TonemapPreset.FILMIC,
        "tm_target": 203,
        "tm_curve": None,
        "frame_count": 12,
        "seed": 123,
        "overlay": OverlayMode.DIAGNOSTIC,
        "no_upload": True,
        "force_interactive_alignment": True,
        "input": str(tmp_path / "comparison_videos"),
    }


class FakeVSLoader:
    def load(self, path: Path) -> SourceInfo:
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self):  # type: ignore[override]
        raise RuntimeError("ensure_core should not be called in tests")


class FakeHDRVSLoader(FakeVSLoader):
    def load(self, path: Path) -> SourceInfo:
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=True,
            hdr_metadata=HDRMetadata(
                mastering_display="G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)",
                max_cll=1000,
                max_fall=400,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
        )


class FakeFFmpegRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")
        self.calls.append((video.name, frame_num, output.name))

    def probe_hdr(self, video: Path):  # type: ignore[override]
        return HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=1,
            transfer=1,
            matrix=1,
        )


def test_execute_run_returns_success_and_records_preflight_timing(
    tmp_path: Path,
) -> None:
    """Given valid workspace → returns success and records preflight timing."""
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

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
        clips=[_clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(warnings=["report: warned"]),
        metadata_prefetched=False,
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
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

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
    """Given missing config → preflight error is raised."""
    request = RunRequest(root=tmp_path)

    with pytest.raises(ConfigNotFoundError):
        asyncio.run(execute_run(request))


def test_execute_run_creates_and_discards_http_client_when_missing(
    tmp_path: Path,
) -> None:
    """Given no injected http client, execute_run must not leak the temporary client."""
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

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
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv", "comp.mkv")

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
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv", "comp.mkv")

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

    async def _capture_execute_phases(_phases, context, _reporter):
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


def test_execute_run_no_cache_deletes_metrics_cache_and_offsets_cache(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv", "comp.mkv")

    analysis_cache_dir = tmp_path / "generated" / "cache"
    analysis_cache_dir.mkdir(parents=True, exist_ok=True)
    analysis_cache_path = analysis_cache_dir / cache_io.CACHE_FILENAME
    analysis_cache_path.write_text("{}", encoding="utf-8")

    offsets_path = tmp_path / "generated" / CACHE_FILE_NAME
    offsets_path.parent.mkdir(parents=True, exist_ok=True)
    offsets_path.write_text('version = "1"\n', encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        no_cache=True,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    asyncio.run(execute_run(request, deps=deps))

    assert not analysis_cache_path.exists()
    assert not offsets_path.exists()


def test_execute_run_no_cache_deletes_run_folder_cache_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv", "comp.mkv")

    run_name = "Movie (2024)"
    monkeypatch.setattr(
        preparation, "reserve_run_folder", lambda input_dir, **_kwargs: input_dir / run_name
    )
    run_generated_dir = input_dir / run_name / "generated"

    analysis_cache_dir = run_generated_dir / "cache"
    analysis_cache_dir.mkdir(parents=True, exist_ok=True)
    analysis_cache_path = analysis_cache_dir / cache_io.CACHE_FILENAME
    analysis_cache_path.write_text("{}", encoding="utf-8")

    offsets_path = run_generated_dir / CACHE_FILE_NAME
    offsets_path.write_text('version = "1"\n', encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        no_cache=True,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    asyncio.run(execute_run(request, deps=deps))

    assert not analysis_cache_path.exists()
    assert not offsets_path.exists()


def test_execute_run_from_cache_only_fails_when_metrics_cache_missing(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(MetricsCalculationError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_does_not_reserve_run_folder_when_metrics_cache_missing(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")
    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_dir = input_dir / run_name

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(MetricsCalculationError):
        asyncio.run(execute_run(request, deps=deps))

    assert not run_dir.exists()


def test_execute_run_from_cache_only_fails_when_metrics_cache_invalid(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    cache_dir = tmp_path / "generated" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_io.CACHE_FILENAME
    cache_path.write_text("{not-json", encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(CacheCorruptionError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_fails_when_metrics_cache_version_mismatch(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    cache_dir = tmp_path / "generated" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_io.CACHE_FILENAME
    config = load_config(tmp_path / "config" / "config.toml")
    fingerprint = cache_io.compute_cache_key([input_dir / "source.mkv"], config.analysis)
    cache_payload = {
        "version": cache_io.CACHE_VERSION + 1,
        "fingerprint": fingerprint,
        "luminance": [0.1],
        "motion": [0.2],
        "metadata": {
            "frame_count": 1,
            "fps": "24",
            "config_fingerprint": "test",
            "clips": [
                {
                    "path": str(input_dir / "source.mkv"),
                    "size": 0,
                    "mtime": 0.0,
                    "sha1": None,
                }
            ],
            "version": cache_io.CACHE_VERSION,
        },
    }
    cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(CacheVersionMismatchError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_uses_run_folder_cache_when_enabled(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_generated_dir = input_dir / run_name / "generated"
    cache_dir = run_generated_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_io.CACHE_FILENAME

    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    fingerprint = cache_io.compute_cache_key([source_path], config.analysis)
    cache_payload = {
        "version": cache_io.CACHE_VERSION,
        "fingerprint": fingerprint,
        "luminance": [0.1] * 100,
        "motion": [0.2] * 100,
        "metadata": {
            "frame_count": 100,
            "fps": "24",
            "config_fingerprint": fingerprint,
            "clips": [
                {
                    "path": str(source_path),
                    "size": 0,
                    "mtime": 0.0,
                    "sha1": None,
                }
            ],
            "version": cache_io.CACHE_VERSION,
        },
    }
    cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True
    assert result.warnings == []
    assert result.screenshot_dir == (run_generated_dir.parent / "screenshots").resolve()
    assert result.slowpics_url is None


def test_execute_run_from_cache_only_preserves_existing_run_folder_casing(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    existing_run_name = run_name.upper()
    run_generated_dir = input_dir / existing_run_name / "generated"
    source_path = input_dir / "source.mkv"
    config = load_config(tmp_path / "config" / "config.toml")
    _write_metrics_cache(run_generated_dir / "cache", source_path=source_path, config=config)

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True
    assert result.screenshot_dir == (input_dir / existing_run_name / "screenshots").resolve()


def test_execute_run_from_cache_only_requires_cached_audio_offsets_when_alignment_enabled(
    tmp_path: Path,
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
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a_source.mkv", "b_comp.mkv")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(AudioAlignmentError, match="a_source:b_comp"):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_ignores_prefetched_tmdb_run_folder_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false

[tmdb]
enabled = true
api_key = "test-key"
unattended = true
"""
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_generated_dir = input_dir / run_name / "generated"
    cache_dir = run_generated_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    fingerprint = cache_io.compute_cache_key([source_path], config.analysis)
    cache_payload = {
        "version": cache_io.CACHE_VERSION,
        "fingerprint": fingerprint,
        "luminance": [0.1] * 100,
        "motion": [0.2] * 100,
        "metadata": {
            "frame_count": 100,
            "fps": "24",
            "config_fingerprint": fingerprint,
            "clips": [
                {
                    "path": str(source_path),
                    "size": 0,
                    "mtime": 0.0,
                    "sha1": None,
                }
            ],
            "version": cache_io.CACHE_VERSION,
        },
    }
    (cache_dir / cache_io.CACHE_FILENAME).write_text(json.dumps(cache_payload), encoding="utf-8")

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata:
        del filenames, config, client
        return TmdbMetadata(
            tmdb_id=123,
            title="Fight Club",
            original_title="Fight Club",
            year=1999,
            media_type="movie",
        )

    monkeypatch.setattr(phase_tasks, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True
    assert result.screenshot_dir == (input_dir / run_name / "screenshots").resolve()


def test_execute_run_passes_prefetched_tmdb_metadata_to_run_folder_derivation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    expected_metadata = TmdbMetadata(
        tmdb_id=123,
        title="Fight Club",
        original_title="Fight Club",
        year=1999,
        media_type="movie",
    )

    captured_tmdb_metadata: list[TmdbMetadata | None] = []
    resolve_calls: list[list[str]] = []

    def _capture_reserve_run_folder(
        input_dir: Path, filenames: list[str], tmdb_metadata: TmdbMetadata | None
    ) -> Path:
        del filenames
        captured_tmdb_metadata.append(tmdb_metadata)
        return input_dir / "Fight Club (1999)"

    async def _fake_resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata | None:
        del config, client
        resolve_calls.append(filenames)
        return expected_metadata

    monkeypatch.setattr(preparation, "reserve_run_folder", _capture_reserve_run_folder)
    monkeypatch.setattr(phase_tasks, "resolve_metadata", _fake_resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert captured_tmdb_metadata == [expected_metadata]
    assert resolve_calls == [["source.mkv"]]
    assert result.screenshot_dir is not None
    assert result.screenshot_dir == (input_dir / "Fight Club (1999)" / "screenshots").resolve()


def test_execute_run_retries_metadata_phase_when_run_folder_prefetch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false

[tmdb]
enabled = true
api_key = "test-key"
unattended = true
timeout_seconds = 7.5
"""
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    expected_metadata = TmdbMetadata(
        tmdb_id=456,
        title="Heat",
        original_title="Heat",
        year=1995,
        media_type="movie",
    )

    prefetch_calls: list[list[str]] = []
    phase_calls: list[list[str]] = []
    captured_configs: list[MetadataConfig] = []

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata | None:
        del client
        captured_configs.append(config)
        if not prefetch_calls:
            prefetch_calls.append(filenames)
            raise TmdbError("temporary metadata failure")
        phase_calls.append(filenames)
        return expected_metadata

    monkeypatch.setattr(phase_tasks, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.warnings == []
    assert prefetch_calls == [["source.mkv"]]
    assert phase_calls == [["source.mkv"]]
    assert captured_configs == [
        MetadataConfig(api_key="test-key", unattended=True, timeout_seconds=7.5),
        MetadataConfig(api_key="test-key", unattended=True, timeout_seconds=7.5),
    ]


def test_execute_run_propagates_unexpected_run_folder_metadata_prefetch_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false

[tmdb]
enabled = true
api_key = "test-key"
unattended = true
timeout_seconds = 7.5
"""
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata | None:
        del filenames, config, client
        raise RuntimeError("unexpected metadata failure")

    monkeypatch.setattr(phase_tasks, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(RuntimeError, match="unexpected metadata failure"):
        asyncio.run(execute_run(request, deps=deps))


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
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    async def _unexpected_publish(**_kwargs: object) -> object:
        raise AssertionError("publish should be skipped by effective slowpics config")

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
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a_ref.mkv", "b_comp1.mkv", "c_comp2.mkv")

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


def test_execute_run_uses_and_populates_probe_cache_without_reprobing(tmp_path: Path) -> None:
    """Prove that probe cache is populated on first run and reused on second run without reprobe calls."""
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )

    # 1. First run populates the cache
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())
    result = asyncio.run(execute_run(request, deps=deps))
    assert result.success is True

    cache_path = tmp_path / "generated" / "clip_probe.toml"
    assert cache_path.exists()
    cache_before = cache_path.read_text(encoding="utf-8")

    # 2. Second run with RaisingFakeVSLoader uses the cache
    class RaisingFakeVSLoader:
        def load(self, path: Path) -> SourceInfo:
            raise AssertionError(f"Fake VS loader should not be called: {path}")

        def ensure_core(self):
            raise AssertionError("Fake VS core should not be requested when cache is warm")

    reuse_deps = RunDependencies(vs_loader=RaisingFakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())
    reuse_result = asyncio.run(execute_run(request, deps=reuse_deps))
    assert reuse_result.success is True

    cache_after = cache_path.read_text(encoding="utf-8")
    assert cache_after == cache_before


def test_run_metadata_phase_uses_prefetched_metadata_without_client(tmp_path: Path) -> None:
    _create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = _clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
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
    artifacts = RunArtifacts(resolved_metadata=expected_metadata)

    asyncio.run(
        phase_tasks.run_metadata_phase(
            ctx,
            client=None,
            prefetched_metadata=expected_metadata,
            metadata_prefetched=True,
            artifacts=artifacts,
        )
    )

    assert artifacts.resolved_metadata == expected_metadata


def test_run_publish_phase_without_client_clears_slowpics_url(tmp_path: Path) -> None:
    _create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = _clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = RunContext(
        config=config, workspace=_workspace(tmp_path), reference=reference, comparisons=[]
    )
    artifacts = RunArtifacts(slowpics_url="https://slow.pics/c/example")

    asyncio.run(phase_tasks.run_publish_phase(ctx, client=None, artifacts=artifacts))

    assert artifacts.slowpics_url is None


def test_run_report_phase_clears_report_path_when_no_screenshots(tmp_path: Path) -> None:
    _create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = _clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = RunContext(
        config=config, workspace=_workspace(tmp_path), reference=reference, comparisons=[]
    )
    artifacts = RunArtifacts(report_path=tmp_path / "stale.html")

    phase_tasks.run_report_phase(ctx, frames=[1, 2], artifacts=artifacts)

    assert artifacts.report_path is None


def test_run_report_phase_builds_report_from_current_clip_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = _clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    comparison = _clip_state(
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
    artifacts = RunArtifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "Reference_000001.png"],
            "Encode 1": [tmp_path / "screenshots" / "Encode_1_000001.png"],
        },
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

    phase_tasks.run_report_phase(ctx, frames=[7, 11], artifacts=artifacts)

    report_data = captured["report_data"]
    assert artifacts.report_path == expected_report_path
    assert report_data.frames == [7, 11]
    assert report_data.clips[0].screenshots == artifacts.screenshots_by_label["Reference"]
    assert report_data.clips[1].screenshots == artifacts.screenshots_by_label["Encode 1"]
    assert report_data.metadata == metadata
    assert report_data.slowpics_url == "https://slow.pics/c/collateral"
    assert [(clip.name, clip.frame_count) for clip in report_data.clips] == [
        ("Reference", 100),
        ("Encode 1", 80),
    ]
    assert captured["report_config"] == config.report
