"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from frame_compare.analysis.errors import (
    ExclusionRecoverySelectionError,
    MetricsCalculationError,
    SelectionError,
)
from frame_compare.analysis.types import (
    CacheLoadResult,
    FrameMetrics,
    FrameSelection,
    MetricActiveRect,
    MetricCacheRequest,
    MetricsMetadata,
    SelectionBreakdown,
    SelectionDetail,
)
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.orchestration import phase_post_render, phase_selection
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.orchestration.execution_types import RunArtifacts
from frame_compare.orchestration.full_window_retry import (
    compute_selection_window_with_recovery,
    recover_from_exclusion_selection_failure,
)
from frame_compare.orchestration.types import (
    FullWindowRetryConfirmationDecision,
    FullWindowRetryConfirmationRequest,
    SlowpicsUploadConfirmationDecision,
    SlowpicsUploadConfirmationRequest,
)
from frame_compare.services.types import MetadataConfig, TmdbMetadata
from tests.orchestration.phase_task_helpers import (
    MINIMAL_CONFIG,
    _clip,
    _context,
    _create_config,
    _render_artifacts,
)

if TYPE_CHECKING:
    from frame_compare.utils.progress_protocol import ProgressReporter
    from frame_compare.vs.loader import VSLoader


class ConfirmationProgressSpy:
    def __init__(self, *, fail_at: str | None = None) -> None:
        self.events: list[str] = []
        self.fail_at = fail_at

    def suspend(self) -> None:
        self.events.append("suspend")
        if self.fail_at == "suspend":
            raise RuntimeError("suspend failed")

    def resume(self) -> None:
        self.events.append("resume")
        if self.fail_at == "resume":
            raise RuntimeError("resume failed")


def test_run_analyze_phase_records_cache_hit_and_selection_breakdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=2)
    input_videos = [ctx.reference.path]
    metrics = FrameMetrics(
        luminance=[0.1, 0.9],
        motion=[0.2, 0.8],
        metadata=MetricsMetadata(
            frame_count=2,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
        ),
    )
    breakdown = SelectionBreakdown(quantile_dark=[1], quantile_bright=[8], motion=[13])
    selection_details = {
        1: SelectionDetail(
            frame_index=1,
            label="Dark",
            source="analysis",
            timecode="00:00:00.042",
            score=0.1,
            clip_role="analyze",
            notes="quantile_dark",
        )
    }
    selection = FrameSelection(
        frames=[1, 8, 13],
        seed=ctx.config.analysis.random_seed,
        breakdown=breakdown,
        selection_details=selection_details,
    )
    calls: dict[str, Any] = {}

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=True, metrics=metrics)

    def _fake_calculate_metrics(**kwargs: object) -> FrameMetrics:
        calls["calculate"] = kwargs
        return metrics

    def _fake_select_frames(**kwargs: object) -> FrameSelection:
        calls["select"] = kwargs
        return selection

    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)
    selected_frames: list[int] = []

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
    )

    assert output.metrics_cache_hit is True
    assert output.selected_frames == [1, 8, 13]
    assert output.selection_breakdown == breakdown
    assert output.analysis_metrics == metrics
    assert output.selection_details_by_source_frame == selection_details
    assert selected_frames == []
    assert ctx.selection_breakdown is None
    assert ctx.selection_details_by_source_frame is None
    assert calls["calculate"]["video_paths"] == input_videos
    assert calls["calculate"]["cache_dir"] == ctx.workspace.cache_dir
    assert calls["select"] == {"metrics": metrics, "config": ctx.config.analysis}


def _metrics_for_range(*, start: int, end: int, source_frame_count: int = 100) -> FrameMetrics:
    frame_count = end - start
    return FrameMetrics(
        luminance=[index / max(1, frame_count) for index in range(frame_count)],
        motion=[float((index * 17) % max(1, frame_count)) for index in range(frame_count)],
        metadata=MetricsMetadata(
            frame_count=frame_count,
            fps=Fraction(24, 1),
            config_fingerprint=f"metrics-{start}-{end}",
            clips=[],
            source_frame_count=source_frame_count,
            metric_source_start=start,
            metric_source_end_exclusive=end,
        ),
    )


def test_run_analyze_phase_confirmed_full_window_retry_recomputes_cache_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    authored_config = ctx.config
    config_path = tmp_path / "config" / "config.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "random_seed = 7",
            "random_seed = 7\nignore_lead_seconds = 1.6666666667\n"
            "ignore_trail_seconds = 1.6666666667",
        ),
        encoding="utf-8",
    )
    authored_bytes = config_path.read_bytes()
    ctx.config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={
                    "user_frames": [10, 120],
                    "random_frame_count": 12,
                    "motion_frame_count": 12,
                    "ignore_lead_seconds": 40 / 24,
                    "ignore_trail_seconds": 40 / 24,
                    "min_window_seconds": 0.0,
                }
            )
        }
    )
    constrained_config = ctx.config
    ctx.selection_window = SelectionWindow(start_frame=40, end_frame_exclusive=60)
    ctx.preflight_warnings = [
        "active-rect auto detection skipped reference.mkv: constrained attempt",
        "probe warning",
    ]
    constrained_metrics = _metrics_for_range(start=40, end=60)
    full_metrics = _metrics_for_range(start=0, end=100)
    cache_keys: list[str] = []
    calculate_ranges: list[tuple[int, int]] = []
    confirmation_requests: list[FullWindowRetryConfirmationRequest] = []
    progress = ConfirmationProgressSpy()

    def _load_cache(*_args: object, **kwargs: Any) -> CacheLoadResult:
        cache_keys.append(str(_args[1]))
        if len(cache_keys) == 1:
            return CacheLoadResult(success=True, metrics=constrained_metrics)
        return CacheLoadResult(success=False, reason="not_found")

    def _calculate_metrics(**kwargs: Any) -> FrameMetrics:
        frame_range = kwargs["metric_frame_range"]
        calculate_ranges.append((frame_range.start, frame_range.end_exclusive))
        return constrained_metrics if frame_range.start == 40 else full_metrics

    def _confirm(
        request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        confirmation_requests.append(request)
        return "confirmed"

    ctx.confirm_full_window_retry = _confirm
    ctx.reporter = cast("ProgressReporter", progress)
    monkeypatch.setattr(phase_selection.cache_io, "load_cached_metrics_for_request", _load_cache)
    monkeypatch.setattr(phase_selection, "calculate_metrics", _calculate_metrics)

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=[ctx.reference.path],
        workspace=ctx.workspace,
    )

    assert len(confirmation_requests) == 1
    assert progress.events == ["suspend", "resume"]
    assert confirmation_requests[0].eligible_frame_count == 20
    assert ctx.config is not constrained_config
    assert ctx.config.analysis.ignore_lead_seconds == 0.0
    assert ctx.config.analysis.ignore_trail_seconds == 0.0
    assert ctx.selection_window == SelectionWindow(start_frame=0, end_frame_exclusive=100)
    assert cache_keys[0] != cache_keys[1]
    assert calculate_ranges == [(40, 60), (0, 100)]
    assert len(output.selected_frames) == 25
    assert output.selection_breakdown.user == [10]
    assert len(output.selection_breakdown.motion) == 12
    assert len(output.selection_breakdown.random) == 12
    assert {detail.label for detail in output.selection_details_by_source_frame.values()} == {
        "User",
        "Motion",
        "Random",
    }
    assert any("disabled for this run only" in warning for warning in output.warnings)
    assert any(warning.endswith(": 120") for warning in output.warnings)
    assert not any(warning.endswith(": 10") for warning in output.warnings)
    assert ctx.preflight_warnings == ["probe warning"]
    assert output.replaces_frame_plan_selection is True
    assert authored_config.analysis.ignore_lead_seconds == 0.0
    assert config_path.read_bytes() == authored_bytes


@pytest.mark.parametrize("margin_seconds", [0.0, 40 / 24])
def test_run_analyze_phase_satisfied_selection_never_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    margin_seconds: float,
) -> None:
    ctx = _context(tmp_path)
    ctx.config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={
                    "random_frame_count": 1,
                    "motion_frame_count": 0,
                    "ignore_lead_seconds": margin_seconds,
                    "ignore_trail_seconds": margin_seconds,
                    "min_window_seconds": 0.0,
                }
            )
        }
    )
    ctx.selection_window = SelectionWindow(start_frame=40, end_frame_exclusive=60)
    ctx.confirm_full_window_retry = lambda _request: (_ for _ in ()).throw(
        AssertionError("valid selection must not prompt")
    )
    monkeypatch.setattr(
        phase_selection.cache_io,
        "load_cached_metrics_for_request",
        lambda *_args, **_kwargs: CacheLoadResult(success=False, reason="not_found"),
    )
    monkeypatch.setattr(
        phase_selection,
        "calculate_metrics",
        lambda **_kwargs: _metrics_for_range(start=40, end=60),
    )

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=[ctx.reference.path],
        workspace=ctx.workspace,
    )

    assert len(output.selected_frames) == 1
    assert ctx.full_window_retry_override is None


@pytest.mark.parametrize(
    "decision",
    [
        "declined",
        pytest.param(EOFError("stdin closed"), id="eof"),
        pytest.param(KeyboardInterrupt(), id="interrupt"),
        pytest.param(RuntimeError("prompt failed"), id="prompt-failure"),
    ],
)
def test_run_analyze_phase_refused_or_failed_prompt_is_fatal_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    decision: str | BaseException,
) -> None:
    ctx = _context(tmp_path)
    config_path = tmp_path / "config" / "config.toml"
    authored_bytes = config_path.read_bytes()
    ctx.config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={
                    "random_frame_count": 12,
                    "motion_frame_count": 12,
                    "ignore_lead_seconds": 40 / 24,
                    "ignore_trail_seconds": 40 / 24,
                    "min_window_seconds": 0.0,
                }
            )
        }
    )
    ctx.selection_window = SelectionWindow(start_frame=40, end_frame_exclusive=60)
    calls = 0
    prompt_calls = 0
    progress = ConfirmationProgressSpy()

    def _load_cache(*_args: object, **_kwargs: object) -> CacheLoadResult:
        nonlocal calls
        calls += 1
        return CacheLoadResult(success=True, metrics=_metrics_for_range(start=40, end=60))

    def _confirm(
        _request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        nonlocal prompt_calls
        prompt_calls += 1
        if isinstance(decision, BaseException):
            raise decision
        return "declined"

    ctx.confirm_full_window_retry = _confirm
    ctx.reporter = cast("ProgressReporter", progress)
    monkeypatch.setattr(phase_selection.cache_io, "load_cached_metrics_for_request", _load_cache)
    monkeypatch.setattr(
        phase_selection,
        "calculate_metrics",
        lambda **_kwargs: _metrics_for_range(start=40, end=60),
    )

    with pytest.raises(ExclusionRecoverySelectionError) as exc_info:
        phase_selection.run_analyze_phase(
            ctx,
            input_videos=[ctx.reference.path],
            workspace=ctx.workspace,
        )

    assert prompt_calls == 1
    assert progress.events == ["suspend", "resume"]
    assert calls == 1
    assert "clip-specific config" in exc_info.value.hint
    assert config_path.read_bytes() == authored_bytes


def test_run_analyze_phase_full_window_retry_failure_does_not_prompt_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={
                    "random_frame_count": 0,
                    "motion_frame_count": 100,
                    "ignore_lead_seconds": 40 / 24,
                    "ignore_trail_seconds": 40 / 24,
                    "min_window_seconds": 0.0,
                }
            )
        }
    )
    ctx.selection_window = SelectionWindow(start_frame=40, end_frame_exclusive=60)
    ctx.run_warnings = []
    prompt_calls = 0
    dense_full_metrics = _metrics_for_range(start=0, end=100)
    sparse_full_metrics = FrameMetrics(
        luminance=dense_full_metrics.luminance[:99],
        motion=dense_full_metrics.motion[:99],
        metadata=replace(
            dense_full_metrics.metadata,
            frame_count=99,
            performance_mode="performance",
        ),
        sampled_source_frames=tuple(range(99)),
    )

    def _load_cache(*_args: object, **kwargs: Any) -> CacheLoadResult:
        frame_range = kwargs["request"].metric_frame_range
        return CacheLoadResult(
            success=True,
            metrics=(
                sparse_full_metrics
                if frame_range.start == 0
                else _metrics_for_range(start=frame_range.start, end=frame_range.end_exclusive)
            ),
        )

    def _confirm(
        _request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        nonlocal prompt_calls
        prompt_calls += 1
        return "confirmed"

    ctx.confirm_full_window_retry = _confirm
    monkeypatch.setattr(phase_selection.cache_io, "load_cached_metrics_for_request", _load_cache)
    monkeypatch.setattr(
        phase_selection,
        "calculate_metrics",
        lambda **kwargs: (
            sparse_full_metrics
            if kwargs["metric_frame_range"].start == 0
            else _metrics_for_range(
                start=kwargs["metric_frame_range"].start,
                end=kwargs["metric_frame_range"].end_exclusive,
            )
        ),
    )

    with pytest.raises(ExclusionRecoverySelectionError, match="full-window retry"):
        phase_selection.run_analyze_phase(
            ctx,
            input_videos=[ctx.reference.path],
            workspace=ctx.workspace,
        )

    assert prompt_calls == 1
    assert len(ctx.run_warnings) == 1
    assert "configured lead=1.66667s" in ctx.run_warnings[0]
    assert "effective lead=0s" in ctx.run_warnings[0]


@pytest.mark.parametrize(
    ("fail_at", "expected_prompt_calls", "expected_events"),
    [("suspend", 0, ["suspend"]), ("resume", 1, ["suspend", "resume"])],
)
def test_full_window_retry_progress_failure_is_fatal_before_override(
    tmp_path: Path,
    fail_at: str,
    expected_prompt_calls: int,
    expected_events: list[str],
) -> None:
    ctx = _context(tmp_path)
    ctx.config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={"ignore_lead_seconds": 1.0, "ignore_trail_seconds": 1.0}
            )
        }
    )
    progress = ConfirmationProgressSpy(fail_at=fail_at)
    prompt_calls = 0

    def _confirm(
        _request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        nonlocal prompt_calls
        prompt_calls += 1
        return "confirmed"

    ctx.confirm_full_window_retry = _confirm
    ctx.reporter = cast("ProgressReporter", progress)

    with pytest.raises(ExclusionRecoverySelectionError) as exc_info:
        recover_from_exclusion_selection_failure(
            ctx,
            SelectionError("insufficient_candidates", requested=8, found=4),
            vs_loader=None,
        )

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert prompt_calls == expected_prompt_calls
    assert progress.events == expected_events
    assert ctx.full_window_retry_override is None


def test_full_window_retry_active_rect_sampling_failure_is_fatal(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.reference = replace(
        ctx.reference,
        active_rect=ClipActiveRect(0, 10, 1920, 1060, "content-derived", "auto"),
    )
    ctx.analysis_clip = ctx.reference
    ctx.config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={"ignore_lead_seconds": 1.0, "ignore_trail_seconds": 1.0}
            ),
            "screenshots": ctx.config.screenshots.model_copy(
                update={"active_rect_detection": ScreenshotActiveRectDetection.AUTO}
            ),
        }
    )
    prompt_calls = 0

    def _confirm(
        _request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        nonlocal prompt_calls
        prompt_calls += 1
        return "confirmed"

    class FailingLoader:
        def load(self, _path: Path) -> object:
            raise RuntimeError("sample boom")

    ctx.confirm_full_window_retry = _confirm
    ctx.run_warnings = []

    with pytest.raises(ExclusionRecoverySelectionError) as exc_info:
        recover_from_exclusion_selection_failure(
            ctx,
            SelectionError("insufficient_candidates", requested=8, found=4),
            vs_loader=cast("VSLoader", FailingLoader()),
        )

    assert prompt_calls == 1
    assert isinstance(exc_info.value.__cause__, MetricsCalculationError)
    assert ctx.full_window_retry_override is None
    assert len(ctx.run_warnings) == 1
    assert "configured lead=1s, trail=1s" in ctx.run_warnings[0]


def test_run_analyze_phase_cache_only_exclusion_failure_does_not_offer_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={
                    "random_frame_count": 12,
                    "motion_frame_count": 12,
                    "ignore_lead_seconds": 40 / 24,
                    "ignore_trail_seconds": 40 / 24,
                    "min_window_seconds": 0.0,
                }
            )
        }
    )
    ctx.selection_window = SelectionWindow(start_frame=40, end_frame_exclusive=60)
    cache_calls = 0

    def _load_cache(*_args: object, **_kwargs: object) -> CacheLoadResult:
        nonlocal cache_calls
        cache_calls += 1
        return CacheLoadResult(success=True, metrics=_metrics_for_range(start=40, end=60))

    monkeypatch.setattr(phase_selection.cache_io, "load_cached_metrics_for_request", _load_cache)

    with pytest.raises(ExclusionRecoverySelectionError):
        phase_selection.run_analyze_phase(
            ctx,
            input_videos=[ctx.reference.path],
            workspace=ctx.workspace,
            require_cache_only=True,
        )

    assert ctx.confirm_full_window_retry is None
    assert cache_calls == 1


def test_empty_exclusion_window_uses_authoritative_window_recovery_once(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    short_clip = _clip(ctx.reference.path, label="Reference", num_frames=10)
    config = ctx.config.model_copy(
        update={
            "analysis": ctx.config.analysis.model_copy(
                update={
                    "ignore_lead_seconds": 1.0,
                    "ignore_trail_seconds": 1.0,
                    "min_window_seconds": 0.0,
                }
            )
        }
    )
    requests: list[FullWindowRetryConfirmationRequest] = []

    def _confirm(
        request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        requests.append(request)
        return "confirmed"

    state = compute_selection_window_with_recovery(
        clips=[short_clip],
        config=config,
        confirm=_confirm,
    )

    assert len(requests) == 1
    assert state.selection_window == SelectionWindow(start_frame=0, end_frame_exclusive=10)
    assert state.config is not config
    assert state.config.analysis.ignore_lead_seconds == 0.0
    assert state.config.analysis.ignore_trail_seconds == 0.0
    assert config.analysis.ignore_lead_seconds == 1.0
    assert state.override is not None


@pytest.mark.unit
def test_run_analyze_phase_uses_prepared_analysis_selection_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=2)
    ctx.analysis_selection_domain = "trim_start=0|trim_end=0|effective_fps=24/1"
    input_videos = [ctx.reference.path]
    metrics = FrameMetrics(
        luminance=[0.1, 0.9],
        motion=[0.2, 0.8],
        metadata=MetricsMetadata(
            frame_count=2,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
        ),
    )
    observed_selection_domains: list[str | None] = []

    def _fake_compute_cache_key(
        _video_paths: list[Path],
        _config: object,
        *,
        selection_domain: str | None = None,
        metric_request: MetricCacheRequest | None = None,
    ) -> str:
        del metric_request
        observed_selection_domains.append(selection_domain)
        return "fingerprint"

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=True, metrics=metrics)

    def _fake_calculate_metrics(**kwargs: object) -> FrameMetrics:
        observed_selection_domains.append(kwargs["selection_domain"])
        return metrics

    def _fake_select_frames(**_kwargs: object) -> FrameSelection:
        return FrameSelection(
            frames=[0],
            seed=ctx.config.analysis.random_seed,
            breakdown=SelectionBreakdown(quantile_dark=[0]),
        )

    monkeypatch.setattr(phase_selection.cache_io, "compute_cache_key", _fake_compute_cache_key)
    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)

    phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
    )

    assert observed_selection_domains == [
        "trim_start=0|trim_end=0|effective_fps=24/1",
        "trim_start=0|trim_end=0|effective_fps=24/1",
    ]


@pytest.mark.unit
def test_run_analyze_phase_forwards_analysis_clip_active_rect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=2)
    assert ctx.analysis_clip is not None
    ctx.analysis_clip = replace(
        ctx.analysis_clip,
        active_rect=ClipActiveRect(
            x=10,
            y=20,
            width=300,
            height=200,
            source="explicit",
            detection_mode="aspect_ratio",
        ),
    )
    input_videos = [ctx.reference.path]
    metrics = FrameMetrics(
        luminance=[0.1, 0.9],
        motion=[0.0, 0.8],
        metadata=MetricsMetadata(
            frame_count=2,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
        ),
    )
    observed_rects: list[MetricActiveRect | None] = []

    def _fake_compute_cache_key(
        _video_paths: list[Path],
        _config: object,
        *,
        selection_domain: str | None = None,
        metric_request: MetricCacheRequest | None = None,
    ) -> str:
        del selection_domain
        observed_rects.append(None if metric_request is None else metric_request.metric_active_rect)
        return "fingerprint"

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=False, reason="not_found")

    def _fake_calculate_metrics(**kwargs: object) -> FrameMetrics:
        observed_rects.append(kwargs["metric_active_rect"])
        return metrics

    def _fake_select_frames(**_kwargs: object) -> FrameSelection:
        return FrameSelection(
            frames=[0],
            seed=ctx.config.analysis.random_seed,
            breakdown=SelectionBreakdown(quantile_dark=[0]),
        )

    monkeypatch.setattr(phase_selection.cache_io, "compute_cache_key", _fake_compute_cache_key)
    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)

    phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
    )

    assert observed_rects == [
        MetricActiveRect(x=10, y=20, width=300, height=200),
        MetricActiveRect(x=10, y=20, width=300, height=200),
    ]


def test_run_analyze_phase_cache_only_missing_cache_does_not_recompute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=2)
    input_videos = [ctx.reference.path]

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=False, reason="not_found")

    def _fake_calculate_metrics(**_kwargs: object) -> FrameMetrics:
        raise AssertionError("cache-only analyze phase must not recompute metrics")

    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)

    with pytest.raises(MetricsCalculationError, match="Cached metrics missing"):
        phase_selection.run_analyze_phase(
            ctx,
            input_videos=input_videos,
            workspace=ctx.workspace,
            require_cache_only=True,
        )


def test_run_analyze_phase_metadata_mismatch_recomputes_and_reports_cache_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=2)
    input_videos = [ctx.reference.path]
    metrics = FrameMetrics(
        luminance=[0.1, 0.9],
        motion=[0.0, 0.8],
        metadata=MetricsMetadata(
            frame_count=2,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
        ),
    )
    calculate_calls = 0

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=False, reason="mismatched_inputs")

    def _fake_calculate_metrics(**_kwargs: object) -> FrameMetrics:
        nonlocal calculate_calls
        calculate_calls += 1
        return metrics

    def _fake_select_frames(**_kwargs: object) -> FrameSelection:
        return FrameSelection(
            frames=[0],
            seed=ctx.config.analysis.random_seed,
            breakdown=SelectionBreakdown(quantile_dark=[0]),
        )

    monkeypatch.setattr(
        phase_selection.cache_io,
        "load_cached_metrics_for_request",
        _fake_load_cached_metrics,
    )
    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
    )

    assert output.metrics_cache_hit is False
    assert calculate_calls == 1


def test_run_analyze_phase_cache_only_metadata_mismatch_does_not_recompute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context(tmp_path)

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=False, reason="mismatched_inputs")

    def _fake_calculate_metrics(**_kwargs: object) -> FrameMetrics:
        raise AssertionError("cache-only analyze phase must not recompute metrics")

    monkeypatch.setattr(
        phase_selection.cache_io,
        "load_cached_metrics_for_request",
        _fake_load_cached_metrics,
    )
    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)

    with pytest.raises(MetricsCalculationError, match="mismatched_inputs"):
        phase_selection.run_analyze_phase(
            ctx,
            input_videos=[ctx.reference.path],
            workspace=ctx.workspace,
            require_cache_only=True,
        )


@pytest.mark.unit
def test_run_analyze_phase_selects_from_reference_base_trim_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=14)
    ctx.analysis_clip = ctx.reference
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=5)
    input_videos = [ctx.reference.path]
    metrics = FrameMetrics(
        luminance=[float(frame) for frame in range(10, 15)],
        motion=[float(frame) / 10.0 for frame in range(10, 15)],
        metadata=MetricsMetadata(
            frame_count=5,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
            source_frame_count=100,
            metric_source_start=10,
            metric_source_end_exclusive=15,
        ),
    )
    calls: dict[str, Any] = {}

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=True, metrics=metrics)

    def _fake_select_frames(**kwargs: object) -> FrameSelection:
        calls["select"] = kwargs
        received_metrics = kwargs["metrics"]
        assert received_metrics.luminance == [10.0, 11.0, 12.0, 13.0, 14.0]
        return FrameSelection(
            frames=[0, 4],
            seed=ctx.config.analysis.random_seed,
            breakdown=SelectionBreakdown(quantile_dark=[0], quantile_bright=[4]),
            selection_details={
                0: SelectionDetail(
                    frame_index=0,
                    label="Dark",
                    source="analysis",
                    notes="quantile_dark",
                ),
                4: SelectionDetail(
                    frame_index=4,
                    label="Bright",
                    source="analysis",
                    notes="quantile_bright",
                ),
            },
        )

    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
        require_cache_only=True,
    )

    assert output.selected_frames == [0, 4]
    assert output.selection_breakdown == SelectionBreakdown(
        quantile_dark=[10],
        quantile_bright=[14],
    )
    assert output.selection_details_by_source_frame is not None
    assert set(output.selection_details_by_source_frame) == {10, 14}
    assert output.selection_details_by_source_frame[10].frame_index == 10
    assert calls["select"]["config"].random_frame_count == 3


@pytest.mark.unit
def test_run_analyze_phase_uses_analysis_clip_metrics_but_reference_frame_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    analysis_clip = ctx.reference.with_trim(trim_start_frames=20, trim_end_frame_inclusive=80)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=70)
    ctx.analysis_clip = analysis_clip
    ctx.selection_window = SelectionWindow(start_frame=5, end_frame_exclusive=15)
    input_videos = [ctx.reference.path, analysis_clip.path]
    metrics = FrameMetrics(
        luminance=[float(frame) for frame in range(25, 35)],
        motion=[float(frame) / 10.0 for frame in range(25, 35)],
        metadata=MetricsMetadata(
            frame_count=10,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
            source_frame_count=100,
            metric_source_start=25,
            metric_source_end_exclusive=35,
        ),
    )

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=True, metrics=metrics)

    def _fake_select_frames(**kwargs: object) -> FrameSelection:
        received_metrics = kwargs["metrics"]
        assert received_metrics.luminance == [float(frame) for frame in range(25, 35)]
        return FrameSelection(
            frames=[0],
            seed=ctx.config.analysis.random_seed,
            breakdown=SelectionBreakdown(quantile_dark=[0]),
            selection_details={
                0: SelectionDetail(
                    frame_index=0,
                    label="Dark",
                    source="analysis",
                    notes="quantile_dark",
                )
            },
        )

    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
        require_cache_only=True,
    )

    assert output.selected_frames == [5]
    assert output.selection_breakdown.quantile_dark == [15]
    assert set(output.selection_details_by_source_frame) == {15}


@pytest.mark.unit
def test_sparse_analysis_source_frames_normalize_into_reference_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(
        trim_start_frames=10,
        trim_end_frame_inclusive=70,
    )
    ctx.analysis_clip = ctx.reference.with_trim(
        trim_start_frames=20,
        trim_end_frame_inclusive=80,
    )
    ctx.selection_window = SelectionWindow(start_frame=5, end_frame_exclusive=15)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={
            "random_frame_count": 0,
            "dark_frame_count": 1,
            "bright_frame_count": 0,
            "motion_frame_count": 0,
        }
    )
    metrics = FrameMetrics(
        luminance=[0.1, 0.9],
        motion=[0.2, 0.8],
        metadata=MetricsMetadata(
            frame_count=2,
            fps=Fraction(24),
            config_fingerprint="fingerprint",
            clips=[],
            source_frame_count=100,
            metric_source_start=25,
            metric_source_end_exclusive=35,
            performance_mode="performance",
        ),
        sampled_source_frames=(25, 34),
    )

    monkeypatch.setattr(
        phase_selection.cache_io,
        "load_cached_metrics_for_request",
        lambda *_args, **_kwargs: CacheLoadResult(success=True, metrics=metrics),
    )

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=[ctx.reference.path],
        workspace=ctx.workspace,
        require_cache_only=True,
    )

    assert output.selected_frames == [5]
    assert output.selection_breakdown.quantile_dark == [15]
    assert set(output.selection_details_by_source_frame) == {15}


@pytest.mark.unit
def test_run_analyze_phase_offsets_labels_when_reference_trim_matches_untrimmed_analysis_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=14)
    ctx.analysis_clip = _clip(
        tmp_path / "comparison_videos" / "analysis.mkv",
        label="Analysis",
        num_frames=5,
    )
    ctx.analysis_clip.path.write_bytes(b"analysis")
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=5)
    input_videos = [ctx.reference.path, ctx.analysis_clip.path]
    metrics = FrameMetrics(
        luminance=[float(frame) for frame in range(5)],
        motion=[float(frame) / 10.0 for frame in range(5)],
        metadata=MetricsMetadata(
            frame_count=5,
            fps=Fraction(48, 1),
            config_fingerprint="fingerprint",
            clips=[],
        ),
    )

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=True, metrics=metrics)

    def _fake_select_frames(**kwargs: object) -> FrameSelection:
        received_metrics = kwargs["metrics"]
        assert received_metrics.luminance == [0.0, 1.0, 2.0, 3.0, 4.0]
        return FrameSelection(
            frames=[0, 4],
            seed=ctx.config.analysis.random_seed,
            breakdown=SelectionBreakdown(quantile_dark=[0], quantile_bright=[4]),
            selection_details={
                0: SelectionDetail(
                    frame_index=0,
                    label="Dark",
                    source="analysis",
                    notes="quantile_dark",
                ),
                4: SelectionDetail(
                    frame_index=4,
                    label="Bright",
                    source="analysis",
                    notes="quantile_bright",
                ),
            },
        )

    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
        require_cache_only=True,
    )

    assert output.selected_frames == [0, 4]
    assert output.selection_breakdown == SelectionBreakdown(
        quantile_dark=[10],
        quantile_bright=[14],
    )
    assert output.selection_details_by_source_frame is not None
    assert set(output.selection_details_by_source_frame) == {10, 14}
    assert output.selection_details_by_source_frame[10].frame_index == 10
    assert output.selection_details_by_source_frame[10].timecode == "00:00:00.417"
    assert output.selection_details_by_source_frame[14].timecode == "00:00:00.583"


@pytest.mark.unit
def test_run_analyze_phase_selects_from_global_selection_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=24, end_frame_exclusive=72)
    input_videos = [ctx.reference.path]
    metrics = FrameMetrics(
        luminance=[float(frame) for frame in range(24, 72)],
        motion=[float(frame) / 10.0 for frame in range(24, 72)],
        metadata=MetricsMetadata(
            frame_count=48,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
            source_frame_count=100,
            metric_source_start=24,
            metric_source_end_exclusive=72,
        ),
    )

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=True, metrics=metrics)

    def _fake_select_frames(**kwargs: object) -> FrameSelection:
        received_metrics = kwargs["metrics"]
        assert received_metrics.luminance[0] == 24.0
        assert len(received_metrics.luminance) == 48
        return FrameSelection(
            frames=[0, 47],
            seed=ctx.config.analysis.random_seed,
            breakdown=SelectionBreakdown(quantile_dark=[0], quantile_bright=[47]),
            selection_details={
                0: SelectionDetail(frame_index=0, label="Dark", source="analysis"),
                47: SelectionDetail(frame_index=47, label="Bright", source="analysis"),
            },
        )

    monkeypatch.setattr(
        phase_selection.cache_io, "load_cached_metrics_for_request", _fake_load_cached_metrics
    )
    monkeypatch.setattr(phase_selection, "select_frames", _fake_select_frames)

    output = phase_selection.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
        require_cache_only=True,
    )

    assert output.selected_frames == [24, 71]
    assert output.selection_breakdown == SelectionBreakdown(
        quantile_dark=[24],
        quantile_bright=[71],
    )
    assert set(output.selection_details_by_source_frame) == {24, 71}


def test_select_initial_frame_plan_uses_effective_selection_domain(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=19)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=10)
    selected_frames: list[int] = []

    output = phase_selection.select_initial_frame_plan(ctx)

    assert selected_frames == []
    assert len(output.selected_frames) == 3
    assert all(0 <= frame < 10 for frame in output.selected_frames)


def test_select_initial_frame_plan_uses_global_selection_window(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=24, end_frame_exclusive=48)

    output = phase_selection.select_initial_frame_plan(ctx)

    assert len(output.selected_frames) == 3
    assert all(24 <= frame < 48 for frame in output.selected_frames)


def test_select_initial_frame_plan_fails_when_user_random_candidates_are_empty(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=19)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=10)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [0], "random_frame_count": 0}
    )

    with pytest.raises(SelectionError, match="no selectable user or random frames"):
        phase_selection.select_initial_frame_plan(ctx)


def test_select_initial_frame_plan_warns_when_user_frames_are_dropped(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=19)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=10)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [0, 12], "random_frame_count": 1}
    )

    output = phase_selection.select_initial_frame_plan(ctx)

    assert 2 in output.selected_frames
    assert output.warnings == ["frame selection: dropped user frame(s) outside trims/windowing: 0"]


def test_select_initial_frame_plan_labels_user_and_random_frames(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [0], "random_frame_count": 1}
    )

    output = phase_selection.select_initial_frame_plan(ctx)

    assert output.selection_breakdown.user == [0]
    assert len(output.selection_breakdown.random) == 1
    assert output.selection_breakdown.random[0] != 0
    assert output.selection_details_by_source_frame[0].label == "User"
    random_frame = output.selection_breakdown.random[0]
    assert output.selection_details_by_source_frame[random_frame].label == "Random"


def test_select_initial_frame_plan_refills_random_after_user_collision(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [8], "random_frame_count": 10, "random_seed": 42}
    )

    output = phase_selection.select_initial_frame_plan(ctx)

    assert output.selection_breakdown.user == [8]
    assert len(output.selection_breakdown.random) == 10
    assert 8 not in output.selection_breakdown.random
    assert len(output.selected_frames) == 11


def test_select_initial_frame_plan_fails_when_random_request_exceeds_remaining_domain(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=2)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [0], "random_frame_count": 2}
    )

    with pytest.raises(SelectionError) as exc_info:
        phase_selection.select_initial_frame_plan(ctx)

    assert exc_info.value.context.details == {
        "reason": "insufficient random candidates after user frames",
        "requested": 2,
        "found": 1,
    }


def test_run_artifacts_uses_render_artifacts_carrier() -> None:
    artifacts = RunArtifacts()
    assert artifacts.render is None

    screenshot = Path("screenshots/reference_1.png")
    artifacts.render = _render_artifacts(
        screenshots_by_label={"Reference": [screenshot]},
        screenshot_dir=Path("screenshots"),
    )

    assert artifacts.render.screenshots_by_label == {"Reference": [screenshot]}
    assert artifacts.render.screenshot_dir == Path("screenshots")


def test_run_confirm_slowpics_upload_phase_marks_report_unavailable_without_prompt(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    callback_calls: list[SlowpicsUploadConfirmationRequest] = []

    def _callback(
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        callback_calls.append(request)
        return "confirmed"

    output = phase_post_render.run_confirm_slowpics_upload_phase(
        ctx,
        report_path=None,
        report_succeeded=False,
        confirm_slowpics_upload=_callback,
    )

    assert output.status == "report_unavailable"
    assert output.warnings == [
        "slow.pics upload skipped because report confirmation was unavailable"
    ]
    assert callback_calls == []


def test_run_confirm_slowpics_upload_phase_requires_callback_when_report_available(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ConfigValidationError, match="requires a confirmation callback"):
        phase_post_render.run_confirm_slowpics_upload_phase(
            ctx,
            report_path=tmp_path / "report.html",
            report_succeeded=True,
            confirm_slowpics_upload=None,
        )


def test_run_confirm_slowpics_upload_phase_records_callback_decision(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    report_path = tmp_path / "report.html"
    callback_calls: list[SlowpicsUploadConfirmationRequest] = []

    def _callback(
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        callback_calls.append(request)
        return "declined"

    output = phase_post_render.run_confirm_slowpics_upload_phase(
        ctx,
        report_path=report_path,
        report_succeeded=True,
        confirm_slowpics_upload=_callback,
    )

    assert output.status == "declined"
    assert output.warnings == []
    assert callback_calls == [SlowpicsUploadConfirmationRequest(report_path=report_path)]


def test_resolve_run_metadata_builds_metadata_config_and_delegates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """\

[tmdb]
api_key = "test-key"
enabled = true
unattended = true
timeout_seconds = 3.5
year_tolerance = 4
category_preference = "tv"
"""
    )
    config = _create_config(tmp_path, content=config_content)
    expected = TmdbMetadata(
        tmdb_id=1,
        title="Heat",
        original_title="Heat",
        year=1995,
        media_type="movie",
    )
    captured: dict[str, Any] = {}

    async def _fake_resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata:
        captured["filenames"] = filenames
        captured["config"] = config
        captured["client"] = client
        return expected

    monkeypatch.setattr(phase_post_render, "resolve_metadata", _fake_resolve_metadata)

    async def _run() -> TmdbMetadata | None:
        async with httpx.AsyncClient() as client:
            result = await phase_post_render.resolve_run_metadata(
                filenames=["Heat.1995.mkv"],
                config=config,
                client=client,
            )
            assert captured["client"] is client
            return result

    assert asyncio.run(_run()) == expected
    assert captured["filenames"] == ["Heat.1995.mkv"]
    assert captured["config"] == MetadataConfig(
        api_key="test-key",
        unattended=True,
        timeout_seconds=3.5,
        year_tolerance=4,
        category_preference="tv",
    )
