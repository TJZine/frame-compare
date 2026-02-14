"""Run coordination types for Frame Compare 2.0."""

from __future__ import annotations

import inspect
import json
import math
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

import httpx

from frame_compare.analysis import cache_io, calculate_metrics, create_frame_plan, select_frames
from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.config import ConfigSchema, apply_cli_overrides
from frame_compare.errors import (
    AudioAlignmentError,
    CacheCorruptionError,
    CacheVersionMismatchError,
    FFmpegError,
    FFmpegNotFoundError,
    MetricsCalculationError,
    TonemapRequiresVapourSynthError,
)
from frame_compare.orchestration.context import (
    ClipAlignmentState,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.fps_report import (
    build_consolidated_fps_report,
    emit_consolidated_fps_report,
)
from frame_compare.orchestration.phases import Phase, execute_phases
from frame_compare.orchestration.preflight import discover_inputs, prepare_preflight
from frame_compare.orchestration.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.orchestration.probe_props import (
    compute_preserved_frame_props,
    compute_tonemap_prop_keys,
)
from frame_compare.orchestration.progress import select_reporter
from frame_compare.render.naming import generate_screenshot_path
from frame_compare.render.orchestrator import render_screenshots
from frame_compare.render.types import OverlayMode as RenderOverlayMode
from frame_compare.services.alignment import CACHE_FILE_NAME, align_clips, load_cached_offsets
from frame_compare.services.metadata import resolve_metadata
from frame_compare.services.publishers import publish_to_slowpics
from frame_compare.services.report import ClipInfo, ReportData, generate_report
from frame_compare.services.run_folder import derive_run_folder_name, get_existing_run_folders
from frame_compare.services.types import AlignmentConfig, MetadataConfig, TmdbMetadata
from frame_compare.utils.progress import ProgressReporter
from frame_compare.utils.subproc import run_subprocess
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.loader import DefaultVSLoader, VSLoader
from frame_compare.vs.types import HDRMetadata
from frame_compare.vspreview import load_manual_overrides


@dataclass(frozen=True)
class RunRequest:
    """Complete configuration for a comparison run.

    All fields map to CLI flags or config file sections.
    See cli-module.md for CLI flag → config mappings.
    """

    # Core paths
    root: Path
    config_path: Path | None = None
    input_dir: Path | None = None

    # Cache behavior
    no_cache: bool = False
    from_cache_only: bool = False

    # Skip flags
    skip_analysis: bool = False
    skip_metadata: bool = False
    skip_dovi: bool = False
    no_upload: bool = False
    force_interactive_alignment: bool = False

    # Tonemap overrides (highest priority)
    tm_preset: str | None = None
    tm_target_nits: int | None = None
    tm_curve: str | None = None

    # Frame selection overrides
    frame_count: int | None = None
    seed: int | None = None

    # Output behavior
    overlay_mode: str | None = None
    no_color: bool = False
    quiet: bool = False
    verbose: bool = False
    json_output: bool = False


def _empty_str_list() -> list[str]:
    return []


def _empty_phase_timings() -> dict[str, float]:
    return {}


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


def _build_metadata_config(config: ConfigSchema) -> MetadataConfig:
    """Build metadata service config from run config."""
    return MetadataConfig(
        api_key=config.tmdb.api_key,
        unattended=config.tmdb.unattended,
        timeout_seconds=config.tmdb.timeout_seconds,
    )


@dataclass(frozen=True)
class RunResult:
    """Complete result from a comparison run."""

    # Outputs
    success: bool
    screenshot_dir: Path | None = None
    slowpics_url: str | None = None
    report_path: Path | None = None

    # Metrics
    frame_count: int = 0
    clips_processed: int = 0
    duration_seconds: float = 0.0
    cache_hit: bool = False

    # Diagnostics
    errors: list[str] = field(default_factory=_empty_str_list)
    warnings: list[str] = field(default_factory=_empty_str_list)
    phase_timings: dict[str, float] = field(default_factory=_empty_phase_timings)


class FFmpegRunner(Protocol):
    """Protocol for FFmpeg-based frame extraction and probing."""

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        """Extract a single frame from the given video into the output path."""
        ...

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        """Probe HDR metadata for a video, returning None if unavailable."""
        ...


class DefaultFFmpegRunner:
    """Default FFmpeg runner for dependency injection in orchestration."""

    _FFPROBE_TIMEOUT_SECONDS = 15.0
    _FFMPEG_TIMEOUT_SECONDS = 30.0

    def _probe_fps(self, video: Path) -> float:
        argv = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
        try:
            proc = run_subprocess(argv, timeout_seconds=self._FFPROBE_TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError("ffprobe timed out while probing fps", 124) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

        raw = proc.stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            raise FFmpegError("ffprobe returned empty avg_frame_rate", proc.returncode)

        try:
            if "/" in raw:
                num, den = raw.split("/", maxsplit=1)
                num_f = float(num)
                den_f = float(den)
                if den_f == 0.0:
                    raise ValueError("zero denominator")
                fps = num_f / den_f
            else:
                fps = float(raw)
        except ValueError as exc:
            raise FFmpegError(f"invalid avg_frame_rate value: {raw!r}", proc.returncode) from exc

        if not math.isfinite(fps) or fps <= 0.0:
            raise FFmpegError(f"invalid probed fps value: {raw!r}", proc.returncode)
        return fps

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        fps = self._probe_fps(video)
        seek_time = f"{math.floor((frame_num / fps) * 1000) / 1000:.3f}"
        output.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            "ffmpeg",
            "-y",
            "-ss",
            seek_time,
            "-i",
            str(video),
            "-vframes",
            "1",
            "-q:v",
            "1",
            str(output),
        ]
        try:
            run_subprocess(argv, timeout_seconds=self._FFMPEG_TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError("ffmpeg timed out while extracting frame", 124) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        argv = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=color_transfer,color_primaries,color_space",
            "-of",
            "json",
            str(video),
        ]
        try:
            proc = run_subprocess(argv, timeout_seconds=self._FFPROBE_TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError("ffprobe timed out while probing hdr", 124) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

        try:
            payload = cast(
                dict[str, object], json.loads(proc.stdout.decode("utf-8", errors="replace"))
            )
        except json.JSONDecodeError as exc:
            raise FFmpegError("ffprobe returned invalid json", proc.returncode) from exc

        streams_obj = payload.get("streams")
        if not isinstance(streams_obj, list) or not streams_obj:
            return None
        streams = cast(list[object], streams_obj)
        stream_obj = streams[0]
        if not isinstance(stream_obj, dict):
            return None
        stream = cast(dict[str, object], stream_obj)

        transfer_raw = str(stream.get("color_transfer", "")).lower().strip()
        primaries_raw = str(stream.get("color_primaries", "")).lower().strip()
        matrix_raw = str(stream.get("color_space", "")).lower().strip()
        is_hdr = transfer_raw in {"smpte2084", "arib-std-b67"} and primaries_raw == "bt2020"
        if not is_hdr:
            return None

        primaries_map = {"bt709": 1, "bt2020": 9}
        transfer_map = {"bt709": 1, "smpte2084": 16, "arib-std-b67": 18}
        matrix_map = {"bt709": 1, "bt2020nc": 9, "bt2020c": 10}
        return HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=primaries_map.get(primaries_raw, 2),
            transfer=transfer_map.get(transfer_raw, 2),
            matrix=matrix_map.get(matrix_raw, 2),
        )


@dataclass
class RunDependencies:
    """Dependency injection container for run orchestration."""

    vs_loader: VSLoader | None = None
    ffmpeg_runner: FFmpegRunner | None = None
    http_client: httpx.AsyncClient | None = None
    progress: ProgressReporter | None = None
    clock: Callable[[], datetime] = field(default=datetime.now)

    def get_vs_loader(self) -> VSLoader:
        """Return the injected VS loader or create the default lazily."""
        if self.vs_loader is None:
            self.vs_loader = DefaultVSLoader()
        return self.vs_loader

    def get_ffmpeg_runner(self) -> FFmpegRunner:
        """Return the injected FFmpeg runner or create the default lazily."""
        if self.ffmpeg_runner is None:
            self.ffmpeg_runner = DefaultFFmpegRunner()
        return self.ffmpeg_runner


async def execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult:
    """Execute a run request asynchronously.

    Raises:
        FrameCompareError: Any preflight validation errors are propagated.
    """
    if deps is None:
        deps = RunDependencies()

    if deps.progress is None:
        deps.progress = select_reporter(
            quiet=request.quiet,
            json_output=request.json_output,
            no_color=request.no_color,
        )

    async def _execute_with_deps() -> RunResult:
        run_start = deps.clock()
        phase_timings: dict[str, float] = {}
        reporter = deps.progress
        if reporter is None:
            raise RuntimeError("Progress reporter must be initialized before execution.")

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

        phase_timings["preflight"] = (preflight_end - preflight_start).total_seconds()

        load_sources_start = deps.clock()
        workspace = preflight.workspace
        cli_args: dict[str, object] = {
            "tm_preset": request.tm_preset,
            "tm_target": request.tm_target_nits,
            "tm_curve": request.tm_curve,
            "frame_count": request.frame_count,
            "seed": request.seed,
            "overlay": request.overlay_mode,
            "no_upload": request.no_upload,
            "force_interactive_alignment": request.force_interactive_alignment,
            "input": str(request.input_dir) if request.input_dir is not None else None,
        }
        config = apply_cli_overrides(preflight.config, cli_args=cli_args)
        input_videos = discover_inputs(workspace.input_dir)
        phase_warnings: set[str] = set()
        resolved_metadata: TmdbMetadata | None = None
        metadata_prefetched = False

        # Resolve run folder before any cache/probe path access so all phases use the same workspace.
        if config.paths.use_run_folders:
            if deps.http_client is not None and config.tmdb.enabled and not request.skip_metadata:
                # Mark prefetch attempt as final for this run. If lookup fails, we keep the
                # folder naming path resilient and skip a second metadata-phase retry.
                metadata_prefetched = True
                try:
                    resolved_metadata = await resolve_metadata(
                        filenames=[input_videos[0].name],
                        config=_build_metadata_config(config),
                        client=deps.http_client,
                    )
                except Exception as exc:
                    # Metadata lookup is optional; keep run folder naming resilient.
                    phase_warnings.add(f"metadata: {exc}")
                    resolved_metadata = None

            filenames = [video.name for video in input_videos]
            existing = get_existing_run_folders(workspace.input_dir)
            run_folder_name = derive_run_folder_name(
                filenames=filenames,
                tmdb_metadata=resolved_metadata,
                existing_folders=existing,
            )
            run_dir = workspace.input_dir / run_folder_name
            workspace = workspace.with_run_dir(run_dir)

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
            reference = input_videos[0]
            comparisons = input_videos[1:]
            manual_overrides = load_manual_overrides(workspace.generated_dir)
            cached_offsets = (
                load_cached_offsets(workspace.generated_dir, [reference] + comparisons) or {}
            )
            missing: list[str] = []
            for comp in comparisons:
                key = f"{reference.stem}:{comp.stem}"
                if key in manual_overrides or key in cached_offsets:
                    continue
                missing.append(key)
            if missing:
                message = "Missing cached audio alignment offsets for: " + ", ".join(missing)
                raise AudioAlignmentError(message)
        cache_path = workspace.generated_dir / "clip_probe.toml"
        cached_entries = load_clip_probe_cache(cache_path)
        entries_by_key: dict[str, ClipProbeSnapshot] = dict(cached_entries)
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
                source_info = deps.get_vs_loader().load(path)
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

        reference = clips[0]
        comparisons = clips[1:]

        context = RunContext(
            config=config,
            workspace=workspace,
            reference=reference,
            comparisons=comparisons,
            reporter=reporter,
        )
        emit_consolidated_fps_report(
            stage="after_load_sources",
            clips=build_consolidated_fps_report(reference, comparisons),
            json_output=request.json_output,
            quiet=request.quiet,
        )
        load_sources_end = deps.clock()
        phase_timings["load_sources"] = (load_sources_end - load_sources_start).total_seconds()

        phase_timings.update(
            {
                "frame_plan": 0.0,
                "analyze": 0.0,
                "align": 0.0,
                "render": 0.0,
                "metadata": 0.0,
                "dovi": 0.0,
                "publish": 0.0,
                "report": 0.0,
            }
        )
        selected_frames: list[int] = []
        metrics_cache_hit = False
        screenshots_by_label: dict[str, list[Path]] = {}
        slowpics_url: str | None = None
        report_path: Path | None = None
        screenshot_dir: Path | None = None

        def _timed_phase(
            name: str,
            timing_key: str,
            skip_condition: Callable[[ConfigSchema], bool] | None,
            executor: Callable[[RunContext], None | Awaitable[None]],
            *,
            warn_only: bool = False,
        ) -> Phase:
            async def _execute(ctx: RunContext) -> None:
                start = deps.clock()
                try:
                    maybe_awaitable = executor(ctx)
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable
                except Exception as exc:
                    if warn_only:
                        phase_warnings.add(f"{name}: {exc}")
                        raise
                    raise
                finally:
                    end = deps.clock()
                    phase_timings[timing_key] = (end - start).total_seconds()

            return Phase(name=name, execute=_execute, skip_condition=skip_condition)

        phases_before_align = [
            _timed_phase(
                "frame_plan",
                "frame_plan",
                None,
                lambda ctx: selected_frames.extend(
                    create_frame_plan(
                        num_frames=ctx.reference.effective_num_frames(),
                        count=ctx.config.analysis.frame_count,
                        seed=ctx.config.analysis.random_seed,
                    ).frames
                ),
            ),
            _timed_phase(
                "analyze",
                "analyze",
                lambda config: request.skip_analysis,
                lambda ctx: _run_analyze_phase(
                    ctx=ctx,
                    input_videos=input_videos,
                    workspace=workspace,
                    selected_frames=selected_frames,
                    metrics_cache_hit_out=lambda hit: _set_metrics_cache_hit(hit),
                ),
                warn_only=True,
            ),
            _timed_phase(
                "align",
                "align",
                lambda config: not config.audio_alignment.enable,
                lambda ctx: _run_align_phase(ctx, selected_frames=selected_frames),
                warn_only=True,
            ),
        ]

        phases_after_align = [
            _timed_phase(
                "render",
                "render",
                None,
                lambda ctx: _run_render_phase(
                    ctx=ctx,
                    frames=selected_frames,
                    runner=deps.get_ffmpeg_runner(),
                    screenshots_out=lambda value: _set_screenshots(value),
                    screenshot_dir_out=lambda value: _set_screenshot_dir(value),
                ),
            ),
            _timed_phase(
                "metadata",
                "metadata",
                lambda config: request.skip_metadata,
                lambda ctx: _run_metadata_phase(
                    ctx=ctx,
                    client=deps.http_client,
                    prefetched_metadata=resolved_metadata,
                    metadata_prefetched=metadata_prefetched,
                    metadata_out=lambda value: _set_metadata(value),
                ),
                warn_only=True,
            ),
            _timed_phase(
                "dovi",
                "dovi",
                lambda config: request.skip_dovi,
                lambda _ctx: phase_warnings.add(
                    "dovi: DOVI processing is not implemented yet; continuing without Dolby Vision extraction."
                ),
                warn_only=True,
            ),
            _timed_phase(
                "publish",
                "publish",
                lambda config: request.no_upload,
                lambda ctx: _run_publish_phase(
                    ctx=ctx,
                    client=deps.http_client,
                    metadata=resolved_metadata,
                    slowpics_url_out=lambda value: _set_slowpics_url(value),
                ),
                warn_only=True,
            ),
            _timed_phase(
                "report",
                "report",
                lambda config: not config.report.enable,
                lambda ctx: _run_report_phase(
                    ctx=ctx,
                    frames=selected_frames,
                    screenshots=screenshots_by_label,
                    metadata=resolved_metadata,
                    slowpics_url=slowpics_url,
                    report_path_out=lambda value: _set_report_path(value),
                ),
                warn_only=True,
            ),
        ]

        def _set_metrics_cache_hit(value: bool) -> None:
            nonlocal metrics_cache_hit
            metrics_cache_hit = value

        def _set_metadata(value: TmdbMetadata | None) -> None:
            nonlocal resolved_metadata
            resolved_metadata = value

        def _set_screenshots(value: dict[str, list[Path]]) -> None:
            nonlocal screenshots_by_label
            screenshots_by_label = value

        def _set_slowpics_url(value: str | None) -> None:
            nonlocal slowpics_url
            slowpics_url = value

        def _set_report_path(value: Path | None) -> None:
            nonlocal report_path
            report_path = value

        def _set_screenshot_dir(value: Path | None) -> None:
            nonlocal screenshot_dir
            screenshot_dir = value

        await execute_phases(phases_before_align, context, reporter)
        emit_consolidated_fps_report(
            stage="after_align",
            clips=build_consolidated_fps_report(context.reference, context.comparisons),
            json_output=request.json_output,
            quiet=request.quiet,
        )
        await execute_phases(phases_after_align, context, reporter)
        run_end = deps.clock()
        duration_seconds = (run_end - run_start).total_seconds()

        return RunResult(
            success=True,
            screenshot_dir=screenshot_dir,
            slowpics_url=slowpics_url,
            report_path=report_path,
            frame_count=len(selected_frames),
            clips_processed=1 + len(context.comparisons),
            duration_seconds=duration_seconds,
            cache_hit=metrics_cache_hit,
            phase_timings=phase_timings,
            warnings=[*preflight.warnings, *sorted(phase_warnings)],
        )

    if deps.http_client is not None:
        return await _execute_with_deps()

    async with httpx.AsyncClient() as http_client:
        deps.http_client = http_client
        return await _execute_with_deps()


def _run_analyze_phase(
    *,
    ctx: RunContext,
    input_videos: list[Path],
    workspace: WorkspacePaths,
    selected_frames: list[int],
    metrics_cache_hit_out: Callable[[bool], None],
) -> None:
    fingerprint = cache_io.compute_cache_key(input_videos, ctx.config.analysis)
    cache_result = cache_io.load_cached_metrics(workspace.cache_dir, fingerprint, clips=[])
    metrics_cache_hit_out(cache_result.success and cache_result.metrics is not None)
    metrics = calculate_metrics(
        video_paths=input_videos,
        config=ctx.config.analysis,
        cache_dir=workspace.cache_dir,
        reporter=ctx.reporter,
    )
    selection = select_frames(metrics=metrics, config=ctx.config.analysis)
    selected_frames[:] = selection.frames
    ctx.selection_breakdown = selection.breakdown


def selection_label_for_frame(frame: int, breakdown: SelectionBreakdown | None) -> str | None:
    if breakdown is None:
        return None
    if frame in breakdown.quantile_dark:
        return "Dark"
    if frame in breakdown.quantile_bright:
        return "Bright"
    if frame in breakdown.motion:
        return "Motion"
    if frame in breakdown.random:
        return "Random"
    return None


async def _run_align_phase(ctx: RunContext, *, selected_frames: list[int]) -> None:
    if not ctx.comparisons:
        return
    alignment_config = AlignmentConfig(
        enable=ctx.config.audio_alignment.enable,
        sample_rate=ctx.config.audio_alignment.sample_rate,
        max_offset_seconds=ctx.config.audio_alignment.max_offset_seconds,
        use_vspreview=ctx.config.audio_alignment.use_vspreview,
        force_interactive=ctx.config.audio_alignment.force_interactive,
        cache_results=ctx.config.audio_alignment.cache_results,
    )
    results = await align_clips(
        reference=ctx.reference.path,
        comparisons=[comp.path for comp in ctx.comparisons],
        config=alignment_config,
        cache_dir=ctx.workspace.generated_dir,
        progress=ctx.reporter,
    )

    def _source_from_method(method: str) -> str:
        if method == "manual":
            return "manual"
        if method == "cross_correlation":
            return "computed"
        return "cached"

    updated_comparisons: list[ClipState] = []
    for comparison, result in zip(ctx.comparisons, results, strict=True):
        updated_comparisons.append(
            replace(
                comparison,
                alignment=ClipAlignmentState(
                    reference_stem=Path(result.reference_clip).stem,
                    comparison_stem=Path(result.comparison_clip).stem,
                    relative_offset_frames=result.frame_offset,
                    source=_source_from_method(result.method),
                ),
            )
        )
    ctx.reference, ctx.comparisons = _apply_alignment_trims(
        reference=ctx.reference,
        comparisons=updated_comparisons,
    )
    selected_frames[:] = _normalize_selected_frames_for_trimmed_domain(
        selected_frames=selected_frames,
        reference=ctx.reference,
        comparisons=ctx.comparisons,
        requested_count=ctx.config.analysis.frame_count,
        seed=ctx.config.analysis.random_seed,
    )


def _run_render_phase(
    *,
    ctx: RunContext,
    frames: list[int],
    runner: FFmpegRunner,
    screenshots_out: Callable[[dict[str, list[Path]]], None],
    screenshot_dir_out: Callable[[Path | None], None],
) -> None:
    from frame_compare.render.encoders import apply_overlay_to_file
    from frame_compare.render.types import OverlayConfig

    clips_state = [ctx.reference, *ctx.comparisons]
    label_map = {clip.path: clip.label for clip in clips_state}
    output_dir = ctx.workspace.screenshots_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Keep FFmpeg-only extraction aligned with render.orchestrator tonemap gating:
    # HDR + tonemap enabled cannot use the FFmpeg-only path.
    if (
        ctx.config.screenshots.use_ffmpeg
        and ctx.config.color.enable_tonemap
        and any(clip.probe.is_hdr for clip in clips_state)
    ):
        raise TonemapRequiresVapourSynthError()

    if ctx.config.screenshots.use_ffmpeg:
        overlay_mode = RenderOverlayMode(ctx.config.screenshots.overlay_mode.value)
        selection_labels = [
            selection_label_for_frame(
                _map_aligned_to_source_frame(clip=ctx.reference, aligned_frame=aligned_frame),
                ctx.selection_breakdown,
            )
            for aligned_frame in frames
        ]
        rendered: dict[str, list[Path]] = {}
        for clip in clips_state:
            paths: list[Path] = []
            for idx, aligned_frame in enumerate(frames):
                source_frame = _map_aligned_to_source_frame(clip=clip, aligned_frame=aligned_frame)
                output = generate_screenshot_path(output_dir, clip.label, aligned_frame)
                runner.extract_frame(clip.path, source_frame, output)
                if overlay_mode != RenderOverlayMode.NONE:
                    overlay = OverlayConfig(
                        mode=overlay_mode,
                        label=clip.label,
                        frame_number=source_frame,
                        resolution=(clip.probe.width, clip.probe.height),
                        hdr_info="HDR" if clip.probe.is_hdr else None,
                        font_path=None,
                        display_frame_number=aligned_frame,
                        num_frames=clip.probe.num_frames,
                        selection_label=selection_labels[idx],
                    )
                    apply_overlay_to_file(output, overlay)
                paths.append(output)
            rendered[clip.label] = paths
        screenshots_out(rendered)
        screenshot_dir_out(output_dir)
        return

    overlay_mode = RenderOverlayMode(ctx.config.screenshots.overlay_mode.value)
    rendered: dict[str, list[Path]] = {}
    selection_labels = [
        selection_label_for_frame(
            _map_aligned_to_source_frame(clip=ctx.reference, aligned_frame=aligned_frame),
            ctx.selection_breakdown,
        )
        for aligned_frame in frames
    ]
    for clip in clips_state:
        source_frames = [
            _map_aligned_to_source_frame(clip=clip, aligned_frame=aligned_frame)
            for aligned_frame in frames
        ]
        rendered_for_clip = render_screenshots(
            clips=[clip.path],
            frames=source_frames,
            output_frames=frames,
            selection_labels=selection_labels,
            output_dir=output_dir,
            config=ctx.config,
            label_map=label_map,
            renderer="auto",
            overlay_mode=overlay_mode,
            reporter=ctx.reporter,
        )
        rendered[clip.label] = rendered_for_clip[clip.label]
    screenshots_out(rendered)
    screenshot_dir_out(output_dir)


async def _run_metadata_phase(
    *,
    ctx: RunContext,
    client: httpx.AsyncClient | None,
    prefetched_metadata: TmdbMetadata | None,
    metadata_prefetched: bool,
    metadata_out: Callable[[TmdbMetadata | None], None],
) -> None:
    if metadata_prefetched:
        metadata_out(prefetched_metadata)
        return

    if client is None or not ctx.config.tmdb.enabled:
        metadata_out(None)
        return
    metadata = await resolve_metadata(
        filenames=[ctx.reference.path.name],
        config=_build_metadata_config(ctx.config),
        client=client,
    )
    metadata_out(metadata)


async def _run_publish_phase(
    *,
    ctx: RunContext,
    client: httpx.AsyncClient | None,
    metadata: TmdbMetadata | None,
    slowpics_url_out: Callable[[str | None], None],
) -> None:
    if client is None:
        slowpics_url_out(None)
        return
    result = await publish_to_slowpics(
        screenshot_dir=ctx.workspace.screenshots_dir,
        config=ctx.config.slowpics,
        client=client,
        metadata=metadata,
        progress=ctx.reporter,
    )
    slowpics_url_out(result.url)


def _run_report_phase(
    *,
    ctx: RunContext,
    frames: list[int],
    screenshots: dict[str, list[Path]],
    metadata: TmdbMetadata | None,
    slowpics_url: str | None,
    report_path_out: Callable[[Path | None], None],
) -> None:
    if not screenshots:
        report_path_out(None)
        return

    clips = [ctx.reference, *ctx.comparisons]
    clip_info = [
        ClipInfo(
            name=clip.label,
            path=clip.path,
            frame_count=clip.probe.num_frames,
            resolution=(clip.probe.width, clip.probe.height),
            fps=float(clip.effective_fps),
            hdr=clip.probe.is_hdr,
            label=clip.label,
        )
        for clip in clips
    ]
    report_data = ReportData(
        clips=clip_info,
        frames=frames,
        screenshots=screenshots,
        metadata=metadata,
        slowpics_url=slowpics_url,
    )
    report_path = generate_report(report_data, ctx.config.report)
    report_path_out(report_path)


def _apply_alignment_trims(
    *,
    reference: ClipState,
    comparisons: list[ClipState],
) -> tuple[ClipState, list[ClipState]]:
    offsets = [
        comparison.alignment.relative_offset_frames
        for comparison in comparisons
        if comparison.alignment is not None
    ]
    if not offsets:
        return reference, comparisons

    baseline = max(0, max(offsets))
    trimmed_reference = reference.with_trim(
        trim_start_frames=baseline,
        trim_end_frame_inclusive=None,
    )
    trimmed_comparisons: list[ClipState] = []
    for comparison in comparisons:
        if comparison.alignment is None:
            relative_offset = 0
        else:
            relative_offset = comparison.alignment.relative_offset_frames
        trim_start = baseline - relative_offset
        trimmed_comparisons.append(
            comparison.with_trim(
                trim_start_frames=trim_start,
                trim_end_frame_inclusive=None,
            )
        )

    common_length = min(
        [
            trimmed_reference.effective_num_frames(),
            *[c.effective_num_frames() for c in trimmed_comparisons],
        ]
    )
    if common_length <= 0:
        raise AudioAlignmentError("No overlapping frames after alignment normalization.")

    trimmed_reference = trimmed_reference.with_trim(
        trim_start_frames=trimmed_reference.trim.trim_start_frames,
        trim_end_frame_inclusive=trimmed_reference.trim.trim_start_frames + common_length - 1,
    )
    equalized_comparisons: list[ClipState] = []
    for comparison in trimmed_comparisons:
        equalized_comparisons.append(
            comparison.with_trim(
                trim_start_frames=comparison.trim.trim_start_frames,
                trim_end_frame_inclusive=comparison.trim.trim_start_frames + common_length - 1,
            )
        )

    return trimmed_reference, equalized_comparisons


def _normalize_selected_frames_for_trimmed_domain(
    *,
    selected_frames: list[int],
    reference: ClipState,
    comparisons: list[ClipState],
    requested_count: int,
    seed: int,
) -> list[int]:
    common_length = min(
        [
            reference.effective_num_frames(),
            *[comparison.effective_num_frames() for comparison in comparisons],
        ]
    )
    if common_length <= 0:
        raise AudioAlignmentError("No overlapping frames remain after alignment.")

    reference_start = reference.trim.trim_start_frames
    reference_end_exclusive = reference_start + common_length
    normalized_frames = sorted(
        {
            frame - reference_start
            for frame in selected_frames
            if reference_start <= frame < reference_end_exclusive
        }
    )
    target_count = min(requested_count, common_length)
    if target_count <= 0:
        return []
    if len(normalized_frames) < target_count:
        return create_frame_plan(num_frames=common_length, count=target_count, seed=seed).frames
    return normalized_frames[:target_count]


def _map_aligned_to_source_frame(*, clip: ClipState, aligned_frame: int) -> int:
    source_frame = clip.trim.trim_start_frames + aligned_frame
    trim_end = (
        clip.trim.trim_end_frame_inclusive
        if clip.trim.trim_end_frame_inclusive is not None
        else clip.probe.num_frames - 1
    )
    if source_frame > trim_end:
        raise AudioAlignmentError(
            f"Aligned frame {aligned_frame} exceeds trimmed domain for {clip.path.name}."
        )
    return source_frame
