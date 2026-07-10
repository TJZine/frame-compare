from __future__ import annotations

from unittest.mock import MagicMock, patch

from frame_compare.analysis.metric_strategies import MetricComputationResult
from frame_compare.analysis.metrics import calculate_metrics
from frame_compare.config.schema import AnalysisConfig
from frame_compare.vs.loader import VSLoader


@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_uses_custom_vs_loader(mock_key, mock_load, tmp_path):
    mock_key.return_value = "fp"
    mock_load.return_value = MagicMock(success=False)

    mock_loader = MagicMock(spec=VSLoader)
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 5
    mock_source.clip = mock_clip
    mock_source.fps = 24.0

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()

    strategy_result = MetricComputationResult(
        luminance=[0.1] * 5,
        motion=[0.0] * 5,
        performance_mode="quality",
        algorithm_id="algorithm-id",
        metric_backend="python_numpy",
        algorithm_identity_json='{"backend":"python_numpy"}',
    )
    with (
        patch(
            "frame_compare.analysis.metrics.calculate_metric_strategy", return_value=strategy_result
        ),
        patch("frame_compare.analysis.metrics.save_metrics_cache"),
    ):
        calculate_metrics(video_paths, config, tmp_path, vs_loader=mock_loader)

    mock_loader.load.assert_called_once_with(video_paths[0])
