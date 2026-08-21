"""Side-effect-free planning for ``frame-compare run --dry-run``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.markup import escape

from frame_compare.cli.output import format_display_path
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
    workspace_root: Path
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
    run_folder_fact = DryRunRuntimeFact(
        status="unknown",
        value=None,
        reason="resolved during run-folder reservation",
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
            run_folders=True,
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
        workspace_root=root,
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


def print_dry_run_plan(
    console: Console,
    plan: DryRunPlan,
    *,
    quiet: bool,
) -> None:
    """Render the typed plan for a human without performing planned actions."""
    if quiet:
        source_label = "source file" if len(plan.input.source_filenames) == 1 else "source files"
        console.print(
            f"Dry run: {len(plan.input.source_filenames)} {source_label}; "
            "no side effects performed."
        )
        return

    console.print(
        "[bold]No side effects:[/] this dry run validates configuration and input "
        "filenames only; it does not write, render, upload, or open anything."
    )
    input_display = format_display_path(
        plan.input.resolved_directory,
        root=plan.workspace_root,
    )
    if input_display == ".":
        input_display = str(plan.input.resolved_directory)
    _print_section(
        console,
        "Will use",
        (
            (
                "Workspace",
                str(plan.workspace_root),
            ),
            (
                "Input directory",
                input_display,
            ),
            (
                f"Sources ({len(plan.input.source_filenames)})",
                ", ".join(plan.input.source_filenames),
            ),
            (
                "Reference",
                f"{plan.reference.configured_selector} -> {plan.reference.resolved_filename}",
            ),
            (
                "Frame selection",
                ", ".join(_selection_label(name) for name in plan.selection.strategy)
                or "configured defaults",
            ),
            (
                "Specific frames",
                ", ".join(str(frame) for frame in plan.selection.requested_user_frames) or "none",
            ),
            (
                "Frame counts",
                (
                    f"specific={len(plan.selection.requested_user_frames)}, "
                    f"random={plan.selection.random_frame_count}, "
                    f"dark={plan.selection.dark_frame_count}, "
                    f"bright={plan.selection.bright_frame_count}, "
                    f"motion={plan.selection.motion_frame_count}"
                ),
            ),
            (
                "Analysis",
                f"{plan.selection.analysis_performance_mode} mode; "
                f"metrics {'required' if plan.selection.analysis_metrics_required else 'not required'}; "
                f"random seed {plan.selection.random_seed}",
            ),
        ),
    )
    _print_section(
        console,
        "Would create in a real run",
        (
            ("Screenshots", _yes_no(plan.outputs.screenshots)),
            ("Run folder", _yes_no(plan.outputs.run_folders)),
            ("Offline report", _yes_no(plan.outputs.report)),
            (
                "Open report after success",
                _configured_when_enabled(
                    parent_enabled=plan.outputs.report,
                    configured=plan.outputs.report_auto_open_configured,
                ),
            ),
        ),
    )
    _print_section(
        console,
        "Publishing after success",
        (
            (
                "slow.pics upload",
                f"{_enabled_disabled(plan.publishing.slowpics_upload)}; "
                f"visibility {plan.publishing.slowpics_visibility}",
            ),
            (
                "Copy URL to clipboard",
                _configured_when_enabled(
                    parent_enabled=plan.publishing.slowpics_upload,
                    configured=plan.publishing.copy_url_to_clipboard_configured,
                ),
            ),
            (
                "Open the published URL",
                _configured_when_enabled(
                    parent_enabled=plan.publishing.slowpics_upload,
                    configured=plan.publishing.open_in_browser_configured,
                ),
            ),
            (
                "Create a URL shortcut",
                _configured_when_enabled(
                    parent_enabled=plan.publishing.slowpics_upload,
                    configured=plan.publishing.create_url_shortcut_configured,
                ),
            ),
            (
                "Send a webhook notification",
                _configured_when_enabled(
                    parent_enabled=plan.publishing.slowpics_upload,
                    configured=plan.publishing.webhook_configured,
                ),
            ),
        ),
    )
    _print_section(
        console,
        "Unknown until execution",
        (
            ("Run folder name", _runtime_fact_human(plan.runtime_facts.run_folder_name)),
            (
                "Final selected frames",
                _runtime_fact_human(plan.runtime_facts.final_selected_frames),
            ),
            ("Clip metadata", _runtime_fact_human(plan.runtime_facts.clip_metadata)),
            (
                "Output dimensions",
                _runtime_fact_human(plan.runtime_facts.output_dimensions),
            ),
        ),
    )
    console.print()
    console.print("[bold]Not performed by dry-run[/]")
    for check in plan.checks_not_performed:
        console.print(f"  - {_human_check(check)}")


def _print_section(
    console: Console,
    title: str,
    rows: tuple[tuple[str, str], ...],
) -> None:
    console.print()
    console.print(f"[bold]{title}[/]")
    for label, value in rows:
        console.print(f"  {label}: {escape(value)}")


def _selection_label(name: str) -> str:
    return {
        "user": "specific frames",
        "random": "random frames",
        "dark": "dark frames",
        "bright": "bright frames",
        "motion": "motion frames",
    }.get(name, name.replace("_", " "))


def _human_check(name: str) -> str:
    return {
        "doctor": "runtime readiness checks",
        "ffprobe_or_ffmpeg": "FFmpeg and ffprobe checks",
        "media_probe": "media probing",
        "analysis": "frame analysis",
        "alignment": "audio alignment",
        "cache_reads_or_writes": "cache reads and writes",
        "run_folder_reservation_or_metadata_writes": "run-folder reservation and metadata writes",
        "render_or_report_generation": "screenshot rendering and report generation",
        "network_publishing_or_metadata": "network metadata lookup and publishing",
        "browser_clipboard_or_vspreview": "browser, clipboard, and VSPreview actions",
    }.get(name, name.replace("_", " "))


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _enabled_disabled(value: bool) -> str:
    return "enabled" if value else "disabled"


def _configured(value: bool) -> str:
    return "configured" if value else "not configured"


def _configured_when_enabled(*, parent_enabled: bool, configured: bool) -> str:
    if not parent_enabled:
        return "not applicable"
    return _configured(configured)


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
        return "not available yet"
    if fact.reason.startswith("requires "):
        return f"not available before {fact.reason.removeprefix('requires ')}"
    return f"not available yet ({fact.reason})"
