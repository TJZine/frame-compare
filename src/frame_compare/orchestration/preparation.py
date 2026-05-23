"""Workspace and input preparation logic for runs."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

import frame_compare.analysis.cache_io as cache_io
from frame_compare.config.overrides import apply_cli_overrides
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import (
    CacheCorruptionError,
    CacheVersionMismatchError,
    MetricsCalculationError,
)
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.phase_tasks import resolve_run_metadata
from frame_compare.orchestration.preflight import discover_inputs, prepare_preflight
from frame_compare.orchestration.probing import (
    compute_preserved_frame_props,
    compute_probe_cache_key,
    compute_tonemap_prop_keys,
    load_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.orchestration.types import (
    PrepState,
    RunArtifacts,
    RunDependencies,
    RunRequest,
)
from frame_compare.services.alignment import CACHE_FILE_NAME, check_alignment_cached
from frame_compare.services.errors import (
    AudioAlignmentError,
    MetadataError,
    TmdbError,
    TmdbRateLimitedError,
)
from frame_compare.services.run_folder import (
    derive_run_folder_name,
    get_existing_run_folders,
    reserve_run_folder,
)
from frame_compare.utils.types import WorkspacePaths

log = structlog.get_logger()


def _build_preflight_overrides(request: RunRequest) -> dict[str, object] | None:
    overrides: dict[str, object] = {}
    if request.input_dir is not None:
        overrides["paths"] = {"input_dir": str(request.input_dir)}
    return overrides or None


def _remove_cached_metrics(workspace: WorkspacePaths) -> None:
    analysis_cache_path = workspace.cache_dir / cache_io.CACHE_FILENAME
    if analysis_cache_path.exists():
        analysis_cache_path.unlink()
    audio_cache_path = workspace.generated_dir / CACHE_FILE_NAME
    if audio_cache_path.exists():
        audio_cache_path.unlink()


def _resolve_cache_only_run_dir(workspace: WorkspacePaths, filenames: list[str]) -> Path:
    """Resolve the deterministic run folder used for cache-only reads.

    Cache-only runs must not depend on live TMDB metadata or reserve a new folder. If the
    expected folder already exists with different casing, keep the on-disk spelling.
    """
    run_folder_name = derive_run_folder_name(
        filenames=filenames,
        tmdb_metadata=None,
    )
    existing_folders = get_existing_run_folders(workspace.input_dir)
    expected = run_folder_name.casefold()
    for folder_name in existing_folders:
        if folder_name.casefold() == expected:
            return workspace.input_dir / folder_name
    return workspace.input_dir / run_folder_name


def _resolve_cache_version(cache_path: Path) -> str | None:
    try:
        data = cache_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    version = payload.get("version")
    return str(version) if version is not None else None


async def _resolve_run_directory(
    *,
    request: RunRequest,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
    artifacts: RunArtifacts,
    deps: RunDependencies,
) -> tuple[WorkspacePaths, bool]:
    metadata_prefetched = False
    if config.paths.use_run_folders:
        if deps.http_client is not None and config.tmdb.enabled and not request.skip_metadata:
            try:
                artifacts.resolved_metadata = await resolve_run_metadata(
                    filenames=[input_videos[0].name],
                    config=config,
                    client=deps.http_client,
                )
                metadata_prefetched = True
            except (MetadataError, TmdbError, TmdbRateLimitedError) as exc:
                log.warning(
                    "metadata_prefetch_degraded",
                    filenames=[input_videos[0].name],
                    error_type=type(exc).__name__,
                    error=str(exc),
                    exc_info=exc,
                )
                artifacts.resolved_metadata = None

        filenames = [video.name for video in input_videos]
        if request.from_cache_only:
            run_dir = _resolve_cache_only_run_dir(workspace, filenames)
            new_workspace = workspace.with_run_dir(run_dir)
        else:
            run_dir = reserve_run_folder(
                input_dir=workspace.input_dir,
                filenames=filenames,
                tmdb_metadata=artifacts.resolved_metadata,
            )
            new_workspace = workspace.with_run_dir(run_dir)
        return new_workspace, metadata_prefetched
    return workspace, metadata_prefetched


def _validate_cache_state(
    *,
    request: RunRequest,
    workspace: WorkspacePaths,
    config: ConfigSchema,
    input_videos: list[Path],
) -> None:
    if request.no_cache:
        _remove_cached_metrics(workspace)

    if request.from_cache_only and not request.skip_analysis:
        fingerprint = cache_io.compute_cache_key(input_videos, config.analysis)
        cache_result = cache_io.load_cached_metrics(workspace.cache_dir, fingerprint, clips=[])
        if not cache_result.success:
            cache_path = workspace.cache_dir / cache_io.CACHE_FILENAME
            if cache_result.reason == "corrupted":
                raise CacheCorruptionError(cache_path)
            if cache_result.reason == "version_mismatch":
                found = _resolve_cache_version(cache_path) or "unknown"
                raise CacheVersionMismatchError(found, str(cache_io.CACHE_VERSION))
            raise MetricsCalculationError(
                f"Cached metrics missing or mismatched ({cache_result.reason})."
            )

    if request.from_cache_only and config.audio_alignment.enable and len(input_videos) > 1:
        missing = check_alignment_cached(
            reference=input_videos[0],
            comparisons=input_videos[1:],
            cache_dir=workspace.generated_dir,
        )
        if missing:
            message = "Missing cached audio alignment offsets for: " + ", ".join(missing)
            raise AudioAlignmentError(message)


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
        cli_args=request.cli_override_args(),
    )
    input_videos = discover_inputs(workspace.input_dir)
    artifacts = RunArtifacts()

    workspace, metadata_prefetched = await _resolve_run_directory(
        request=request,
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        artifacts=artifacts,
        deps=deps,
    )

    _validate_cache_state(
        request=request,
        workspace=workspace,
        config=config,
        input_videos=input_videos,
    )

    clips = _probe_input_videos(
        workspace=workspace,
        input_videos=input_videos,
        deps=deps,
    )

    return PrepState(
        workspace=workspace,
        config=config,
        input_videos=input_videos,
        clips=clips,
        artifacts=artifacts,
        metadata_prefetched=metadata_prefetched,
        preflight_warnings=preflight.warnings,
        preflight_duration=preflight_duration,
        load_sources_start=load_sources_start,
    )
