"""Tests for analysis tier validation helpers."""

from __future__ import annotations

import importlib.util
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from frame_compare.analysis.tier_validation import (
    compare_rankings,
    compare_selection_category,
    nearest_frame_distances,
    spearman_rank_correlation,
    top_k_overlap,
)
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
)
from frame_compare.config.schema import ConfigSchema


def test_nearest_frame_distances_returns_one_distance_per_candidate() -> None:
    assert nearest_frame_distances([10, 20], [9, 18, 30]) == [1, 2, 10]
    assert nearest_frame_distances([], [1, 2]) == [None, None]


def test_compare_selection_category_reports_overlap_and_miss_rate() -> None:
    result = compare_selection_category(
        quality_frames=[10, 20, 30],
        candidate_frames=[10, 22, 50],
        tolerance_frames=3,
    )

    assert result.overlap_count == 1
    assert result.jaccard_overlap == pytest.approx(1 / 5)
    assert result.nearest_quality_distances == [0, 2, 20]
    assert result.max_nearest_distance == 20
    assert result.median_nearest_distance == 2.0
    assert result.miss_rate_at_tolerance == pytest.approx(1 / 3)


def test_top_k_overlap_uses_source_offsets_and_stable_ordering() -> None:
    result = top_k_overlap(
        [0.1, 0.9, 0.9, 0.2],
        [0.1, 0.8, 0.7, 0.95],
        k=2,
        largest=True,
        source_offset=100,
    )

    assert result.k == 2
    assert result.quality_indices == [101, 102]
    assert result.candidate_indices == [103, 101]
    assert result.overlap_count == 1


def test_spearman_rank_correlation_handles_identical_reversed_and_tied_arrays() -> None:
    assert spearman_rank_correlation([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)
    assert spearman_rank_correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)
    assert spearman_rank_correlation([1.0, 1.0, 2.0], [1.0, 1.0, 2.0]) == pytest.approx(1.0)


def test_compare_rankings_builds_required_top_k_sections() -> None:
    result = compare_rankings(
        quality_luminance=[0.0, 0.2, 1.0],
        candidate_luminance=[0.0, 0.1, 1.0],
        quality_motion=[0.0, 0.8, 0.2],
        candidate_motion=[0.0, 0.1, 0.9],
        dark_count=1,
        bright_count=1,
        motion_count=1,
        source_offset=10,
    )

    assert result.luminance_spearman == pytest.approx(1.0)
    assert result.lowest_luminance_top_k.k == 3
    assert result.highest_luminance_top_k.quality_indices == [12, 11, 10]
    assert result.highest_motion_top_k.candidate_indices == [12, 11, 10]


def test_benchmark_script_comparison_schema_contains_required_sections() -> None:
    script = _load_benchmark_script()
    quality = _tier_payload("quality", [0.0, 0.2, 1.0], [0.0, 0.1, 0.7], [0, 1, 2])
    candidate = _tier_payload("fast", [0.0, 0.1, 1.0], [0.0, 0.0, 0.8], [0, 2])

    result = cast(dict[str, Any], script._compare_tier(quality=quality, candidate=candidate))

    assert result["mode"] == "fast"
    assert set(result["comparisons"]) == {"dark", "bright", "motion"}
    assert set(result["ranking"]) == {
        "highest_luminance_top_k",
        "highest_motion_top_k",
        "lowest_luminance_top_k",
        "luminance_spearman",
        "motion_spearman",
    }
    assert result["selected"]["frames"] == [0, 2]


def test_benchmark_script_resolves_configured_analysis_source_and_effective_fps(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    input_dir = tmp_path / "comparison_videos"
    input_dir.mkdir()
    reference = input_dir / "reference.mkv"
    analysis = input_dir / "analysis.mkv"
    reference.write_bytes(b"ref")
    analysis.write_bytes(b"analysis")
    config = ConfigSchema.model_validate(
        {
            "sources": {
                "analysis_source": "analysis.mkv",
                "overrides": {"analysis.mkv": {"effective_fps": "24000/1001"}},
            }
        }
    )

    source_path = script._resolve_benchmark_analysis_source_path(
        input_dir=input_dir,
        input_paths=[reference, analysis],
        config=config,
    )
    effective_fps = script._effective_fps_override_for_path(
        input_dir=input_dir,
        input_paths=[reference, analysis],
        config=config,
        source_path=source_path,
    )

    assert source_path == analysis
    assert effective_fps == Fraction(24000, 1001)


def test_benchmark_script_uses_configured_generated_dir_for_default_cache(tmp_path: Path) -> None:
    script = _load_benchmark_script()

    assert (
        script._resolve_config_path(tmp_path, "custom-generated") == tmp_path / "custom-generated"
    )


@pytest.mark.parametrize(
    "sources",
    [
        {"analysis_source": "fastest"},
        {"match_fps": "assume_reference"},
    ],
)
def test_benchmark_script_rejects_unsupported_production_contexts(
    tmp_path: Path,
    sources: dict[str, str],
) -> None:
    script = _load_benchmark_script()
    input_dir = tmp_path / "comparison_videos"
    input_dir.mkdir()
    source = input_dir / "source.mkv"
    source.write_bytes(b"source")
    config = ConfigSchema.model_validate({"sources": sources})

    with pytest.raises(SystemExit):
        script._resolve_benchmark_analysis_source_path(
            input_dir=input_dir,
            input_paths=[source],
            config=config,
        )


def _load_benchmark_script() -> ModuleType:
    script_path = Path(__file__).resolve().parents[2] / "tools" / "benchmark_analysis_tiers.py"
    spec = importlib.util.spec_from_file_location("benchmark_analysis_tiers_for_test", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _tier_payload(
    mode: str,
    luminance: list[float],
    motion: list[float],
    selected_frames: list[int],
) -> dict[str, Any]:
    metrics = FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=len(luminance),
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[ClipIdentity(path="clip.mkv", size=1, mtime=1.0)],
            performance_mode=mode,
            algorithm_id=f"{mode}-algorithm",
            metric_backend="test",
            algorithm_identity_json="{}",
        ),
    )
    selection = FrameSelection(
        frames=selected_frames,
        seed=0,
        breakdown=SelectionBreakdown(
            quantile_dark=selected_frames[:1],
            quantile_bright=selected_frames[-1:],
            motion=selected_frames,
        ),
    )
    return {
        "mode": mode,
        "analyze_seconds": 0.1,
        "cache_state": "unknown",
        "metadata": {
            "frame_count": len(luminance),
            "performance_mode": mode,
            "algorithm_id": f"{mode}-algorithm",
            "metric_backend": "test",
            "algorithm_identity": {},
        },
        "window": {"start_frame": 0, "end_frame_exclusive": len(luminance)},
        "windowed_metrics": metrics,
        "selection": selection,
    }
