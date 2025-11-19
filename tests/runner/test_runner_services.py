"""Runner dependency wiring and service orchestration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence, cast

import pytest

from src.frame_compare import runner as runner_module
from src.frame_compare.cli_runtime import ClipPlan
from src.frame_compare.services.alignment import AlignmentRequest, AlignmentResult
from src.frame_compare.services.metadata import MetadataResolveResult

pytestmark = pytest.mark.usefixtures("runner_vs_core_stub", "dummy_progress")  # type: ignore[attr-defined]


class SentinelError(RuntimeError):
    """Raised to stop the runner after service orchestration assertions."""


def _write_media(cli_runner_env: Any) -> list[Path]:
    files: list[Path] = []
    for name in ("Alpha.mkv", "Beta.mkv"):
        path = cli_runner_env.media_root / name
        path.write_bytes(b"0")
        files.append(path)
    return files


def _make_metadata_result(files: Sequence[Path]) -> MetadataResolveResult:
    plans = [
        ClipPlan(path=files[0], metadata={"label": "Alpha"}),
        ClipPlan(path=files[1], metadata={"label": "Beta"}),
    ]
    plans[0].use_as_reference = True
    return MetadataResolveResult(
        plans=plans,
        metadata=[{"label": "Alpha"}, {"label": "Beta"}],
        metadata_title="Demo Title",
        analyze_path=files[0],
        slowpics_title_inputs={
            "resolved_base": "Demo Base",
            "collection_name": "Collection",
            "collection_suffix": "Vol.1",
        },
        slowpics_final_title="Demo Title",
        slowpics_resolved_base="Demo Base",
        slowpics_tmdb_disclosure_line=None,
        slowpics_verbose_tmdb_tag=None,
        tmdb_notes=["tmdb demo note"],
    )


def _build_dependencies(
    metadata_resolver: object,
    alignment_workflow: object,
) -> runner_module.RunDependencies:
    return runner_module.RunDependencies(
        metadata_resolver=cast(runner_module.MetadataResolver, metadata_resolver),
        alignment_workflow=cast(runner_module.AlignmentWorkflow, alignment_workflow),
    )


class _RecordingMetadataResolver:
    def __init__(self, result: MetadataResolveResult, log: list[str]) -> None:
        self._result = result
        self._log = log
        self.last_request: runner_module.MetadataResolveRequest | None = None

    def resolve(self, request: runner_module.MetadataResolveRequest) -> MetadataResolveResult:
        self._log.append("metadata")
        self.last_request = request
        return self._result


class _RecordingAlignmentWorkflow:
    def __init__(self, result: AlignmentResult, log: list[str]) -> None:
        self._result = result
        self._log = log
        self.last_request: AlignmentRequest | None = None

    def run(self, request: AlignmentRequest) -> AlignmentResult:
        self._log.append("alignment")
        self.last_request = request
        return self._result


def test_runner_calls_services_in_order(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: Any,
    recording_output_manager: runner_module.CliOutputManager,
) -> None:
    """Runner should sequence MetadataResolver before AlignmentWorkflow."""

    files = _write_media(cli_runner_env)
    monkeypatch.setattr(runner_module.media_utils, "discover_media", lambda _root: list(files))
    metadata_result = _make_metadata_result(files)
    alignment_result = AlignmentResult(plans=list(metadata_result.plans), summary=None, display=None)
    call_order: list[str] = []
    metadata_resolver = _RecordingMetadataResolver(metadata_result, call_order)
    alignment_workflow = _RecordingAlignmentWorkflow(alignment_result, call_order)

    def _stop(*_args: object, **_kwargs: object) -> None:
        raise SentinelError("halt after alignment")

    monkeypatch.setattr(runner_module.selection_utils, "init_clips", _stop)
    dependencies = _build_dependencies(metadata_resolver, alignment_workflow)
    request = runner_module.RunRequest(
        config_path=str(cli_runner_env.config_path),
        reporter=recording_output_manager,
    )

    with pytest.raises(SentinelError):
        runner_module.run(request, dependencies=dependencies)

    assert call_order == ["metadata", "alignment"]
    assert metadata_resolver.last_request is not None
    assert list(metadata_resolver.last_request.files) == list(files)
    assert alignment_workflow.last_request is not None
    assert alignment_workflow.last_request.analyze_path == files[0]
    assert list(alignment_workflow.last_request.plans) == list(metadata_result.plans)


def test_metadata_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: Any,
    recording_output_manager: runner_module.CliOutputManager,
) -> None:
    """CLIAppError raised by the metadata service should bubble out unchanged."""

    files = _write_media(cli_runner_env)
    monkeypatch.setattr(runner_module.media_utils, "discover_media", lambda _root: list(files))

    class _ExplodingMetadata:
        def resolve(self, _request: runner_module.MetadataResolveRequest) -> MetadataResolveResult:
            raise runner_module.CLIAppError("metadata boom")

    metadata_resolver = _ExplodingMetadata()
    alignment_result = AlignmentResult(plans=[], summary=None, display=None)
    alignment_workflow = _RecordingAlignmentWorkflow(alignment_result, [])
    dependencies = _build_dependencies(metadata_resolver, alignment_workflow)
    request = runner_module.RunRequest(
        config_path=str(cli_runner_env.config_path),
        reporter=recording_output_manager,
    )

    with pytest.raises(runner_module.CLIAppError, match="metadata boom"):
        runner_module.run(request, dependencies=dependencies)


def test_alignment_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: Any,
    recording_output_manager: runner_module.CliOutputManager,
) -> None:
    """Failures from AlignmentWorkflow should also surface as CLIAppError."""

    files = _write_media(cli_runner_env)
    monkeypatch.setattr(runner_module.media_utils, "discover_media", lambda _root: list(files))
    metadata_result = _make_metadata_result(files)
    metadata_resolver = _RecordingMetadataResolver(metadata_result, [])

    class _ExplodingAlignment:
        def run(self, _request: AlignmentRequest) -> AlignmentResult:
            raise runner_module.CLIAppError("alignment boom")

    alignment_workflow = _ExplodingAlignment()
    dependencies = _build_dependencies(metadata_resolver, alignment_workflow)
    request = runner_module.RunRequest(
        config_path=str(cli_runner_env.config_path),
        reporter=recording_output_manager,
    )

    with pytest.raises(runner_module.CLIAppError, match="alignment boom"):
        runner_module.run(request, dependencies=dependencies)


def test_reporter_flags_initialized_with_service_context(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: Any,
    recording_output_manager: runner_module.CliOutputManager,
) -> None:
    """Runner should set upload/tmdb flags before service sequencing."""

    cli_runner_env.cfg.slowpics.auto_upload = True
    cli_runner_env.reinstall(cli_runner_env.cfg)
    files = _write_media(cli_runner_env)
    monkeypatch.setattr(runner_module.media_utils, "discover_media", lambda _root: list(files))
    metadata_result = _make_metadata_result(files)
    alignment_result = AlignmentResult(plans=list(metadata_result.plans), summary=None, display=None)
    call_order: list[str] = []
    metadata_resolver = _RecordingMetadataResolver(metadata_result, call_order)
    alignment_workflow = _RecordingAlignmentWorkflow(alignment_result, call_order)

    def _stop(*_args: object, **_kwargs: object) -> None:
        raise SentinelError("stop after metadata/alignment")

    monkeypatch.setattr(runner_module.selection_utils, "init_clips", _stop)
    dependencies = _build_dependencies(metadata_resolver, alignment_workflow)
    request = runner_module.RunRequest(
        config_path=str(cli_runner_env.config_path),
        reporter=recording_output_manager,
    )

    with pytest.raises(SentinelError):
        runner_module.run(request, dependencies=dependencies)

    assert recording_output_manager.flags.get("upload_enabled") is True
    assert recording_output_manager.flags.get("tmdb_resolved") is False
