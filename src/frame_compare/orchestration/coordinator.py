"""Run coordination types for Frame Compare 2.0."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

import httpx

from frame_compare.analysis import cache_io
from frame_compare.config import ConfigSchema, apply_cli_overrides
from frame_compare.errors import (
    AudioAlignmentError,
    CacheCorruptionError,
    CacheVersionMismatchError,
    MetricsCalculationError,
)
from frame_compare.orchestration.context import (
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
from frame_compare.services.alignment import CACHE_FILE_NAME, load_cached_offsets
from frame_compare.utils.progress import ProgressReporter
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
    """Stub FFmpeg runner for dependency injection in this slice."""

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        raise NotImplementedError(
            "DefaultFFmpegRunner is a stub in Phase 6.7; inject a runner to use FFmpeg."
        )

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        raise NotImplementedError(
            "DefaultFFmpegRunner is a stub in Phase 6.7; inject a runner to use FFmpeg."
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

        def _timed_phase(
            name: str,
            timing_key: str,
            skip_condition: Callable[[ConfigSchema], bool] | None,
        ) -> Phase:
            async def _execute(_: RunContext) -> None:
                start = deps.clock()
                end = deps.clock()
                phase_timings[timing_key] = (end - start).total_seconds()

            return Phase(name=name, execute=_execute, skip_condition=skip_condition)

        phases_before_align = [
            _timed_phase("frame_plan", "frame_plan", None),
            _timed_phase(
                "analyze",
                "analyze",
                lambda config: request.skip_analysis,
            ),
            _timed_phase(
                "align",
                "align",
                lambda config: not config.audio_alignment.enable,
            ),
        ]

        phases_after_align = [
            _timed_phase("render", "render", None),
            _timed_phase(
                "metadata",
                "metadata",
                lambda config: request.skip_metadata,
            ),
            _timed_phase("dovi", "dovi", lambda config: request.skip_dovi),
            _timed_phase("publish", "publish", lambda config: request.no_upload),
            _timed_phase(
                "report",
                "report",
                lambda config: not config.report.enable,
            ),
        ]

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
            duration_seconds=duration_seconds,
            phase_timings=phase_timings,
            warnings=preflight.warnings,
        )

    if deps.http_client is not None:
        return await _execute_with_deps()

    async with httpx.AsyncClient() as http_client:
        deps.http_client = http_client
        return await _execute_with_deps()
