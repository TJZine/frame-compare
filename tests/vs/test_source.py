import logging
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest

from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.source import (
    LWLibavSourceOptions,
    apply_trim,
    load_source,
    source_index_path,
    validate_source_index,
)
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

    def mock_loader(path: str, **_kwargs: object):
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


def _index_kwargs(path: str | Path) -> dict[str, object]:
    return {"cachefile": str(source_index_path(Path(path)))}


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


def test_load_source_default_does_not_forward_decoder_kwargs():
    calls: list[tuple[str, dict[str, object]]] = []

    def loader(path: str, **kwargs: object) -> MockClip:
        calls.append((path, kwargs))
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    load_source("video.mkv", core)  # type: ignore[arg-type]

    assert calls == [("video.mkv", _index_kwargs("video.mkv"))]


def test_validate_source_index_opens_existing_index_without_mutating_it(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    index = source_index_path(video)
    index.write_bytes(b"ready index")
    calls: list[tuple[str, dict[str, object]]] = []

    def loader(path: str, **kwargs: object) -> MockClip:
        calls.append((path, kwargs))
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    validate_source_index(video, core)  # type: ignore[arg-type]

    assert calls == [(str(video), {"cachefile": str(index)})]
    assert index.read_bytes() == b"ready index"


def test_validate_source_index_rejects_index_rebuilt_during_probe(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    index = source_index_path(video)
    index.write_bytes(b"rejected index")

    def loader(_path: str, **_kwargs: object) -> MockClip:
        index.write_bytes(b"rebuilt index")
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    with pytest.raises(SourceLoadError, match="changed during validation"):
        validate_source_index(video, core)  # type: ignore[arg-type]


def test_load_source_forwards_explicit_decoder_options():
    calls: list[tuple[str, dict[str, object]]] = []

    def loader(path: str, **kwargs: object) -> MockClip:
        calls.append((path, kwargs))
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    load_source(  # type: ignore[arg-type]
        "video.mkv",
        core,
        decoder_options=LWLibavSourceOptions(
            threads=12,
            ff_options="skip_loop_filter=all",
            prefer_hw=1,
        ),
    )

    assert calls == [
        (
            "video.mkv",
            {
                **_index_kwargs("video.mkv"),
                "threads": 12,
                "ff_options": "skip_loop_filter=all",
                "prefer_hw": 1,
            },
        )
    ]


@pytest.mark.parametrize("threads", [-1, True, "4", 1.5])
def test_lwlibav_source_options_reject_invalid_thread_count(threads: object) -> None:
    with pytest.raises(
        ValueError,
        match="thread count must be a non-negative integer or None",
    ):
        LWLibavSourceOptions(threads=cast("int", threads))


def test_lwlibav_source_options_accept_boundary_values() -> None:
    defaults = LWLibavSourceOptions()
    explicit = LWLibavSourceOptions(threads=0, prefer_hw=1)

    assert (defaults.threads, defaults.ff_options, defaults.prefer_hw) == (None, None, None)
    assert (explicit.threads, explicit.prefer_hw) == (0, 1)


@pytest.mark.parametrize("prefer_hw", [0, 2, -1, True, 1.0, "1", [1]])
def test_lwlibav_source_options_reject_invalid_hardware_preference(
    prefer_hw: object,
) -> None:
    with pytest.raises(
        ValueError,
        match=r"prefer_hw must be the integer 1 \(NVIDIA CUVID\) or None",
    ):
        LWLibavSourceOptions(
            prefer_hw=cast("Literal[1]", prefer_hw),
        )


def test_load_source_missing_lsmas_raises_plugin_not_found():
    core = make_mock_core(with_lsmas=False)
    with pytest.raises(PluginNotFoundError) as exc:
        load_source("video.mkv", core)  # type: ignore
    assert exc.value.code == "FC-2003"


def test_load_source_file_error_raises_source_load_error(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        raise RuntimeError("File corrupt")

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    with pytest.raises(SourceLoadError) as exc:
        load_source(tmp_path / "video.mkv", core)  # type: ignore[arg-type]

    assert exc.value.code == "FC-4015"
    assert calls == [_index_kwargs(tmp_path / "video.mkv")]


def test_load_source_recovers_by_rebuilding_owned_index(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mkv"
    index_path = source_index_path(video_path)
    index_path.write_bytes(b"unusable index")
    calls: list[dict[str, object]] = []

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("lsmas: failed to construct index for video.mkv")
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    source = load_source(  # type: ignore[arg-type]
        video_path,
        core,
        decoder_options=LWLibavSourceOptions(
            threads=12,
            ff_options="skip_loop_filter=all",
            prefer_hw=1,
        ),
    )

    assert source.num_frames == 1000
    expected = {
        **_index_kwargs(video_path),
        "threads": 12,
        "ff_options": "skip_loop_filter=all",
        "prefer_hw": 1,
    }
    assert calls == [expected, expected]
    assert not index_path.exists()


def test_load_source_does_not_retry_unrelated_loader_failure_with_adjacent_index(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "video.mkv"
    source_index_path(video_path).write_bytes(b"existing index")
    calls: list[dict[str, object]] = []

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        raise RuntimeError("decoder initialization failed")

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    with pytest.raises(SourceLoadError, match="decoder initialization failed"):
        load_source(video_path, core)  # type: ignore[arg-type]

    assert calls == [_index_kwargs(video_path)]


def test_load_source_preserves_original_error_when_index_retry_fails(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mkv"
    source_index_path(video_path).write_bytes(b"unusable index")
    calls: list[dict[str, object]] = []

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("lsmas: failed to construct index for video.mkv")
        raise RuntimeError("cache-free retry also failed")

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    with pytest.raises(SourceLoadError, match="failed to construct index") as exc_info:
        load_source(video_path, core)  # type: ignore[arg-type]

    original_error = exc_info.value.__cause__
    assert isinstance(original_error, RuntimeError)
    assert "failed to construct index" in str(original_error)
    assert isinstance(original_error.__cause__, RuntimeError)
    assert str(original_error.__cause__) == "cache-free retry also failed"
    assert calls == [_index_kwargs(video_path), _index_kwargs(video_path), {"cache": 0}]


def test_load_source_warns_when_rejected_index_cannot_be_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    video_path = tmp_path / "video.mkv"
    index_path = source_index_path(video_path)
    index_path.write_bytes(b"unusable index")
    calls: list[dict[str, object]] = []

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("lsmas: failed to construct index for video.mkv")
        return MockClip()

    original_unlink = Path.unlink

    def fail_owned_index_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == index_path:
            raise PermissionError("index is locked")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_owned_index_unlink)
    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    with caplog.at_level(logging.WARNING, logger="frame_compare.vs.source"):
        source = load_source(video_path, core)  # type: ignore[arg-type]

    assert source.num_frames == 1000
    assert calls == [_index_kwargs(video_path), {"cache": 0}]
    assert "Could not remove rejected L-SMASH index" in caplog.text
    assert "retrying without an index cache" in caplog.text


def test_load_source_does_not_retry_frame_read_failure(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mkv"
    source_index_path(video_path).write_bytes(b"existing index")
    calls: list[dict[str, object]] = []

    class FrameReadFailureClip(MockClip):
        def get_frame(self, n: int) -> SimpleNamespace:
            raise RuntimeError(f"failed to read frame {n}")

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        return FrameReadFailureClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    with pytest.raises(SourceLoadError) as exc:
        load_source(video_path, core)  # type: ignore[arg-type]

    assert exc.value.code == "FC-4015"
    assert calls == [_index_kwargs(video_path)]


def test_load_source_ignores_legacy_unversioned_index(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mkv"
    legacy_index = Path(f"{video_path}.lwi")
    legacy_index.write_bytes(b"legacy")
    calls: list[dict[str, object]] = []

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))
    load_source(video_path, core)  # type: ignore[arg-type]

    assert calls == [_index_kwargs(video_path)]
    assert legacy_index.read_bytes() == b"legacy"


# HDR Detection Tests


def test_detect_hdr_pq_bt2020_returns_true():
    props = {"_Transfer": 16, "_Primaries": 9}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p, **_kwargs: MockClip(frame_props=props)  # type: ignore
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
            LWLibavSource=lambda p, **_kwargs: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is True


def test_detect_hdr_pq_bt709_returns_false():
    props = {"_Transfer": 16, "_Primaries": 1}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p, **_kwargs: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is False
    assert source.hdr_metadata is None


def test_detect_hdr_sdr_returns_false():
    props = {"_Transfer": 1, "_Primaries": 1}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p, **_kwargs: MockClip(frame_props=props)  # type: ignore
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
            LWLibavSource=lambda p, **_kwargs: MockClip(frame_props=props)  # type: ignore
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
            LWLibavSource=lambda p, **_kwargs: MockClip(frame_props=props)  # type: ignore
        )
    )
    source = load_source("video.mkv", core)  # type: ignore
    assert source.is_hdr is False
    assert source.hdr_metadata is None


def test_detect_hdr_defaults_matrix_when_missing():
    props = {"_Transfer": 16, "_Primaries": 9}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(
            LWLibavSource=lambda p, **_kwargs: MockClip(frame_props=props)  # type: ignore
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
