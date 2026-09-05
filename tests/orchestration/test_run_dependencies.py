from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC
from pathlib import Path
from types import SimpleNamespace

import pytest

from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration import RunDependencies as PublicRunDependencies
from frame_compare.orchestration.coordinator import (
    RunDependencies,
    execute_run,
)
from frame_compare.orchestration.execution_types import RunArtifacts
from frame_compare.orchestration.types import (
    FullWindowRetryConfirmationDecision,
    FullWindowRetryConfirmationRequest,
    ReservedRunCapture,
    RunRequest,
    SlowpicsUploadConfirmationDecision,
    SlowpicsUploadConfirmationRequest,
)
from frame_compare.utils.progress import NullProgressReporter
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.types import HDRMetadata


class StopAfterDependencyInit(RuntimeError):
    pass


class DummyFFmpegRunner:
    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        raise RuntimeError("Not used in tests.")

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        return None


def test_run_dependencies_exported_from_orchestration() -> None:
    assert PublicRunDependencies is RunDependencies


def test_run_dependencies_default_clock_is_aware_utc() -> None:
    assert RunDependencies().clock().tzinfo is UTC


def test_run_artifacts_warning_defaults_are_isolated() -> None:
    first = RunArtifacts()
    second = RunArtifacts()

    first.warnings.append("first-run warning")

    assert second.warnings == []


def test_execute_run_initializes_local_dependencies_without_mutating_injected_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    captured_local_deps: RunDependencies | None = None
    prep_completed = False
    configured_timeouts: list[float] = []

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        nonlocal captured_local_deps, prep_completed
        captured_local_deps = local_deps
        assert local_deps is not deps
        assert local_deps.vs_loader is not None
        assert local_deps.ffmpeg_runner is None
        assert local_deps.progress is not None
        assert local_deps.http_client is not None
        prep_completed = True
        return SimpleNamespace(
            config=ConfigSchema(
                screenshots={"ffmpeg_timeout_seconds": 47.0},
            )
        )

    def fake_default_ffmpeg_runner(*, extraction_timeout_seconds: float):
        assert prep_completed is True
        configured_timeouts.append(extraction_timeout_seconds)
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "DefaultFFmpegRunner", fake_default_ffmpeg_runner)

    request = RunRequest(root=tmp_path, quiet=True)
    deps = RunDependencies()

    assert deps.vs_loader is None
    assert deps.ffmpeg_runner is None
    assert deps.progress is None

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(request, deps=deps))

    assert captured_local_deps is not None
    assert configured_timeouts == [47.0]
    assert deps.vs_loader is None
    assert deps.ffmpeg_runner is None
    assert deps.progress is None
    assert deps.http_client is None


def test_execute_run_preserves_injected_ffmpeg_runner_after_prep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    injected_runner = DummyFFmpegRunner()

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        assert local_deps.ffmpeg_runner is injected_runner
        return SimpleNamespace(config=ConfigSchema(), artifacts=None)

    def fail_default_ffmpeg_runner(*, extraction_timeout_seconds: float):
        del extraction_timeout_seconds
        raise AssertionError("injected FFmpeg runner must not be replaced")

    def stop_after_ffmpeg_resolution(*, artifacts: object):
        del artifacts
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "DefaultFFmpegRunner", fail_default_ffmpeg_runner)
    monkeypatch.setattr(coordinator, "ExecutionState", stop_after_ffmpeg_resolution)

    deps = RunDependencies(ffmpeg_runner=injected_runner)
    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(RunRequest(root=tmp_path, quiet=True), deps=deps))

    assert deps.ffmpeg_runner is injected_runner


def test_execute_run_passes_no_color_to_progress_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    captured: dict[str, bool] = {}
    progress = NullProgressReporter()

    def fake_select_reporter(
        *,
        quiet: bool = False,
        json_output: bool = False,
        no_color: bool = False,
        force_tty: bool | None = None,
    ) -> NullProgressReporter:
        del force_tty
        captured["quiet"] = quiet
        captured["json_output"] = json_output
        captured["no_color"] = no_color
        return progress

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        assert local_deps.progress is progress
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "select_reporter", fake_select_reporter)
    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(RunRequest(root=tmp_path, no_color=True), deps=RunDependencies()))

    assert captured == {
        "quiet": False,
        "json_output": False,
        "no_color": True,
    }


def test_execute_run_preserves_slowpics_confirmation_callback_when_cloning_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    captured_local_deps: RunDependencies | None = None

    def _confirm(
        _request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        return "confirmed"

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        nonlocal captured_local_deps
        captured_local_deps = local_deps
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)

    deps = RunDependencies(confirm_slowpics_upload=_confirm)

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(RunRequest(root=tmp_path, quiet=True), deps=deps))

    assert captured_local_deps is not None
    assert captured_local_deps.confirm_slowpics_upload is _confirm


@pytest.mark.parametrize(
    "run_request",
    [
        RunRequest(root=Path("."), json_output=True),
        RunRequest(root=Path("."), quiet=True),
        RunRequest(root=Path("."), from_cache_only=True),
        RunRequest(root=Path("."), skip_analysis=True),
    ],
)
def test_execute_run_removes_full_window_confirmation_in_unattended_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_request: RunRequest,
) -> None:
    from frame_compare.orchestration import coordinator

    captured_local_deps: RunDependencies | None = None

    def _confirm(
        _request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        raise AssertionError("unattended mode must not confirm")

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        nonlocal captured_local_deps
        captured_local_deps = local_deps
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    deps = RunDependencies(confirm_full_window_retry=_confirm)

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(replace(run_request, root=tmp_path), deps=deps))

    assert captured_local_deps is not None
    assert captured_local_deps.confirm_full_window_retry is None
    assert deps.confirm_full_window_retry is _confirm


def test_reserved_warning_sink_survives_prep_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.orchestration import coordinator

    captured_artifacts: RunArtifacts | None = None
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        generated_root=tmp_path / "generated",
        run_dir=tmp_path / "generated" / "run",
        screenshots_dir=tmp_path / "generated" / "run" / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        assert local_deps.capture_reserved_run is not None
        warnings: list[str] = []
        local_deps.capture_reserved_run(
            ReservedRunCapture(
                workspace=workspace,
                clip_count=2,
                preflight_duration=0.1,
                preflight_warnings=(),
                run_warnings=warnings,
            )
        )
        warnings.append("accepted full-window override")
        raise StopAfterDependencyInit

    def fake_record_failed_run_best_effort(
        *, artifacts: RunArtifacts | None, **_kwargs: object
    ) -> None:
        nonlocal captured_artifacts
        captured_artifacts = artifacts

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(
        coordinator,
        "record_failed_run_best_effort",
        fake_record_failed_run_best_effort,
    )

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(RunRequest(root=tmp_path), deps=RunDependencies()))

    assert captured_artifacts is not None
    assert captured_artifacts.warnings == ["accepted full-window override"]
