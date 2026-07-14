"""Cache identity and filename contract tests."""

import os
from fractions import Fraction
from pathlib import Path

from frame_compare.analysis.cache_io import compute_cache_key, metrics_cache_filename
from frame_compare.analysis.metric_identity import stable_metric_algorithm_identity_json
from frame_compare.analysis.types import MetricActiveRect, MetricCacheRequest, MetricFrameRange
from frame_compare.config.schema import AnalysisConfig
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
        for mode in ("quality", "performance")
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


def test_compute_cache_key_ignores_selection_counts(tmp_path: Path) -> None:
    """Selection counts affect frame choice, not metric-array computation."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(random_frame_count=10))
    key2 = compute_cache_key(
        [v1],
        AnalysisConfig(
            user_frames=[1, 2],
            random_frame_count=3,
            dark_frame_count=4,
            bright_frame_count=5,
            motion_frame_count=6,
        ),
    )
    assert key1 == key2


def test_compute_cache_key_ignores_user_frames_only_change(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(user_frames=[1, 2]))
    key2 = compute_cache_key([v1], AnalysisConfig(user_frames=[3, 4]))

    assert key1 == key2


def test_compute_cache_key_ignores_selection_counts_within_performance_mode(
    tmp_path: Path,
) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key(
        [v1], AnalysisConfig(performance_mode="performance", motion_frame_count=1)
    )
    key2 = compute_cache_key(
        [v1],
        AnalysisConfig(
            performance_mode="performance",
            random_frame_count=3,
            dark_frame_count=4,
            bright_frame_count=5,
            motion_frame_count=6,
        ),
    )

    assert key1 == key2


def test_metric_algorithm_identity_serialization_is_deterministic() -> None:
    first = stable_metric_algorithm_identity_json(AnalysisConfig(performance_mode="performance"))
    second = stable_metric_algorithm_identity_json(AnalysisConfig(performance_mode="performance"))

    assert first == second
    assert '"performance_mode":"performance"' in first
    assert '"exact_ceil_one_quarter_in_up_to_eight_centered_bursts"' in first
    assert '"active_rect_aware_full_resolution_luma"' in first
    assert '"resize"' not in first
    assert '"sampled_burst_pairs_with_per_burst_source_lookbehind"' in first


def test_compute_cache_key_ignores_random_seed(tmp_path: Path) -> None:
    """Random seed affects frame choice, not metric-array computation."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(random_seed=42))
    key2 = compute_cache_key([v1], AnalysisConfig(random_seed=43))
    assert key1 == key2


def test_compute_cache_key_ignores_dark_quantile(tmp_path: Path) -> None:
    """Dark quantile affects frame choice, not metric-array computation."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(dark_quantile=0.05))
    key2 = compute_cache_key([v1], AnalysisConfig(dark_quantile=0.10))
    assert key1 == key2


def test_compute_cache_key_ignores_bright_quantile(tmp_path: Path) -> None:
    """Bright quantile affects frame choice, not metric-array computation."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(bright_quantile=0.95))
    key2 = compute_cache_key([v1], AnalysisConfig(bright_quantile=0.90))
    assert key1 == key2


def test_compute_cache_key_changes_on_path_change(tmp_path: Path) -> None:
    """Rename file → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(random_frame_count=10)
    key1 = compute_cache_key([v1], config)

    v2 = tmp_path / "v2.mkv"
    v1.rename(v2)
    key2 = compute_cache_key([v2], config)
    assert key1 != key2


def test_compute_cache_key_changes_on_size_change(tmp_path: Path) -> None:
    """Write more bytes to file → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv", content=b"test")
    key1 = compute_cache_key([v1], AnalysisConfig(random_frame_count=10))

    create_video_file(tmp_path, "v1.mkv", content=b"test-longer")
    key2 = compute_cache_key([v1], AnalysisConfig(random_frame_count=10))
    assert key1 != key2


def test_compute_cache_key_changes_on_mtime_change(tmp_path: Path) -> None:
    """os.utime(path, (new_mtime, new_mtime)) → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(random_frame_count=10))

    os.utime(v1, (FIXED_MTIME + 1, FIXED_MTIME + 1))
    key2 = compute_cache_key([v1], AnalysisConfig(random_frame_count=10))
    assert key1 != key2


def test_metrics_cache_filename_sanitizes_lowercase_label(tmp_path: Path) -> None:
    fingerprint = "f" * 64
    path = tmp_path / "Movie.Name 2024 [HDR]!.mkv"

    filename = metrics_cache_filename([path], fingerprint)

    assert filename == f"movie.name-2024-hdr__{fingerprint}.compframes"
