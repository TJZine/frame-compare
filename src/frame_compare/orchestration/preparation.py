"""Workspace and input preparation logic for runs."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import structlog

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.config.overrides import apply_cli_overrides
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.context import (
    ClipActiveRect,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.errors import MixedSourceFpsError, SourceSelectionError
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
from frame_compare.orchestration.source_selection import (
    reference_cache_domain_token,
    resolve_source_selection,
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
    *,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
    reference_domain: str | None,
) -> None:
    fingerprint = cache_io.compute_cache_key(
        input_videos,
        config.analysis,
        reference_domain=reference_domain,
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
    reference_domain: str | None,
) -> None:
    if request.no_cache:
        _remove_cached_metrics(
            workspace=workspace,
            config=config,
            input_videos=input_videos,
            reference_domain=reference_domain,
        )

    if request.from_cache_only and not request.skip_analysis:
        fingerprint = cache_io.compute_cache_key(
            input_videos,
            config.analysis,
            reference_domain=reference_domain,
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


def _probe_input_videos(
    *,
    workspace: WorkspacePaths,
    input_videos: list[Path],
    deps: RunDependencies,
    overrides_by_path: dict[Path, SourceOverrideConfig],
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

        override = overrides_by_path.get(path)
        trim_start_frames = override.trim_start_frames if override is not None else 0
        trim_end_frames = override.trim_end_frames if override is not None else 0
        end_inclusive = snapshot.num_frames - 1 - trim_end_frames if trim_end_frames > 0 else None
        effective_end = end_inclusive if end_inclusive is not None else snapshot.num_frames - 1
        if trim_start_frames > effective_end:
            raise SourceSelectionError(
                selector=path.name,
                reason="source trims remove every frame",
                role="sources.overrides",
                matches=[path],
            )
        active_rect = None
        if override is not None and override.active_rect is not None:
            rect = override.active_rect
            if rect.x + rect.width > snapshot.width or rect.y + rect.height > snapshot.height:
                raise SourceSelectionError(
                    selector=path.name,
                    reason="active_rect is outside source dimensions",
                    role="sources.overrides",
                    matches=[path],
                )
            active_rect = ClipActiveRect(
                x=rect.x,
                y=rect.y,
                width=rect.width,
                height=rect.height,
            )
        label = "Reference" if index == 0 else f"Encode {index}"
        effective_fps = (
            override.effective_fps
            if override is not None and override.effective_fps is not None
            else snapshot.fps
        )
        clips.append(
            ClipState(
                path=path,
                label=label,
                probe=snapshot,
                source_fps=snapshot.fps,
                effective_fps=effective_fps,
                active_rect=active_rect,
            ).with_trim(
                trim_start_frames=trim_start_frames,
                trim_end_frame_inclusive=end_inclusive,
            )
        )

    save_clip_probe_cache(cache_path, entries_by_key)
    return clips


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
    reference_domain = reference_cache_domain_token(
        source_selection.overrides_by_path.get(input_videos[0])
    )
    artifacts = RunArtifacts()

    _validate_cache_state(
        request=request,
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        reference_domain=reference_domain,
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
        overrides_by_path=dict(source_selection.overrides_by_path),
    )
    _validate_source_fps_compatibility(clips)

    return PrepState(
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        reference_cache_domain=reference_domain,
        clips=clips,
        artifacts=artifacts,
        metadata_prefetch=metadata_prefetch,
        preflight_warnings=preflight.warnings,
        preflight_duration=preflight_duration,
        load_sources_start=load_sources_start,
    )
