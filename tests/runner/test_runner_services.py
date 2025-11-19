"""Runner dependency wiring and service orchestration tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence, cast

import pytest

from src.datatypes import AppConfig
from src.frame_compare import runner as runner_module
from src.frame_compare.cli_runtime import ClipPlan, JsonTail
from src.frame_compare.interfaces import PublisherIO, ReportRendererProtocol, SlowpicsClientProtocol
from src.frame_compare.services.alignment import AlignmentRequest, AlignmentResult
from src.frame_compare.services.metadata import MetadataResolveResult
from tests.services.conftest import StubReporter, build_base_json_tail, build_service_config

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


class _RendererStub(ReportRendererProtocol):
    def __init__(self) -> None:
        self.output = Path("report/index.html")

    def generate(  # type: ignore[override]
        self,
        *,
        report_dir: Path,
        report_cfg,  # noqa: ANN001
        frames,
        selection_details,
        image_paths,
        plans,
        metadata_title,
        include_metadata,
        slowpics_url,
    ) -> Path:
        return report_dir / self.output


class _PublisherIOStub(PublisherIO):
    def file_size(self, path: str | Path) -> int:
        return 0

    def path_exists(self, path: Path) -> bool:
        return False

    def resolve_report_dir(self, root: Path, relative: str, *, purpose: str) -> Path:  # noqa: ARG002
        resolved = root / relative
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved


class _SlowpicsClientStub(SlowpicsClientProtocol):
    def upload(
        self,
        image_paths,
        out_dir: Path,
        cfg,  # noqa: ANN001
        *,
        progress_callback=None,
    ) -> str:
        if progress_callback is not None:
            progress_callback(len(list(image_paths)))
        return "https://slow.pics/c/test"


class _StubReportPublisher(runner_module.ReportPublisher):
    def __init__(self) -> None:
        super().__init__(renderer=_RendererStub(), io=_PublisherIOStub())
        self.last_request: runner_module.ReportPublisherRequest | None = None
        self.call_count = 0

    def publish(self, request: runner_module.ReportPublisherRequest) -> object:  # type: ignore[override]
        self.last_request = request
        self.call_count += 1
        return SimpleNamespace(report_path=None)


class _StubSlowpicsPublisher(runner_module.SlowpicsPublisher):
    def __init__(self) -> None:
        super().__init__(client=_SlowpicsClientStub(), io=_PublisherIOStub())
        self.last_request: runner_module.SlowpicsPublisherRequest | None = None
        self.call_count = 0

    def publish(self, request: runner_module.SlowpicsPublisherRequest) -> object:  # type: ignore[override]
        self.last_request = request
        self.call_count += 1
        return SimpleNamespace(url="https://slow.pics/c/test")


def _build_dependencies(
    metadata_resolver: object,
    alignment_workflow: object,
    report_publisher: object | None = None,
    slowpics_publisher: object | None = None,
) -> runner_module.RunDependencies:
    return runner_module.RunDependencies(
        metadata_resolver=cast(runner_module.MetadataResolver, metadata_resolver),
        alignment_workflow=cast(runner_module.AlignmentWorkflow, alignment_workflow),
        report_publisher=cast(runner_module.ReportPublisher, report_publisher or _StubReportPublisher()),
        slowpics_publisher=cast(runner_module.SlowpicsPublisher, slowpics_publisher or _StubSlowpicsPublisher()),
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


def _build_context(tmp_path: Path) -> tuple[runner_module.RunContext, JsonTail, dict[str, Any], AppConfig]:
    cfg = build_service_config(tmp_path)
    cfg.report.enable = True
    cfg.slowpics.auto_upload = False
    json_tail = build_base_json_tail(cfg)
    layout_data = {
        "slowpics": json_tail["slowpics"],
        "report": json_tail["report"],
    }
    files = [tmp_path / "Alpha.mkv", tmp_path / "Beta.mkv"]
    for file in files:
        file.write_bytes(b"0")
    metadata_result = _make_metadata_result(files)
    context = runner_module.RunContext(
        plans=list(metadata_result.plans),
        metadata=list(metadata_result.metadata),
        json_tail=json_tail,
        layout_data=layout_data,
        metadata_title=metadata_result.metadata_title,
        analyze_path=metadata_result.analyze_path,
        slowpics_title_inputs=metadata_result.slowpics_title_inputs,
        slowpics_final_title=metadata_result.slowpics_final_title,
        slowpics_resolved_base=metadata_result.slowpics_resolved_base,
        slowpics_tmdb_disclosure_line=None,
        slowpics_verbose_tmdb_tag=None,
        tmdb_notes=list(metadata_result.tmdb_notes),
    )
    return context, json_tail, layout_data, cfg


def test_publish_results_uses_services_when_enabled(tmp_path: Path) -> None:
    context, json_tail, layout_data, cfg = _build_context(tmp_path)
    reporter = StubReporter()
    report_publisher = _StubReportPublisher()
    slowpics_publisher = _StubSlowpicsPublisher()

    slowpics_url, report_path = runner_module._publish_results(
        service_mode_enabled=True,
        context=context,
        reporter=reporter,
        cfg=cfg,
        layout_data=layout_data,
        json_tail=json_tail,
        image_paths=["img-a.png"],
        out_dir=tmp_path,
        collected_warnings=[],
        report_enabled=True,
        root=tmp_path,
        plans=list(context.plans),
        frames=[1, 2],
        selection_details={},
        report_publisher=report_publisher,
        slowpics_publisher=slowpics_publisher,
    )

    assert report_publisher.call_count == 1
    assert slowpics_publisher.call_count == 1
    assert slowpics_url == "https://slow.pics/c/test"
    assert report_path is None


def test_publish_results_uses_legacy_path_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, json_tail, layout_data, cfg = _build_context(tmp_path)
    reporter = StubReporter()
    report_publisher = _StubReportPublisher()
    slowpics_publisher = _StubSlowpicsPublisher()
    legacy_calls: list[tuple[int, int]] = []

    def _fake_legacy(**kwargs: Any) -> tuple[str, Path]:
        legacy_calls.append((len(kwargs.get("image_paths", [])), len(kwargs.get("frames", []))))
        return "https://slow.pics/c/legacy", tmp_path / "report" / "index.html"

    monkeypatch.setattr(runner_module, "_run_legacy_publishers", _fake_legacy)

    slowpics_url, report_path = runner_module._publish_results(
        service_mode_enabled=False,
        context=context,
        reporter=reporter,
        cfg=cfg,
        layout_data=layout_data,
        json_tail=json_tail,
        image_paths=["img-a.png"],
        out_dir=tmp_path,
        collected_warnings=[],
        report_enabled=True,
        root=tmp_path,
        plans=list(context.plans),
        frames=[1, 2],
        selection_details={},
        report_publisher=report_publisher,
        slowpics_publisher=slowpics_publisher,
    )

    assert legacy_calls == [(1, 2)]
    assert slowpics_url == "https://slow.pics/c/legacy"
    assert report_path == tmp_path / "report" / "index.html"
    assert report_publisher.call_count == 0
    assert slowpics_publisher.call_count == 0


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
