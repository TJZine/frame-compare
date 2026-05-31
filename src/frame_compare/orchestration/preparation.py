"""Workspace and input preparation logic for runs."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import structlog

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.config.overrides import apply_cli_overrides
from frame_compare.config.schema import ConfigSchema
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
    *, workspace: WorkspacePaths, config: ConfigSchema, input_videos: list[Path]
) -> None:
    fingerprint = cache_io.compute_cache_key(input_videos, config.analysis)
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
) -> None:
    if request.no_cache:
        _remove_cached_metrics(workspace=workspace, config=config, input_videos=input_videos)

    if request.from_cache_only and not request.skip_analysis:
        fingerprint = cache_io.compute_cache_key(input_videos, config.analysis)
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


def _probe_input_videos(
    *,
    workspace: WorkspacePaths,
    input_videos: list[Path],
    deps: RunDependencies,
) -> list[ClipState]:
    cache_path = workspace.generated_dir / "clip_probe.toml"
    cached_entries = load_clip_probe_cache(cache_path)
    entries_by_key = dict(cached_entries)
    clips: list[ClipState] = []

    for index, path in enumerate(input_videos):
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

        label = "Reference" if index == 0 else f"Encode {index}"
        clips.append(
            ClipState(
                path=path,
                label=label,
                probe=snapshot,
                source_fps=snapshot.fps,
                effective_fps=snapshot.fps,
            )
        )

    save_clip_probe_cache(cache_path, entries_by_key)
    return clips


def _validate_source_fps_compatibility(clips: list[ClipState]) -> None:
    if len(clips) < 2:
        return

    reference = clips[0]
    reference_fps = _normalized_fps(reference.source_fps)
    for comparison in clips[1:]:
        if _normalized_fps(comparison.source_fps) != reference_fps:
            raise MixedSourceFpsError(
                reference_path=reference.path,
                reference_fps=reference.source_fps,
                comparison_label=comparison.label,
                comparison_path=comparison.path,
                comparison_fps=comparison.source_fps,
            )


def _normalized_fps(fps: Fraction) -> Fraction:
    return Fraction(fps.numerator, fps.denominator)


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
    input_videos = discover_inputs(workspace.input_dir)
    artifacts = RunArtifacts()

    _validate_cache_state(
        request=request,
        workspace=workspace,
        config=config,
        input_videos=input_videos,
    )

    workspace, metadata_prefetch = await _resolve_run_directory(
        request=request,
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        deps=deps,
    )

    clips = _probe_input_videos(
        workspace=workspace,
        input_videos=input_videos,
        deps=deps,
    )
    _validate_source_fps_compatibility(clips)

    return PrepState(
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        clips=clips,
        artifacts=artifacts,
        metadata_prefetch=metadata_prefetch,
        preflight_warnings=preflight.warnings,
        preflight_duration=preflight_duration,
        load_sources_start=load_sources_start,
    )
