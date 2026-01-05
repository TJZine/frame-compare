"""Audio alignment service using cross-correlation."""

import tomllib
from fractions import Fraction
from pathlib import Path

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
            sample_offset, score = _cross_correlate(ref_audio, comp_audio)

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
            data = tomllib.load(f)
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
            results[key] = AlignmentResult(
                reference_clip=entry["reference_clip"],
                comparison_clip=entry["comparison_clip"],
                frame_offset=entry["frame_offset"],
                time_offset_seconds=entry["time_offset_seconds"],
                correlation_score=entry["correlation_score"],
                method=entry["method"],
            )

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
        except (tomllib.TOMLDecodeError, Exception):
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
        proc = run_subprocess(argv)
        output = proc.stdout.decode("utf-8").strip()
        if not output:
            raise FFmpegError("ffprobe returned empty output", proc.returncode)
        return Fraction(output)
    except FileNotFoundError:
        raise FFmpegNotFoundError() from None
    except Exception as e:
        if isinstance(e, FFmpegNotFoundError):
            raise
        # run_subprocess raises CalledProcessError if check=True
        from subprocess import CalledProcessError

        if isinstance(e, CalledProcessError):
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
        proc = run_subprocess(argv)

    except FileNotFoundError:
        raise FFmpegNotFoundError() from None

    except Exception as e:
        from subprocess import CalledProcessError

        if isinstance(e, CalledProcessError):
            raise FFmpegError(e.stderr.decode("utf-8"), e.returncode) from e

        raise FFmpegError(str(e), 1) from e

    if not proc.stdout:
        raise AudioAlignmentError(f"empty audio track in {video_path.name}")

    return np.frombuffer(proc.stdout, dtype=np.float32)


def _cross_correlate(
    reference: np.ndarray,
    comparison: np.ndarray,
) -> tuple[int, float]:
    """Find offset using cross-correlation."""

    correlation = np.correlate(reference, comparison, mode="full")

    peak_idx = int(np.argmax(correlation))

    # offset = peak_idx - len(reference) + 1  # This gave flipped signs in tests

    offset = len(reference) - 1 - peak_idx

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
