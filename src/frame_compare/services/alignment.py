"""Audio alignment service using cross-correlation."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import structlog

from frame_compare.services.alignment_audio import extract_audio, probe_fps
from frame_compare.services.alignment_cache import (
    CACHE_FILE_NAME,
    CACHE_VERSION,
    load_cached_offsets,
    save_offsets_cache,
)
from frame_compare.services.alignment_math import (
    calculate_alignment_trims,
    cross_correlate,
    samples_to_frames,
)
from frame_compare.services.alignment_vspreview import maybe_launch_alignment_vspreview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vspreview.overrides import load_manual_overrides

log = structlog.get_logger()

_extract_audio = extract_audio
_probe_fps = probe_fps
_cross_correlate = cross_correlate
_samples_to_frames = samples_to_frames

__all__ = [
    "CACHE_FILE_NAME",
    "CACHE_VERSION",
    "_cross_correlate",
    "_extract_audio",
    "_probe_fps",
    "_samples_to_frames",
    "align_clips",
    "calculate_alignment_trims",
    "check_alignment_cached",
    "load_cached_offsets",
    "save_offsets_cache",
]


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
    maybe_launch_alignment_vspreview(
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
