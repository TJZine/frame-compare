"""Workspace and input preparation logic for runs."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import structlog

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.types import MetricActiveRect
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.effective import (
    build_preflight_input_dir_override,
    resolve_effective_config,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.analysis_policy import (
    needs_analysis,
    validate_skip_analysis_frame_selection_contract,
)
from frame_compare.orchestration.analysis_source import resolve_analysis_source
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.errors import (
    FastestAnalysisSourceCacheOnlyError,
    MixedSourceFpsError,
)
from frame_compare.orchestration.execution_types import (
    MetadataPrefetch,
    PrepState,
    RunArtifacts,
)
from frame_compare.orchestration.phase_post_render import resolve_run_metadata
from frame_compare.orchestration.preflight import discover_inputs, prepare_preflight
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.orchestration.probing.probe_props import (
    compute_preserved_frame_props,
    compute_tonemap_prop_keys,
)
from frame_compare.orchestration.selection_domain import (
    build_analysis_selection_domain_token,
    build_selection_domain_clips_with_diagnostics,
    compute_selection_window_for_clips,
)
from frame_compare.orchestration.source_selection import resolve_source_selection
from frame_compare.orchestration.types import (
    RunDependencies,
    RunRequest,
)
from frame_compare.services.errors import (
    MetadataError,
    TmdbError,
    TmdbRateLimitedError,
)
from frame_compare.services.run_folder import reserve_run_folder
from frame_compare.services.run_info import (
    RunInfo,
    RunInfoTmdbPrefetchFacts,
    RunInfoTmdbSkipReason,
    write_run_info,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError
from frame_compare.utils.types import WorkspacePaths

log = structlog.get_logger()


def _remove_cached_metrics(
    *,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
    selection_domain: str | None,
    metric_active_rect: MetricActiveRect | None,
) -> None:
    fingerprint = cache_io.compute_cache_key(
        input_videos,
        config.analysis,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect,
    )
    cache_io.delete_metrics_cache_entry(workspace.cache_dir, fingerprint)


async def _resolve_run_directory(
    *,
    request: RunRequest,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
    deps: RunDependencies,
) -> tuple[WorkspacePaths, MetadataPrefetch]:
    metadata = None
    was_attempted = False
    if config.paths.use_run_folders:
        tmdb_facts = _skipped_run_info_tmdb_prefetch_facts(
            enabled=config.tmdb.enabled,
            skip_metadata=request.skip_metadata,
            has_http_client=deps.http_client is not None,
        )
        if deps.http_client is not None and config.tmdb.enabled and not request.skip_metadata:
            try:
                metadata = await resolve_run_metadata(
                    filenames=[input_videos[0].name],
                    config=config,
                    client=deps.http_client,
                )
                was_attempted = True
                tmdb_facts = _attempted_run_info_tmdb_prefetch_facts(metadata)
            except (MetadataError, TmdbError, TmdbRateLimitedError) as exc:
                tmdb_facts = RunInfoTmdbPrefetchFacts(
                    enabled=config.tmdb.enabled,
                    attempted=True,
                    resolved=False,
                    failed=True,
                    error_type=type(exc).__name__,
                )
                log.warning(
                    "metadata_prefetch_degraded",
                    filenames=[input_videos[0].name],
                    error_type=type(exc).__name__,
                    error=str(exc),
                    exc_info=exc,
                )

        filenames = [video.name for video in input_videos]
        run_dir = reserve_run_folder(
            input_dir=workspace.input_dir,
            filenames=filenames,
            tmdb_metadata=metadata,
        )
        try:
            write_run_info(
                run_dir.path / "run_info.toml",
                RunInfo(
                    created_at=deps.clock(),
                    folder_name=run_dir.folder_name,
                    naming_source=run_dir.naming_source,
                    source_filenames=filenames,
                    tmdb=tmdb_facts,
                ),
            )
        except OSError as exc:
            _cleanup_empty_reserved_run_dir(run_dir.path, original_error=exc)
            raise
        new_workspace = workspace.with_run_dir(run_dir.path)
        return new_workspace, MetadataPrefetch(metadata=metadata, was_attempted=was_attempted)
    return workspace, MetadataPrefetch(metadata=None, was_attempted=False)


def _skipped_run_info_tmdb_prefetch_facts(
    *,
    enabled: bool,
    skip_metadata: bool,
    has_http_client: bool,
) -> RunInfoTmdbPrefetchFacts:
    skipped_reason: RunInfoTmdbSkipReason | None = None
    if not enabled:
        skipped_reason = "disabled"
    elif skip_metadata:
        skipped_reason = "skip_metadata"
    elif not has_http_client:
        skipped_reason = "no_http_client"
    return RunInfoTmdbPrefetchFacts(
        enabled=enabled,
        attempted=False,
        resolved=False,
        failed=False,
        skipped_reason=skipped_reason,
    )


def _attempted_run_info_tmdb_prefetch_facts(
    metadata: TmdbMetadata | None,
) -> RunInfoTmdbPrefetchFacts:
    if metadata is None:
        return RunInfoTmdbPrefetchFacts(
            enabled=True,
            attempted=True,
            resolved=False,
            failed=False,
        )
    return RunInfoTmdbPrefetchFacts(
        enabled=True,
        attempted=True,
        resolved=True,
        failed=False,
        tmdb_id=metadata.tmdb_id,
        title=metadata.title,
        year=metadata.year,
        media_type=metadata.media_type,
    )


def _cleanup_empty_reserved_run_dir(run_dir: Path, *, original_error: OSError) -> None:
    try:
        run_dir.rmdir()
    except OSError as cleanup_error:
        log.warning(
            "run_info_write_cleanup_degraded",
            run_dir=str(run_dir),
            error_type=type(cleanup_error).__name__,
            error=str(cleanup_error),
        )
        original_error.add_note(
            f"Could not remove empty reserved run folder {run_dir}: {cleanup_error}"
        )


def _validate_cache_state(
    *,
    request: RunRequest,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
    selection_domain: str | None,
    metric_active_rect: MetricActiveRect | None,
) -> None:
    if not needs_analysis(config.analysis):
        return

    if request.no_cache:
        _remove_cached_metrics(
            workspace=workspace,
            config=config,
            input_videos=input_videos,
            selection_domain=selection_domain,
            metric_active_rect=metric_active_rect,
        )

    if request.from_cache_only and not request.skip_analysis:
        fingerprint = cache_io.compute_cache_key(
            input_videos,
            config.analysis,
            selection_domain=selection_domain,
            metric_active_rect=metric_active_rect,
        )
        cache_result = cache_io.load_cached_metrics(workspace.cache_dir, fingerprint, clips=[])
        if not cache_result.success:
            cache_path = cache_io.find_metrics_cache_file(workspace.cache_dir, fingerprint)
            expected_cache_path = workspace.cache_dir / cache_io.metrics_cache_filename(
                input_videos, fingerprint
            )
            error_cache_path = cache_path or expected_cache_path
            if cache_result.reason == "corrupted":
                raise CacheCorruptionError(error_cache_path)
            if cache_result.reason == "version_mismatch":
                found = cache_io.read_cache_version(error_cache_path) or "unknown"
                raise CacheVersionMismatchError(found, str(cache_io.CACHE_VERSION))
            raise MetricsCalculationError(
                f"Cached metrics missing or mismatched ({cache_result.reason})."
            )


def _cached_probe_snapshots_for_cache_only(
    *,
    workspace: WorkspacePaths,
    input_videos: list[Path],
) -> dict[Path, ClipProbeSnapshot]:
    cache_path = _shared_probe_cache_path(workspace)
    cached_entries = load_clip_probe_cache(cache_path)
    entries_by_key = dict(cached_entries)
    snapshots: dict[Path, ClipProbeSnapshot] = {}
    for path in input_videos:
        stats = path.stat()
        fingerprint = ClipFingerprint(
            path=path,
            size_bytes=stats.st_size,
            mtime_ns=stats.st_mtime_ns,
        )
        snapshot = entries_by_key.get(compute_probe_cache_key(fingerprint))
        if snapshot is None:
            raise MetricsCalculationError(
                "Cached clip probe data is required to validate --from-cache-only "
                "analysis cache for the configured selection domain."
            )
        snapshots[path] = snapshot
    return snapshots


def _shared_probe_cache_path(workspace: WorkspacePaths) -> Path:
    return workspace.shared_analysis_cache_dir.parent.parent / "clip_probe.toml"


def _metric_active_rect_for_clip(clip: ClipState | None) -> MetricActiveRect | None:
    if clip is None or clip.active_rect is None:
        return None
    rect = clip.active_rect
    return MetricActiveRect(
        x=rect.x,
        y=rect.y,
        width=rect.width,
        height=rect.height,
    )


def _probe_cache_paths_for_run(workspace: WorkspacePaths) -> list[Path]:
    paths = [workspace.generated_dir / "clip_probe.toml", _shared_probe_cache_path(workspace)]
    unique_paths: list[Path] = []
    for path in paths:
        if path not in unique_paths:
            unique_paths.append(path)
    return unique_paths


def _load_probe_cache_entries(cache_paths: list[Path]) -> dict[str, ClipProbeSnapshot]:
    entries_by_key: dict[str, ClipProbeSnapshot] = {}
    for cache_path in reversed(cache_paths):
        entries_by_key.update(dict(load_clip_probe_cache(cache_path)))
    return entries_by_key


def _probe_input_videos(
    *,
    workspace: WorkspacePaths,
    input_videos: list[Path],
    deps: RunDependencies,
    config: ConfigSchema,
    overrides_by_path: dict[Path, SourceOverrideConfig],
) -> tuple[list[ClipState], list[str], list[str]]:
    cache_paths = _probe_cache_paths_for_run(workspace)
    entries_by_key = _load_probe_cache_entries(cache_paths)
    snapshots_by_path: dict[Path, ClipProbeSnapshot] = {}

    for path in input_videos:
        stats = path.stat()
        fingerprint = ClipFingerprint(
            path=path,
            size_bytes=stats.st_size,
            mtime_ns=stats.st_mtime_ns,
        )
        cache_key = compute_probe_cache_key(fingerprint)
        snapshot = entries_by_key.get(cache_key)
        if snapshot is None:
            if deps.vs_loader is None:
                raise RuntimeError("VS loader must be initialized before probing clips.")
            source_info = deps.vs_loader.load(path)
            tonemap_prop_keys = compute_tonemap_prop_keys(source_info.frame_props)
            preserved_props = compute_preserved_frame_props(source_info.frame_props)
            snapshot = ClipProbeSnapshot(
                fingerprint=fingerprint,
                width=source_info.width,
                height=source_info.height,
                num_frames=source_info.num_frames,
                fps=source_info.fps,
                is_hdr=source_info.is_hdr,
                hdr_metadata=source_info.hdr_metadata,
                preserved_frame_props=preserved_props,
                tonemap_prop_keys=tonemap_prop_keys,
            )
            del source_info
            entries_by_key[cache_key] = snapshot

        snapshots_by_path[path] = snapshot

    for cache_path in cache_paths:
        save_clip_probe_cache(cache_path, entries_by_key)
    result = build_selection_domain_clips_with_diagnostics(
        ordered_paths=input_videos,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=overrides_by_path,
        match_fps=config.sources.match_fps,
        active_rect_detection=config.screenshots.active_rect_detection,
    )
    return result.clips, result.fps_diagnostics.messages(), result.fps_diagnostics.warnings()


def _validate_source_fps_compatibility(clips: list[ClipState]) -> None:
    if len(clips) < 2:
        return

    reference = clips[0]
    reference_fps = _normalized_fps(reference.effective_fps)
    for comparison in clips[1:]:
        if _normalized_fps(comparison.effective_fps) != reference_fps:
            raise MixedSourceFpsError(
                reference_path=reference.path,
                reference_fps=reference.effective_fps,
                comparison_label=comparison.label,
                comparison_path=comparison.path,
                comparison_fps=comparison.effective_fps,
            )


def _normalized_fps(fps: Fraction) -> Fraction:
    return Fraction(fps.numerator, fps.denominator)


def _probe_input_videos_from_snapshots(
    *,
    input_videos: list[Path],
    config: ConfigSchema,
    overrides_by_path: dict[Path, SourceOverrideConfig],
    snapshots_by_path: dict[Path, ClipProbeSnapshot],
) -> tuple[list[ClipState], list[str], list[str]]:
    result = build_selection_domain_clips_with_diagnostics(
        ordered_paths=input_videos,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=overrides_by_path,
        match_fps=config.sources.match_fps,
        active_rect_detection=config.screenshots.active_rect_detection,
    )
    return result.clips, result.fps_diagnostics.messages(), result.fps_diagnostics.warnings()


async def execute_prep(
    request: RunRequest,
    deps: RunDependencies,
) -> PrepState:
    preflight_start = deps.clock()
    if request.no_cache and request.from_cache_only:
        raise MetricsCalculationError(
            "Flags --no-cache and --from-cache-only are mutually exclusive."
        )

    preflight = prepare_preflight(
        root=request.root,
        config_path=request.config_path,
        overrides=build_preflight_input_dir_override(request.input_dir),
    )
    preflight_end = deps.clock()
    preflight_duration = (preflight_end - preflight_start).total_seconds()

    load_sources_start = deps.clock()
    workspace = preflight.workspace
    config = resolve_effective_config(preflight.config, request.cli_config_overrides())
    validate_skip_analysis_frame_selection_contract(
        skip_analysis=request.skip_analysis,
        config=config.analysis,
    )
    discovered_videos = discover_inputs(workspace.input_dir)
    source_selection = resolve_source_selection(
        input_dir=workspace.input_dir,
        discovered_paths=discovered_videos,
        config=config.sources,
    )
    input_videos = source_selection.ordered_paths
    overrides_by_path = dict(source_selection.overrides_by_path)
    analysis_required = not request.skip_analysis and needs_analysis(config.analysis)
    if (
        request.from_cache_only
        and analysis_required
        and config.sources.analysis_source == "fastest"
    ):
        raise FastestAnalysisSourceCacheOnlyError()

    artifacts = RunArtifacts()
    prevalidated_clips: list[ClipState] | None = None
    prevalidated_analysis_clip: ClipState | None = None
    prevalidated_selection_window: SelectionWindow | None = None
    prevalidated_selection_domain: str | None = None
    load_source_diagnostics: list[str] = []
    source_warnings: list[str] = []

    if request.from_cache_only and analysis_required:
        cached_snapshots = _cached_probe_snapshots_for_cache_only(
            workspace=workspace,
            input_videos=input_videos,
        )
        (
            prevalidated_clips,
            load_source_diagnostics,
            source_warnings,
        ) = _probe_input_videos_from_snapshots(
            input_videos=input_videos,
            config=config,
            overrides_by_path=overrides_by_path,
            snapshots_by_path=cached_snapshots,
        )
        _validate_source_fps_compatibility(prevalidated_clips)
        prevalidated_selection_window = compute_selection_window_for_clips(
            clips=prevalidated_clips,
            config=config,
        )
        prevalidated_analysis_selection = resolve_analysis_source(
            selector=config.sources.analysis_source,
            input_dir=workspace.input_dir,
            clips=prevalidated_clips,
            vs_loader=deps.vs_loader,
        )
        prevalidated_analysis_clip = prevalidated_analysis_selection.clip
        if prevalidated_analysis_selection.warning is not None:
            load_source_diagnostics.append(prevalidated_analysis_selection.warning)
        prevalidated_selection_domain = build_analysis_selection_domain_token(
            clips=prevalidated_clips,
            analysis_clip=prevalidated_analysis_clip,
            config=config,
            selection_window=prevalidated_selection_window,
        )
        _validate_cache_state(
            request=request,
            workspace=workspace,
            config=config,
            input_videos=input_videos,
            selection_domain=prevalidated_selection_domain,
            metric_active_rect=_metric_active_rect_for_clip(prevalidated_analysis_clip),
        )

    workspace, metadata_prefetch = await _resolve_run_directory(
        request=request,
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        deps=deps,
    )

    if prevalidated_clips is not None:
        if prevalidated_selection_window is None or prevalidated_selection_domain is None:
            raise RuntimeError("Prevalidated selection domain was not resolved.")
        clips = prevalidated_clips
        analysis_clip = prevalidated_analysis_clip
        selection_window = prevalidated_selection_window
        selection_domain = prevalidated_selection_domain
    else:
        clips, load_source_diagnostics, source_warnings = _probe_input_videos(
            workspace=workspace,
            input_videos=input_videos,
            deps=deps,
            config=config,
            overrides_by_path=overrides_by_path,
        )
        _validate_source_fps_compatibility(clips)
        selection_window = compute_selection_window_for_clips(clips=clips, config=config)
        analysis_clip = None
        if analysis_required:
            analysis_selection = resolve_analysis_source(
                selector=config.sources.analysis_source,
                input_dir=workspace.input_dir,
                clips=clips,
                vs_loader=deps.vs_loader,
            )
            analysis_clip = analysis_selection.clip
            if analysis_selection.warning is not None:
                load_source_diagnostics.append(analysis_selection.warning)
            selection_domain = build_analysis_selection_domain_token(
                clips=clips,
                analysis_clip=analysis_clip,
                config=config,
                selection_window=selection_window,
            )
        else:
            selection_domain = ""
        if request.no_cache:
            _validate_cache_state(
                request=request,
                workspace=workspace,
                config=config,
                input_videos=input_videos,
                selection_domain=selection_domain,
                metric_active_rect=_metric_active_rect_for_clip(analysis_clip),
            )

    return PrepState(
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        analysis_selection_domain=selection_domain,
        analysis_clip=analysis_clip,
        selection_window=selection_window,
        clips=clips,
        artifacts=artifacts,
        metadata_prefetch=metadata_prefetch,
        preflight_warnings=[*preflight.warnings, *source_warnings],
        preflight_duration=preflight_duration,
        load_sources_start=load_sources_start,
        load_source_diagnostics=load_source_diagnostics,
    )
