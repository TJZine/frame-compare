"""Contract tests for the production analysis benchmark tool."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from frame_compare.analysis.sampling import plan_performance_bursts
from frame_compare.analysis.types import (
    FrameMetrics,
    FrameSelection,
    MetricFrameRange,
    MetricsMetadata,
    SelectionBreakdown,
)
from frame_compare.config.schema import AnalysisConfig, ConfigSchema
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection


def test_help_exposes_only_production_benchmark_options() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "benchmark_analysis_tiers.py"), "--help"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0
    assert "--window-end-exclusive" in result.stdout
    assert "--metric-cache-policy" in result.stdout
    assert "--inspect-frame-types" in result.stdout
    assert "--mode" not in result.stdout
    assert "candidate" not in result.stdout.lower()


@pytest.mark.parametrize(
    ("args", "message"),
    [
        pytest.param(
            ["--output", "out.json", "--window-end-exclusive", "0", "a.mkv"],
            "--window-end-exclusive must be greater than --window-start",
            id="empty-default-window",
        ),
        pytest.param(
            [
                "--output",
                "out.json",
                "--window-start",
                "3",
                "--window-end-exclusive",
                "3",
                "a.mkv",
            ],
            "--window-end-exclusive must be greater than --window-start",
            id="empty-offset-window",
        ),
        pytest.param(
            [
                "--output",
                "out.json",
                "--window-end-exclusive",
                "10",
                "--repetitions",
                "0",
                "a.mkv",
            ],
            "--repetitions must be positive",
            id="zero-repetitions",
        ),
    ],
)
def test_invalid_benchmark_arguments_fail_closed(args: list[str], message: str) -> None:
    root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, str(root / "tools" / "benchmark_analysis_tiers.py"), *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert message in result.stderr


def test_trial_order_rotates_without_candidate_modes() -> None:
    script = _load_script()

    assert script._rotated_trial_order(0) == ("quality", "performance")
    assert script._rotated_trial_order(1) == ("performance", "quality")
    assert script._rotated_trial_order(2) == ("quality", "performance")


def test_performance_contract_requires_exact_production_source_map() -> None:
    script = _load_script()
    frame_range = MetricFrameRange(100, 10, 50)
    source_frames = tuple(
        frame
        for burst in plan_performance_bursts(window_start=10, window_end_exclusive=50)
        for frame in range(burst.start, burst.end_exclusive)
    )
    metrics = _metrics(
        mode="performance",
        start=10,
        end=50,
        source_frame_count=100,
        sampled=source_frames,
    )

    script._require_metric_contract(metrics, mode="performance", expected_range=frame_range)

    with pytest.raises(RuntimeError, match="source-frame map"):
        script._require_metric_contract(
            _metrics(
                mode="performance",
                start=10,
                end=50,
                source_frame_count=100,
                sampled=tuple(frame + 1 for frame in source_frames),
            ),
            mode="performance",
            expected_range=frame_range,
        )


@pytest.mark.parametrize(
    ("policy", "cache_state", "cache_write_state", "message"),
    [
        pytest.param("cold", "hit", "not_attempted", "Cold", id="cold-hit"),
        pytest.param("cold", "miss", "failed", "Cold", id="cold-write-failed"),
        pytest.param("reuse", "miss", "written", "Reuse", id="reuse-miss"),
        pytest.param("reuse", "hit", "written", "Reuse", id="reuse-hit-and-write"),
    ],
)
def test_cache_policy_rejects_mislabeled_trials(
    policy: str,
    cache_state: str,
    cache_write_state: str,
    message: str,
) -> None:
    script = _load_script()

    with pytest.raises(RuntimeError, match=message):
        script._require_cache_policy(
            policy=policy,
            mode="quality",
            cache_state=cache_state,
            cache_write_state=cache_write_state,
        )


@pytest.mark.parametrize(
    ("policy", "cache_state", "cache_write_state"),
    [
        pytest.param("cold", "miss", "written", id="cold-miss-and-write"),
        pytest.param("reuse", "hit", "not_attempted", id="reuse-hit"),
    ],
)
def test_cache_policy_accepts_observed_trial_state(
    policy: str,
    cache_state: str,
    cache_write_state: str,
) -> None:
    script = _load_script()

    script._require_cache_policy(
        policy=policy,
        mode="quality",
        cache_state=cache_state,
        cache_write_state=cache_write_state,
    )


def test_sampling_json_records_exact_budget_and_bursts() -> None:
    script = _load_script()
    source_frames = tuple(
        frame
        for burst in plan_performance_bursts(window_start=20, window_end_exclusive=120)
        for frame in range(burst.start, burst.end_exclusive)
    )
    result = script._sampling_json(
        _metrics(
            mode="performance",
            start=20,
            end=120,
            source_frame_count=200,
            sampled=source_frames,
        )
    )

    assert result is not None
    assert result["sample_count"] == 25
    assert result["actual_fraction"] == 0.25
    assert len(result["bursts"]) == 8
    assert result["source_frames"] == list(source_frames)


def test_sampled_fidelity_compares_only_mapped_frames() -> None:
    script = _load_script()
    quality = _metrics(mode="quality", start=100, end=108, source_frame_count=200)
    performance = _metrics(
        mode="performance",
        start=100,
        end=108,
        source_frame_count=200,
        sampled=(101, 106),
        luminance=[10.1, 10.6],
        motion=[1.01, 1.06],
    )

    result = script._sampled_metric_fidelity(
        quality_metrics=quality,
        performance_metrics=performance,
    )

    assert result["scope"] == "performance-sampled-source-frames-only"
    assert result["sample_count"] == 2
    assert result["luminance"]["max_absolute_error"] == pytest.approx(0.0)
    assert result["motion"]["max_absolute_error"] == pytest.approx(0.0)


def test_compute_pipeline_excludes_cache_persistence_only() -> None:
    script = _load_script()

    assert script._compute_pipeline_seconds(
        10.0,
        {"cache_lookup": 1.0, "cache_write": 2.0, "source_load": 3.0},
    ) == pytest.approx(7.0)


def test_git_provenance_records_commit_and_dirty_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    outputs = iter(["abc123", " M file.py"])
    monkeypatch.setattr(script, "_git_output", lambda *_args: next(outputs))

    result = script._git_provenance(tmp_path)

    assert result == {
        "available": True,
        "commit": "abc123",
        "dirty": True,
        "status_porcelain": [" M file.py"],
    }


def test_frame_type_summary_records_distribution() -> None:
    script = _load_script()

    result = script._frame_type_summary(
        {
            "success": True,
            "payload": {
                "frames": [
                    {"key_frame": 1, "pict_type": "I"},
                    {"key_frame": 0, "pict_type": "B"},
                    {"key_frame": 1, "pict_type": "P"},
                ]
            },
        }
    )

    assert result["available"] is True
    assert result["type_counts"] == {"I": 1, "B": 1, "P": 1}
    assert result["keyframe_count"] == 2


def test_frame_type_probe_bounds_window_when_fps_is_known() -> None:
    script = _load_script()

    options, scope = script._frame_type_probe_options(
        window_start=240,
        window_end_exclusive=2640,
        source_fps=Fraction(24),
    )

    assert "-read_intervals" in options
    assert scope["kind"] == "benchmark-window"
    assert scope["start_frame"] == 240
    assert scope["end_frame_exclusive"] == 2640


def test_source_index_detection_finds_adjacent_lwi(tmp_path: Path) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"video")
    Path(f"{video}.lwi").write_bytes(b"index")

    result = script._source_index_facts([video])[video.as_posix()]

    assert result["detected"] is True
    assert result["sizes_bytes"] == [5]


def test_nondefault_domain_requires_explicit_selection_token(tmp_path: Path) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    source = script.BenchmarkAnalysisSource(
        path=video,
        ordered_paths=(video,),
        effective_fps=Fraction(24),
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={},
    )

    with pytest.raises(SystemExit, match="selection-domain"):
        script._require_selection_domain_for_analysis_cache_identity(
            selection_domain=None,
            video_paths=(video,),
            analysis_source=source,
            active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
        )


def test_main_writes_atomic_production_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    output = tmp_path / "report.json"
    source = script.BenchmarkAnalysisSource(
        path=reference,
        ordered_paths=(reference,),
        effective_fps=None,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={},
        source_frame_count=20,
        source_fps=Fraction(24),
    )
    quality_metrics = _metrics(mode="quality", start=0, end=20, source_frame_count=20)
    sampled = tuple(
        frame
        for burst in plan_performance_bursts(window_start=0, window_end_exclusive=20)
        for frame in range(burst.start, burst.end_exclusive)
    )
    performance_metrics = _metrics(
        mode="performance",
        start=0,
        end=20,
        source_frame_count=20,
        sampled=sampled,
    )
    config = ConfigSchema().model_copy(
        update={
            "analysis": AnalysisConfig(
                random_frame_count=0,
                dark_frame_count=1,
                bright_frame_count=1,
                motion_frame_count=1,
                dark_quantile=0.2,
                bright_quantile=0.8,
            )
        }
    )
    quality_selection = _selection(dark=[0], bright=[19], motion=[18])
    performance_selection = _selection(dark=[1], bright=[11], motion=[11])
    monkeypatch.setattr(script, "load_config", lambda _path: config)
    monkeypatch.setattr(script, "_resolve_benchmark_analysis_source", lambda **_kwargs: source)
    monkeypatch.setattr(
        script, "_source_index_facts", lambda _paths: {reference.as_posix(): {"detected": True}}
    )
    monkeypatch.setattr(
        script,
        "_run_benchmark",
        lambda **_kwargs: (
            _aggregate(script, quality_metrics, quality_selection, "quality", 2.0),
            _aggregate(script, performance_metrics, performance_selection, "performance", 1.0),
        ),
    )
    monkeypatch.setattr(script, "_probe_source_facts", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(script, "_git_provenance", lambda _root: {"available": True})

    result = script.main(
        [
            "--root",
            str(tmp_path),
            "--config",
            str(config_path),
            "--output",
            str(output),
            "--window-end-exclusive",
            "20",
            "--skip-decode-baseline",
            str(reference),
        ]
    )

    assert result == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == 2
    assert set(report["comparisons"]) == {"performance"}
    comparison = report["comparisons"]["performance"]
    assert comparison["sampling"]["sample_count"] == 5
    assert comparison["comparisons"]["dark"]["overlap_count"] == 0
    assert comparison["exact_selected_equality"]["dark"] is False
    assert "quality_category_pool_retention" in comparison
    assert comparison["timing_comparison"]["speedup"] == pytest.approx(2.0)
    assert capsys.readouterr().out.strip() == output.as_posix()


def _load_script() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "benchmark_analysis_tiers.py"
    name = f"benchmark_analysis_tiers_test_{id(path)}_{len(sys.modules)}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _metrics(
    *,
    mode: str,
    start: int,
    end: int,
    source_frame_count: int,
    sampled: tuple[int, ...] | None = None,
    luminance: list[float] | None = None,
    motion: list[float] | None = None,
) -> FrameMetrics:
    frames = tuple(range(start, end)) if sampled is None else sampled
    values = [frame / 10 for frame in frames] if luminance is None else luminance
    motion_values = [frame / 100 for frame in frames] if motion is None else motion
    return FrameMetrics(
        luminance=values,
        motion=motion_values,
        metadata=MetricsMetadata(
            frame_count=len(frames),
            fps=Fraction(24),
            config_fingerprint="fp",
            clips=[],
            source_frame_count=source_frame_count,
            metric_source_start=start,
            metric_source_end_exclusive=end,
            performance_mode=mode,
            algorithm_id="algorithm",
            metric_backend="vapoursynth_planestats",
        ),
        sampled_source_frames=sampled,
    )


def _selection(
    *,
    dark: list[int] | None = None,
    bright: list[int] | None = None,
    motion: list[int] | None = None,
) -> FrameSelection:
    breakdown = SelectionBreakdown(
        quantile_dark=[] if dark is None else dark,
        quantile_bright=[] if bright is None else bright,
        motion=[] if motion is None else motion,
    )
    return FrameSelection(
        frames=sorted({*breakdown.quantile_dark, *breakdown.quantile_bright, *breakdown.motion}),
        seed=42,
        breakdown=breakdown,
    )


def _aggregate(
    script: ModuleType,
    metrics: FrameMetrics,
    selection: FrameSelection,
    mode: str,
    seconds: float,
) -> dict[str, Any]:
    trial: dict[str, Any] = {
        "mode": mode,
        "analyze_seconds": seconds,
        "compute_pipeline_seconds": seconds,
        "selection_seconds": 0.01,
        "trial_seconds": seconds,
        "process_cpu_seconds": seconds,
        "cpu_to_wall_ratio": 1.0,
        "peak_rss_bytes": None,
        "cache_state": "miss",
        "cache_write_state": "written",
        "phase_timings_seconds": {},
        "repetition": 0,
        "order_index": 0,
        "metrics": metrics,
        "selection": selection,
        "metadata": script._metrics_metadata_json(metrics),
        "sampling": script._sampling_json(metrics),
    }
    return cast(dict[str, Any], script._aggregate_tier_trials([trial]))
