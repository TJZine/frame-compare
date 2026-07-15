"""Side-effect-free planning for ``frame-compare run --dry-run``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.analysis_policy import needs_analysis
from frame_compare.orchestration.errors import (
    DirectoryNotFoundError,
    FastestAnalysisSourceCacheOnlyError,
)
from frame_compare.orchestration.preflight import discover_inputs, resolve_paths
from frame_compare.orchestration.source_selection import (
    resolve_source_selection,
    resolve_source_selector,
)

type RuntimeFactStatus = Literal["known", "unknown"]


CHECKS_NOT_PERFORMED: tuple[str, ...] = (
    "doctor",
    "ffprobe_or_ffmpeg",
    "media_probe",
    "analysis",
    "alignment",
    "cache_reads_or_writes",
    "run_folder_reservation_or_metadata_writes",
    "render_or_report_generation",
    "network_publishing_or_metadata",
    "browser_clipboard_or_vspreview",
)


@dataclass(frozen=True, slots=True)
class DryRunInput:
    """Input facts available from path resolution and filename discovery."""

    resolved_directory: Path
    source_filenames: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DryRunReference:
    """Configured reference intent and its filename-only resolution."""

    configured_selector: str
    resolved_filename: str


@dataclass(frozen=True, slots=True)
class DryRunSelection:
    """Effective configured frame-selection intent."""

    strategy: tuple[str, ...]
    requested_user_frames: tuple[int, ...]
    random_frame_count: int
    dark_frame_count: int
    bright_frame_count: int
    motion_frame_count: int
    random_seed: int
    analysis_performance_mode: str
    analysis_metrics_required: bool


@dataclass(frozen=True, slots=True)
class DryRunOutputs:
    """Declared local output intentions."""

    screenshots: bool
    run_folders: bool
    report: bool
    report_auto_open_configured: bool


@dataclass(frozen=True, slots=True)
class DryRunPublishing:
    """Declared publishing intentions with secret material excluded."""

    slowpics_upload: bool
    slowpics_visibility: str
    copy_url_to_clipboard_configured: bool
    open_in_browser_configured: bool
    create_url_shortcut_configured: bool
    webhook_configured: bool


@dataclass(frozen=True, slots=True)
class DryRunRuntimeFact:
    """Availability of a fact that normally belongs to runtime execution."""

    status: RuntimeFactStatus
    value: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class DryRunRuntimeFacts:
    """Facts that dry-run must not invent or probe."""

    run_folder_name: DryRunRuntimeFact
    final_selected_frames: DryRunRuntimeFact
    clip_metadata: DryRunRuntimeFact
    output_dimensions: DryRunRuntimeFact


@dataclass(frozen=True, slots=True)
class DryRunPlan:
    """Complete immutable dry-run DTO shared by human and JSON renderers."""

    input: DryRunInput
    reference: DryRunReference
    selection: DryRunSelection
    outputs: DryRunOutputs
    publishing: DryRunPublishing
    runtime_facts: DryRunRuntimeFacts
    checks_not_performed: tuple[str, ...] = CHECKS_NOT_PERFORMED


def build_dry_run_plan(
    *,
    root: Path,
    config: ConfigSchema,
    from_cache_only: bool,
) -> DryRunPlan:
    """Resolve only configuration and filename-level facts for a future run."""
    workspace = resolve_paths(config, root)
    input_dir = workspace.input_dir
    if not input_dir.is_dir():
        raise DirectoryNotFoundError(input_dir)

    discovered_paths = discover_inputs(input_dir)
    source_selection = resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=discovered_paths,
        config=config.sources,
    )
    metrics_required = needs_analysis(config.analysis)
    if metrics_required:
        analysis_selector = config.sources.analysis_source
        if analysis_selector == "fastest" and from_cache_only:
            raise FastestAnalysisSourceCacheOnlyError()
        if analysis_selector not in {"reference", "fastest"}:
            resolve_source_selector(
                selector=analysis_selector,
                input_dir=input_dir,
                paths=source_selection.ordered_paths,
                role="sources.analysis_source",
            )

    source_filenames = tuple(
        path.name
        for path in sorted(
            discovered_paths,
            key=lambda path: (path.name.casefold(), path.name),
        )
    )
    analysis = config.analysis
    strategy = tuple(
        name
        for name, active in (
            ("user", bool(analysis.user_frames)),
            ("random", analysis.random_frame_count > 0),
            ("dark", analysis.dark_frame_count > 0),
            ("bright", analysis.bright_frame_count > 0),
            ("motion", analysis.motion_frame_count > 0),
        )
        if active
    )
    run_folder_fact = (
        DryRunRuntimeFact(
            status="unknown",
            value=None,
            reason="resolved during run-folder reservation",
        )
        if config.paths.use_run_folders
        else DryRunRuntimeFact(status="known", value=None, reason=None)
    )

    return DryRunPlan(
        input=DryRunInput(
            resolved_directory=input_dir,
            source_filenames=source_filenames,
        ),
        reference=DryRunReference(
            configured_selector=config.sources.reference or "auto",
            resolved_filename=source_selection.ordered_paths[0].name,
        ),
        selection=DryRunSelection(
            strategy=strategy,
            requested_user_frames=tuple(analysis.user_frames),
            random_frame_count=analysis.random_frame_count,
            dark_frame_count=analysis.dark_frame_count,
            bright_frame_count=analysis.bright_frame_count,
            motion_frame_count=analysis.motion_frame_count,
            random_seed=analysis.random_seed,
            analysis_performance_mode=analysis.performance_mode.value,
            analysis_metrics_required=metrics_required,
        ),
        outputs=DryRunOutputs(
            screenshots=True,
            run_folders=config.paths.use_run_folders,
            report=config.report.enable,
            report_auto_open_configured=config.report.auto_open,
        ),
        publishing=DryRunPublishing(
            slowpics_upload=config.slowpics.auto_upload,
            slowpics_visibility=config.slowpics.visibility.value,
            copy_url_to_clipboard_configured=config.slowpics.copy_url_to_clipboard,
            open_in_browser_configured=config.slowpics.open_in_browser,
            create_url_shortcut_configured=config.slowpics.create_url_shortcut,
            webhook_configured=config.slowpics.webhook_url is not None,
        ),
        runtime_facts=DryRunRuntimeFacts(
            run_folder_name=run_folder_fact,
            final_selected_frames=DryRunRuntimeFact(
                status="unknown",
                value=None,
                reason="requires media probing and runtime frame selection",
            ),
            clip_metadata=DryRunRuntimeFact(
                status="unknown",
                value=None,
                reason="requires media probing",
            ),
            output_dimensions=DryRunRuntimeFact(
                status="unknown",
                value=None,
                reason="requires media probing and render planning",
            ),
        ),
    )


def dry_run_plan_json(plan: DryRunPlan) -> dict[str, object]:
    """Project a dry-run plan into its stable allowlisted JSON shape."""
    return {
        "dry_run": True,
        "input": {
            "resolved_directory": str(plan.input.resolved_directory),
            "source_filenames": list(plan.input.source_filenames),
        },
        "reference": {
            "configured_selector": plan.reference.configured_selector,
            "resolved_filename": plan.reference.resolved_filename,
        },
        "selection": {
            "strategy": list(plan.selection.strategy),
            "requested_user_frames": list(plan.selection.requested_user_frames),
            "random_frame_count": plan.selection.random_frame_count,
            "dark_frame_count": plan.selection.dark_frame_count,
            "bright_frame_count": plan.selection.bright_frame_count,
            "motion_frame_count": plan.selection.motion_frame_count,
            "random_seed": plan.selection.random_seed,
            "analysis_performance_mode": plan.selection.analysis_performance_mode,
            "analysis_metrics_required": plan.selection.analysis_metrics_required,
        },
        "outputs": {
            "screenshots": plan.outputs.screenshots,
            "run_folders": plan.outputs.run_folders,
            "report": plan.outputs.report,
            "report_auto_open_configured": plan.outputs.report_auto_open_configured,
        },
        "publishing": {
            "slowpics_upload": plan.publishing.slowpics_upload,
            "slowpics_visibility": plan.publishing.slowpics_visibility,
            "copy_url_to_clipboard_configured": (plan.publishing.copy_url_to_clipboard_configured),
            "open_in_browser_configured": plan.publishing.open_in_browser_configured,
            "create_url_shortcut_configured": (plan.publishing.create_url_shortcut_configured),
            "webhook_configured": plan.publishing.webhook_configured,
        },
        "runtime_facts": {
            "run_folder_name": _runtime_fact_json(plan.runtime_facts.run_folder_name),
            "final_selected_frames": _runtime_fact_json(plan.runtime_facts.final_selected_frames),
            "clip_metadata": _runtime_fact_json(plan.runtime_facts.clip_metadata),
            "output_dimensions": _runtime_fact_json(plan.runtime_facts.output_dimensions),
        },
        "checks_not_performed": list(plan.checks_not_performed),
    }


def print_dry_run_plan(console: Console, plan: DryRunPlan, *, quiet: bool) -> None:
    """Render the typed plan for a human without performing planned actions."""
    if quiet:
        console.print(
            f"Dry run: {len(plan.input.source_filenames)} source files; no side effects performed."
        )
        return

    table = Table(title="Dry-run plan", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("input", escape(str(plan.input.resolved_directory)))
    table.add_row("sources", escape(", ".join(plan.input.source_filenames)))
    table.add_row(
        "reference",
        escape(f"{plan.reference.configured_selector} -> {plan.reference.resolved_filename}"),
    )
    table.add_row("selection", ", ".join(plan.selection.strategy))
    table.add_row(
        "requested user frames",
        ", ".join(str(frame) for frame in plan.selection.requested_user_frames) or "none",
    )
    table.add_row(
        "selection counts",
        (
            f"user={len(plan.selection.requested_user_frames)}, "
            f"random={plan.selection.random_frame_count}, "
            f"dark={plan.selection.dark_frame_count}, "
            f"bright={plan.selection.bright_frame_count}, "
            f"motion={plan.selection.motion_frame_count}"
        ),
    )
    table.add_row("random seed", str(plan.selection.random_seed))
    table.add_row("analysis mode", plan.selection.analysis_performance_mode)
    table.add_row(
        "analysis metrics required",
        "yes" if plan.selection.analysis_metrics_required else "no",
    )
    table.add_row(
        "outputs",
        (
            f"screenshots=yes, run folders={'yes' if plan.outputs.run_folders else 'no'}, "
            f"report={'yes' if plan.outputs.report else 'no'}, "
            "report auto-open configured="
            f"{'yes' if plan.outputs.report_auto_open_configured else 'no'}"
        ),
    )
    table.add_row(
        "publishing",
        (
            f"slow.pics={'yes' if plan.publishing.slowpics_upload else 'no'}, "
            f"visibility={plan.publishing.slowpics_visibility}, "
            "configured after upload: "
            f"clipboard={'yes' if plan.publishing.copy_url_to_clipboard_configured else 'no'}, "
            f"browser={'yes' if plan.publishing.open_in_browser_configured else 'no'}, "
            f"shortcut={'yes' if plan.publishing.create_url_shortcut_configured else 'no'}, "
            f"webhook={'yes' if plan.publishing.webhook_configured else 'no'}"
        ),
    )
    table.add_row(
        "run folder name",
        _runtime_fact_human(plan.runtime_facts.run_folder_name),
    )
    table.add_row(
        "final selected frames",
        _runtime_fact_human(plan.runtime_facts.final_selected_frames),
    )
    table.add_row("clip metadata", _runtime_fact_human(plan.runtime_facts.clip_metadata))
    table.add_row(
        "output dimensions",
        _runtime_fact_human(plan.runtime_facts.output_dimensions),
    )
    table.add_row("checks not performed", ", ".join(plan.checks_not_performed))
    console.print(table)


def _runtime_fact_json(fact: DryRunRuntimeFact) -> dict[str, object]:
    return {
        "status": fact.status,
        "value": fact.value,
        "reason": fact.reason,
    }


def _runtime_fact_human(fact: DryRunRuntimeFact) -> str:
    if fact.status == "known":
        return "known: none" if fact.value is None else f"known: {fact.value}"
    if fact.reason is None:
        return "unknown"
    return f"unknown ({fact.reason})"
