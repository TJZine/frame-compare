"""Tests for the analysis-tier benchmark tool."""

from __future__ import annotations

import importlib.util
import sys
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricActiveRect,
    MetricsMetadata,
    SelectionBreakdown,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import (
    AnalysisPerformanceMode,
    ScreenshotActiveRectDetection,
)
from frame_compare.config.schema_models import SourceOverrideConfig
from tests.orchestration.execute_run_helpers import write_probe_cache_for_inputs


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
        active_rect = cast(Any, kwargs["active_rect"])
        assert active_rect.rect == MetricActiveRect(x=10, y=20, width=300, height=200)
        assert active_rect.source == "explicit"
        assert active_rect.detection_mode == "provided"
        calls.append(mode)
        return _tier_payload(mode, [0.0, 1.0], [0.0, 0.5], [0, 1])

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
        active_rect=script.BenchmarkActiveRect(
            rect=MetricActiveRect(x=10, y=20, width=300, height=200),
            source="explicit",
            detection_mode="provided",
        ),
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
    add_task_events = [payload for event, payload in progress_events if event == "add_task"]
    assert len(add_task_events) == 1
    start_description, total = cast(tuple[str, int], add_task_events[0])
    assert start_description
    assert total == 2
    update_events = [
        cast(tuple[int, str], payload) for event, payload in progress_events if event == "update"
    ]
    assert len(update_events) == 3
    assert all(task_id == 7 and description for task_id, description in update_events)
    assert progress_events.count(("advance", 7)) == 2
    assert progress_events.index(("add_task", add_task_events[0])) < progress_events.index(
        ("advance", 7)
    )
    assert max(
        index for index, event in enumerate(progress_events) if event == ("advance", 7)
    ) < max(index for index, (event, _payload) in enumerate(progress_events) if event == "update")


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
        metric_active_rect: MetricActiveRect | None,
        active_rect_source: str,
        active_rect_detection_mode: str,
        active_rect_algorithm_id: str,
        selection_domain: str | None,
        timing_recorder: object,
    ) -> FrameMetrics:
        assert video_paths == [tmp_path / "reference.mkv"]
        assert cache_dir == tmp_path / "cache"
        assert analysis_source_path == tmp_path / "reference.mkv"
        assert effective_fps is None
        assert metric_active_rect == MetricActiveRect(x=10, y=20, width=300, height=200)
        assert active_rect_source == "explicit"
        assert active_rect_detection_mode == "provided"
        assert active_rect_algorithm_id == "active_rect_resolution_v2"
        assert selection_domain is None
        assert timing_recorder is not None
        observed_modes.append(analysis_config.performance_mode)
        return _metrics_payload(
            "performance",
            [0.0, 0.2, 1.0],
            [0.0, 0.1, 0.7],
            metric_active_rect=MetricActiveRect(x=10, y=20, width=300, height=200),
            active_rect_source="explicit",
            active_rect_detection_mode="provided",
        )

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
        active_rect=script.BenchmarkActiveRect(
            rect=MetricActiveRect(x=10, y=20, width=300, height=200),
            source="explicit",
            detection_mode="provided",
        ),
        selection_domain=None,
        window_start=0,
        window_end_exclusive=None,
    )

    assert observed_modes == [AnalysisPerformanceMode.PERFORMANCE]
    assert result["metadata"]["performance_mode"] == "performance"
    assert result["cache_state"] == "miss"
    assert result["cache_write_state"] == "not_attempted"


def test_benchmark_script_rotates_trial_order_and_aggregates_distributions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    calls: list[tuple[int, int, str]] = []
    timings = iter((3.0, 6.0, 5.0, 4.0, 7.0, 2.0))

    def fake_run_tier(**kwargs: object) -> dict[str, object]:
        mode = cast(str, kwargs["mode"])
        result = _tier_payload(mode, [0.0, 1.0], [0.0, 0.5], [0, 1])
        elapsed = next(timings)
        result.update(
            {
                "analyze_seconds": elapsed,
                "selection_seconds": 0.1,
                "trial_seconds": elapsed + 0.1,
                "process_cpu_seconds": elapsed / 2,
                "cpu_to_wall_ratio": 0.5,
                "peak_rss_bytes": 123,
                "phase_timings_seconds": {"frame_render": elapsed - 0.1},
                "cache_state": "miss",
                "cache_write_state": "written",
                "repetition": kwargs["repetition"],
                "order_index": kwargs["order_index"],
            }
        )
        calls.append(
            (
                cast(int, kwargs["repetition"]),
                cast(int, kwargs["order_index"]),
                mode,
            )
        )
        return result

    monkeypatch.setattr(script, "_run_tier", fake_run_tier)

    quality, comparisons = script._run_benchmark_tiers(
        candidate_modes=["performance"],
        video_paths=[tmp_path / "reference.mkv"],
        analysis_config=ConfigSchema().analysis,
        cache_dir=tmp_path / "cache",
        analysis_source_path=tmp_path / "reference.mkv",
        effective_fps=None,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        selection_domain=None,
        window_start=0,
        window_end_exclusive=None,
        progress_enabled=False,
        repetitions=3,
        metric_cache_policy="cold",
    )

    assert calls == [
        (0, 0, "quality"),
        (0, 1, "performance"),
        (1, 0, "performance"),
        (1, 1, "quality"),
        (2, 0, "quality"),
        (2, 1, "performance"),
    ]
    assert quality["timing_summary"]["analyze_seconds"]["median"] == 4.0
    assert quality["cache_state"] == {"miss": 3}
    assert quality["cache_write_state"] == {"written": 3}
    assert len(quality["trials"]) == 3
    assert comparisons["performance"]["timing_summary"]["analyze_seconds"]["median"] == 5.0


def test_benchmark_script_frame_type_summary_records_gop_distribution() -> None:
    script = _load_benchmark_script()

    summary = script._frame_type_summary(
        {
            "success": True,
            "payload": {
                "frames": [
                    {"key_frame": 1, "pict_type": "I"},
                    {"key_frame": 0, "pict_type": "B"},
                    {"key_frame": 0, "pict_type": "P"},
                    {"key_frame": 1, "pict_type": "I"},
                ]
            },
        }
    )

    assert summary["type_counts"] == {"I": 2, "B": 1, "P": 1}
    assert summary["keyframe_count"] == 2
    assert summary["keyframe_gap_frames"]["median"] == 3.0


def test_benchmark_script_detects_adjacent_source_index(tmp_path: Path) -> None:
    script = _load_benchmark_script()
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source")
    index = Path(f"{source}.lwi")
    index.write_bytes(b"index")

    facts = script._source_index_facts([source])

    assert facts[source.as_posix()] == {
        "detected": True,
        "paths": [index.as_posix()],
        "sizes_bytes": [5],
    }


def test_benchmark_script_ffprobe_timeout_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()

    def timeout(*_args: object, **_kwargs: object) -> object:
        raise script.subprocess.TimeoutExpired(cmd="ffprobe", timeout=2.5)

    monkeypatch.setattr(script.subprocess, "run", timeout)

    result = script._run_ffprobe_json([], path=tmp_path / "source.mkv", timeout_seconds=2.5)

    assert result == {"success": False, "error": "ffprobe timed out after 2.5s"}


def test_benchmark_script_reports_unavailable_peak_rss_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_benchmark_script()
    monkeypatch.setattr(script.sys, "platform", "win32")

    assert script._peak_rss_bytes() is None


def test_benchmark_script_recomputes_stale_active_rect_provenance_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"ref")
    active_rect = script.BenchmarkActiveRect(
        rect=MetricActiveRect(x=10, y=20, width=300, height=200),
        source="explicit",
        detection_mode="provided",
    )
    calls = 0
    deleted: list[tuple[Path, str]] = []

    def fake_calculate_metrics(*args: object, **kwargs: object) -> FrameMetrics:
        nonlocal calls
        calls += 1
        assert kwargs["metric_active_rect"] == active_rect.rect
        if calls == 1:
            return _metrics_payload(
                "performance",
                [0.0, 0.2, 1.0],
                [0.0, 0.1, 0.7],
                metric_active_rect=active_rect.rect,
                active_rect_source="full-frame",
                active_rect_detection_mode="aspect_ratio",
            )
        return _metrics_payload(
            "performance",
            [0.0, 0.2, 1.0],
            [0.0, 0.1, 0.7],
            metric_active_rect=active_rect.rect,
            active_rect_source="explicit",
            active_rect_detection_mode="provided",
        )

    def fake_compute_cache_key(*args: object, **kwargs: object) -> str:
        assert args[0] == [reference]
        assert kwargs["metric_request"].metric_active_rect == active_rect.rect
        return "stale-fingerprint"

    def fake_delete_metrics_cache_entry(cache_dir: Path, fingerprint: str) -> None:
        deleted.append((cache_dir, fingerprint))

    monkeypatch.setattr(script, "calculate_metrics", fake_calculate_metrics)
    monkeypatch.setattr(script, "compute_cache_key", fake_compute_cache_key)
    monkeypatch.setattr(script, "delete_metrics_cache_entry", fake_delete_metrics_cache_entry)

    result = script._calculate_metrics_with_expected_active_rect(
        video_paths=[reference],
        config=ConfigSchema.model_validate(
            {"analysis": {"performance_mode": "performance"}}
        ).analysis,
        cache_dir=tmp_path / "cache",
        analysis_source_path=reference,
        effective_fps=None,
        active_rect=active_rect,
        selection_domain=None,
    )

    assert calls == 2
    assert deleted == [(tmp_path / "cache", "stale-fingerprint")]
    assert result.metadata.active_rect_source == "explicit"
    assert result.metadata.active_rect_detection_mode == "provided"


def test_benchmark_script_resolves_configured_analysis_source_effective_fps_and_active_rect(
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
                "overrides": {
                    "analysis.mkv": {
                        "effective_fps": "24000/1001",
                        "active_rect": {"x": 10, "y": 20, "width": 300, "height": 200},
                    }
                },
            }
        }
    )

    source = script._resolve_benchmark_analysis_source(
        root=tmp_path,
        input_dir=input_dir,
        input_paths=[reference, analysis],
        config=config,
    )
    legacy_effective_fps = script._effective_fps_override_for_path(
        input_dir=input_dir,
        input_paths=[reference, analysis],
        config=config,
        source_path=source.path,
    )

    assert source.path == analysis
    assert source.reference_path == reference
    assert source.effective_fps == Fraction(24000, 1001)
    assert legacy_effective_fps == Fraction(24000, 1001)
    assert source.active_rect.rect == MetricActiveRect(x=10, y=20, width=300, height=200)
    assert source.active_rect.source == "explicit"
    assert source.active_rect.detection_mode == "aspect_ratio"


def test_benchmark_script_uses_full_frame_active_rect_provenance_by_default(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    input_dir = tmp_path / "comparison_videos"
    input_dir.mkdir()
    reference = input_dir / "reference.mkv"
    reference.write_bytes(b"ref")
    config = ConfigSchema()
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [reference], config)

    source = script._resolve_benchmark_analysis_source(
        root=tmp_path,
        input_dir=input_dir,
        input_paths=[reference],
        config=config,
    )

    assert source.path == reference
    assert source.reference_path == reference
    assert source.effective_fps is None
    assert source.active_rect.rect == MetricActiveRect(x=0, y=0, width=1920, height=1080)
    assert source.active_rect.source == "full-frame"
    assert source.active_rect.detection_mode == "aspect_ratio"
    assert source.active_rect.algorithm_id == "active_rect_resolution_v2"


def test_benchmark_script_uses_resolved_reference_order_for_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_benchmark_script()
    input_dir = tmp_path / "comparison_videos"
    input_dir.mkdir()
    first = input_dir / "first.mkv"
    reference = input_dir / "reference.mkv"
    first.write_bytes(b"first")
    reference.write_bytes(b"reference")
    config = ConfigSchema.model_validate(
        {
            "sources": {
                "reference": reference.name,
                "overrides": {
                    reference.name: {"active_rect": {"x": 0, "y": 0, "width": 100, "height": 100}}
                },
            }
        }
    )
    source = script._resolve_benchmark_analysis_source(
        root=tmp_path,
        input_dir=input_dir,
        input_paths=[first, reference],
        config=config,
    )
    captured_paths: list[Path] = []
    sentinel = object()

    def fake_calculate_metrics(
        video_paths: list[Path], *_args: object, **_kwargs: object
    ) -> object:
        captured_paths.extend(video_paths)
        return sentinel

    monkeypatch.setattr(script, "calculate_metrics", fake_calculate_metrics)

    result = script._calculate_metrics_once(
        video_paths=source.ordered_paths,
        config=config.analysis,
        cache_dir=tmp_path / "cache",
        analysis_source_path=source.path,
        effective_fps=source.effective_fps,
        active_rect=source.active_rect,
        selection_domain="prepared-domain",
    )

    assert source.ordered_paths == (reference, first)
    assert captured_paths == [reference, first]
    assert result is sentinel


def test_benchmark_script_requires_prepared_probe_for_implicit_active_rect(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    input_dir = tmp_path / "comparison_videos"
    input_dir.mkdir()
    reference = input_dir / "reference.mkv"
    reference.write_bytes(b"ref")

    with pytest.raises(SystemExit, match="prepared clip probe data"):
        script._resolve_benchmark_analysis_source(
            root=tmp_path,
            input_dir=input_dir,
            input_paths=[reference],
            config=ConfigSchema(),
        )


def test_benchmark_script_requires_selection_domain_for_non_first_analysis_source(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    analysis = tmp_path / "analysis.mkv"

    with pytest.raises(SystemExit, match="selection-domain token is required"):
        script._require_selection_domain_for_analysis_cache_identity(
            selection_domain=None,
            video_paths=[reference, analysis],
            analysis_source=_benchmark_analysis_source(script, path=analysis, reference=reference),
            active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
        )

    script._require_selection_domain_for_analysis_cache_identity(
        selection_domain="benchmark-domain",
        video_paths=[reference, analysis],
        analysis_source=_benchmark_analysis_source(script, path=analysis, reference=reference),
        active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
    )
    script._require_selection_domain_for_analysis_cache_identity(
        selection_domain=None,
        video_paths=[reference, analysis],
        analysis_source=_benchmark_analysis_source(script, path=reference, reference=reference),
        active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
    )


def test_benchmark_script_requires_selection_domain_for_effective_fps_override(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"

    with pytest.raises(SystemExit, match="selection-domain token is required"):
        script._require_selection_domain_for_analysis_cache_identity(
            selection_domain=None,
            video_paths=[reference],
            analysis_source=_benchmark_analysis_source(
                script,
                path=reference,
                reference=reference,
                effective_fps=Fraction(24, 1),
            ),
            active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
        )

    script._require_selection_domain_for_analysis_cache_identity(
        selection_domain="fps-domain",
        video_paths=[reference],
        analysis_source=_benchmark_analysis_source(
            script,
            path=reference,
            reference=reference,
            effective_fps=Fraction(24, 1),
        ),
        active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
    )


def test_benchmark_script_requires_selection_domain_for_trim_overrides(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"

    overrides = {reference: SourceOverrideConfig(trim_start_frames=10)}
    with pytest.raises(SystemExit, match="selection-domain token is required"):
        script._require_selection_domain_for_analysis_cache_identity(
            selection_domain=None,
            video_paths=[reference],
            analysis_source=_benchmark_analysis_source(
                script,
                path=reference,
                reference=reference,
                overrides=overrides,
            ),
            active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
        )

    script._require_selection_domain_for_analysis_cache_identity(
        selection_domain="trim-domain",
        video_paths=[reference],
        analysis_source=_benchmark_analysis_source(
            script,
            path=reference,
            reference=reference,
            overrides=overrides,
        ),
        active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
    )

    script._require_selection_domain_for_analysis_cache_identity(
        selection_domain=None,
        video_paths=[reference],
        analysis_source=_benchmark_analysis_source(
            script,
            path=reference,
            reference=reference,
            overrides={reference: SourceOverrideConfig()},
        ),
        active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
    )


def test_benchmark_script_requires_selection_domain_for_other_domain_facts(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    configured_reference = tmp_path / "configured-reference.mkv"

    cases = (
        (
            _benchmark_analysis_source(
                script,
                path=reference,
                reference=configured_reference,
            ),
            ScreenshotActiveRectDetection.ASPECT_RATIO,
        ),
        (
            _benchmark_analysis_source(
                script,
                path=reference,
                reference=reference,
                overrides={
                    reference: SourceOverrideConfig.model_validate(
                        {"active_rect": {"x": 0, "y": 0, "width": 100, "height": 100}}
                    )
                },
            ),
            ScreenshotActiveRectDetection.ASPECT_RATIO,
        ),
        (
            _benchmark_analysis_source(script, path=reference, reference=reference),
            ScreenshotActiveRectDetection.AUTO,
        ),
    )

    for source, detection in cases:
        with pytest.raises(SystemExit, match="selection-domain token is required"):
            script._require_selection_domain_for_analysis_cache_identity(
                selection_domain=None,
                video_paths=[reference, configured_reference],
                analysis_source=source,
                active_rect_detection=detection,
            )


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


def _benchmark_analysis_source(
    script: ModuleType,
    *,
    path: Path,
    reference: Path,
    effective_fps: Fraction | None = None,
    overrides: dict[Path, SourceOverrideConfig] | None = None,
) -> Any:
    return script.BenchmarkAnalysisSource(
        path=path,
        ordered_paths=(reference,) if path == reference else (reference, path),
        effective_fps=effective_fps,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={} if overrides is None else overrides,
    )


def _load_benchmark_script() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "tools" / "benchmark_analysis_tiers.py"
    spec = importlib.util.spec_from_file_location("benchmark_analysis_tiers_for_test", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
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
        "cache_write_state": "not_attempted",
        "phase_timings_seconds": {},
        "selection_seconds": 0.0,
        "trial_seconds": 0.1,
        "process_cpu_seconds": 0.05,
        "cpu_to_wall_ratio": 0.5,
        "peak_rss_bytes": 1,
        "repetition": 0,
        "order_index": 0,
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
    *,
    metric_active_rect: MetricActiveRect | None = None,
    active_rect_source: str = "full-frame",
    active_rect_detection_mode: str = "aspect_ratio",
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
            metric_active_rect=metric_active_rect,
            active_rect_source=active_rect_source,
            active_rect_detection_mode=active_rect_detection_mode,
        ),
    )
