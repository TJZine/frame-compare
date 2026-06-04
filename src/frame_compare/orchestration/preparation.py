"""Workspace and input preparation logic for runs."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import structlog

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.overrides import apply_cli_overrides
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.analysis_policy import needs_analysis
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.errors import MixedSourceFpsError
from frame_compare.orchestration.phase_tasks import resolve_run_metadata
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
    build_selection_domain_clips,
    compute_selection_window_for_clips,
)
from frame_compare.orchestration.source_selection import resolve_source_selection
from frame_compare.orchestration.types import (
    MetadataPrefetch,
    PrepState,
    RunArtifacts,
    RunDependencies,
    RunRequest,
)
from frame_compare.services.errors import (
    MetadataError,
    TmdbError,
    TmdbRateLimitedError,
)
from frame_compare.services.run_folder import reserve_run_folder
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError
from frame_compare.utils.types import WorkspacePaths

log = structlog.get_logger()


def _build_preflight_overrides(request: RunRequest) -> dict[str, object] | None:
    overrides: dict[str, object] = {}
    if request.input_dir is not None:
        overrides["paths"] = {"input_dir": str(request.input_dir)}
    return overrides or None


def _remove_cached_metrics(
    *,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
    selection_domain: str | None,
) -> None:
    fingerprint = cache_io.compute_cache_key(
        input_videos,
        config.analysis,
        selection_domain=selection_domain,
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
        if deps.http_client is not None and config.tmdb.enabled and not request.skip_metadata:
            try:
                metadata = await resolve_run_metadata(
                    filenames=[input_videos[0].name],
                    config=config,
                    client=deps.http_client,
                )
                was_attempted = True
            except (MetadataError, TmdbError, TmdbRateLimitedError) as exc:
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
        new_workspace = workspace.with_run_dir(run_dir)
        return new_workspace, MetadataPrefetch(metadata=metadata, was_attempted=was_attempted)
    return workspace, MetadataPrefetch(metadata=None, was_attempted=False)


def _validate_cache_state(
    *,
    request: RunRequest,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
    selection_domain: str | None,
) -> None:
    if not needs_analysis(config.analysis):
        return

    if request.no_cache:
        _remove_cached_metrics(
            workspace=workspace,
            config=config,
            input_videos=input_videos,
            selection_domain=selection_domain,
        )

    if request.from_cache_only and not request.skip_analysis:
        fingerprint = cache_io.compute_cache_key(
            input_videos,
            config.analysis,
            selection_domain=selection_domain,
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
    overrides_by_path: dict[Path, SourceOverrideConfig],
) -> list[ClipState]:
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
            entries_by_key[cache_key] = snapshot

        snapshots_by_path[path] = snapshot

    for cache_path in cache_paths:
        save_clip_probe_cache(cache_path, entries_by_key)
    return build_selection_domain_clips(
        ordered_paths=input_videos,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=overrides_by_path,
    )


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
    overrides_by_path: dict[Path, SourceOverrideConfig],
    snapshots_by_path: dict[Path, ClipProbeSnapshot],
) -> list[ClipState]:
    return build_selection_domain_clips(
        ordered_paths=input_videos,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=overrides_by_path,
    )


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
        overrides=_build_preflight_overrides(request),
    )
    preflight_end = deps.clock()
    preflight_duration = (preflight_end - preflight_start).total_seconds()

    load_sources_start = deps.clock()
    workspace = preflight.workspace
    config = apply_cli_overrides(
        preflight.config,
        cli_args=request.cli_config_overrides(),
    )
    discovered_videos = discover_inputs(workspace.input_dir)
    source_selection = resolve_source_selection(
        input_dir=workspace.input_dir,
        discovered_paths=discovered_videos,
        config=config.sources,
    )
    input_videos = source_selection.ordered_paths
    overrides_by_path = dict(source_selection.overrides_by_path)
    artifacts = RunArtifacts()
    prevalidated_clips: list[ClipState] | None = None
    prevalidated_selection_window: SelectionWindow | None = None
    prevalidated_selection_domain: str | None = None

    if request.from_cache_only and not request.skip_analysis and needs_analysis(config.analysis):
        cached_snapshots = _cached_probe_snapshots_for_cache_only(
            workspace=workspace,
            input_videos=input_videos,
        )
        prevalidated_clips = _probe_input_videos_from_snapshots(
            input_videos=input_videos,
            overrides_by_path=overrides_by_path,
            snapshots_by_path=cached_snapshots,
        )
        _validate_source_fps_compatibility(prevalidated_clips)
        prevalidated_selection_window = compute_selection_window_for_clips(
            clips=prevalidated_clips,
            config=config,
        )
        prevalidated_selection_domain = build_analysis_selection_domain_token(
            clips=prevalidated_clips,
            config=config,
            selection_window=prevalidated_selection_window,
        )
        _validate_cache_state(
            request=request,
            workspace=workspace,
            config=config,
            input_videos=input_videos,
            selection_domain=prevalidated_selection_domain,
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
        selection_window = prevalidated_selection_window
        selection_domain = prevalidated_selection_domain
    else:
        clips = _probe_input_videos(
            workspace=workspace,
            input_videos=input_videos,
            deps=deps,
            overrides_by_path=overrides_by_path,
        )
        _validate_source_fps_compatibility(clips)
        selection_window = compute_selection_window_for_clips(clips=clips, config=config)
        selection_domain = build_analysis_selection_domain_token(
            clips=clips,
            config=config,
            selection_window=selection_window,
        )
        if request.no_cache:
            _validate_cache_state(
                request=request,
                workspace=workspace,
                config=config,
                input_videos=input_videos,
                selection_domain=selection_domain,
            )

    return PrepState(
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        analysis_selection_domain=selection_domain,
        selection_window=selection_window,
        clips=clips,
        artifacts=artifacts,
        metadata_prefetch=metadata_prefetch,
        preflight_warnings=preflight.warnings,
        preflight_duration=preflight_duration,
        load_sources_start=load_sources_start,
    )
