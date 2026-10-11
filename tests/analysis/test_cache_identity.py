"""Cache identity and filename contract tests."""

import os
from fractions import Fraction
from pathlib import Path

import pytest

import frame_compare.analysis.metric_identity as metric_identity
from frame_compare.analysis.cache_io import compute_cache_key, metrics_cache_filename
from frame_compare.analysis.metric_identity import stable_metric_algorithm_identity_json
from frame_compare.analysis.types import MetricActiveRect, MetricCacheRequest, MetricFrameRange
from frame_compare.config.schema import AnalysisConfig
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from tests.analysis._cache_io_test_helpers import FIXED_MTIME, create_video_file


def test_compute_cache_key_deterministic(tmp_path: Path) -> None:
    """Same paths + config → same 64-char hex."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(random_frame_count=10)
    key1 = compute_cache_key([v1], config)
    key2 = compute_cache_key([v1], config)
    assert key1 == key2
    assert len(key1) == 64


def test_compute_cache_key_changes_when_selected_reference_changes(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    v2 = create_video_file(tmp_path, "v2.mkv")
    config = AnalysisConfig(random_frame_count=10)
    key1 = compute_cache_key([v1, v2], config)
    key2 = compute_cache_key([v2, v1], config)
    assert key1 != key2


def test_compute_cache_key_changes_when_selection_domain_changes(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    v2 = create_video_file(tmp_path, "v2.mkv")
    config = AnalysisConfig(random_frame_count=10)
    key1 = compute_cache_key([v1, v2], config, selection_domain="window=0:100")
    key2 = compute_cache_key([v1, v2], config, selection_domain="window=10:100")
    assert key1 != key2


def test_compute_cache_key_changes_on_ignore_window_config(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    default_key = compute_cache_key([v1], AnalysisConfig())
    lead_key = compute_cache_key([v1], AnalysisConfig(ignore_lead_seconds=1.0))
    trail_key = compute_cache_key([v1], AnalysisConfig(ignore_trail_seconds=1.0))
    min_window_key = compute_cache_key([v1], AnalysisConfig(min_window_seconds=10.0))

    assert len({default_key, lead_key, trail_key, min_window_key}) == 4


def test_compute_cache_key_changes_by_analysis_performance_mode(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    keys = {
        compute_cache_key([v1], AnalysisConfig(performance_mode=mode))
        for mode in (AnalysisPerformanceMode.QUALITY, AnalysisPerformanceMode.PERFORMANCE)
    }

    assert len(keys) == 2


def test_compute_cache_key_changes_by_metric_active_rect(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig()

    full_frame = compute_cache_key([v1], config)
    first_rect = compute_cache_key(
        [v1],
        config,
        metric_request=MetricCacheRequest(
            analysis_source_path=v1,
            metric_active_rect=MetricActiveRect(x=0, y=0, width=100, height=100),
        ),
    )
    second_rect = compute_cache_key(
        [v1],
        config,
        metric_request=MetricCacheRequest(
            analysis_source_path=v1,
            metric_active_rect=MetricActiveRect(x=10, y=0, width=100, height=100),
        ),
    )

    assert len({full_frame, first_rect, second_rect}) == 3


def test_compute_cache_key_changes_by_complete_metric_request_identity(tmp_path: Path) -> None:
    video = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig()
    rect = MetricActiveRect(x=0, y=10, width=100, height=60)
    base = MetricCacheRequest(
        analysis_source_path=video,
        metric_active_rect=rect,
        active_rect_source="content-derived",
        active_rect_detection_mode="auto",
    )
    requests = (
        base,
        MetricCacheRequest(
            analysis_source_path=video,
            effective_fps=Fraction(48, 1),
            metric_active_rect=rect,
            active_rect_source="content-derived",
            active_rect_detection_mode="auto",
        ),
        MetricCacheRequest(
            analysis_source_path=video,
            metric_active_rect=rect,
            active_rect_source="explicit",
            active_rect_detection_mode="provided",
        ),
    )

    keys = {compute_cache_key([video], config, metric_request=request) for request in requests}

    assert len(keys) == len(requests)


def test_compute_cache_key_changes_by_exact_metric_frame_range(tmp_path: Path) -> None:
    video = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig()
    requests = (
        MetricCacheRequest(
            analysis_source_path=video,
            metric_frame_range=MetricFrameRange(100, 0, 100),
        ),
        MetricCacheRequest(
            analysis_source_path=video,
            metric_frame_range=MetricFrameRange(100, 10, 90),
        ),
        MetricCacheRequest(
            analysis_source_path=video,
            metric_frame_range=MetricFrameRange(120, 10, 90),
        ),
    )

    keys = {compute_cache_key([video], config, metric_request=request) for request in requests}

    assert len(keys) == len(requests)


def test_metrics_cache_filename_order_independent(tmp_path: Path) -> None:
    fingerprint = "f" * 64
    v1 = create_video_file(tmp_path, "b-source.mkv")
    v2 = create_video_file(tmp_path, "a-source.mkv")

    forward = metrics_cache_filename([v1, v2], fingerprint)
    reversed_order = metrics_cache_filename([v2, v1], fingerprint)

    assert forward == reversed_order
    assert forward == f"a-source__b-source__{fingerprint}.compframes"


def test_metric_algorithm_identity_changes_with_media_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AnalysisConfig(performance_mode=AnalysisPerformanceMode.QUALITY)
    original = stable_metric_algorithm_identity_json(config)
    captured_scopes: list[str] = []

    def changed_runtime_identity(scope: str) -> dict[str, object]:
        captured_scopes.append(scope)
        return {"contract_version": 999, "scope": scope, "profile": "test-runtime"}

    monkeypatch.setattr(metric_identity, "media_runtime_identity", changed_runtime_identity)

    changed = stable_metric_algorithm_identity_json(config)

    assert changed != original
    assert captured_scopes == ["analysis"]
    assert '"algorithm_version":"analysis_metrics_v7"' in original
    assert '"media_runtime"' in original
    assert '"contract_version":999' in changed
    assert '"profile":"test-runtime"' in changed
    assert '"scope":"analysis"' in changed


def test_metrics_cache_filename_sanitizes_lowercase_label(tmp_path: Path) -> None:
    fingerprint = "f" * 64
    path = tmp_path / "Movie.Name 2024 [HDR]!.mkv"

    filename = metrics_cache_filename([path], fingerprint)

    assert filename == f"movie.name-2024-hdr__{fingerprint}.compframes"


@pytest.mark.parametrize(
    "first, second",
    [
        pytest.param(
            AnalysisConfig(random_frame_count=10),
            AnalysisConfig(
                user_frames=[1, 2],
                random_frame_count=3,
                dark_frame_count=4,
                bright_frame_count=5,
                motion_frame_count=6,
            ),
            id="selection_counts",
        ),
        pytest.param(
            AnalysisConfig(user_frames=[1, 2]), AnalysisConfig(user_frames=[3, 4]), id="user_frames"
        ),
        pytest.param(
            AnalysisConfig(
                performance_mode=AnalysisPerformanceMode.PERFORMANCE, motion_frame_count=1
            ),
            AnalysisConfig(
                performance_mode=AnalysisPerformanceMode.PERFORMANCE,
                random_frame_count=3,
                dark_frame_count=4,
                bright_frame_count=5,
                motion_frame_count=6,
            ),
            id="performance_counts",
        ),
        pytest.param(
            AnalysisConfig(random_seed=42), AnalysisConfig(random_seed=43), id="random_seed"
        ),
        pytest.param(
            AnalysisConfig(dark_quantile=0.05),
            AnalysisConfig(dark_quantile=0.10),
            id="dark_quantile",
        ),
        pytest.param(
            AnalysisConfig(bright_quantile=0.95),
            AnalysisConfig(bright_quantile=0.90),
            id="bright_quantile",
        ),
    ],
)
def test_cache_key_ignores_selection_fields(
    tmp_path: Path, first: AnalysisConfig, second: AnalysisConfig
) -> None:
    video = create_video_file(tmp_path, "v1.mkv")
    assert compute_cache_key([video], first) == compute_cache_key([video], second)


@pytest.mark.parametrize("change", ["path", "size", "mtime"])
def test_cache_key_changes_with_file_identity(tmp_path: Path, change: str) -> None:
    video = create_video_file(tmp_path, "v1.mkv", content=b"test")
    config = AnalysisConfig(random_frame_count=10)
    first = compute_cache_key([video], config)
    if change == "path":
        renamed = tmp_path / "v2.mkv"
        video.rename(renamed)
        video = renamed
    elif change == "size":
        create_video_file(tmp_path, "v1.mkv", content=b"test-longer")
    else:
        os.utime(video, (FIXED_MTIME + 1, FIXED_MTIME + 1))
    assert first != compute_cache_key([video], config)
