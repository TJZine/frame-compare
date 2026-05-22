"""Audio alignment service using cross-correlation."""

from __future__ import annotations

import subprocess
import tomllib
from fractions import Fraction
from pathlib import Path
from typing import cast

import numpy as np
import structlog
import tomli_w

from frame_compare.errors import (
    AudioAlignmentError,
    CacheCorruptionError,
    CacheVersionMismatchError,
    FFmpegError,
    FFmpegNotFoundError,
    VSPreviewError,
)
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.progress import ProgressReporter
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vspreview.adapter import (
    VSPreviewAvailabilityStatus,
    VSPreviewConfig,
    check_vspreview_availability,
    launch_alignment_verification_session,
)

CACHE_VERSION = "1"
CACHE_FILE_NAME = "audio_offsets.toml"
_FFPROBE_TIMEOUT_SECONDS = 15.0
_FFMPEG_AUDIO_TIMEOUT_SECONDS = 120.0

log = structlog.get_logger()


def _build_offsets_map(
    *,
    reference: Path,
    comparisons: list[Path],
    results_map: dict[str, AlignmentResult],
) -> dict[str, int]:
    """Build stable `{reference:comparison -> frame_offset}` map for VSPreview."""
    offsets_by_key: dict[str, int] = {}
    for comp in comparisons:
        key = f"{reference.stem}:{comp.stem}"
        res = results_map.get(key)
        offsets_by_key[key] = 0 if res is None else int(res.frame_offset)
    return offsets_by_key


def _maybe_launch_vspreview(
    *,
    reference: Path,
    comparisons: list[Path],
    offsets_by_key: dict[str, int],
    cache_dir: Path,
    config: AlignmentConfig,
    progress: ProgressReporter | None,
) -> None:
    """Best-effort VSPreview alignment verification.

    This is intended for interactive verification/inspection only. Actual offsets
    used by the pipeline are still sourced from:
      1) manual overrides (highest precedence)
      2) cached offsets
      3) computed offsets (cross-correlation)
    """
    if not (config.use_vspreview or config.force_interactive):
        return

    availability = check_vspreview_availability()

    if config.force_interactive and not availability.is_available:
        if availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            err_msg = "Interactive alignment requested but VSPreview availability check failed."
            if availability.error_details:
                err_msg += f" ({availability.error_details.get('exception_type')}: {availability.error_details.get('exception')})"
            raise AudioAlignmentError(err_msg)
        else:
            raise AudioAlignmentError(
                "Interactive alignment requested but VSPreview is not available."
            )

    if not availability.is_available:
        if availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            log.warning(
                "vspreview_availability_probe_failed",
                error=availability.error_details.get("exception")
                if availability.error_details
                else "unknown error",
                exception_type=availability.error_details.get("exception_type")
                if availability.error_details
                else "Exception",
                hint=availability.hint,
                use_vspreview=config.use_vspreview,
                force_interactive=config.force_interactive,
            )
        elif config.use_vspreview and not config.force_interactive:
            log.warning(
                "vspreview_unavailable",
                hint=availability.hint,
                use_vspreview=config.use_vspreview,
                force_interactive=config.force_interactive,
            )

    should_launch = bool(
        (config.use_vspreview or config.force_interactive) and availability.is_available
    )

    if progress:
        progress.set_description("Alignment verification")

    try:
        launch_alignment_verification_session(
            reference=reference,
            comparisons=comparisons,
            suggested_offsets_by_key=offsets_by_key,
            cache_dir=cache_dir,
            config=VSPreviewConfig(enabled=should_launch),
        )
    except VSPreviewError as exc:
        if config.force_interactive:
            raise
        log.warning(
            "vspreview_optional_launch_failed",
            error=str(exc),
            force_interactive=config.force_interactive,
            use_vspreview=config.use_vspreview,
        )


def _check_duplicate_stems(comparisons: list[Path]) -> None:
    """Validate that comparison filenames have unique stems."""
    stems_to_paths: dict[str, list[Path]] = {}
    for comp in comparisons:
        stems_to_paths.setdefault(comp.stem, []).append(comp)
    duplicate_stems = {stem: paths for stem, paths in stems_to_paths.items() if len(paths) > 1}
    if duplicate_stems:
        formatted = ", ".join(
            f"{stem}: {[p.name for p in paths]}"
            for stem, paths in sorted(duplicate_stems.items(), key=lambda item: item[0])
        )
        raise AudioAlignmentError(
            "Duplicate comparison clip stems detected (alignment keys use filename stems). "
            f"Rename clips to be unique. Duplicates: {formatted}"
        )


def _apply_manual_overrides(
    reference: Path,
    comparisons: list[Path],
    cache_dir: Path,
    results_map: dict[str, AlignmentResult],
) -> Fraction | None:
    """Apply manual offsets from overrides config, returning reference FPS if probed."""
    from frame_compare.vspreview.overrides import load_manual_overrides

    manual_overrides = load_manual_overrides(cache_dir)
    fps_reference: Fraction | None = None

    for comp in comparisons:
        key = f"{reference.stem}:{comp.stem}"
        if key in manual_overrides:
            override = manual_overrides[key]
            if fps_reference is None:
                fps_reference = _probe_fps(reference)
            results_map[key] = AlignmentResult(
                reference_clip=reference.name,
                comparison_clip=comp.name,
                frame_offset=override.frame_offset,
                time_offset_seconds=override.frame_offset / float(fps_reference),
                correlation_score=1.0,
                algorithm=None,
                source="manual",
            )
    return fps_reference


def _compute_missing_alignments(
    *,
    reference: Path,
    requested_comparisons: list[Path],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    fps_reference: Fraction,
    progress: ProgressReporter | None,
) -> None:
    """Extract audio, perform cross-correlation, and populate results map."""
    ref_audio = _extract_audio(reference, config.sample_rate)

    for comp in requested_comparisons:
        if progress:
            progress.set_description(f"Aligning {comp.name}")

        comp_audio = _extract_audio(comp, config.sample_rate)
        max_offset_samples = int(config.max_offset_seconds * config.sample_rate)
        sample_offset, score = _cross_correlate(
            ref_audio,
            comp_audio,
            max_offset_samples=max_offset_samples,
        )

        frame_offset = _samples_to_frames(sample_offset, config.sample_rate, fps_reference)
        time_offset = sample_offset / config.sample_rate

        res = AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=comp.name,
            frame_offset=frame_offset,
            time_offset_seconds=time_offset,
            correlation_score=float(score),
            algorithm="cross_correlation",
            source="computed",
        )
        results_map[f"{reference.stem}:{comp.stem}"] = res


def align_clips(
    reference: Path,
    comparisons: list[Path],
    config: AlignmentConfig,
    cache_dir: Path,
    progress: ProgressReporter | None = None,
) -> list[AlignmentResult]:
    """
    Align comparison clips to reference using audio cross-correlation.

    Returns:
        List of AlignmentResult for each comparison, in the same order
        as the input `comparisons` list.
    """
    _check_duplicate_stems(comparisons)

    if progress:
        progress.set_description("Audio Alignment")

    results_map: dict[str, AlignmentResult] = {}
    # 0. Load manual overrides (highest precedence per §2.4)
    fps_reference = _apply_manual_overrides(reference, comparisons, cache_dir, results_map)

    # 1. Check cache for non-manual entries
    requested_comparisons = [
        c for c in comparisons if f"{reference.stem}:{c.stem}" not in results_map
    ]
    if config.cache_results and requested_comparisons:
        try:
            cached = load_cached_offsets(cache_dir, [reference] + requested_comparisons)
            if cached is not None:
                results_map.update(cached)
                requested_comparisons = [
                    c for c in comparisons if f"{reference.stem}:{c.stem}" not in results_map
                ]
        except (CacheCorruptionError, CacheVersionMismatchError) as exc:
            log.warning(
                "audio_offsets_cache_load_failed",
                path=str(cache_dir / CACHE_FILE_NAME),
                error=str(exc),
                action="degrade_to_computed_alignment",
            )

    # 2. Compute missing
    if requested_comparisons:
        if fps_reference is None:
            fps_reference = _probe_fps(reference)
        _compute_missing_alignments(
            reference=reference,
            requested_comparisons=requested_comparisons,
            config=config,
            results_map=results_map,
            fps_reference=fps_reference,
            progress=progress,
        )

        # 3. Save cache if needed (only computed results, not manual)
        if config.cache_results:
            computed_results = [
                results_map[f"{reference.stem}:{c.stem}"]
                for c in comparisons
                if results_map[f"{reference.stem}:{c.stem}"].source != "manual"
            ]
            if computed_results:
                save_offsets_cache(cache_dir, computed_results)

    offsets_by_key = _build_offsets_map(
        reference=reference,
        comparisons=comparisons,
        results_map=results_map,
    )
    _maybe_launch_vspreview(
        reference=reference,
        comparisons=comparisons,
        offsets_by_key=offsets_by_key,
        cache_dir=cache_dir,
        config=config,
        progress=progress,
    )

    # Return results in the same order as input comparisons
    return [results_map[f"{reference.stem}:{c.stem}"] for c in comparisons]


def check_alignment_cached(
    reference: Path,
    comparisons: list[Path],
    cache_dir: Path,
) -> list[str]:
    """Check if all comparison offsets are cached/overridden, returning missing keys."""
    from frame_compare.vspreview.overrides import load_manual_overrides

    _check_duplicate_stems(comparisons)

    manual_overrides = load_manual_overrides(cache_dir)
    cached_offsets = load_cached_offsets(cache_dir, [reference] + comparisons) or {}

    missing: list[str] = []
    for comp in comparisons:
        key = f"{reference.stem}:{comp.stem}"
        if key in manual_overrides or key in cached_offsets:
            continue
        missing.append(key)
    return missing


def _resolve_cached_algorithm(entry_dict: dict[str, object]) -> str:
    """Resolve the canonical cache algorithm field, accepting legacy key names."""
    algorithm = entry_dict.get("algorithm")
    if algorithm is None and "method" in entry_dict:
        algorithm = entry_dict["method"]

    if not isinstance(algorithm, str):
        raise TypeError("algorithm must be str")
    if algorithm != "cross_correlation":
        raise ValueError("unsupported algorithm value")
    return algorithm


def _normalize_legacy_cache_entries(data: dict[str, object]) -> None:
    """Rewrite legacy cache keys to the current schema before saving."""
    for key, entry in data.items():
        if key == "version" or not isinstance(entry, dict):
            continue
        entry_dict = cast(dict[str, object], entry)
        if "algorithm" not in entry_dict and "method" in entry_dict:
            entry_dict["algorithm"] = entry_dict["method"]
        entry_dict.pop("method", None)


def load_cached_offsets(
    cache_dir: Path,
    clips: list[Path],
) -> dict[str, AlignmentResult] | None:
    """Load previously calculated offsets from cache."""
    cache_path = cache_dir / CACHE_FILE_NAME
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("rb") as f:
            data = cast(dict[str, object], tomllib.load(f))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise CacheCorruptionError(cache_path) from exc

    if data.get("version") != CACHE_VERSION:
        raise CacheVersionMismatchError(str(data.get("version")), CACHE_VERSION)

    reference = clips[0]
    comparisons = clips[1:]

    results: dict[str, AlignmentResult] = {}
    for comp in comparisons:
        key = f"{reference.stem}:{comp.stem}"
        if key in data:
            entry = data[key]
            if not isinstance(entry, dict):
                raise CacheCorruptionError(cache_path)
            entry_dict = cast(dict[str, object], entry)
            try:
                reference_clip = entry_dict["reference_clip"]
                comparison_clip = entry_dict["comparison_clip"]
                frame_offset = entry_dict["frame_offset"]
                time_offset_seconds = entry_dict["time_offset_seconds"]
                correlation_score = entry_dict["correlation_score"]
                _resolve_cached_algorithm(entry_dict)

                if not isinstance(reference_clip, str):
                    raise TypeError("reference_clip must be str")
                if not isinstance(comparison_clip, str):
                    raise TypeError("comparison_clip must be str")
                if not isinstance(frame_offset, int):
                    raise TypeError("frame_offset must be int")
                if not isinstance(time_offset_seconds, int | float):
                    raise TypeError("time_offset_seconds must be number")
                if not isinstance(correlation_score, int | float):
                    raise TypeError("correlation_score must be number")

                results[key] = AlignmentResult(
                    reference_clip=reference_clip,
                    comparison_clip=comparison_clip,
                    frame_offset=frame_offset,
                    time_offset_seconds=float(time_offset_seconds),
                    correlation_score=float(correlation_score),
                    algorithm="cross_correlation",
                    source="cached",
                )
            except (KeyError, TypeError, ValueError) as e:
                raise CacheCorruptionError(cache_path) from e

    return results


def save_offsets_cache(
    cache_dir: Path,
    results: list[AlignmentResult],
) -> None:
    """Persist alignment results to cache."""
    cache_path = cache_dir / CACHE_FILE_NAME

    # Load existing cache to preserve other entries
    data: dict[str, object] = {"version": CACHE_VERSION}
    if cache_path.exists():
        try:
            with cache_path.open("rb") as f:
                data.update(tomllib.load(f))
            _normalize_legacy_cache_entries(data)
        except (tomllib.TOMLDecodeError, OSError) as exc:
            log.warning(
                "audio_offsets_cache_corrupt_on_write",
                path=str(cache_path),
                cache_version=CACHE_VERSION,
                action="overwrite_cache_and_discard_prior_entries",
                error=str(exc),
                exc_info=exc,
            )

    # Update with new results
    for res in results:
        key = f"{Path(res.reference_clip).stem}:{Path(res.comparison_clip).stem}"
        data[key] = {
            "reference_clip": res.reference_clip,
            "comparison_clip": res.comparison_clip,
            "frame_offset": res.frame_offset,
            "time_offset_seconds": res.time_offset_seconds,
            "correlation_score": res.correlation_score,
            "algorithm": res.algorithm,
        }

    try:
        write_bytes_atomic(cache_path, tomli_w.dumps(data).encode("utf-8"))
    except OSError as exc:
        log.warning(
            "audio_offsets_cache_write_failed",
            path=str(cache_path),
            error=str(exc),
            action="alignment_results_not_cached",
            exc_info=exc,
        )


def _probe_fps(video_path: Path) -> Fraction:
    """Probe video FPS using FFprobe."""
    argv = [
        "ffprobe",
        "-v",
        "quiet",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=r_frame_rate",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        proc = run_subprocess(argv, timeout_seconds=_FFPROBE_TIMEOUT_SECONDS)
        output = proc.stdout.decode("utf-8").strip()
        if not output:
            raise FFmpegError("ffprobe returned empty output", proc.returncode)
        return Fraction(output)
    except FileNotFoundError:
        raise FFmpegNotFoundError() from None
    except subprocess.TimeoutExpired as e:
        raise FFmpegError("ffprobe timed out", 124) from e
    except Exception as e:
        if isinstance(e, FFmpegError):
            raise
        if isinstance(e, FFmpegNotFoundError):
            raise
        if isinstance(e, subprocess.CalledProcessError):
            raise FFmpegError(e.stderr.decode("utf-8"), e.returncode) from e
        raise FFmpegError(str(e), 1) from e


def _extract_audio(video_path: Path, sample_rate: int) -> np.ndarray:
    """Extract audio using FFmpeg."""

    argv = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "-",
    ]

    try:
        proc = run_subprocess(argv, timeout_seconds=_FFMPEG_AUDIO_TIMEOUT_SECONDS)

    except FileNotFoundError:
        raise FFmpegNotFoundError() from None

    except subprocess.TimeoutExpired as e:
        raise FFmpegError("ffmpeg audio extraction timed out", 124) from e

    except Exception as e:
        if isinstance(e, subprocess.CalledProcessError):
            raise FFmpegError(e.stderr.decode("utf-8"), e.returncode) from e

        raise FFmpegError(str(e), 1) from e

    if not proc.stdout:
        raise AudioAlignmentError(f"empty audio track in {video_path.name}")

    return np.frombuffer(proc.stdout, dtype=np.float32)


def _cross_correlate(
    reference: np.ndarray,
    comparison: np.ndarray,
    max_offset_samples: int | None = None,
) -> tuple[int, float]:
    """Find offset using cross-correlation."""
    if reference.size == 0 or comparison.size == 0:
        raise AudioAlignmentError("empty audio signal prevents correlation")

    # FFT-based cross-correlation is substantially cheaper than direct O(n^2) correlation
    # for long clips and keeps deterministic results.
    correlation_size = reference.size + comparison.size - 1
    fft_size = 1 << (correlation_size - 1).bit_length()

    reference_fft = np.fft.rfft(reference, fft_size)
    comparison_fft = np.fft.rfft(comparison, fft_size)
    correlation_raw = np.fft.irfft(reference_fft * np.conj(comparison_fft), fft_size)
    correlation = np.concatenate(
        (
            correlation_raw[-(comparison.size - 1) :],
            correlation_raw[: reference.size],
        )
    )

    if max_offset_samples is not None:
        bounded = max(0, max_offset_samples)
        center = reference.size - 1
        start_idx = max(0, center - bounded)
        end_idx = min(correlation.size, center + bounded + 1)
        if start_idx >= end_idx:
            raise AudioAlignmentError("max_offset_seconds produced an empty search window")
        peak_idx = int(np.argmax(correlation[start_idx:end_idx])) + start_idx
    else:
        peak_idx = int(np.argmax(correlation))

    offset = reference.size - 1 - peak_idx

    norm_ref = np.linalg.norm(reference)

    norm_comp = np.linalg.norm(comparison)

    if norm_ref == 0 or norm_comp == 0:
        raise AudioAlignmentError("zero-norm audio signal prevents correlation")

    score = float(correlation[peak_idx] / (norm_ref * norm_comp))

    return offset, score


def _samples_to_frames(
    sample_offset: int,
    sample_rate: int,
    fps: Fraction,
) -> int:
    """Convert sample offset to frame offset."""
    time_offset = sample_offset / sample_rate
    return int(round(time_offset * float(fps)))
