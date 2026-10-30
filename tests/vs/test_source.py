import asyncio
import logging
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast
from unittest.mock import MagicMock

import pytest
from vapoursynth import Core, VideoFormat, VideoNode

import frame_compare.vs.hdr_probe as hdr_probe_module
import frame_compare.vs.source as source_module
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.source import (
    LWLibavSourceOptions,
    apply_trim,
    load_source,
    source_index_path,
    validate_source_index,
)
from frame_compare.vs.types import SourceInfo


@pytest.fixture(autouse=True)
def _stub_hdr_probe(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("vs_required") is not None:
        return
    monkeypatch.setattr(
        source_module, "resolve_optional_executable", lambda _executable: "/fake/ffprobe"
    )
    monkeypatch.setattr(source_module, "probe_video_streams", lambda _path: [])
    monkeypatch.setattr(source_module, "probe_hdr_metadata", lambda _path, **_kwargs: None)


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


def make_mock_core(with_lsmas: bool = True, fail_load: bool = False) -> SimpleNamespace:
    """Create mock VS core with optional lsmas plugin.

    Args:
        with_lsmas: Whether lsmas plugin is available
        fail_load: If True, LWLibavSource raises Exception
    """
    core = SimpleNamespace()

    def mock_loader(path: str, **_kwargs: object):
        if fail_load:
            raise Exception("File corrupt")
        return MockClip()

    loader = SimpleNamespace(LWLibavSource=mock_loader)

    if with_lsmas:
        core.lsmas = loader
    return core


def _index_kwargs(path: str | Path) -> dict[str, object]:
    return {"cachefile": str(source_index_path(Path(path)))}


def test_load_source_returns_source_info():
    core = make_mock_core(with_lsmas=True)
    source = load_source(Path("video.mkv"), cast(Core, core))
    assert source.width == 1920
    assert source.height == 1080
    assert source.num_frames == 1000


def test_load_source_extracts_fps():
    core = make_mock_core(with_lsmas=True)
    source = load_source(Path("video.mkv"), cast(Core, core))
    assert source.fps == Fraction(24, 1)


def test_load_source_default_does_not_forward_decoder_kwargs():
    calls: list[tuple[str, dict[str, object]]] = []

    def loader(path: str, **kwargs: object) -> MockClip:
        calls.append((path, kwargs))
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    load_source(Path("video.mkv"), cast(Core, core))

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

    validate_source_index(video, cast(Core, core))

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
        validate_source_index(video, cast(Core, core))


def test_load_source_forwards_explicit_decoder_options():
    calls: list[tuple[str, dict[str, object]]] = []

    def loader(path: str, **kwargs: object) -> MockClip:
        calls.append((path, kwargs))
        return MockClip()

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    load_source(
        Path("video.mkv"),
        cast(Core, core),
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
        load_source(Path("video.mkv"), cast(Core, core))
    assert exc.value.code == "FC-2003"


def test_load_source_file_error_raises_source_load_error(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def loader(_path: str, **kwargs: object) -> MockClip:
        calls.append(kwargs)
        raise RuntimeError("File corrupt")

    core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))

    with pytest.raises(SourceLoadError) as exc:
        load_source(tmp_path / "video.mkv", cast(Core, core))

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

    source = load_source(
        video_path,
        cast(Core, core),
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
        load_source(video_path, cast(Core, core))

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
        load_source(video_path, cast(Core, core))

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
        source = load_source(video_path, cast(Core, core))

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
        load_source(video_path, cast(Core, core))

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
    load_source(video_path, cast(Core, core))

    assert calls == [_index_kwargs(video_path)]
    assert legacy_index.read_bytes() == b"legacy"


# HDR Detection Tests


def test_load_source_falls_back_to_ffprobe_for_absent_hdr_props(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.vs.types import HDRMetadata

    probe_hdr_metadata = MagicMock(
        return_value=HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=9,
            transfer=16,
            matrix=9,
        )
    )
    monkeypatch.setattr(source_module, "probe_hdr_metadata", probe_hdr_metadata)

    source = load_source(Path("video.mkv"), cast(Core, make_mock_core()))

    assert source.is_hdr is True
    assert source.hdr_metadata is not None
    assert source.hdr_metadata.transfer == 16
    assert source.hdr_metadata.color_primaries == 9
    probe_hdr_metadata.assert_called_once_with(Path("video.mkv"), streams=[])


def test_load_source_requires_ffprobe_for_unspecified_hdr_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_module, "resolve_optional_executable", lambda _executable: None)
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", raising=False)
    monkeypatch.setattr(source_module, "probe_hdr_metadata", hdr_probe_module.probe_hdr_metadata)
    monkeypatch.setattr(source_module, "probe_video_streams", hdr_probe_module.probe_video_streams)

    with pytest.raises(SourceLoadError) as exc_info:
        load_source(Path("video.mkv"), cast(Core, make_mock_core()))

    assert exc_info.value.code == "FC-4015"
    assert isinstance(exc_info.value.__cause__, hdr_probe_module.FFmpegNotFoundError)
    assert isinstance(exc_info.value.__cause__.__cause__, FileNotFoundError)
    assert "ffprobe" in str(exc_info.value.__cause__.__cause__)


def test_load_source_loads_signaled_source_without_ffprobe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_module, "resolve_optional_executable", lambda _executable: None)
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", raising=False)
    hdr_probe = MagicMock(wraps=hdr_probe_module.probe_hdr_metadata)
    stream_probe = MagicMock(wraps=hdr_probe_module.probe_video_streams)
    monkeypatch.setattr(source_module, "probe_hdr_metadata", hdr_probe)
    monkeypatch.setattr(source_module, "probe_video_streams", stream_probe)
    props = {"_Primaries": 1, "_Transfer": 1, "_Matrix": 1}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(LWLibavSource=lambda _p, **_kwargs: MockClip(frame_props=props))
    )

    source = load_source(Path("video.mkv"), cast(Core, core))

    assert source.num_frames == 1000
    assert source.is_hdr is False
    hdr_probe.assert_not_called()
    stream_probe.assert_not_called()


def test_load_source_falls_back_to_ffprobe_for_unspecified_hdr_props(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.vs.types import HDRMetadata

    props = {"_Transfer": 2, "_Primaries": 2}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(LWLibavSource=lambda _p, **_kwargs: MockClip(frame_props=props))
    )
    monkeypatch.setattr(
        source_module,
        "probe_hdr_metadata",
        lambda _path, **_kwargs: HDRMetadata(None, None, None, 9, 18, 9),
    )

    source = load_source(Path("video.mkv"), cast(Core, core))

    assert source.is_hdr is True
    assert source.hdr_metadata is not None
    assert source.hdr_metadata.transfer == 18


def test_load_source_merges_partial_frame_signal_before_hdr_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.vs.types import HDRMetadata

    props = {
        "_Transfer": 16,
        "_Primaries": 2,
        "_Matrix": 9,
        "MasteringDisplayPrimaries": "frame mastering",
        "ContentLightLevelMax": 1000,
        "ContentLightLevelAverage": 400,
    }
    core = SimpleNamespace(
        lsmas=SimpleNamespace(LWLibavSource=lambda _p, **_kwargs: MockClip(frame_props=props))
    )
    monkeypatch.setattr(
        source_module,
        "probe_hdr_metadata",
        lambda _path, **_kwargs: HDRMetadata("probe mastering", 900, 350, 9, 1, 1),
    )

    source = load_source(Path("video.mkv"), cast(Core, core))

    assert source.is_hdr is True
    assert source.hdr_metadata == HDRMetadata("frame mastering", 1000, 400, 9, 16, 9)


@pytest.mark.parametrize(
    ("props", "probed_metadata"),
    [
        (
            {"_Transfer": 16, "_Primaries": 2, "_Matrix": 9},
            (9, 2, 2),
        ),
        (
            {"_Transfer": 2, "_Primaries": 9, "_Matrix": 9},
            (2, 16, 2),
        ),
    ],
)
def test_load_source_combines_partial_frame_and_probe_signal_for_hdr(
    monkeypatch: pytest.MonkeyPatch,
    props: dict[str, object],
    probed_metadata: tuple[int, int, int],
) -> None:
    from frame_compare.vs.types import HDRMetadata

    core = SimpleNamespace(
        lsmas=SimpleNamespace(LWLibavSource=lambda _p, **_kwargs: MockClip(frame_props=props))
    )
    primaries, transfer, matrix = probed_metadata
    monkeypatch.setattr(
        source_module,
        "probe_hdr_metadata",
        lambda _path, **_kwargs: HDRMetadata(None, None, None, primaries, transfer, matrix),
    )

    source = load_source(Path("video.mkv"), cast(Core, core))

    assert source.is_hdr is True
    assert source.hdr_metadata == HDRMetadata(None, None, None, 9, 16, 9)


def test_load_source_backfills_malformed_matrix_without_overriding_explicit_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.vs.types import HDRMetadata

    props = {"_Transfer": b"16", "_Primaries": "9", "_Matrix": "malformed"}
    core = SimpleNamespace(
        lsmas=SimpleNamespace(LWLibavSource=lambda _p, **_kwargs: MockClip(frame_props=props))
    )
    probe = MagicMock(return_value=HDRMetadata(None, None, None, 1, 1, 9))
    monkeypatch.setattr(source_module, "probe_hdr_metadata", probe)

    source = load_source(Path("video.mkv"), cast(Core, core))

    assert source.is_hdr is True
    assert source.hdr_metadata == HDRMetadata(None, None, None, 9, 16, 9)
    probe.assert_called_once_with(Path("video.mkv"), streams=[])


@pytest.mark.parametrize("matrix", [None, "malformed"])
def test_load_source_keeps_explicit_sdr_without_ffprobe(
    monkeypatch: pytest.MonkeyPatch,
    matrix: object,
) -> None:
    props: dict[str, object] = {"_Transfer": 1, "_Primaries": 1}
    if matrix is not None:
        props["_Matrix"] = matrix
    core = SimpleNamespace(
        lsmas=SimpleNamespace(LWLibavSource=lambda _p, **_kwargs: MockClip(frame_props=props))
    )
    probe_hdr_metadata = MagicMock(side_effect=RuntimeError("ffprobe failed"))
    monkeypatch.setattr(source_module, "probe_hdr_metadata", probe_hdr_metadata)

    source = load_source(Path("video.mkv"), cast(Core, core))

    assert source.is_hdr is False
    assert source.hdr_metadata is None
    probe_hdr_metadata.assert_not_called()


def test_load_source_wraps_malformed_ffprobe_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.utils.ffmpeg_errors import FFmpegError

    def fail_probe(_path: Path, **_kwargs: object) -> None:
        raise FFmpegError("ffprobe returned invalid json", 0)

    monkeypatch.setattr(source_module, "probe_hdr_metadata", fail_probe)

    with pytest.raises(SourceLoadError) as exc_info:
        load_source(Path("video.mkv"), cast(Core, make_mock_core()))

    assert exc_info.value.code == "FC-4015"


# Apply Trim Tests


@pytest.mark.parametrize(
    "end, expected_frames", [(200, 101), (None, 900)], ids=["inclusive_end", "to_end"]
)
def test_apply_trim_frame_count(end: int | None, expected_frames: int) -> None:
    clip = MockClip(num_frames=1000)
    source = SourceInfo(
        clip=cast(VideoNode, clip),
        width=1920,
        height=1080,
        num_frames=1000,
        fps=Fraction(24, 1),
        format=cast(VideoFormat, SimpleNamespace()),
        frame_props={},
        is_hdr=False,
        hdr_metadata=None,
    )
    trimmed = apply_trim(source, 100, end)
    assert trimmed.num_frames == expected_frames


@pytest.mark.parametrize(
    "props, expected_hdr, expected_metadata, metadata_none",
    [
        pytest.param(
            {"_Transfer": 16, "_Primaries": 9},
            True,
            {"transfer": 16, "color_primaries": 9},
            False,
            id="pq_bt2020",
        ),
        pytest.param({"_Transfer": 18, "_Primaries": 9}, True, {}, False, id="hlg_bt2020"),
        pytest.param({"_Transfer": 16, "_Primaries": 1}, False, {}, True, id="pq_bt709"),
        pytest.param({"_Transfer": 1, "_Primaries": 1}, False, {}, False, id="sdr"),
        pytest.param(
            {
                "_Transfer": 16,
                "_Primaries": 9,
                "MasteringDisplayPrimaries": "Display P3",
                "ContentLightLevelMax": 1000,
                "ContentLightLevelAverage": 400,
                "_Matrix": 9,
            },
            None,
            {"mastering_display": "Display P3", "max_cll": 1000, "max_fall": 400, "matrix": 9},
            False,
            id="metadata_fields",
        ),
        pytest.param({}, False, {}, True, id="empty"),
        pytest.param(
            {"_Transfer": 16, "_Primaries": 9}, True, {"matrix": 2}, False, id="default_matrix"
        ),
    ],
)
def test_load_source_hdr_cases(
    props: dict[str, object],
    expected_hdr: bool | None,
    expected_metadata: dict[str, object],
    metadata_none: bool,
) -> None:
    core = SimpleNamespace(
        lsmas=SimpleNamespace(LWLibavSource=lambda _p, **_kwargs: MockClip(frame_props=props))
    )
    source = load_source(Path("video.mkv"), cast(Core, core))
    if expected_hdr is not None:
        assert source.is_hdr is expected_hdr
    if metadata_none:
        assert source.hdr_metadata is None
    if expected_metadata:
        assert source.hdr_metadata is not None
        for field, value in expected_metadata.items():
            assert getattr(source.hdr_metadata, field) == value


@pytest.mark.parametrize(
    ("stage", "ffprobe_available", "signaled_sdr"),
    [
        pytest.param("load", True, False, id="load"),
        pytest.param("index_retry", True, False, id="index-retry"),
        pytest.param("frame", True, False, id="frame-unspecified-with-probe"),
        pytest.param("frame", False, False, id="frame-unspecified-without-probe"),
        pytest.param("frame", True, True, id="frame-sdr-with-probe"),
        pytest.param("frame", False, True, id="frame-sdr-without-probe"),
    ],
)
def test_load_source_stops_native_admission_after_interruption(
    stage: str,
    ffprobe_available: bool,
    signaled_sdr: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint

    video_path = tmp_path / "video.mkv"
    index_path = source_index_path(video_path)
    index_path.write_bytes(b"existing-index")
    calls: list[str] = []
    monkeypatch.setattr(
        source_module,
        "resolve_optional_executable",
        lambda _executable: "/fake/ffprobe" if ffprobe_available else None,
    )

    async def run() -> None:
        task = asyncio.current_task()
        assert task is not None

        class InterruptingClip(MockClip):
            def get_frame(self, n: int) -> SimpleNamespace:
                calls.append("frame")
                if stage == "frame":
                    task.cancel()
                return super().get_frame(n)

        def loader(_path: str, **_kwargs: object) -> MockClip:
            calls.append("load")
            if stage in {"load", "index_retry"}:
                task.cancel()
            if stage == "index_retry":
                raise RuntimeError("failed to construct index")
            return InterruptingClip(
                frame_props={"_Primaries": 1, "_Transfer": 1, "_Matrix": 1} if signaled_sdr else {}
            )

        def probe(_path: Path, **_kwargs: object) -> None:
            calls.append("probe")

        monkeypatch.setattr(source_module, "probe_hdr_metadata", probe)
        core = SimpleNamespace(lsmas=SimpleNamespace(LWLibavSource=loader))
        with pytest.raises(_RunInterrupt):
            load_source(video_path, cast(Core, core))
        assert calls == (["load", "frame"] if stage == "frame" else ["load"])
        assert index_path.read_bytes() == b"existing-index"
        assert task.cancelling() == 1
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())


@pytest.mark.vs_required
@pytest.mark.parametrize(
    "mode",
    [
        "multiple-video",
        "attached-cover",
        "no-ffprobe",
        "no-ffprobe-untagged",
        "multiple-override",
        "cover-override",
        "invalid-override",
    ],
)
def test_load_source_real_video_stream_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    import json
    import shutil

    import vapoursynth as vs
    from PIL import Image

    from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
    from frame_compare.utils.subproc import run_subprocess
    from frame_compare.vs.hdr_probe import probe_hdr_metadata

    if isinstance(cast(object, vs), MagicMock) or not hasattr(vs.core, "lsmas"):
        pytest.skip("native VapourSynth with L-SMASH is unavailable")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are unavailable")
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    assert ffprobe is not None and ffmpeg is not None
    video = tmp_path / "streams.mp4"
    if mode in {"no-ffprobe", "no-ffprobe-untagged"}:
        color_tags = (
            [
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-colorspace",
                "bt709",
                "-x264-params",
                "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            ]
            if mode == "no-ffprobe"
            else []
        )
        run_subprocess(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=white:s=32x24:r=2",
                "-frames:v",
                "2",
                "-c:v",
                "libx264",
                *color_tags,
                str(video),
            ],
            timeout_seconds=15,
        )
        monkeypatch.delenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", raising=False)
        monkeypatch.setenv("PATH", "")
        if mode == "no-ffprobe-untagged":
            with pytest.raises(SourceLoadError) as exc_info:
                load_source(video)
            assert exc_info.value.code == "FC-4015"
            assert isinstance(exc_info.value.__cause__, hdr_probe_module.FFmpegNotFoundError)
            assert isinstance(exc_info.value.__cause__.__cause__, FileNotFoundError)
            assert "ffprobe" in str(exc_info.value.__cause__.__cause__)
            return
        source = load_source(video)
        assert (source.width, source.height) == (32, 24)
        assert source.is_hdr is False
        return
    if mode in {"multiple-video", "multiple-override", "invalid-override"}:
        inputs = [
            "-f",
            "lavfi",
            "-i",
            "color=red:s=64x48:r=2",
            "-f",
            "lavfi",
            "-i",
            "color=white:s=32x24:r=2",
        ]
        encoding = ["-c:v", "libx264", "-frames:v", "2"]
    else:
        cover = tmp_path / "cover.png"
        Image.new("RGB", (64, 48), (255, 0, 0)).save(cover)
        # Map the cover first; the MP4 demuxer may expose cover art after tracks.
        inputs = ["-i", str(cover), "-f", "lavfi", "-i", "color=white:s=32x24:r=2"]
        encoding = [
            "-c:v:0",
            "png",
            "-disposition:v:0",
            "attached_pic",
            "-c:v:1",
            "libx264",
            "-frames:v:1",
            "2",
            "-x264-params:v:1",
            "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc",
            "-color_primaries:v:1",
            "bt2020",
            "-color_trc:v:1",
            "smpte2084",
            "-colorspace:v:1",
            "bt2020nc",
        ]
    run_subprocess(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            *inputs,
            "-map",
            "0:v",
            "-map",
            "1:v",
            *encoding,
            str(video),
        ],
        timeout_seconds=15,
    )
    if mode.endswith("-override"):
        monkeypatch.setenv("PATH", "")
        monkeypatch.setenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", ffprobe)
        monkeypatch.setenv("FRAME_COMPARE_FFMPEG_EXECUTABLE", ffmpeg)
    if mode == "invalid-override":
        monkeypatch.setenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", str(tmp_path / "missing-ffprobe"))
        with pytest.raises(SourceLoadError):
            load_source(video)
        assert not source_index_path(video).exists()
        return
    if mode in {"multiple-video", "multiple-override"}:
        with pytest.raises(SourceLoadError, match="multiple video streams are not supported"):
            load_source(video)
        assert not source_index_path(video).exists()
        return
    # This generated MP4 has one track and cover metadata at the end of moov.
    # Put udta before trak so the demuxer discovers the attached picture first.
    # Atom byte counts stay unchanged, preserving every media chunk offset.
    data = video.read_bytes()
    moov_start = data.index(b"moov") - 4
    moov_size = int.from_bytes(data[moov_start : moov_start + 4], "big")
    assert moov_size >= 8 and moov_start + moov_size == len(data)
    children: list[bytes] = []
    cursor = moov_start + 8
    while cursor < len(data):
        size = int.from_bytes(data[cursor : cursor + 4], "big")
        assert 8 <= size <= len(data) - cursor
        children.append(data[cursor : cursor + size])
        cursor += size
    assert [child[4:8] for child in children] == [b"mvhd", b"trak", b"udta"]
    video.write_bytes(data[: moov_start + 8] + children[0] + children[2] + children[1])
    stream_probe = run_subprocess(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video)],
        timeout_seconds=15,
    )
    streams = json.loads(stream_probe.stdout)["streams"]
    assert [(stream["index"], stream["disposition"]["attached_pic"]) for stream in streams] == [
        (0, 1),
        (1, 0),
    ]
    source = load_source(video)
    assert (source.width, source.height) == (32, 24)
    assert source.is_hdr is True
    metadata = probe_hdr_metadata(video)
    assert metadata is not None
    assert (metadata.color_primaries, metadata.transfer, metadata.matrix) == (9, 16, 9)
    runner = DefaultFFmpegRunner()
    output = tmp_path / "single.png"
    runner.extract_frame(video, 0, output)
    runner.extract_frames(video, [0, 1], tmp_path / "batch")
    for screenshot in [output, *sorted((tmp_path / "batch").glob("*.png"))]:
        with Image.open(screenshot) as image:
            assert image.size == (32, 24)
            pixel = image.convert("RGB").getpixel((16, 12))
            assert isinstance(pixel, tuple)
            assert min(pixel) >= 250
