from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import pytest

from src.datatypes import AppConfig, RuntimeConfig, TMDBConfig
from src.frame_compare.cli_runtime import CLIAppError, CliOutputManagerProtocol, ClipPlan
from src.frame_compare.services.metadata import (
    FilesystemProbeProtocol,
    MetadataResolver,
    MetadataResolveRequest,
    PlanBuilder,
    TMDBClientProtocol,
)
from src.frame_compare.tmdb_workflow import TMDBLookupResult
from src.frame_compare.vs import ClipInitError
from src.tmdb import TMDBCandidate, TMDBResolution
from tests.services.conftest import StubReporter, build_base_json_tail, build_service_config


class _StubProbe(FilesystemProbeProtocol):
    calls: list[tuple[Sequence[ClipPlan], RuntimeConfig, Path | None]] | None = None

    def probe(
        self,
        plans: Sequence[ClipPlan],
        runtime_cfg: RuntimeConfig,
        cache_dir: Path | None,
        *,
        reporter: CliOutputManagerProtocol | None = None,
    ) -> None:
        if self.calls is None:
            self.calls = []
        self.calls.append((plans, runtime_cfg, cache_dir))


class _FailingProbe(FilesystemProbeProtocol):
    def probe(
        self,
        plans: Sequence[ClipPlan],
        runtime_cfg: RuntimeConfig,
        cache_dir: Path | None,
        *,
        reporter: CliOutputManagerProtocol | None = None,
    ) -> None:
        raise ClipInitError("sentinel failure")


class _StubTMDBClient(TMDBClientProtocol):
    def __init__(self, result: TMDBLookupResult) -> None:
        self.result = result
        self.calls = 0

    def resolve(
        self,
        *,
        files: Sequence[Path],
        metadata: Sequence[dict[str, str]],
        tmdb_cfg: TMDBConfig,
        year_hint_raw: str | None,
    ) -> TMDBLookupResult:
        self.calls += 1
        return self.result


def _make_plan_builder() -> PlanBuilder:
    def _builder(
        files: Sequence[Path],
        metadata: Sequence[dict[str, str]],
        cfg: AppConfig,
    ) -> Sequence[ClipPlan]:
        plans: list[ClipPlan] = []
        for idx, file_path in enumerate(files):
            plan_metadata = dict(metadata[idx]) if idx < len(metadata) else {}
            plan_metadata.setdefault("label", file_path.stem)
            plans.append(ClipPlan(path=file_path, metadata=plan_metadata))
        return plans

    return _builder


def _identity_picker(
    files: Sequence[Path],
    metadata: Sequence[dict[str, str]],
    target: str | None,
    *,
    cache_dir: Path | None = None,
) -> Path:
    return files[0]


def test_metadata_resolver_populates_tmdb_context(tmp_path: Path) -> None:
    file_a = tmp_path / "Example Film 2024.mkv"
    file_b = tmp_path / "Example Film 2024 pt2.mkv"
    file_a.write_text("a")
    file_b.write_text("b")
    cfg = build_service_config(tmp_path)
    reporter = StubReporter()
    json_tail = build_base_json_tail(cfg)
    layout_data: dict[str, Any] = {"slowpics": {}, "tmdb": {}}
    tmdb_candidate = TMDBCandidate(
        category="movie",
        tmdb_id="123",
        title="Example Film",
        original_title="Example Film",
        year=2024,
        score=0.99,
        original_language="en",
        reason="match",
        used_filename_search=True,
        payload={},
    )
    tmdb_resolution = TMDBResolution(candidate=tmdb_candidate, margin=0.5, source_query="Example")
    tmdb_result = TMDBLookupResult(
        resolution=tmdb_resolution,
        manual_override=None,
        error_message=None,
        ambiguous=False,
    )
    resolver = MetadataResolver(
        tmdb_client=_StubTMDBClient(result=tmdb_result),
        plan_builder=_make_plan_builder(),
        analyze_picker=_identity_picker,
        clip_probe=_StubProbe(),
    )
    request = MetadataResolveRequest(
        cfg=cfg,
        root=tmp_path,
        files=[file_a, file_b],
        reporter=reporter,
        json_tail=json_tail,
        layout_data=layout_data,
        collected_warnings=[],
    )

    result = resolver.resolve(request)

    assert len(result.plans) == 2
    assert result.metadata_title == "Example Film 2024"
    assert result.analyze_path == file_a
    assert result.slowpics_final_title == "Example Film (2024)"
    assert result.slowpics_tmdb_disclosure_line is not None
    assert reporter.flags.get("tmdb_resolved") is True
    assert layout_data["tmdb"]["id"] == "123"


def test_metadata_resolver_records_unattended_ambiguity(tmp_path: Path) -> None:
    cfg = build_service_config(tmp_path)
    cfg.tmdb.unattended = True
    reporter = StubReporter()
    json_tail = build_base_json_tail(cfg)
    layout_data: dict[str, Any] = {"slowpics": {}, "tmdb": {}}
    tmdb_result = TMDBLookupResult(
        resolution=None,
        manual_override=None,
        error_message=None,
        ambiguous=True,
    )
    resolver = MetadataResolver(
        tmdb_client=_StubTMDBClient(result=tmdb_result),
        plan_builder=_make_plan_builder(),
        analyze_picker=_identity_picker,
        clip_probe=_StubProbe(),
    )
    files = [tmp_path / "Film A.mkv", tmp_path / "Film B.mkv"]
    for file in files:
        file.write_text("x")
    request = MetadataResolveRequest(
        cfg=cfg,
        root=tmp_path,
        files=files,
        reporter=reporter,
        json_tail=json_tail,
        layout_data=layout_data,
        collected_warnings=[],
    )

    result = resolver.resolve(request)

    assert result.tmdb_notes
    assert "ambiguous" in result.tmdb_notes[0]
    assert reporter.flags.get("tmdb_resolved") is None


def test_metadata_resolver_records_tmdb_errors(tmp_path: Path) -> None:
    cfg = build_service_config(tmp_path)
    reporter = StubReporter()
    json_tail = build_base_json_tail(cfg)
    layout_data: dict[str, Any] = {"slowpics": {}, "tmdb": {}}
    tmdb_result = TMDBLookupResult(
        resolution=None,
        manual_override=None,
        error_message="rate limited",
        ambiguous=False,
    )
    resolver = MetadataResolver(
        tmdb_client=_StubTMDBClient(result=tmdb_result),
        plan_builder=_make_plan_builder(),
        analyze_picker=_identity_picker,
        clip_probe=_StubProbe(),
    )
    files = [tmp_path / "Clip A.mkv", tmp_path / "Clip B.mkv"]
    for file in files:
        file.write_text("y")
    warnings: list[str] = []
    request = MetadataResolveRequest(
        cfg=cfg,
        root=tmp_path,
        files=files,
        reporter=reporter,
        json_tail=json_tail,
        layout_data=layout_data,
        collected_warnings=warnings,
    )

    result = resolver.resolve(request)

    assert result.tmdb_notes[0].startswith("TMDB lookup failed")
    assert warnings == result.tmdb_notes


def test_metadata_resolver_raises_cli_error_on_probe_failure(tmp_path: Path) -> None:
    cfg = build_service_config(tmp_path)
    reporter = StubReporter()
    json_tail = build_base_json_tail(cfg)
    layout_data: dict[str, Any] = {"slowpics": {}, "tmdb": {}}
    files = [tmp_path / "Clip A.mkv", tmp_path / "Clip B.mkv"]
    for file in files:
        file.write_text("z")
    tmdb_result = TMDBLookupResult(
        resolution=None,
        manual_override=None,
        error_message=None,
        ambiguous=False,
    )
    resolver = MetadataResolver(
        tmdb_client=_StubTMDBClient(result=tmdb_result),
        plan_builder=_make_plan_builder(),
        analyze_picker=_identity_picker,
        clip_probe=_FailingProbe(),
    )
    request = MetadataResolveRequest(
        cfg=cfg,
        root=tmp_path,
        files=files,
        reporter=reporter,
        json_tail=json_tail,
        layout_data=layout_data,
        collected_warnings=[],
    )

    with pytest.raises(CLIAppError, match="Failed to open clip"):
        resolver.resolve(request)
