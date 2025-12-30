import sys
from collections.abc import Mapping
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Mock vapoursynth BEFORE importing module under test (VS missing in CI)
if "vapoursynth" not in sys.modules:
    sys.modules["vapoursynth"] = MagicMock()

from frame_compare.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.source import apply_trim, load_source
from frame_compare.vs.types import SourceInfo


class MockClip:
    """Mock VS clip that supports slicing via __getitem__."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        num_frames: int = 1000,
        fps_num: int = 24,
        fps_den: int = 1,
        frame_props: Mapping[str, object] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.num_frames = num_frames
        self.fps = SimpleNamespace(numerator=fps_num, denominator=fps_den)
        self.format = SimpleNamespace(name="YUV420P8")
        self._frame_props = frame_props or {}

    def get_frame(self, n: int) -> SimpleNamespace:
        return SimpleNamespace(props=self._frame_props)

    def __getitem__(self, s: slice) -> "MockClip":
        """Return sliced clip with updated num_frames."""
        start = s.start or 0
        stop = s.stop if s.stop is not None else self.num_frames
        return MockClip(
            width=self.width,
            height=self.height,
            num_frames=stop - start,
            fps_num=self.fps.numerator,
            fps_den=self.fps.denominator,
            frame_props=self._frame_props,
        )


def make_mock_core(
    with_lsmas: bool = True, use_lw_namespace: bool = False, fail_load: bool = False
) -> SimpleNamespace:
    """Create mock VS core with optional lsmas plugin.

    Args:
        with_lsmas: Whether lsmas plugin is available
        use_lw_namespace: If True, use core.lw instead of core.lsmas
        fail_load: If True, LWLibavSource raises Exception
    """
    core = SimpleNamespace()

    def mock_loader(path: str):
        if fail_load:
            raise Exception("File corrupt")
        return MockClip()

    loader = SimpleNamespace(LWLibavSource=mock_loader)

    if with_lsmas:
        if use_lw_namespace:
            core.lw = loader
        else:
            core.lsmas = loader
            # Detect plugins checks both, so if we put it in lsmas, we're good.
    return core


def test_load_source_returns_source_info():
    core = make_mock_core(with_lsmas=True)
    source = load_source("video.mkv", core)  # type: ignore
    assert source.width == 1920
    assert source.height == 1080
    assert source.num_frames == 1000


def test_load_source_extracts_fps():
    core = make_mock_core(with_lsmas=True)
    source = load_source("video.mkv", core)  # type: ignore
    assert source.fps == Fraction(24, 1)


def test_load_source_extracts_dimensions():
    # MockClip defaults to 1920x1080
    core = make_mock_core(with_lsmas=True)
    source = load_source("video.mkv", core)  # type: ignore
    assert source.width == 1920
    assert source.height == 1080


def test_load_source_uses_lw_namespace_fallback():
    core = make_mock_core(with_lsmas=True, use_lw_namespace=True)
    source = load_source("video.mkv", core)  # type: ignore
    assert source.num_frames == 1000


def test_load_source_missing_lsmas_raises_plugin_not_found():
    core = make_mock_core(with_lsmas=False)
    with pytest.raises(PluginNotFoundError) as exc:
        load_source("video.mkv", core)  # type: ignore
    assert exc.value.code == "FC-2003"


def test_load_source_file_error_raises_source_load_error():
    core = make_mock_core(with_lsmas=True, fail_load=True)
    with pytest.raises(SourceLoadError) as exc:
        load_source("video.mkv", core)  # type: ignore
    assert exc.value.code == "FC-4015"


# HDR Detection Tests


def test_detect_hdr_pq_bt2020_returns_true():
    props = {"_Transfer": 16, "_Primaries": 9}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is True
    assert source.hdr_metadata is not None
    assert source.hdr_metadata.transfer == 16
    assert source.hdr_metadata.color_primaries == 9


def test_detect_hdr_hlg_bt2020_returns_true():
    props = {"_Transfer": 18, "_Primaries": 9}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is True


def test_detect_hdr_pq_bt709_returns_false():
    props = {"_Transfer": 16, "_Primaries": 1}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is False
    assert source.hdr_metadata is None


def test_detect_hdr_sdr_returns_false():
    props = {"_Transfer": 1, "_Primaries": 1}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is False


def test_detect_hdr_extracts_metadata_fields():
    props = {
        "_Transfer": 16,
        "_Primaries": 9,
        "MasteringDisplayPrimaries": "Display P3",
        "ContentLightLevelMax": 1000,
        "ContentLightLevelAverage": 400,
        "_Matrix": 9,
    }
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore

    meta = source.hdr_metadata
    assert meta is not None
    assert meta.mastering_display == "Display P3"
    assert meta.max_cll == 1000
    assert meta.max_fall == 400
    assert meta.matrix == 9


def test_detect_hdr_empty_props_returns_false_and_none():
    props = {}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is False
    assert source.hdr_metadata is None


def test_detect_hdr_defaults_matrix_when_missing():
    props = {"_Transfer": 16, "_Primaries": 9}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is True
    assert source.hdr_metadata.matrix == 2


# Apply Trim Tests


def test_apply_trim_with_end_is_inclusive():
    clip = MockClip(num_frames=1000)
    source = SourceInfo(
        clip=clip,  # type: ignore
        width=1920,
        height=1080,
        num_frames=1000,
        fps=Fraction(24, 1),
        format=SimpleNamespace(),  # type: ignore
        frame_props={},
        is_hdr=False,
        hdr_metadata=None,
    )
    trimmed = apply_trim(source, 100, 200)
    # 100 to 200 inclusive is 200 - 100 + 1 = 101 frames
    assert trimmed.num_frames == 101


def test_apply_trim_end_none_trims_to_end():
    clip = MockClip(num_frames=1000)
    source = SourceInfo(
        clip=clip,  # type: ignore
        width=1920,
        height=1080,
        num_frames=1000,
        fps=Fraction(24, 1),
        format=SimpleNamespace(),  # type: ignore
        frame_props={},
        is_hdr=False,
        hdr_metadata=None,
    )
    trimmed = apply_trim(source, 100, None)
    # 100 to end (999) is 1000 - 100 = 900 frames
    assert trimmed.num_frames == 900
