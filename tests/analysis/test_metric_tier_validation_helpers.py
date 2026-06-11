"""Tests for analysis tier validation helpers."""

from __future__ import annotations

import importlib.util
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from frame_compare.analysis.tier_validation import (
    PerformanceTier,
    SelectionCategory,
    compare_rankings,
    compare_selection_category,
    nearest_frame_distances,
    spearman_rank_correlation,
    tier_category_tolerance,
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
from frame_compare.config.schema_enums import AnalysisPerformanceMode


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


def test_tier_category_tolerance_handles_known_tiers_and_categories() -> None:
    assert tier_category_tolerance("performance", "dark") == 2
    assert tier_category_tolerance("performance", "bright") == 2
    assert tier_category_tolerance("performance", "motion") == 3


def test_tier_category_tolerance_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="Unsupported PerformanceTier"):
        tier_category_tolerance(cast(PerformanceTier, "quality"), "motion")

    with pytest.raises(ValueError, match="Unsupported SelectionCategory"):
        tier_category_tolerance("performance", cast(SelectionCategory, "invalid"))


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


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"candidate_luminance": [0.0, 0.1]}, "candidate_luminance"),
        ({"candidate_motion": [0.0, 0.1]}, "candidate_motion"),
        ({"quality_motion": [0.0, 0.8]}, "quality_motion"),
    ],
)
def test_compare_rankings_rejects_mismatched_vector_lengths(
    overrides: dict[str, list[float]],
    expected_field: str,
) -> None:
    kwargs = {
        "quality_luminance": [0.0, 0.2, 1.0],
        "candidate_luminance": [0.0, 0.1, 1.0],
        "quality_motion": [0.0, 0.8, 0.2],
        "candidate_motion": [0.0, 0.1, 0.9],
        "dark_count": 1,
        "bright_count": 1,
        "motion_count": 1,
    } | overrides

    with pytest.raises(ValueError, match=f"compare_rankings.*{expected_field}"):
        compare_rankings(**kwargs)


def test_benchmark_script_comparison_schema_contains_required_sections() -> None:
    script = _load_benchmark_script()
    quality = _tier_payload("quality", [0.0, 0.2, 1.0], [0.0, 0.1, 0.7], [0, 1, 2])
    candidate = _tier_payload("performance", [0.0, 0.1, 1.0], [0.0, 0.0, 0.8], [0, 2])

    result = cast(dict[str, Any], script._compare_tier(quality=quality, candidate=candidate))

    assert result["mode"] == "performance"
    assert set(result["comparisons"]) == {"dark", "bright", "motion"}
    assert set(result["ranking"]) == {
        "highest_luminance_top_k",
        "highest_motion_top_k",
        "lowest_luminance_top_k",
        "luminance_spearman",
        "motion_spearman",
    }
    assert result["selected"]["frames"] == [0, 2]


def test_benchmark_script_progress_wraps_quality_and_candidate_tiers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    calls: list[str] = []
    progress_events: list[tuple[str, object]] = []

    class FakeProgress:
        def __init__(self, *args: object, **kwargs: object) -> None:
            progress_events.append(("disable", kwargs["disable"]))

        def __enter__(self) -> FakeProgress:
            progress_events.append(("enter", None))
            return self

        def __exit__(self, *args: object) -> None:
            progress_events.append(("exit", None))

        def add_task(self, description: str, *, total: int) -> int:
            progress_events.append(("add_task", (description, total)))
            return 7

        def update(self, task_id: int, *, description: str) -> None:
            progress_events.append(("update", (task_id, description)))

        def advance(self, task_id: int) -> None:
            progress_events.append(("advance", task_id))

    def fake_run_tier(**kwargs: object) -> dict[str, object]:
        mode = cast(str, kwargs["mode"])
        calls.append(mode)
        return {"mode": mode, "analyze_seconds": 0.1}

    def fake_compare_tier(
        *,
        quality: dict[str, object],
        candidate: dict[str, object],
    ) -> dict[str, object]:
        return {
            "quality_mode": quality["mode"],
            "candidate_mode": candidate["mode"],
        }

    monkeypatch.setattr(script, "Progress", FakeProgress)
    monkeypatch.setattr(script, "_run_tier", fake_run_tier)
    monkeypatch.setattr(script, "_compare_tier", fake_compare_tier)

    quality, comparisons = script._run_benchmark_tiers(
        candidate_modes=["performance"],
        video_paths=[tmp_path / "reference.mkv"],
        analysis_config=ConfigSchema().analysis,
        cache_dir=tmp_path / "cache",
        analysis_source_path=tmp_path / "reference.mkv",
        effective_fps=None,
        selection_domain=None,
        window_start=0,
        window_end_exclusive=None,
        progress_enabled=True,
    )

    assert quality["mode"] == "quality"
    assert calls == ["quality", "performance"]
    assert comparisons == {
        "performance": {"quality_mode": "quality", "candidate_mode": "performance"},
    }
    assert ("disable", False) in progress_events
    assert ("add_task", ("Starting analysis benchmark", 2)) in progress_events
    assert ("update", (7, "Running quality analysis")) in progress_events
    assert ("update", (7, "Running performance analysis")) in progress_events
    assert ("update", (7, "Analysis benchmark complete")) in progress_events
    assert progress_events.count(("advance", 7)) == 2


def test_benchmark_script_run_tier_preserves_typed_performance_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    observed_modes: list[AnalysisPerformanceMode] = []

    def fake_calculate_metrics(
        video_paths: list[Path],
        analysis_config: object,
        cache_dir: Path,
        *,
        analysis_source_path: Path,
        effective_fps: object,
        selection_domain: str | None,
    ) -> FrameMetrics:
        assert video_paths == [tmp_path / "reference.mkv"]
        assert cache_dir == tmp_path / "cache"
        assert analysis_source_path == tmp_path / "reference.mkv"
        assert effective_fps is None
        assert selection_domain is None
        observed_modes.append(analysis_config.performance_mode)
        return _metrics_payload("performance", [0.0, 0.2, 1.0], [0.0, 0.1, 0.7])

    monkeypatch.setattr(script, "calculate_metrics", fake_calculate_metrics)

    result = script._run_tier(
        mode="performance",
        video_paths=[tmp_path / "reference.mkv"],
        analysis_config=ConfigSchema.model_validate(
            {
                "analysis": {
                    "random_frame_count": 0,
                    "dark_frame_count": 1,
                    "bright_frame_count": 0,
                    "motion_frame_count": 0,
                }
            }
        ).analysis,
        cache_dir=tmp_path / "cache",
        analysis_source_path=tmp_path / "reference.mkv",
        effective_fps=None,
        selection_domain=None,
        window_start=0,
        window_end_exclusive=None,
    )

    assert observed_modes == [AnalysisPerformanceMode.PERFORMANCE]
    assert result["metadata"]["performance_mode"] == "performance"


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
                "match_fps": "disabled",
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
    metrics = _metrics_payload(mode, luminance, motion)
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


def _metrics_payload(
    mode: str,
    luminance: list[float],
    motion: list[float],
) -> FrameMetrics:
    return FrameMetrics(
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
