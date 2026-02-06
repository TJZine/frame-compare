"""Audio alignment service using cross-correlation."""

import subprocess
import tomllib
from fractions import Fraction
from pathlib import Path
from typing import cast

import numpy as np
import tomli_w

from frame_compare.errors import (
    AudioAlignmentError,
    CacheCorruptionError,
    CacheVersionMismatchError,
    FFmpegError,
    FFmpegNotFoundError,
)
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.progress import ProgressReporter
from frame_compare.utils.subproc import run_subprocess

CACHE_VERSION = "1"
CACHE_FILE_NAME = "audio_offsets.toml"
_FFPROBE_TIMEOUT_SECONDS = 15.0
_FFMPEG_AUDIO_TIMEOUT_SECONDS = 120.0


async def align_clips(
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
    if progress:
        progress.start_phase("Audio Alignment", total=len(comparisons))

    results_map: dict[str, AlignmentResult] = {}

    # 0. Load manual overrides (highest precedence per §2.4)
    from frame_compare.vspreview import load_manual_overrides

    manual_overrides = load_manual_overrides(cache_dir)
    fps_reference: Fraction | None = None  # Lazy probe, only when needed

    for comp in comparisons:
        key = f"{reference.stem}:{comp.stem}"
        if key in manual_overrides:
            override = manual_overrides[key]
            # Need FPS for time_offset_seconds calculation
            if fps_reference is None:
                fps_reference = _probe_fps(reference)
            results_map[key] = AlignmentResult(
                reference_clip=reference.name,
                comparison_clip=comp.name,
                frame_offset=override.frame_offset,
                time_offset_seconds=override.frame_offset / float(fps_reference),
                correlation_score=1.0,  # Explicit constant per §2.4
                method="manual",
            )

    # 1. Check cache for non-manual entries
    requested_comparisons = [
        c for c in comparisons if f"{reference.stem}:{c.stem}" not in results_map
    ]
    if config.cache_results and requested_comparisons:
        cached = load_cached_offsets(cache_dir, [reference] + requested_comparisons)
        if cached is not None:
            results_map.update(cached)
            # Find what is still missing
            requested_comparisons = [
                c for c in comparisons if f"{reference.stem}:{c.stem}" not in results_map
            ]

    # If everything is resolved (manual + cached), return early
    if not requested_comparisons:
        if progress:
            progress.complete_phase()
        return [results_map[f"{reference.stem}:{c.stem}"] for c in comparisons]

    # 2. Compute missing
    try:
        if fps_reference is None:
            fps_reference = _probe_fps(reference)
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
                method="cross_correlation",
            )
            results_map[f"{reference.stem}:{comp.stem}"] = res

            if progress:
                progress.advance()

        # 3. Save cache if needed (only computed results, not manual)
        if config.cache_results:
            # Save only the computed results (method != "manual")
            computed_results = [
                results_map[f"{reference.stem}:{c.stem}"]
                for c in comparisons
                if results_map[f"{reference.stem}:{c.stem}"].method != "manual"
            ]
            if computed_results:
                save_offsets_cache(cache_dir, computed_results)

    finally:
        if progress:
            progress.complete_phase()

    # Return results in the same order as input comparisons
    return [results_map[f"{reference.stem}:{c.stem}"] for c in comparisons]


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
    except tomllib.TOMLDecodeError:
        raise CacheCorruptionError(cache_path) from None

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
                method = entry_dict["method"]

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
                if not isinstance(method, str):
                    raise TypeError("method must be str")

                results[key] = AlignmentResult(
                    reference_clip=reference_clip,
                    comparison_clip=comparison_clip,
                    frame_offset=frame_offset,
                    time_offset_seconds=float(time_offset_seconds),
                    correlation_score=float(correlation_score),
                    method=method,
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
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Load existing cache to preserve other entries
    data: dict[str, object] = {"version": CACHE_VERSION}
    if cache_path.exists():
        try:
            with cache_path.open("rb") as f:
                data.update(tomllib.load(f))
        except tomllib.TOMLDecodeError:
            # If corrupt, we'll just overwrite
            pass

    # Update with new results
    for res in results:
        key = f"{Path(res.reference_clip).stem}:{Path(res.comparison_clip).stem}"
        data[key] = {
            "reference_clip": res.reference_clip,
            "comparison_clip": res.comparison_clip,
            "frame_offset": res.frame_offset,
            "time_offset_seconds": res.time_offset_seconds,
            "correlation_score": res.correlation_score,
            "method": res.method,
        }

    with cache_path.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))


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
