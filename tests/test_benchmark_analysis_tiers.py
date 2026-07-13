"""Tests for the analysis-tier benchmark tool."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import ModuleType, SimpleNamespace
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


def test_benchmark_script_help_is_available_through_documented_process_entrypoint() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "tools" / "benchmark_analysis_tiers.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0
    for option in (
        "--repetitions",
        "--metric-cache-policy",
        "--require-warm-source-index",
        "--skip-decode-baseline",
        "--inspect-frame-types",
        "--ffprobe-timeout",
        "--sparse-burst-count",
    ):
        assert option in result.stdout
    assert "performance-skip-loop-filter-candidate" in result.stdout
    assert "performance-skip-loop-filter-max-threads-candidate" in result.stdout
    assert "performance-sparse-25pct-candidate" in result.stdout
    assert "performance-sparse-6_25pct-skip-loop-filter-candidate" in result.stdout
    assert result.stderr == ""


def test_benchmark_script_main_writes_json_and_honors_public_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    output_path = tmp_path / "benchmark.json"
    config = ConfigSchema()
    source = _benchmark_analysis_source(script, path=reference, reference=reference)
    observed_run_options: dict[str, object] = {}

    def fake_run_benchmark_tiers(**kwargs: object) -> tuple[dict[str, Any], dict[str, Any]]:
        observed_run_options.update(kwargs)
        trial = _tier_payload("quality", [0.1, 0.9], [0.0, 0.5], [0, 1])
        return script._aggregate_tier_trials([trial]), {}

    monkeypatch.setattr(script, "load_config", lambda _path: config)
    monkeypatch.setattr(script, "_resolve_benchmark_analysis_source", lambda **_kwargs: source)
    monkeypatch.setattr(
        script,
        "_require_selection_domain_for_analysis_cache_identity",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        script,
        "_source_index_facts",
        lambda _paths: {reference.as_posix(): {"detected": False}},
    )
    monkeypatch.setattr(script, "_run_benchmark_tiers", fake_run_benchmark_tiers)
    monkeypatch.setattr(script, "_probe_source_facts", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(script, "_runtime_facts", lambda: {})

    exit_code = script.main(
        [
            "--root",
            str(tmp_path),
            "--config",
            config_path.name,
            "--output",
            output_path.name,
            "--no-progress",
            "--skip-decode-baseline",
            reference.name,
        ]
    )

    captured = capsys.readouterr()
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert captured.out == f"{output_path.as_posix()}\n"
    assert captured.err == ""
    assert report["inputs"] == [reference.as_posix()]
    assert report["config"]["repetitions"] == 3
    assert report["config"]["metric_cache_policy"] == "cold"
    assert report["config"]["requested_modes"] == ["performance"]
    assert report["decode_baseline"] is None
    assert report["quality_planestats_candidate_timing_comparisons"] == {}
    assert observed_run_options["candidate_modes"] == ["performance"]
    assert observed_run_options["repetitions"] == 3
    assert observed_run_options["metric_cache_policy"] == "cold"
    assert observed_run_options["progress_enabled"] is False


def test_benchmark_script_main_rejects_explicit_window_without_prepared_frame_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    source = _benchmark_analysis_source(script, path=reference, reference=reference)

    monkeypatch.setattr(script, "load_config", lambda _path: ConfigSchema())
    monkeypatch.setattr(script, "_resolve_benchmark_analysis_source", lambda **_kwargs: source)

    with pytest.raises(SystemExit, match="explicit benchmark window requires"):
        script.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                config_path.name,
                "--output",
                "benchmark.json",
                "--window-start",
                "10",
                "--window-end-exclusive",
                "20",
                reference.name,
            ]
        )


def test_benchmark_script_comparison_schema_contains_required_sections() -> None:
    script = _load_benchmark_script()
    quality = _tier_payload("quality", [0.0, 0.2, 1.0], [0.0, 0.1, 0.7], [0, 1, 2])
    candidate = _tier_payload("performance", [0.0, 0.1, 1.0], [0.0, 0.0, 0.8], [0, 2])

    result = cast(dict[str, Any], script._compare_tier(quality=quality, candidate=candidate))

    assert result["mode"] == "performance"
    assert set(result["comparisons"]) == {"dark", "bright", "motion"}
    assert set(result["quality_category_retention"]) == {"dark", "bright", "motion"}
    assert set(result["ranking"]) == {
        "highest_luminance_top_k",
        "highest_motion_top_k",
        "lowest_luminance_top_k",
        "luminance_spearman",
        "motion_spearman",
    }
    assert result["selected"]["frames"] == [0, 2]


def test_benchmark_script_accepts_quality_planestats_candidate_mode_only_in_tool(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_benchmark_script()

    args = script._parse_args(
        [
            "--output",
            "candidate.json",
            "--mode",
            "quality-planestats-candidate",
            "reference.mkv",
        ]
    )

    assert args.modes == ["quality-planestats-candidate"]
    with pytest.raises(ValueError):
        AnalysisPerformanceMode("quality-planestats-candidate")
    with pytest.raises(SystemExit):
        script._parse_args(
            [
                "--output",
                "candidate.json",
                "--mode",
                "quality-planestats-candidate",
                "--metric-cache-policy",
                "reuse",
                "reference.mkv",
            ]
        )
    assert "requires --metric-cache-policy cold" in capsys.readouterr().err


def test_benchmark_script_programmatic_candidate_requires_cold_quality(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()

    with pytest.raises(ValueError, match="requires metric_cache_policy='cold'"):
        script._run_benchmark_tiers(
            candidate_modes=["quality-planestats-candidate"],
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
            metric_cache_policy="reuse",
        )


@pytest.mark.parametrize(
    "mode",
    [
        "performance-skip-loop-filter-candidate",
        "performance-skip-loop-filter-max-threads-candidate",
    ],
)
def test_benchmark_script_accepts_decoder_candidates_only_in_tool(
    mode: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_benchmark_script()

    args = script._parse_args(["--output", "candidate.json", "--mode", mode, "reference.mkv"])

    assert args.modes == [mode]
    with pytest.raises(ValueError):
        AnalysisPerformanceMode(mode)
    with pytest.raises(SystemExit):
        script._parse_args(
            [
                "--output",
                "candidate.json",
                "--mode",
                mode,
                "--metric-cache-policy",
                "reuse",
                "reference.mkv",
            ]
        )
    assert "requires --metric-cache-policy cold" in capsys.readouterr().err


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
        metric_frame_range: object,
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
        assert metric_frame_range is None
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


def test_benchmark_script_candidate_trial_bypasses_cache_and_uses_explicit_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    clip = SimpleNamespace(num_frames=3)
    source = SimpleNamespace(clip=clip, fps=Fraction(24, 1))
    loader = SimpleNamespace(load=lambda path: source)
    observed: dict[str, object] = {}

    def fake_candidate(
        loaded_clip: object,
        reporter: object = None,
        metric_active_rect: MetricActiveRect | None = None,
        *,
        timing_recorder: object = None,
    ) -> tuple[list[float], list[float]]:
        observed.update(
            {
                "clip": loaded_clip,
                "reporter": reporter,
                "active_rect": metric_active_rect,
                "timing_recorder": timing_recorder,
            }
        )
        return [0.1, 0.5, 0.9], [0.0, 0.4, 0.4]

    monkeypatch.setattr(script, "DefaultVSLoader", lambda: loader)
    monkeypatch.setattr(script, "calculate_quality_planestats_metrics", fake_candidate)
    monkeypatch.setattr(
        script,
        "_delete_tier_metrics_cache",
        lambda **_kwargs: pytest.fail("candidate cache must not be deleted or written"),
    )

    result = script._run_tier(
        mode="quality-planestats-candidate",
        video_paths=[reference],
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
        analysis_source_path=reference,
        effective_fps=Fraction(24000, 1001),
        active_rect=script.BenchmarkActiveRect(
            rect=MetricActiveRect(x=10, y=20, width=300, height=200),
            source="explicit",
            detection_mode="provided",
        ),
        selection_domain="prepared-domain",
        window_start=0,
        window_end_exclusive=None,
        metric_cache_policy="cold",
    )

    assert observed["clip"] is clip
    assert observed["active_rect"] == MetricActiveRect(x=10, y=20, width=300, height=200)
    assert observed["timing_recorder"] is not None
    assert result["cache_state"] == "bypassed"
    assert result["cache_write_state"] == "not-written"
    assert result["metadata"] == {
        "frame_count": 3,
        "source_frame_count": 3,
        "performance_mode": "quality-planestats-candidate",
        "algorithm_id": "quality_fullres_planestats_candidate_v1",
        "metric_backend": "vapoursynth-planestats-fullres",
        "algorithm_identity": {
            "algorithm_id": "quality_fullres_planestats_candidate_v1",
            "backend": "vapoursynth-planestats-fullres",
            "benchmark_only": True,
            "luminance": "full_resolution_luma_planestats_average",
            "motion": "full_resolution_luma_planestats_diff_all_adjacent_pairs",
        },
    }
    metrics = cast(FrameMetrics, result["metrics"])
    assert metrics.metadata.fps == Fraction(24000, 1001)
    assert metrics.metadata.config_fingerprint == "benchmark-only-non-cacheable"
    assert result["compute_pipeline_seconds"] == result["analyze_seconds"]


@pytest.mark.parametrize(
    ("mode", "expected_threads", "expected_policy", "algorithm_id"),
    [
        (
            "performance-skip-loop-filter-candidate",
            None,
            "automatic",
            "performance_320_planestats_skip_loop_filter_candidate_v1",
        ),
        (
            "performance-skip-loop-filter-max-threads-candidate",
            12,
            "explicit_logical_cpu_count",
            "performance_320_planestats_skip_loop_filter_max_threads_candidate_v1",
        ),
    ],
)
def test_benchmark_script_decoder_candidates_bypass_cache_and_record_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
    expected_threads: int | None,
    expected_policy: str,
    algorithm_id: str,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    clip = SimpleNamespace(num_frames=3)
    source = SimpleNamespace(clip=clip, fps=Fraction(24, 1))
    observed: dict[str, object] = {}

    def fake_load_source(path: Path, *, decoder_options: object) -> object:
        observed["path"] = path
        observed["decoder_options"] = decoder_options
        return source

    def fake_metrics(
        loaded_clip: object,
        reporter: object = None,
        metric_active_rect: MetricActiveRect | None = None,
        *,
        timing_recorder: object = None,
    ) -> tuple[list[float], list[float]]:
        observed["clip"] = loaded_clip
        observed["active_rect"] = metric_active_rect
        observed["timing_recorder"] = timing_recorder
        return [0.1, 0.5, 0.9], [0.0, 0.4, 0.4]

    monkeypatch.setattr(script, "load_source", fake_load_source)
    monkeypatch.setattr(script, "calculate_performance_planestats_metrics", fake_metrics)
    monkeypatch.setattr(script.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(
        script,
        "_delete_tier_metrics_cache",
        lambda **_kwargs: pytest.fail("candidate cache must not be deleted or written"),
    )

    result = script._run_tier(
        mode=mode,
        video_paths=[reference],
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
        analysis_source_path=reference,
        effective_fps=None,
        active_rect=script.BenchmarkActiveRect(
            rect=MetricActiveRect(x=10, y=20, width=300, height=200),
            source="explicit",
            detection_mode="provided",
        ),
        selection_domain=None,
        window_start=0,
        window_end_exclusive=None,
        metric_cache_policy="cold",
    )

    decoder_options = cast(Any, observed["decoder_options"])
    assert decoder_options.ff_options == "skip_loop_filter=all"
    assert decoder_options.threads == expected_threads
    assert observed["clip"] is clip
    assert result["cache_state"] == "bypassed"
    assert result["cache_write_state"] == "not-written"
    assert result["metadata"]["performance_mode"] == mode
    assert result["metadata"]["algorithm_id"] == algorithm_id
    assert result["metadata"]["metric_backend"] == (
        "vapoursynth-planestats-320-lwlibavsource-skip-loop-filter"
    )
    assert result["metadata"]["algorithm_identity"]["decoder"] == {
        "ff_options": "skip_loop_filter=all",
        "source": "LWLibavSource",
        "thread_policy": expected_policy,
        "threads": expected_threads,
    }


def test_benchmark_script_max_threads_candidate_fails_without_cpu_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    monkeypatch.setattr(script.os, "cpu_count", lambda: None)
    monkeypatch.setattr(
        script,
        "load_source",
        lambda *_args, **_kwargs: pytest.fail("source must not be loaded"),
    )

    with pytest.raises(SystemExit, match="positive logical CPU count"):
        script._calculate_performance_decoder_candidate_trial_metrics(
            mode="performance-skip-loop-filter-max-threads-candidate",
            video_paths=[reference],
            analysis_source_path=reference,
            effective_fps=None,
            active_rect=script.BenchmarkActiveRect(
                rect=None,
                source="full-frame",
                detection_mode="aspect_ratio",
            ),
            timing_recorder=script.AnalysisTimingRecorder(),
        )


@pytest.mark.parametrize(
    "mode",
    [
        "performance-sparse-25pct-candidate",
        "performance-sparse-25pct-skip-loop-filter-candidate",
        "performance-sparse-12_5pct-candidate",
        "performance-sparse-12_5pct-skip-loop-filter-candidate",
        "performance-sparse-6_25pct-candidate",
        "performance-sparse-6_25pct-skip-loop-filter-candidate",
    ],
)
def test_benchmark_script_sparse_candidates_require_decision_evidence_inputs(
    mode: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_benchmark_script()

    args = script._parse_args(
        [
            "--output",
            "candidate.json",
            "--mode",
            mode,
            "--window-start",
            "100",
            "--window-end-exclusive",
            "2500",
            "--inspect-frame-types",
            "reference.mkv",
        ]
    )

    assert args.modes == [mode]
    assert args.sparse_burst_count == 8
    with pytest.raises(ValueError):
        AnalysisPerformanceMode(mode)
    with pytest.raises(SystemExit):
        script._parse_args(["--output", "candidate.json", "--mode", mode, "reference.mkv"])
    assert "requires --window-end-exclusive" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        script._parse_args(
            [
                "--output",
                "candidate.json",
                "--mode",
                mode,
                "--window-end-exclusive",
                "2500",
                "reference.mkv",
            ]
        )
    assert "requires --inspect-frame-types" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("fraction", "expected_budget", "expected_sizes"),
    [
        (Fraction(1, 4), 600, [75] * 8),
        (Fraction(1, 8), 300, [38, 38, 38, 38, 37, 37, 37, 37]),
        (Fraction(1, 16), 150, [19, 19, 19, 19, 19, 19, 18, 18]),
    ],
)
def test_benchmark_script_sparse_burst_plan_has_exact_budget_and_lookbehind(
    fraction: Fraction,
    expected_budget: int,
    expected_sizes: list[int],
) -> None:
    script = _load_benchmark_script()

    bursts = script._plan_sparse_bursts(
        window_start=100,
        window_end_exclusive=2500,
        sampling_fraction=fraction,
        requested_burst_count=8,
    )

    assert sum(burst.frame_count for burst in bursts) == expected_budget
    assert [burst.frame_count for burst in bursts] == expected_sizes
    assert all(burst.decode_start == burst.start - 1 for burst in bursts)
    assert all(
        earlier.end_exclusive <= later.start
        for earlier, later in zip(bursts, bursts[1:], strict=False)
    )


@pytest.mark.parametrize(
    ("mode", "expected_ff_options"),
    [
        ("performance-sparse-25pct-candidate", None),
        (
            "performance-sparse-25pct-skip-loop-filter-candidate",
            "skip_loop_filter=all",
        ),
    ],
)
def test_benchmark_script_sparse_metrics_preserve_source_map_and_motion_lookbehind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
    expected_ff_options: str | None,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    observed_slices: list[tuple[int, int]] = []

    class FakeClip:
        def __init__(self, start: int, end: int, source_count: int = 40) -> None:
            self.start = start
            self.end = end
            self.num_frames = end - start
            self.source_count = source_count

        def __getitem__(self, key: slice) -> FakeClip:
            start = cast(int, key.start)
            end = cast(int, key.stop)
            observed_slices.append((start, end))
            return FakeClip(start, end, self.source_count)

    source = SimpleNamespace(clip=FakeClip(0, 40), fps=Fraction(24, 1))
    observed_decoder_options: list[object] = []

    def fake_metrics(
        clip: FakeClip,
        reporter: object = None,
        metric_active_rect: object = None,
        *,
        timing_recorder: object = None,
    ) -> tuple[list[float], list[float]]:
        del reporter, metric_active_rect, timing_recorder
        frames = list(range(clip.start, clip.end))
        return [frame / 100 for frame in frames], [frame / 1000 for frame in frames]

    monkeypatch.setattr(
        script,
        "DefaultVSLoader",
        lambda: SimpleNamespace(load=lambda _path: source),
    )
    monkeypatch.setattr(
        script,
        "load_source",
        lambda _path, *, decoder_options: (
            observed_decoder_options.append(decoder_options) or source
        ),
    )
    monkeypatch.setattr(script, "calculate_quality_planestats_metrics", fake_metrics)

    result = script._calculate_sparse_candidate_trial_metrics(
        mode=mode,
        analysis_source_path=reference,
        effective_fps=None,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        metric_frame_range=script.MetricFrameRange(
            source_frame_count=40,
            start=8,
            end_exclusive=32,
        ),
        burst_count=3,
        timing_recorder=script.AnalysisTimingRecorder(),
    )

    assert len(result.source_frames) == 6
    assert tuple(value / 100 for value in result.source_frames) == result.luminance
    assert tuple(value / 1000 for value in result.source_frames) == result.motion
    assert observed_slices == [(burst.decode_start, burst.end_exclusive) for burst in result.bursts]
    assert all(
        start == burst.start - 1
        for (start, _end), burst in zip(observed_slices, result.bursts, strict=True)
    )
    if expected_ff_options is None:
        assert observed_decoder_options == []
    else:
        assert len(observed_decoder_options) == 1
        assert cast(Any, observed_decoder_options[0]).ff_options == expected_ff_options


def test_benchmark_script_sparse_selector_uses_source_space_for_random_and_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_benchmark_script()

    class FakeDigest:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def digest(self) -> bytes:
            local_frame = int(self.payload.decode("ascii").split(":")[1])
            return bytes([0 if local_frame == 50 else 1])

    monkeypatch.setattr(
        script.hashlib,
        "blake2b",
        lambda payload, digest_size: FakeDigest(payload),
    )
    metrics = script.SparseMetricSet(
        luminance=(0.1, 0.2, 0.8, 0.9),
        motion=(0.0, 0.9, 0.8, 0.7),
        source_frames=(110, 111, 160, 161),
        source_frame_count=300,
        fps=Fraction(24, 1),
        window_start=100,
        window_end_exclusive=200,
        sampling_fraction=Fraction(1, 16),
        requested_burst_count=2,
        bursts=(
            script.SparseBurst(start=110, end_exclusive=112, decode_start=109),
            script.SparseBurst(start=160, end_exclusive=162, decode_start=159),
        ),
        mode="performance-sparse-6_25pct-candidate",
        algorithm_id="sparse-test",
        metric_backend="test",
        algorithm_identity_json="{}",
    )
    config = ConfigSchema.model_validate(
        {
            "analysis": {
                "dark_frame_count": 1,
                "bright_frame_count": 1,
                "motion_frame_count": 0,
                "random_frame_count": 1,
                "random_seed": 42,
            }
        }
    ).analysis

    selection = script._select_sparse_frames(metrics, config)

    assert selection.breakdown.quantile_dark == [110]
    assert selection.breakdown.quantile_bright == [161]
    assert selection.breakdown.random == [150]
    assert 150 not in metrics.source_frames
    assert all(abs(150 - frame) >= 5 for frame in [110, 161])


def test_benchmark_script_sparse_run_bounds_quality_reference_to_same_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    observed_ranges: dict[str, object] = {}

    def fake_run_tier(**kwargs: object) -> dict[str, Any]:
        mode = cast(str, kwargs["mode"])
        observed_ranges[mode] = kwargs["metric_frame_range"]
        return _tier_payload(mode, [0.1, 0.9], [0.0, 0.5], [10, 59])

    monkeypatch.setattr(script, "_run_tier", fake_run_tier)
    monkeypatch.setattr(
        script,
        "_compare_tier",
        lambda **_kwargs: {"bounded": True},
    )

    script._run_benchmark_tiers(
        candidate_modes=["performance-sparse-25pct-candidate"],
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
        window_start=10,
        window_end_exclusive=60,
        source_frame_count=100,
        progress_enabled=False,
        metric_cache_policy="cold",
    )

    for metric_range in observed_ranges.values():
        assert metric_range == script.MetricFrameRange(
            source_frame_count=100,
            start=10,
            end_exclusive=60,
        )


def test_benchmark_script_explicit_window_requires_source_frame_count(tmp_path: Path) -> None:
    script = _load_benchmark_script()

    with pytest.raises(ValueError, match="requires a source frame count"):
        script._run_benchmark_tiers(
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
            window_start=10,
            window_end_exclusive=60,
            source_frame_count=None,
            progress_enabled=False,
            metric_cache_policy="cold",
        )


def test_benchmark_script_rejects_nonzero_start_without_explicit_end(tmp_path: Path) -> None:
    script = _load_benchmark_script()

    with pytest.raises(ValueError, match="nonzero benchmark window start"):
        script._run_benchmark_tiers(
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
            window_start=10,
            window_end_exclusive=None,
            source_frame_count=100,
            progress_enabled=False,
            metric_cache_policy="cold",
        )

    with pytest.raises(SystemExit):
        script._parse_args(
            [
                "--output",
                "benchmark.json",
                "--window-start",
                "10",
                "reference.mkv",
            ]
        )


def test_benchmark_script_sparse_comparison_reports_decision_metrics() -> None:
    script = _load_benchmark_script()
    quality = _tier_payload(
        "quality",
        [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        [0.0, 0.8, 0.1, 0.7, 0.2, 0.6, 0.3, 0.5],
        [100, 101, 107],
    )
    quality["window"] = {"start_frame": 100, "end_frame_exclusive": 108}
    quality["timing_summary"] = {"compute_pipeline_seconds": {"median": 8.0, "pstdev": 0.2}}
    quality["trials"] = [{"repetition": 0, "compute_pipeline_seconds": 8.0}]
    sparse = script.SparseMetricSet(
        luminance=(0.2, 0.3, 0.6, 0.7),
        motion=(0.8, 0.1, 0.6, 0.3),
        source_frames=(101, 102, 105, 106),
        source_frame_count=200,
        fps=Fraction(24, 1),
        window_start=100,
        window_end_exclusive=108,
        sampling_fraction=Fraction(1, 2),
        requested_burst_count=2,
        bursts=(
            script.SparseBurst(start=101, end_exclusive=103, decode_start=100),
            script.SparseBurst(start=105, end_exclusive=107, decode_start=104),
        ),
        mode="performance-sparse-25pct-candidate",
        algorithm_id="sparse-test",
        metric_backend="test",
        algorithm_identity_json="{}",
    )
    candidate = _tier_payload(
        "performance-sparse-25pct-candidate",
        [],
        [],
        [101, 105, 106],
    )
    candidate["window"] = {"start_frame": 100, "end_frame_exclusive": 108}
    candidate["sparse_metrics"] = sparse
    candidate["sampling"] = script._sparse_sampling_json(sparse)
    candidate["timing_summary"] = {"compute_pipeline_seconds": {"median": 2.0, "pstdev": 0.1}}
    candidate["trials"] = [{"repetition": 0, "compute_pipeline_seconds": 2.0}]

    result = script._compare_tier(quality=quality, candidate=candidate)

    assert result["timing_comparison"]["speedup"] == 4.0
    assert result["sampling"]["source_frames"] == [101, 102, 105, 106]
    assert result["sampled_metric_fidelity"]["luminance"]["allclose"] is True
    assert result["sampled_metric_fidelity"]["motion"]["allclose"] is True
    assert result["sampled_ranking"]["dark_luminance"]["spearman"] == pytest.approx(1.0)
    assert result["sampled_ranking"]["dark_luminance"]["direction"] == "lowest"
    assert result["sampled_ranking"]["bright_luminance"]["direction"] == "highest"
    assert set(result["quality_extreme_coverage"]) == {"dark", "bright", "motion"}
    assert set(result["comparisons"]) == {"dark", "bright", "motion"}


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
                "compute_pipeline_seconds": elapsed - 0.25,
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


def test_benchmark_script_compares_decoder_timing_to_planestats_quality_candidate() -> None:
    script = _load_benchmark_script()
    reference = {
        "timing_summary": {"compute_pipeline_seconds": {"median": 10.0, "pstdev": 0.5}},
        "trials": [
            {"repetition": 0, "compute_pipeline_seconds": 10.0},
            {"repetition": 1, "compute_pipeline_seconds": 9.0},
            {"repetition": 2, "compute_pipeline_seconds": 8.0},
        ],
    }
    candidate = {
        "timing_summary": {"compute_pipeline_seconds": {"median": 4.0, "pstdev": 0.25}},
        "trials": [
            {"repetition": 0, "compute_pipeline_seconds": 4.0},
            {"repetition": 1, "compute_pipeline_seconds": 12.0},
            {"repetition": 2, "compute_pipeline_seconds": 3.0},
        ],
    }
    mode = "performance-skip-loop-filter-candidate"

    result = script._quality_planestats_candidate_timing_comparisons(
        {
            "quality-planestats-candidate": reference,
            mode: candidate,
        },
        requested_modes=["quality-planestats-candidate", mode],
    )

    comparison = result[mode]
    assert comparison["timing_field"] == "compute_pipeline_seconds"
    assert comparison["speedup"] == 2.5
    assert comparison["percent_time_reduction"] == 60.0
    assert comparison["reference_minus_candidate_median_seconds"] == 6.0
    assert comparison["reference_pstdev_seconds"] == 0.5
    assert comparison["candidate_pstdev_seconds"] == 0.25
    assert comparison["max_pstdev_noise_band_seconds"] == 0.5
    assert comparison["outside_noise_band"] is True
    assert comparison["paired_faster_count"] == 2
    assert comparison["paired_count"] == 3
    assert comparison["meets_1_5x_speedup"] is True
    assert comparison["meets_2x_speedup"] is True
    assert (
        script._quality_planestats_candidate_timing_comparisons(
            {mode: candidate},
            requested_modes=[mode],
        )
        == {}
    )


def test_benchmark_script_timing_matrix_includes_current_performance_and_rejects_slower() -> None:
    script = _load_benchmark_script()
    reference = {
        "timing_summary": {"compute_pipeline_seconds": {"median": 10.0, "pstdev": 0.2}},
        "trials": [{"repetition": 0, "compute_pipeline_seconds": 10.0}],
    }
    current_performance = {
        "timing_summary": {"compute_pipeline_seconds": {"median": 11.0, "pstdev": 0.1}},
        "trials": [{"repetition": 0, "compute_pipeline_seconds": 11.0}],
    }

    result = script._quality_planestats_candidate_timing_comparisons(
        {
            "quality-planestats-candidate": reference,
            "performance": current_performance,
        },
        requested_modes=["quality-planestats-candidate", "performance"],
    )

    comparison = result["performance"]
    assert comparison["reference_minus_candidate_median_seconds"] == -1.0
    assert comparison["outside_noise_band"] is False
    assert comparison["paired_faster_count"] == 0
    assert comparison["meets_1_5x_speedup"] is False


def test_benchmark_script_compute_pipeline_excludes_only_cache_persistence() -> None:
    script = _load_benchmark_script()

    result = script._compute_pipeline_seconds(
        analyze_seconds=10.0,
        phase_timings_seconds={
            "cache_lookup": 1.25,
            "source_load": 2.0,
            "frame_render": 5.0,
            "cache_write": 0.75,
        },
    )

    assert result == 8.0


def test_benchmark_script_reports_dense_equivalence_and_exact_top_k_ordering() -> None:
    script = _load_benchmark_script()
    quality = _tier_payload(
        "quality",
        [0.1, 0.2, 0.3, 0.4],
        [0.0, 0.7, 0.2, 0.5],
        [0, 1, 3],
    )
    candidate = _tier_payload(
        "quality-planestats-candidate",
        [0.1, 0.2 + 5e-13, 0.3, 0.4],
        [0.0, 0.7, 0.2, 0.5 + 2e-12],
        [0, 1, 3],
    )
    quality["window"] = {"start_frame": 100, "end_frame_exclusive": 104}
    candidate["window"] = {"start_frame": 100, "end_frame_exclusive": 104}

    result = cast(dict[str, Any], script._compare_tier(quality=quality, candidate=candidate))

    assert result["window"] == {"start_frame": 100, "end_frame_exclusive": 104}
    dense = result["dense_metric_differences"]
    assert dense["tolerance"] == {"rtol": 0.0, "atol": 1e-12}
    assert dense["luminance"]["allclose"] is True
    assert dense["luminance"]["first_differing_index"] == 1
    assert dense["luminance"]["first_differing_source_frame"] == 101
    assert dense["luminance"]["first_outside_tolerance_index"] is None
    assert dense["luminance"]["first_outside_tolerance_source_frame"] is None
    assert dense["luminance"]["max_absolute_error"] == pytest.approx(5e-13)
    assert dense["luminance"]["mean_absolute_error"] == pytest.approx(1.25e-13)
    assert dense["motion"]["allclose"] is False
    assert dense["motion"]["first_differing_index"] == 3
    assert dense["motion"]["first_differing_source_frame"] == 103
    assert dense["motion"]["first_outside_tolerance_index"] == 3
    assert dense["motion"]["first_outside_tolerance_source_frame"] == 103
    assert result["exact_selected_equality"] == {
        "dark": True,
        "bright": True,
        "motion": True,
    }
    assert result["exact_top_k_ordering"] == {
        "dark": {
            "quality_indices": [100, 101, 102, 103],
            "candidate_indices": [100, 101, 102, 103],
            "equal": True,
        },
        "bright": {
            "quality_indices": [103, 102, 101, 100],
            "candidate_indices": [103, 102, 101, 100],
            "equal": True,
        },
        "motion": {
            "quality_indices": [101, 103, 102, 100],
            "candidate_indices": [101, 103, 102, 100],
            "equal": True,
        },
    }


def test_benchmark_script_reports_quality_category_retention_with_ties_and_offset() -> None:
    script = _load_benchmark_script()
    luminance = [0.1, 0.1, 0.5, 0.8, 0.9, 0.9, 0.7, 0.6]
    motion = [0.0, 0.2, 0.9, 0.9, 0.1, 0.8, 0.4, 0.3]
    quality = _tier_payload("quality", luminance, motion, [100, 103])
    candidate = _tier_payload(
        "performance-skip-loop-filter-candidate",
        luminance,
        motion,
        [100, 102, 104, 105, 107],
    )
    candidate["selection"] = FrameSelection(
        frames=[100, 102, 104, 105, 107],
        seed=0,
        breakdown=SelectionBreakdown(
            quantile_dark=[100, 102],
            quantile_bright=[104, 105],
            motion=[102, 107],
        ),
    )
    quality["window"] = {"start_frame": 100, "end_frame_exclusive": 108}
    candidate["window"] = {"start_frame": 100, "end_frame_exclusive": 108}

    result = script._compare_tier(quality=quality, candidate=candidate)

    retention = result["quality_category_retention"]
    assert retention["dark"] == {
        "threshold": 0.1,
        "selected_source_frames": [100, 102],
        "passing_source_frames": [100],
        "passing_count": 1,
        "passing_fraction": 0.5,
        "total_count": 2,
        "required_fraction": 1.0,
    }
    assert retention["bright"]["threshold"] == 0.9
    assert retention["bright"]["passing_source_frames"] == [104, 105]
    assert retention["bright"]["passing_fraction"] == 1.0
    assert retention["motion"]["threshold"] == 0.9
    assert retention["motion"]["passing_source_frames"] == [102]
    assert retention["motion"]["passing_fraction"] == 0.5
    assert result["comparisons"]["dark"]["tolerance_frames"] == 2
    assert result["comparisons"]["motion"]["tolerance_frames"] == 3


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


def test_benchmark_script_frame_type_probe_is_bounded_to_selection_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source")
    calls: list[list[str]] = []

    def fake_ffprobe(
        options: list[str],
        *,
        path: Path,
        timeout_seconds: float,
    ) -> dict[str, object]:
        del path, timeout_seconds
        calls.append(options)
        if "-show_frames" in options:
            return {
                "success": True,
                "payload": {
                    "frames": [
                        {"key_frame": 1, "pict_type": "I"},
                        {"key_frame": 0, "pict_type": "P"},
                    ]
                },
            }
        return {"success": True, "payload": {"streams": []}}

    monkeypatch.setattr(script, "_run_ffprobe_json", fake_ffprobe)

    facts = script._probe_source_facts(
        source,
        inspect_frame_types=True,
        timeout_seconds=30.0,
        window_start=240,
        window_end_exclusive=2640,
        source_fps=Fraction(24000, 1001),
    )

    assert calls[1] == [
        "-select_streams",
        "v:0",
        "-read_intervals",
        "10.010000%+100.100000",
        "-show_frames",
        "-show_entries",
        "frame=key_frame,pict_type",
    ]
    assert facts["frame_type_inspection_scope"] == {
        "kind": "benchmark-window",
        "start_frame": 240,
        "end_frame_exclusive": 2640,
        "source_fps": "24000/1001",
        "read_interval": "10.010000%+100.100000",
    }
    assert facts["frame_types"] == {
        "available": True,
        "frame_count": 2,
        "type_counts": {"I": 1, "P": 1},
        "keyframe_count": 1,
        "keyframe_gap_frames": {"count": 0},
    }


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
    assert script._frame_type_summary(result) == {
        "available": False,
        "error": "ffprobe timed out after 2.5s",
    }


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
    assert source.path == analysis
    assert source.reference_path == reference
    assert source.effective_fps == Fraction(24000, 1001)
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


def test_benchmark_script_rejects_different_reference_and_analysis_trim_starts(
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    analysis = tmp_path / "analysis.mkv"
    source = _benchmark_analysis_source(
        script,
        path=analysis,
        reference=reference,
        overrides={
            reference: SourceOverrideConfig(trim_start_frames=12),
            analysis: SourceOverrideConfig(trim_start_frames=20),
        },
    )

    with pytest.raises(SystemExit, match="different trim_start_frames"):
        script._require_selection_coordinate_compatibility(source)


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


def test_benchmark_script_nvidia_candidate_is_benchmark_only_and_cold() -> None:
    script = _load_benchmark_script()

    args = script._parse_args(
        [
            "--output",
            "candidate.json",
            "--mode",
            "quality-nvidia-cuvid-candidate",
            "reference.mkv",
        ]
    )

    assert args.modes == ["quality-nvidia-cuvid-candidate"]
    with pytest.raises(ValueError):
        AnalysisPerformanceMode("quality-nvidia-cuvid-candidate")
    with pytest.raises(SystemExit):
        script._parse_args(
            [
                "--output",
                "candidate.json",
                "--mode",
                "quality-nvidia-cuvid-candidate",
                "--metric-cache-policy",
                "reuse",
                "reference.mkv",
            ]
        )


def test_benchmark_script_nvidia_preflight_reports_gpu_without_claiming_decoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_benchmark_script()
    monkeypatch.setattr(
        script.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="GeForce RTX 4080, 591.44\n",
            stderr="",
        ),
    )

    result = script._require_nvidia_preflight()

    assert result["gpus"] == [{"name": "GeForce RTX 4080", "driver_version": "591.44"}]
    assert result["effective_decoder_proven"] is False


def test_benchmark_script_nvidia_candidate_bounds_metrics_and_reports_unverified_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    reference = tmp_path / "reference.mkv"
    reference.write_bytes(b"source")
    observed_options: list[object] = []

    class FakeClip:
        def __init__(self, frames: list[int]) -> None:
            self.frames = frames
            self.num_frames = len(frames)

        def __getitem__(self, key: slice) -> FakeClip:
            return FakeClip(self.frames[key])

    source = SimpleNamespace(clip=FakeClip([0, 1, 2, 3]), fps=Fraction(24, 1))

    def fake_load_source(_path: Path, *, decoder_options: object) -> object:
        observed_options.append(decoder_options)
        return source

    def fake_metrics(
        clip: FakeClip, *_args: object, **_kwargs: object
    ) -> tuple[list[float], list[float]]:
        values = [frame / 10 for frame in clip.frames]
        return values, [0.0, *values[1:]]

    utilization = iter([0.0, 14.0])
    monkeypatch.setattr(script, "load_source", fake_load_source)
    monkeypatch.setattr(script, "calculate_quality_planestats_metrics", fake_metrics)
    monkeypatch.setattr(script, "_nvidia_decoder_utilization", lambda: next(utilization))

    metrics = script._calculate_nvidia_candidate_trial_metrics(
        video_paths=[reference],
        analysis_source_path=reference,
        effective_fps=None,
        active_rect=script.BenchmarkActiveRect(
            rect=None,
            source="full-frame",
            detection_mode="aspect_ratio",
        ),
        metric_frame_range=script.MetricFrameRange(4, 1, 3),
        timing_recorder=script.AnalysisTimingRecorder(),
    )

    assert cast(Any, observed_options[0]).prefer_hw == 1
    assert metrics.luminance == [0.1, 0.2]
    assert metrics.metadata.metric_source_start == 1
    assert metrics.metadata.metric_source_end_exclusive == 3
    evidence = script._nvidia_decoder_evidence(
        utilization_before=next(utilization),
        utilization_after=next(utilization),
    )
    assert evidence["effective_decoder_proven"] is False
    assert evidence["verification_status"] == "decoder_engine_activity_observed_unattributed"
    assert script._category_tolerance("quality-nvidia-cuvid-candidate", "motion") == 0


def test_benchmark_script_nvidia_telemetry_is_outside_all_timed_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    script = _load_benchmark_script()
    clock = 0.0

    def fake_utilization() -> float:
        nonlocal clock
        clock += 100.0
        return 5.0

    monkeypatch.setattr(script.time, "perf_counter", lambda: clock)
    monkeypatch.setattr(script, "_nvidia_decoder_utilization", fake_utilization)
    monkeypatch.setattr(
        script,
        "_calculate_nvidia_candidate_trial_metrics",
        lambda **_kwargs: _metrics_payload(
            "quality-nvidia-cuvid-candidate",
            [float(index) for index in range(20)],
            [0.0, *[float(index) for index in range(1, 20)]],
        ),
    )

    result = script._run_tier(
        mode="quality-nvidia-cuvid-candidate",
        video_paths=[tmp_path / "reference.mkv"],
        analysis_config=ConfigSchema.model_validate(
            {"analysis": {"random_frame_count": 1}}
        ).analysis,
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
        window_end_exclusive=20,
    )

    assert result["analyze_seconds"] == 0.0
    assert result["trial_seconds"] == 0.0
    assert result["decoder_evidence"]["decoder_utilization_percent_before"] == 5.0
    assert result["decoder_evidence"]["decoder_utilization_percent_after"] == 5.0


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
        "compute_pipeline_seconds": 0.1,
        "cache_state": "unknown",
        "cache_write_state": "not_attempted",
        "phase_timings_seconds": {},
        "selection_seconds": 0.0,
        "trial_seconds": 0.1,
        "process_cpu_seconds": 0.05,
        "cpu_to_wall_ratio": 0.5,
        "peak_rss_bytes": 1,
        "timing_summary": {
            "compute_pipeline_seconds": {
                "count": 1,
                "min": 0.1,
                "max": 0.1,
                "mean": 0.1,
                "median": 0.1,
                "pstdev": 0.0,
            }
        },
        "trials": [{"repetition": 0, "compute_pipeline_seconds": 0.1}],
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
