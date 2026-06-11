"""Tests for cache I/O operations."""

import json
import os
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    compute_cache_key,
    delete_metrics_cache_entry,
    load_cached_metrics,
    metrics_cache_filename,
    save_metrics_cache,
)
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    MetricActiveRect,
    MetricsMetadata,
)
from frame_compare.config.schema import AnalysisConfig

FIXED_MTIME = 1704067200.0  # 2024-01-01 00:00:00 UTC


def create_video_file(tmp_path: Path, name: str = "video.mkv", content: bytes = b"test") -> Path:
    """Create a dummy video file with fixed mtime."""
    f = tmp_path / name
    f.write_bytes(content)
    os.utime(f, (FIXED_MTIME, FIXED_MTIME))
    return f


def cache_file(cache_dir: Path, fingerprint: str, *video_paths: Path) -> Path:
    return cache_dir / metrics_cache_filename(list(video_paths), fingerprint)


def metrics_metadata(
    *,
    frame_count: int,
    fps: Fraction,
    config_fingerprint: str,
    clips: list[ClipIdentity],
    config: AnalysisConfig,
    analysis_source_path: str = "",
    metric_active_rect: MetricActiveRect | None = None,
) -> MetricsMetadata:
    return MetricsMetadata(
        frame_count=frame_count,
        fps=fps,
        config_fingerprint=config_fingerprint,
        clips=clips,
        analysis_source_path=analysis_source_path,
        performance_mode=config.performance_mode.value,
        algorithm_id=metric_algorithm_id(config),
        metric_backend=metric_backend(config),
        algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        metric_active_rect=metric_active_rect,
        version=CACHE_VERSION,
    )


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
        metric_active_rect=MetricActiveRect(x=0, y=0, width=100, height=100),
    )
    second_rect = compute_cache_key(
        [v1],
        config,
        metric_active_rect=MetricActiveRect(x=10, y=0, width=100, height=100),
    )

    assert len({full_frame, first_rect, second_rect}) == 3


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
    assert '"target_max_width":320' in first
    assert '"resize":"bicubic"' in first
    assert '"temporal":"all_adjacent_pairs"' in first


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


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """Save → load → success=True, data matches, fps == Fraction(24)."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(random_frame_count=10)
    fingerprint = compute_cache_key([v1], config)

    clips = [ClipIdentity(path=str(v1), size=v1.stat().st_size, mtime=v1.stat().st_mtime)]
    metadata = metrics_metadata(
        frame_count=3,
        fps=Fraction(24, 1),
        config_fingerprint=fingerprint,
        clips=clips,
        config=config,
    )
    metrics = FrameMetrics(
        luminance=[0.1, 0.2, 0.3],
        motion=[0.0, 0.5, 0.1],
        metadata=metadata,
    )

    save_metrics_cache(metrics, tmp_path)
    result = load_cached_metrics(tmp_path, fingerprint, clips)

    assert (tmp_path / f"v1__{fingerprint}.compframes").exists()
    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.luminance == [0.1, 0.2, 0.3]
    assert result.metrics.motion == [0.0, 0.5, 0.1]
    assert result.metrics.metadata.frame_count == 3
    assert result.metrics.metadata.fps == Fraction(24, 1)
    assert result.metrics.metadata.config_fingerprint == fingerprint
    assert result.metrics.metadata.analysis_source_path == ""
    assert result.metrics.metadata.performance_mode == "quality"
    assert result.metrics.metadata.metric_backend == "python_numpy"
    assert result.metrics.metadata.algorithm_id == metric_algorithm_id(config)
    assert result.metrics.metadata.algorithm_identity_json == (
        stable_metric_algorithm_identity_json(config)
    )
    assert result.metrics.metadata.metric_active_rect is None
    assert result.metrics.metadata.active_rect_source == "full-frame"
    assert result.metrics.metadata.active_rect_detection_mode == "aspect_ratio"
    assert result.metrics.metadata.active_rect_algorithm_id == "active_rect_resolution_v1"


def test_save_and_load_round_trip_serializes_metric_active_rect(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(random_frame_count=10)
    rect = MetricActiveRect(x=4, y=8, width=320, height=180)
    fingerprint = compute_cache_key([v1], config, metric_active_rect=rect)

    clips = [ClipIdentity(path=str(v1), size=v1.stat().st_size, mtime=v1.stat().st_mtime)]
    metadata = metrics_metadata(
        frame_count=2,
        fps=Fraction(24, 1),
        config_fingerprint=fingerprint,
        clips=clips,
        config=config,
        metric_active_rect=rect,
    )
    metrics = FrameMetrics(
        luminance=[0.1, 0.2],
        motion=[0.0, 0.3],
        metadata=metadata,
    )

    save_metrics_cache(metrics, tmp_path)
    result = load_cached_metrics(tmp_path, fingerprint, clips)

    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.metadata.metric_active_rect == rect


def test_load_not_found(tmp_path: Path) -> None:
    """Empty dir → reason="not_found"."""
    result = load_cached_metrics(tmp_path, "some-fingerprint", [])
    assert result.success is False
    assert result.reason == "not_found"


def test_load_ignores_legacy_single_cache_filename(tmp_path: Path) -> None:
    """Legacy run-folder cache filename is not a shared-cache hit."""
    (tmp_path / "cache.compframes").write_text("invalid json", encoding="utf-8")

    result = load_cached_metrics(tmp_path, "some-fingerprint", [])

    assert result.success is False
    assert result.reason == "not_found"


def test_metrics_cache_filename_sanitizes_lowercase_label(tmp_path: Path) -> None:
    fingerprint = "f" * 64
    path = tmp_path / "Movie.Name 2024 [HDR]!.mkv"

    filename = metrics_cache_filename([path], fingerprint)

    assert filename == f"movie.name-2024-hdr__{fingerprint}.compframes"


def test_delete_metrics_cache_entry_deletes_only_matching_fingerprint(tmp_path: Path) -> None:
    matching = cache_file(tmp_path, "fp")
    matching.write_text("{}", encoding="utf-8")
    matching_sidecar = matching.with_suffix(".meta.json")
    matching_sidecar.write_text("{}", encoding="utf-8")
    other = cache_file(tmp_path, "other")
    other.write_text("{}", encoding="utf-8")

    delete_metrics_cache_entry(tmp_path, "fp")

    assert not matching.exists()
    assert not matching_sidecar.exists()
    assert other.exists()


def test_load_corrupted(tmp_path: Path) -> None:
    """Invalid JSON → reason="corrupted"."""
    cache_file(tmp_path, "some-fingerprint").write_text("invalid json")
    result = load_cached_metrics(tmp_path, "some-fingerprint", [])
    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize("payload", ["null", "42"])
def test_load_non_mapping_root_returns_corrupted(tmp_path: Path, payload: str) -> None:
    cache_file(tmp_path, "some-fingerprint").write_text(payload, encoding="utf-8")

    result = load_cached_metrics(tmp_path, "some-fingerprint", [])

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_version_mismatch(tmp_path: Path) -> None:
    """Wrong version → reason="version_mismatch"."""
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": 1,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {},
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp", [])
    assert result.success is False
    assert result.reason == "version_mismatch"


def test_load_v4_payload_returns_version_mismatch(tmp_path: Path) -> None:
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": 4,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {},
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp", [])
    assert result.success is False
    assert result.reason == "version_mismatch"


def test_load_mismatched_inputs(tmp_path: Path) -> None:
    """Wrong fingerprint → reason="mismatched_inputs"."""
    cache_file(tmp_path, "fp2").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp1",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp1",
                    "analysis_source_path": "",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp2", [])
    assert result.success is False
    assert result.reason == "mismatched_inputs"


def test_save_creates_directory(tmp_path: Path) -> None:
    """Non-existent dir → created."""
    sub_dir = tmp_path / "new_dir"
    metadata = metrics_metadata(
        frame_count=0,
        fps=Fraction(24, 1),
        config_fingerprint="fp",
        clips=[],
        config=AnalysisConfig(),
    )
    metrics = FrameMetrics(luminance=[], motion=[], metadata=metadata)
    save_metrics_cache(metrics, sub_dir)
    assert sub_dir.exists()
    assert (sub_dir / "analysis__fp.compframes").exists()


def test_save_writes_required_keys(tmp_path: Path) -> None:
    """Cache file JSON has all required keys + version == CACHE_VERSION."""
    config = AnalysisConfig()
    metadata = metrics_metadata(
        frame_count=10,
        fps=Fraction(24000, 1001),
        config_fingerprint="fp",
        clips=[],
        config=config,
    )
    metrics = FrameMetrics(luminance=[0.5], motion=[0.1], metadata=metadata)
    save_metrics_cache(metrics, tmp_path)

    with (tmp_path / "analysis__fp.compframes").open("r") as f:
        data = json.load(f)

    assert data["version"] == CACHE_VERSION
    assert "fingerprint" in data
    assert "luminance" in data
    assert "motion" in data
    assert "metadata" in data
    assert data["metadata"]["frame_count"] == 10
    assert data["metadata"]["fps"] == "24000/1001"
    assert data["metadata"]["analysis_source_path"] == ""
    assert data["metadata"]["performance_mode"] == "quality"
    assert data["metadata"]["algorithm_id"] == metric_algorithm_id(config)
    assert data["metadata"]["metric_backend"] == "python_numpy"
    assert data["metadata"]["algorithm_identity_json"] == stable_metric_algorithm_identity_json(
        config
    )
    assert data["metadata"]["metric_active_rect"] is None
    assert data["metadata"]["active_rect_source"] == "full-frame"
    assert data["metadata"]["active_rect_detection_mode"] == "aspect_ratio"
    assert data["metadata"]["active_rect_algorithm_id"] == "active_rect_resolution_v1"


def test_load_same_version_cache_without_analysis_source_path_is_corrupted(
    tmp_path: Path,
) -> None:
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    "removed_key",
    [
        "performance_mode",
        "algorithm_id",
        "metric_backend",
        "algorithm_identity_json",
    ],
)
def test_load_same_version_cache_without_algorithm_metadata_is_corrupted(
    tmp_path: Path,
    removed_key: str,
) -> None:
    config = AnalysisConfig()
    metadata = {
        "frame_count": 0,
        "fps": "24/1",
        "config_fingerprint": "fp",
        "analysis_source_path": "",
        "clips": [],
        "performance_mode": "quality",
        "algorithm_id": metric_algorithm_id(config),
        "metric_backend": "python_numpy",
        "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
        "metric_active_rect": None,
        "version": CACHE_VERSION,
    }
    del metadata[removed_key]
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_same_version_cache_without_metric_active_rect_metadata_is_corrupted(
    tmp_path: Path,
) -> None:
    config = AnalysisConfig()
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "analysis_source_path": "",
                    "clips": [],
                    "performance_mode": "quality",
                    "algorithm_id": metric_algorithm_id(config),
                    "metric_backend": "python_numpy",
                    "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    "removed_key",
    [
        "active_rect_source",
        "active_rect_detection_mode",
        "active_rect_algorithm_id",
    ],
)
def test_load_same_version_cache_without_active_rect_provenance_is_corrupted(
    tmp_path: Path,
    removed_key: str,
) -> None:
    config = AnalysisConfig()
    metadata = {
        "frame_count": 0,
        "fps": "24/1",
        "config_fingerprint": "fp",
        "analysis_source_path": "",
        "clips": [],
        "performance_mode": "quality",
        "algorithm_id": metric_algorithm_id(config),
        "metric_backend": "python_numpy",
        "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
        "metric_active_rect": None,
        "active_rect_source": "full-frame",
        "active_rect_detection_mode": "aspect_ratio",
        "active_rect_algorithm_id": "active_rect_resolution_v1",
        "version": CACHE_VERSION,
    }
    del metadata[removed_key]
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("x", -1),
        ("y", -1),
        ("width", 0),
        ("height", 0),
        ("width", -1),
        ("height", -1),
    ],
)
def test_load_same_version_cache_with_invalid_metric_active_rect_is_corrupted(
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    config = AnalysisConfig()
    rect = {"x": 0, "y": 0, "width": 100, "height": 100}
    rect[field] = value
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "analysis_source_path": "",
                    "clips": [],
                    "performance_mode": "quality",
                    "algorithm_id": metric_algorithm_id(config),
                    "metric_backend": "python_numpy",
                    "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
                    "metric_active_rect": rect,
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_same_version_cache_with_malformed_algorithm_identity_is_corrupted(
    tmp_path: Path,
) -> None:
    config = AnalysisConfig()
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "analysis_source_path": "",
                    "clips": [],
                    "performance_mode": "quality",
                    "algorithm_id": metric_algorithm_id(config),
                    "metric_backend": "python_numpy",
                    "algorithm_identity_json": "not-json",
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("algorithm_id", "wrong"),
        ("metric_backend", "wrong"),
        ("performance_mode", "performance"),
    ],
)
def test_load_same_version_cache_with_inconsistent_algorithm_metadata_is_corrupted(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    config = AnalysisConfig()
    metadata = {
        "frame_count": 0,
        "fps": "24/1",
        "config_fingerprint": "fp",
        "analysis_source_path": "",
        "clips": [],
        "performance_mode": "quality",
        "algorithm_id": metric_algorithm_id(config),
        "metric_backend": "python_numpy",
        "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
        "metric_active_rect": None,
        "version": CACHE_VERSION,
    }
    metadata[field] = value
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    ("luminance", "motion", "frame_count"),
    [
        ([0.1], [0.0, 0.2], 2),
        ([0.1, 0.2], [0.0], 2),
        ([0.1], [0.0], 2),
        ([0.1], [0.1], 1),
        ([float("nan")], [0.0], 1),
        ([0.1], [float("inf")], 1),
    ],
)
def test_load_metric_array_contract_violation_is_corrupted(
    tmp_path: Path,
    luminance: list[float],
    motion: list[float],
    frame_count: int,
) -> None:
    config = AnalysisConfig()
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": luminance,
                "motion": motion,
                "metadata": {
                    "frame_count": frame_count,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "analysis_source_path": "",
                    "clips": [],
                    "performance_mode": "quality",
                    "algorithm_id": metric_algorithm_id(config),
                    "metric_backend": "python_numpy",
                    "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
                    "metric_active_rect": None,
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def test_save_metrics_cache_uses_atomic_text_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata = MetricsMetadata(
        frame_count=10,
        fps=Fraction(24, 1),
        config_fingerprint="fp",
        clips=[],
    )
    metrics = FrameMetrics(luminance=[0.5], motion=[0.1], metadata=metadata)
    calls: list[tuple[Path, str, str]] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append((path, content, encoding))
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.analysis.cache_io.write_text_atomic", _fake_write)

    save_metrics_cache(metrics, tmp_path)

    assert calls
    assert calls[0][0] == tmp_path / "analysis__fp.compframes"
    assert calls[0][2] == "utf-8"
    assert json.loads(calls[0][1])["fingerprint"] == "fp"


def test_load_missing_key_returns_corrupted(tmp_path: Path) -> None:
    """Missing luminance key → reason="corrupted"."""
    # Missing luminance
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp", [])
    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    "field,value",
    [
        ("luminance", "not-a-list"),
        ("motion", [False]),
        ("metadata.fps", "not-a-fraction"),
        ("metadata.fps", "24000/0"),
        ("metadata.version", "3"),
        ("metadata.clips.0.path", 123),
        ("metadata.clips.0.size", True),
        ("metadata.clips.0.mtime", False),
        ("metadata.clips.0.sha1", 123),
    ],
)
def test_load_malformed_nested_payload_returns_corrupted(
    tmp_path: Path, field: str, value: object
) -> None:
    payload: dict[str, object] = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.1],
        "motion": [0.0],
        "metadata": {
            "frame_count": 1,
            "fps": "24/1",
            "config_fingerprint": "fp",
            "analysis_source_path": "",
            "clips": [{"path": "video.mkv", "size": 10, "mtime": 1.0, "sha1": None}],
            "performance_mode": "quality",
            "algorithm_id": metric_algorithm_id(AnalysisConfig()),
            "metric_backend": "python_numpy",
            "algorithm_identity_json": stable_metric_algorithm_identity_json(AnalysisConfig()),
            "metric_active_rect": None,
            "active_rect_source": "full-frame",
            "active_rect_detection_mode": "aspect_ratio",
            "active_rect_algorithm_id": "active_rect_resolution_v1",
            "version": CACHE_VERSION,
        },
    }
    _set_payload_field(payload, field, value)
    cache_file(tmp_path, "fp").write_text(json.dumps(payload), encoding="utf-8")

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def _set_payload_field(payload: dict[str, object], field: str, value: object) -> None:
    current: object = payload
    parts = field.split(".")
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current[part]
            continue
        if isinstance(current, list):
            current = current[int(part)]
            continue
        raise AssertionError(f"unsupported payload path: {field}")

    if isinstance(current, dict):
        current[parts[-1]] = value
        return
    if isinstance(current, list):
        current[int(parts[-1])] = value
        return
    raise AssertionError(f"unsupported payload path: {field}")
