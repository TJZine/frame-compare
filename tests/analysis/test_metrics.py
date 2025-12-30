"""Unit tests for metrics calculation."""

from __future__ import annotations

import sys
from fractions import Fraction
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Create a mock vapoursynth module before importing metrics
vs_mock = MagicMock()
vs_mock.YUV = 1
vs_mock.GRAY = 2
vs_mock.INTEGER = 0
vs_mock.FLOAT = 1
sys.modules["vapoursynth"] = vs_mock

from frame_compare.analysis.metrics import (  # noqa: E402
    ProgressReporter,
    _calculate_luminance,
    _calculate_motion,
    calculate_metrics,
)
from frame_compare.analysis.types import FrameMetrics  # noqa: E402
from frame_compare.config.schema import AnalysisConfig  # noqa: E402
from frame_compare.errors import (  # noqa: E402
    MetricsCalculationError,
    PluginNotFoundError,
    SourceLoadError,
)


class MockFrame:
    """Mock VapourSynth frame."""

    def __init__(self, data: np.ndarray):
        self._data = data

    def __getitem__(self, index: int) -> np.ndarray:
        if index == 0:
            return self._data
        raise IndexError("Mock only supports Y plane (index 0)")

    @property
    def props(self) -> dict:
        return {}


class MockClip:
    """Mock VapourSynth clip."""

    def __init__(self, frames: list[np.ndarray], fps: Fraction = Fraction(24, 1)):
        self._frames = [MockFrame(f) for f in frames]
        self.num_frames = len(frames)
        self.fps = MagicMock()
        self.fps.numerator = fps.numerator
        self.fps.denominator = fps.denominator
        self.width = frames[0].shape[1] if frames else 0
        self.height = frames[0].shape[0] if frames else 0
        self.format = MagicMock()
        self.format.color_family = vs_mock.YUV
        self.format.sample_type = vs_mock.INTEGER
        self.format.bits_per_sample = 8
        self.resize = MagicMock()

    def get_frame(self, n: int) -> MockFrame:
        if 0 <= n < self.num_frames:
            return self._frames[n]
        raise Exception(f"Frame {n} out of range")


@pytest.fixture
def mock_reporter():
    return MagicMock(spec=ProgressReporter)


def test_calculate_luminance_black_frames_returns_zeros():
    frames = [np.zeros((10, 10), dtype=np.uint8) for _ in range(3)]
    clip = MockClip(frames)
    luminance = _calculate_luminance(clip)  # type: ignore
    assert luminance == [0.0, 0.0, 0.0]


def test_calculate_luminance_white_frames_returns_ones():
    frames = [np.full((10, 10), 255, dtype=np.uint8) for _ in range(3)]
    clip = MockClip(frames)
    luminance = _calculate_luminance(clip)  # type: ignore
    assert luminance == [1.0, 1.0, 1.0]


def test_calculate_luminance_single_frame():
    frames = [np.full((10, 10), 127, dtype=np.uint8)]
    clip = MockClip(frames)
    luminance = _calculate_luminance(clip)  # type: ignore
    assert len(luminance) == 1
    assert pytest.approx(luminance[0], abs=1e-2) == 127 / 255


def test_calculate_luminance_calls_progress_reporter(mock_reporter):
    frames = [np.zeros((10, 10), dtype=np.uint8) for _ in range(5)]
    clip = MockClip(frames)
    _calculate_luminance(clip, reporter=mock_reporter)  # type: ignore
    mock_reporter.start_phase.assert_called_once_with("Calculating luminance", 5)
    assert mock_reporter.advance.call_count == 5
    mock_reporter.complete_phase.assert_called_once()


def test_calculate_motion_static_clip_returns_zeros():
    frames = [np.full((10, 10), 100, dtype=np.uint8) for _ in range(3)]
    clip = MockClip(frames)
    motion = _calculate_motion(clip)  # type: ignore
    assert motion == [0.0, 0.0, 0.0]


def test_calculate_motion_first_frame_is_zero():
    frames = [
        np.zeros((10, 10), dtype=np.uint8),
        np.full((10, 10), 255, dtype=np.uint8),
    ]
    clip = MockClip(frames)
    motion = _calculate_motion(clip)  # type: ignore
    assert motion[0] == 0.0
    assert motion[1] == 1.0


def test_calculate_motion_changing_frames_returns_positive():
    frames = [
        np.zeros((10, 10), dtype=np.uint8),
        np.full((10, 10), 127, dtype=np.uint8),
    ]
    clip = MockClip(frames)
    motion = _calculate_motion(clip)  # type: ignore
    assert motion[0] == 0.0
    assert 0.0 < motion[1] < 1.0


def test_calculate_motion_single_frame_returns_single_zero():
    frames = [np.zeros((10, 10), dtype=np.uint8)]
    clip = MockClip(frames)
    motion = _calculate_motion(clip)  # type: ignore
    assert motion == [0.0]


def test_calculate_motion_output_length_equals_num_frames():
    frames = [np.zeros((10, 10), dtype=np.uint8) for _ in range(10)]
    clip = MockClip(frames)
    motion = _calculate_motion(clip)  # type: ignore
    assert len(motion) == 10


def test_calculate_luminance_empty_clip_raises_error():
    clip = MockClip([])
    with pytest.raises(MetricsCalculationError, match="Empty clip"):
        _calculate_luminance(clip)  # type: ignore


def test_calculate_motion_empty_clip_raises_error():
    clip = MockClip([])
    with pytest.raises(MetricsCalculationError, match="Empty clip"):
        _calculate_motion(clip)  # type: ignore


def test_calculate_metrics_frame_access_failure_raises_fc4002():
    clip = MagicMock()
    clip.num_frames = 1
    clip.format.color_family = vs_mock.YUV
    clip.format.sample_type = vs_mock.INTEGER
    clip.format.bits_per_sample = 8
    clip.get_frame.side_effect = Exception("VS Error")

    with pytest.raises(MetricsCalculationError) as exc:
        _calculate_luminance(clip)  # type: ignore
    assert exc.value.code == "FC-4002"


@patch("frame_compare.analysis.metrics.load_cached_metrics")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_uses_cache_on_hit(mock_key, mock_load, tmp_path):
    mock_key.return_value = "fp"
    metrics = MagicMock(spec=FrameMetrics)
    mock_load.return_value = MagicMock(success=True, metrics=metrics)

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()

    result = calculate_metrics(video_paths, config, tmp_path)
    assert result == metrics
    mock_load.assert_called_once()


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics._calculate_motion")
@patch("frame_compare.analysis.metrics._calculate_luminance")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_computes_on_cache_miss(
    mock_key, mock_load, mock_loader_cls, mock_lum, mock_mot, mock_save, tmp_path
):
    mock_key.return_value = "fp"
    mock_load.return_value = MagicMock(success=False)

    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 10
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(24, 1)

    mock_lum.return_value = [0.1] * 10
    mock_motion_vals = [0.0] + [0.1] * 9
    mock_mot.return_value = mock_motion_vals

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()

    result = calculate_metrics(video_paths, config, tmp_path)

    assert len(result.luminance) == 10
    assert len(result.motion) == 10
    mock_lum.assert_called_once_with(mock_clip, None)
    mock_mot.assert_called_once_with(mock_clip)
    mock_save.assert_called_once()


@patch("frame_compare.analysis.metrics._calculate_motion")
@patch("frame_compare.analysis.metrics._calculate_luminance")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_analyzes_reference_only(
    mock_load, mock_loader_cls, mock_lum, mock_mot, tmp_path
):
    mock_load.return_value = MagicMock(success=False)
    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 10
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(24, 1)

    video_paths = [tmp_path / "ref.mkv", tmp_path / "comp.mkv"]
    for p in video_paths:
        p.write_bytes(b"")

    calculate_metrics(video_paths, AnalysisConfig(), tmp_path)

    # loader.load should only be called once with reference path
    mock_loader.load.assert_called_once_with(video_paths[0])


@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_propagates_plugin_not_found(mock_load, mock_loader_cls, tmp_path):
    """Verify PluginNotFoundError bubbles up unwrapped."""
    mock_load.return_value = MagicMock(success=False)
    mock_loader = mock_loader_cls.return_value
    mock_loader.load.side_effect = PluginNotFoundError("lsmas")

    video_paths = [tmp_path / "ref.mkv"]
    video_paths[0].write_bytes(b"")

    with pytest.raises(PluginNotFoundError) as exc:
        calculate_metrics(video_paths, AnalysisConfig(), tmp_path)
    assert exc.value.code == "FC-2003"


@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_propagates_source_load_error(mock_load, mock_loader_cls, tmp_path):
    """Verify SourceLoadError bubbles up unwrapped."""
    mock_load.return_value = MagicMock(success=False)
    mock_loader = mock_loader_cls.return_value
    path = tmp_path / "ref.mkv"
    path.write_bytes(b"")
    mock_loader.load.side_effect = SourceLoadError(path, "Corrupt")

    video_paths = [path]

    with pytest.raises(SourceLoadError) as exc:
        calculate_metrics(video_paths, AnalysisConfig(), tmp_path)
    assert exc.value.code == "FC-4015"


def test_no_toplevel_vapoursynth_import() -> None:
    """Verify vapoursynth is only imported inside TYPE_CHECKING or functions.

    Per SSOT: Import-Time VapourSynth Dependency (SSOT)
    - No top-level 'import vapoursynth' outside TYPE_CHECKING blocks
    - TYPE_CHECKING blocks are explicitly allowed
    """
    import ast
    from pathlib import Path

    metrics_path = (
        Path(__file__).parent.parent.parent / "src" / "frame_compare" / "analysis" / "metrics.py"
    )
    source = metrics_path.read_text()
    tree = ast.parse(source)

    def is_type_checking_guard(node: ast.If) -> bool:
        """Check if an If node is 'if TYPE_CHECKING:' or 'if typing.TYPE_CHECKING:'."""
        test = node.test
        # Handle: if TYPE_CHECKING:
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        # Handle: if typing.TYPE_CHECKING:
        return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"

    def has_vapoursynth_import(nodes: list[ast.stmt]) -> tuple[bool, int]:
        """Check if any node is a vapoursynth import. Returns (found, lineno)."""
        for node in nodes:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "vapoursynth":
                        return (True, node.lineno)
            if isinstance(node, ast.ImportFrom) and node.module == "vapoursynth":
                return (True, node.lineno)
        return (False, 0)

    for node in ast.iter_child_nodes(tree):
        # Direct top-level import vapoursynth -> FAIL
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert (
                    alias.name != "vapoursynth"
                ), f"Top-level 'import vapoursynth' at line {node.lineno}"
        # Direct top-level from vapoursynth import ... -> FAIL
        if isinstance(node, ast.ImportFrom) and node.module == "vapoursynth":
            raise AssertionError(f"Top-level 'from vapoursynth import' at line {node.lineno}")
        # Top-level If block
        if isinstance(node, ast.If):
            if is_type_checking_guard(node):
                # TYPE_CHECKING block: vapoursynth imports ALLOWED
                continue
            else:
                # Other if block: vapoursynth imports NOT allowed
                found, lineno = has_vapoursynth_import(node.body)
                if found:
                    raise AssertionError(
                        f"vapoursynth import in non-TYPE_CHECKING if block at line {lineno}"
                    )
