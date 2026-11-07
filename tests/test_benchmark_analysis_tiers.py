"""Contract tests for the production analysis benchmark tool."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest

from frame_compare.analysis.sampling import plan_performance_bursts
from frame_compare.analysis.types import (
    CacheLoadResult,
    FrameMetrics,
    FrameSelection,
    MetricCacheRequest,
    MetricFrameRange,
    MetricsMetadata,
    SelectionBreakdown,
)
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import AnalysisConfig
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.context import (
    ClipActiveRect,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)


def test_help_exposes_only_production_benchmark_options() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "benchmark_analysis_tiers.py"), "--help"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert "--window-end-exclusive" in result.stdout
    assert "--metric-cache-policy" in result.stdout
    assert "--inspect-frame-types" in result.stdout
    assert "prepared analysis clip after" in result.stdout
    assert "source trims" in result.stdout
    assert "source-frame" in result.stdout
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


@pytest.mark.parametrize("collision", ["input", "config"])
def test_output_collision_is_rejected_before_preparation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, collision: str
) -> None:
    script = _load_script()
    input_path = tmp_path / "clip.mkv"
    config_path = tmp_path / "config.toml"
    input_path.write_bytes(b"video")
    config_path.write_bytes(b"config bytes")
    output = input_path if collision == "input" else config_path

    def unexpected_load(_path: Path) -> object:
        pytest.fail("output collision must be rejected before configuration loading")

    monkeypatch.setattr(script, "load_config", unexpected_load)

    def unexpected_preparation(**_kwargs: object) -> object:
        pytest.fail("output collision must be rejected before preparation")

    monkeypatch.setattr(script, "_resolve_benchmark_analysis_source", unexpected_preparation)

    with pytest.raises(SystemExit, match="must not resolve to an input or the selected config"):
        script.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(config_path),
                "--output",
                str(output),
                "--window-end-exclusive",
                "1",
                str(input_path),
            ]
        )

    assert input_path.read_bytes() == b"video"
    assert config_path.read_bytes() == b"config bytes"


def test_output_case_alias_collision_preserves_input_when_supported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    input_path = tmp_path / "Clip.mkv"
    case_alias = tmp_path / "clip.mkv"
    input_path.write_bytes(b"case-sensitive source")
    try:
        same_file = os.path.samefile(input_path, case_alias)
    except FileNotFoundError:
        pytest.skip("filesystem is case-sensitive")
    except OSError as exc:
        pytest.skip(f"filesystem cannot compare case aliases: {exc}")
    if not same_file:
        pytest.skip("filesystem is case-sensitive")

    config_path = tmp_path / "config.toml"
    config_path.write_bytes(b"config bytes")

    def unexpected_load(_path: Path) -> object:
        pytest.fail("case-alias collision must be rejected before configuration loading")

    monkeypatch.setattr(script, "load_config", unexpected_load)
    monkeypatch.setattr(
        script,
        "_resolve_benchmark_analysis_source",
        lambda **_kwargs: pytest.fail("case-alias collision must be rejected before preparation"),
    )

    with pytest.raises(SystemExit, match="must not resolve to an input or the selected config"):
        script.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(config_path),
                "--output",
                str(case_alias),
                "--window-end-exclusive",
                "1",
                str(input_path),
            ]
        )

    assert input_path.read_bytes() == b"case-sensitive source"


def test_run_tier_unwraps_the_production_metrics_acquisition(tmp_path: Path) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"fixture")
    frame_range = MetricFrameRange(source_frame_count=4, start=0, end_exclusive=4)
    metrics = _metrics(mode="quality", start=0, end=4, source_frame_count=4)
    active_rect = script.BenchmarkActiveRect(
        rect=None,
        source="full-frame",
        detection_mode="aspect_ratio",
    )

    with patch(
        "frame_compare.analysis.metrics.load_cached_metrics_for_request",
        return_value=CacheLoadResult(success=True, metrics=metrics),
    ):
        result = script._run_tier(
            mode="quality",
            video_paths=[video],
            analysis_config=AnalysisConfig(random_frame_count=1),
            cache_dir=tmp_path / "cache",
            analysis_source_path=video,
            effective_fps=Fraction(24),
            reference_fps=Fraction(25),
            active_rect=active_rect,
            selection_domain=None,
            metric_frame_range=frame_range,
            metric_cache_policy="reuse",
            repetition=0,
            order_index=0,
        )

    assert result["metrics"] is metrics
    assert isinstance(result["metrics"], FrameMetrics)
    assert isinstance(result["selection"], FrameSelection)
    assert result["cache_state"] == "hit"
    assert result["cache_write_state"] == "not_attempted"
    assert "cache_lookup" in result["phase_timings_seconds"]


def test_run_tier_uses_prepared_reference_fps_for_selection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"fixture")
    frame_range = MetricFrameRange(source_frame_count=40, start=7, end_exclusive=27)
    metrics = _metrics(mode="quality", start=7, end=27, source_frame_count=40)
    active_rect = script.BenchmarkActiveRect(
        rect=None,
        source="full-frame",
        detection_mode="aspect_ratio",
    )
    captured: dict[str, object] = {}

    def calculate(request: object, **kwargs: object) -> object:
        captured["request"] = request
        recorder = cast(Any, kwargs["timing_recorder"])
        recorder.cache_write_state = "written"
        return SimpleNamespace(metrics=metrics)

    monkeypatch.setattr(script, "calculate_metrics", calculate)
    monkeypatch.setattr(script, "_delete_tier_metrics_cache", lambda *_args, **_kwargs: None)

    def select(_metrics: object, _config: object, *, selection_fps: Fraction) -> FrameSelection:
        captured["selection_fps"] = selection_fps
        return _selection(dark=[0])

    monkeypatch.setattr(script, "select_frames", select)

    result = script._run_tier(
        mode="quality",
        video_paths=[video],
        analysis_config=AnalysisConfig(random_frame_count=1),
        cache_dir=tmp_path / "cache",
        analysis_source_path=video,
        effective_fps=Fraction(25),
        reference_fps=Fraction(25),
        active_rect=active_rect,
        selection_domain=None,
        metric_frame_range=frame_range,
        metric_cache_policy="cold",
        repetition=0,
        order_index=0,
    )

    request = captured["request"]
    assert isinstance(request, MetricCacheRequest)
    assert request.effective_fps == Fraction(25)
    assert request.metric_frame_range == frame_range
    assert captured["selection_fps"] == Fraction(25)
    assert cast(FrameSelection, result["selection"]).frames == [7]


def test_resolved_benchmark_source_preserves_prepared_fps_and_trim_facts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"video")
    snapshot = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path=video, size_bytes=5, mtime_ns=1),
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24001, 1000),
        is_hdr=False,
    )
    prepared = ClipState(
        path=video,
        label="clip",
        probe=snapshot,
        source_fps=Fraction(24),
        effective_fps=Fraction(24),
        active_rect=ClipActiveRect(
            x=0,
            y=0,
            width=1920,
            height=1080,
            source="aspect-ratio-derived",
            detection_mode="aspect_ratio",
        ),
    ).with_trim(trim_start_frames=7, trim_end_frame_inclusive=92)
    monkeypatch.setattr(script, "_prepared_benchmark_clips", lambda **_kwargs: [prepared])

    resolved = script._resolve_benchmark_analysis_source(
        root=tmp_path,
        input_dir=tmp_path,
        input_paths=(video,),
        config=get_default_config(),
    )

    assert resolved.effective_fps == Fraction(24)
    assert resolved.reference_fps == Fraction(24)
    assert resolved.trim_start_frames == 7
    assert resolved.effective_frame_count == 86
    assert resolved.source_frame_count == 100


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
                    {
                        "key_frame": 1,
                        "pict_type": "I",
                        "best_effort_timestamp_time": "0.000",
                    },
                    {
                        "key_frame": 0,
                        "pict_type": "B",
                        "best_effort_timestamp_time": "0.042",
                    },
                    {
                        "key_frame": 1,
                        "pict_type": "P",
                        "best_effort_timestamp_time": "0.083",
                    },
                ]
            },
        }
    )

    assert result["available"] is True
    assert result["type_counts"] == {"I": 1, "B": 1, "P": 1}
    assert result["keyframe_count"] == 2
    assert result["observed_timestamps_seconds"] == [0.0, 0.042, 0.083]


def test_frame_type_probe_bounds_window_when_fps_is_known() -> None:
    script = _load_script()

    options, scope = script._frame_type_probe_options(
        window_start=240,
        window_end_exclusive=2640,
        source_fps=Fraction(24),
    )

    assert "-read_intervals" in options
    assert scope["kind"] == "approximate-benchmark-window"
    assert scope["approximate"] is True
    assert scope["start_frame"] == 240
    assert scope["end_frame_exclusive"] == 2640


@pytest.mark.parametrize("legacy_name", ["appended", "replaced"])
def test_main_rejects_legacy_indexes_for_warm_requirement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    legacy_name: str,
) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"video")
    legacy = Path(f"{video}.lwi") if legacy_name == "appended" else video.with_suffix(".lwi")
    legacy.write_bytes(b"legacy")
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    config = get_default_config()
    source = script.BenchmarkAnalysisSource(
        path=video,
        ordered_paths=(video,),
        effective_fps=Fraction(24),
        reference_fps=Fraction(24),
        effective_frame_count=20,
        trim_start_frames=0,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={},
        source_frame_count=20,
        source_fps=Fraction(24),
    )
    monkeypatch.setattr(script, "load_config", lambda _path: config)
    monkeypatch.setattr(script, "_resolve_benchmark_analysis_source", lambda **_kwargs: source)

    with pytest.raises(SystemExit, match="warm source index was required"):
        script.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(config_path),
                "--output",
                str(tmp_path / "report.json"),
                "--window-end-exclusive",
                "20",
                "--selection-domain",
                "test-selection-domain",
                "--require-warm-source-index",
                str(video),
            ]
        )


def test_main_rejects_unusable_owned_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"video")
    script.source_index_path(video).write_bytes(b"corrupt index")
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    source = script.BenchmarkAnalysisSource(
        path=video,
        ordered_paths=(video,),
        effective_fps=Fraction(24),
        reference_fps=Fraction(24),
        effective_frame_count=20,
        trim_start_frames=0,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={},
        source_frame_count=20,
        source_fps=Fraction(24),
    )

    def reject_index(_path: Path) -> None:
        raise script.SourceLoadError(video, "Warm source index validation failed")

    monkeypatch.setattr(script, "load_config", lambda _path: get_default_config())
    monkeypatch.setattr(script, "_resolve_benchmark_analysis_source", lambda **_kwargs: source)
    monkeypatch.setattr(script, "validate_source_index", reject_index)

    with pytest.raises(SystemExit, match="required warm source index is not ready"):
        script.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(config_path),
                "--output",
                str(tmp_path / "report.json"),
                "--window-end-exclusive",
                "20",
                "--selection-domain",
                "test-selection-domain",
                "--require-warm-source-index",
                str(video),
            ]
        )


def test_nondefault_domain_requires_explicit_selection_token(tmp_path: Path) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    source = script.BenchmarkAnalysisSource(
        path=video,
        ordered_paths=(video,),
        effective_fps=Fraction(24),
        reference_fps=Fraction(24),
        effective_frame_count=20,
        trim_start_frames=0,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={video: SourceOverrideConfig(effective_fps=Fraction(25))},
    )

    with pytest.raises(SystemExit, match="selection-domain"):
        script._require_selection_domain_for_analysis_cache_identity(
            selection_domain=None,
            video_paths=(video,),
            analysis_source=source,
            active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
        )


def test_default_prepared_domain_accepts_prepared_effective_fps(tmp_path: Path) -> None:
    script = _load_script()
    video = tmp_path / "clip.mkv"
    source = script.BenchmarkAnalysisSource(
        path=video,
        ordered_paths=(video,),
        effective_fps=Fraction(24),
        reference_fps=Fraction(24),
        effective_frame_count=20,
        trim_start_frames=0,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={},
    )

    script._require_selection_domain_for_analysis_cache_identity(
        selection_domain=None,
        video_paths=(video,),
        analysis_source=source,
        active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
    )


def test_main_writes_expected_production_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    expected_index = script.source_index_path(reference)
    expected_index.write_bytes(b"index")
    legacy_index = Path(f"{reference}.lwi")
    legacy_index.write_bytes(b"legacy")
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    output = tmp_path / "report.json"
    source = script.BenchmarkAnalysisSource(
        path=reference,
        ordered_paths=(reference,),
        effective_fps=Fraction(24),
        reference_fps=Fraction(24),
        effective_frame_count=86,
        trim_start_frames=7,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        overrides_by_path={},
        source_frame_count=100,
        source_fps=Fraction(24),
    )
    quality_metrics = _metrics(mode="quality", start=9, end=29, source_frame_count=100)
    sampled = tuple(
        frame
        for burst in plan_performance_bursts(window_start=9, window_end_exclusive=29)
        for frame in range(burst.start, burst.end_exclusive)
    )
    performance_metrics = _metrics(
        mode="performance",
        start=9,
        end=29,
        source_frame_count=100,
        sampled=sampled,
    )
    config = get_default_config().model_copy(
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
    quality_selection = _selection(dark=[9], bright=[28], motion=[27])
    performance_selection = _selection(dark=[10], bright=[20], motion=[20])
    captured: dict[str, object] = {}
    monkeypatch.setattr(script, "load_config", lambda _path: config)
    monkeypatch.setattr(script, "_resolve_benchmark_analysis_source", lambda **_kwargs: source)
    monkeypatch.setattr(script, "validate_source_index", lambda _path: None)

    def run_benchmark(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        captured.update(kwargs)
        return (
            _aggregate(script, quality_metrics, quality_selection, "quality", 2.0),
            _aggregate(script, performance_metrics, performance_selection, "performance", 1.0),
        )

    def probe_source_facts(*_args: object, **kwargs: object) -> dict[str, object]:
        captured["probe_window"] = kwargs
        return {}

    monkeypatch.setattr(script, "_run_benchmark", run_benchmark)
    monkeypatch.setattr(script, "_probe_source_facts", probe_source_facts)
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
            "22",
            "--window-start",
            "2",
            "--selection-domain",
            "test-selection-domain",
            "--require-warm-source-index",
            "--skip-decode-baseline",
            str(reference),
        ]
    )

    assert result == 0
    assert captured["reference_fps"] == Fraction(24)
    assert captured["metric_frame_range"] == MetricFrameRange(100, 9, 29)
    assert cast(dict[str, object], captured["probe_window"])["window_start"] == 9
    assert cast(dict[str, object], captured["probe_window"])["window_end_exclusive"] == 29
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == 2
    assert report["config"]["selection_window"] == {
        "start_frame": 9,
        "end_frame_exclusive": 29,
    }
    index_facts = report["source"]["indexes"][reference.as_posix()]
    assert index_facts == {
        "detected": True,
        "expected_path": expected_index.as_posix(),
        "legacy_paths_ignored": [legacy_index.as_posix()],
        "paths": [expected_index.as_posix()],
        "sizes_bytes": [5],
    }
    assert set(report["comparisons"]) == {"performance"}
    comparison = report["comparisons"]["performance"]
    assert comparison["selected"]["frames"] == [10, 20]
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
