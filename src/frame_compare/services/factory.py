"""Factory helpers for service construction."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import src.frame_compare.alignment_runner as alignment_runner
import src.frame_compare.core as core
import src.frame_compare.planner as planner_utils
import src.frame_compare.selection as selection_utils
import src.frame_compare.tmdb_workflow as tmdb_workflow
from src.datatypes import RuntimeConfig, TMDBConfig
from src.frame_compare.cli_runtime import ClipPlan
from src.frame_compare.tmdb_workflow import TMDBLookupResult

from .alignment import AlignmentWorkflow
from .metadata import (
    CliPromptProtocol,
    FilesystemProbeProtocol,
    MetadataResolver,
    PlanBuilder,
    TMDBClientProtocol,
)

__all__ = [
    "build_alignment_workflow",
    "build_metadata_resolver",
]


class _TMDBWorkflowClient(TMDBClientProtocol):
    """Adapter that delegates TMDB lookups to tmdb_workflow."""

    def resolve(
        self,
        *,
        files: Sequence[Path],
        metadata: Sequence[dict[str, str]],
        tmdb_cfg: TMDBConfig,
        year_hint_raw: str | None,
    ) -> TMDBLookupResult:
        return tmdb_workflow.resolve_workflow(
            files=files,
            metadata=metadata,
            tmdb_cfg=tmdb_cfg,
            year_hint_raw=year_hint_raw,
        )


class _ClipProbeAdapter(FilesystemProbeProtocol):
    """Adapter for selection_utils.probe_clip_metadata."""

    def probe(
        self,
        plans: Sequence[ClipPlan],
        runtime_cfg: RuntimeConfig,
        cache_dir: Path,
        *,
        reporter: CliPromptProtocol | None = None,
    ) -> None:
        selection_utils.probe_clip_metadata(
            plans,
            runtime_cfg,
            cache_dir,
            reporter=reporter,
        )


def build_metadata_resolver() -> MetadataResolver:
    """Construct a MetadataResolver wired to the concrete adapters."""

    plan_builder: PlanBuilder = planner_utils.build_plans
    return MetadataResolver(
        tmdb_client=_TMDBWorkflowClient(),
        plan_builder=plan_builder,
        analyze_picker=core.pick_analyze_file,
        clip_probe=_ClipProbeAdapter(),
    )


def build_alignment_workflow() -> AlignmentWorkflow:
    """Construct an AlignmentWorkflow with default adapters."""

    return AlignmentWorkflow(
        apply_alignment=alignment_runner.apply_audio_alignment,
        format_output=alignment_runner.format_alignment_output,
        confirm_alignment=core.confirm_alignment_with_screenshots,
    )
