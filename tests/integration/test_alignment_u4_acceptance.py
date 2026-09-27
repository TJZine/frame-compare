"""U4 acceptance matrix over deterministic ten-minute L-SMASH media."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.env import detect_plugins, ensure_vs_environment
from frame_compare.vs.errors import VapourSynthError, VapourSynthNotFoundError
from frame_compare.vs.loader import DefaultVSLoader
from tests.services.alignment_request_test_support import alignment_request

vs_mod = pytest.importorskip("vapoursynth")
if isinstance(vs_mod, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)

try:
    _core = ensure_vs_environment()
except (VapourSynthNotFoundError, VapourSynthError) as exc:
    pytest.skip(f"vapoursynth not available: {exc}", allow_module_level=True)

if not detect_plugins(_core).get("lsmas", False):
    pytest.skip("lsmas plugin not available", allow_module_level=True)

_DURATION = 600
_CHUNK_SECONDS = 30
_CHUNK_COUNT = _DURATION // _CHUNK_SECONDS
_FPS = 24
_VIDEO_SIZE = "128x72"
_SAMPLE_RATE = 48000
_BASE_AUDIO = f"anoisesrc=color=white:sample_rate={_SAMPLE_RATE}:duration={_DURATION}:seed=1101"
_OTHER_AUDIO = f"anoisesrc=color=pink:sample_rate={_SAMPLE_RATE}:duration={_DURATION}:seed=3303"


@dataclass(frozen=True)
class _MediaSet:
    reference: Path
    comparisons: dict[str, Path]
    multipath_reference: Path


def _run_ffmpeg(argv: list[str], *, timeout_seconds: int = 600) -> None:
    run_subprocess(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *argv],
        timeout_seconds=timeout_seconds,
    )


def _source(kind: str, duration: float) -> str:
    if kind == "video":
        return f"testsrc2=size={_VIDEO_SIZE}:rate={_FPS}:duration={duration}"
    return kind


def _write_media(
    path: Path,
    *,
    audio_graph: str = "[1:a]anull[a]",
    video_graph: str = "[0:v]null[v]",
    audio_sources: tuple[str, ...] = (),
    video_sources: tuple[str, ...] = (),
) -> None:
    video_inputs = (_source("video", _DURATION), *video_sources)
    audio_inputs = (_BASE_AUDIO, *audio_sources)
    argv: list[str] = []
    for source in (*video_inputs, *audio_inputs):
        argv.extend(["-f", "lavfi", "-i", source])
    _run_ffmpeg(
        [
            *argv,
            "-filter_complex",
            f"{video_graph};{audio_graph}",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(path),
        ]
    )


def _splice_graph(
    *,
    delayed: tuple[int, ...] = (),
    delay_ms: int = 10,
) -> str:
    pieces: list[str] = []
    graph: list[str] = []
    for index in range(_CHUNK_COUNT):
        start = index * _CHUNK_SECONDS
        label = f"a{index}"
        piece = f"[1:a]atrim=start={start}:end={start + _CHUNK_SECONDS},asetpts=PTS-STARTPTS"
        if index in delayed:
            piece += f",adelay={delay_ms}:all=1,atrim=duration=30"
        graph.append(f"{piece}[{label}]")
        pieces.append(f"[{label}]")
    graph.append("".join(pieces) + f"concat=n={_CHUNK_COUNT}:v=0:a=1[a]")
    return ";".join(graph)


def _multipath_graph(*, reverse_chunks: tuple[int, ...] = (8, 9)) -> str:
    graph: list[str] = []
    pieces: list[str] = []
    for index in range(_CHUNK_COUNT):
        label = f"a{index}"
        start = index * _CHUNK_SECONDS
        source = f"m{index}"
        delayed = f"d{index}"
        weights = "0.1 1.0" if index in reverse_chunks else "1.0 0.1"
        graph.extend(
            [
                f"[1:a]atrim=start={start}:end={start + _CHUNK_SECONDS},"
                f"asetpts=PTS-STARTPTS[{source}]",
                f"[{source}]asplit=2[m{index}][c{index}]",
                f"[c{index}]adelay=30:all=1,atrim=duration=30[{delayed}]",
                f"[m{index}][{delayed}]amix=inputs=2:duration=first:"
                f"weights={weights}:normalize=0[{label}]",
            ]
        )
        pieces.append(f"[{label}]")
    graph.append("".join(pieces) + f"concat=n={_CHUNK_COUNT}:v=0:a=1[a]")
    return ";".join(graph)


def _span_delay_graph(first_chunk: int, last_chunk: int, delay_ms: int) -> str:
    start = first_chunk * _CHUNK_SECONDS
    end = (last_chunk + 1) * _CHUNK_SECONDS
    graph = [
        f"[1:a]atrim=start=0:end={start},asetpts=PTS-STARTPTS[before]",
        f"[1:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
        f"adelay={delay_ms}:all=1,atrim=duration={end - start}[middle]",
        f"[1:a]atrim=start={end}:end={_DURATION},asetpts=PTS-STARTPTS[after]",
        "[before][middle][after]concat=n=3:v=0:a=1[a]",
    ]
    return ";".join(graph)


def _write_insert(
    path: Path, at_seconds: int, *, low_motion: bool = False, noisy_tail: bool = False
) -> None:
    base_video = "[0:v]null,split=2[base_a][base_b]"
    if low_motion:
        base_video = r"[0:v]drawbox=x=0:y=0:w=128:h=72:color=black:t=fill:enable=between(t\,0\,60),split=2[base_a][base_b]"
    video_graph = ";".join(
        [
            base_video,
            f"[base_a]trim=start=0:end={at_seconds},setpts=PTS-STARTPTS[v0]",
            "[1:v]setpts=PTS-STARTPTS[v1]",
            f"[base_b]trim=start={at_seconds}:end={_DURATION},setpts=PTS-STARTPTS[v2]",
            "[v0][v1][v2]concat=n=3:v=1:a=0[v]",
        ]
    )
    tail = f"[2:a]atrim=start={at_seconds}:end={_DURATION},asetpts=PTS-STARTPTS[tail]"
    audio_graph = ";".join(
        [
            f"[2:a]atrim=start=0:end={at_seconds},asetpts=PTS-STARTPTS[a0]",
            tail,
        ]
    )
    if noisy_tail:
        audio_graph += (
            ";[tail]volume=0.02[tail_signal]"
            ";[4:a]volume=1.0[tail_noise]"
            ";[tail_signal][tail_noise]amix=inputs=2:duration=first:"
            "weights=1 1:normalize=0[tail_mix]"
        )
        tail_label = "tail_mix"
    else:
        tail_label = "tail"
    audio_graph += f";[3:a]atrim=duration=4,asetpts=PTS-STARTPTS[insert];[a0][insert][{tail_label}]concat=n=3:v=0:a=1[a]"
    # The second video input is the four-second inserted segment. Audio inputs
    # are base, foreign insert, and optionally an unrelated tail source.
    _write_media(
        path,
        audio_graph=audio_graph,
        video_graph=video_graph,
        video_sources=("color=c=black:size=128x72:r=24:d=4",),
        audio_sources=("anullsrc=channel_layout=mono:sample_rate=48000:d=4", _OTHER_AUDIO)
        if noisy_tail
        else ("anullsrc=channel_layout=mono:sample_rate=48000:d=4",),
    )


def _write_replacement(path: Path, duration_seconds: int) -> None:
    video = rf"[0:v]drawbox=x=0:y=0:w=128:h=72:color=black:t=fill:enable=between(t\,300\,{300 + duration_seconds})[v]"
    _write_media(path, video_graph=video)


def _write_low_motion_cue(path: Path) -> None:
    video = r"[0:v]drawbox=x=0:y=0:w=128:h=72:color=black:t=fill:enable=between(t\,299\,331)[v]"
    _write_media(path, video_graph=video, audio_graph=_splice_graph(delayed=(10,), delay_ms=100))


def _write_active_tail(path: Path) -> None:
    _write_insert(path, 540, noisy_tail=True)


def _write_media_set(root: Path) -> _MediaSet:
    reference = root / "u4-reference.mkv"
    if not reference.exists():
        _write_media(reference)
    multipath_reference = root / "u4-multipath-reference.mkv"
    if not multipath_reference.exists():
        _write_media(multipath_reference, audio_graph=_multipath_graph(reverse_chunks=()))
    comparisons: dict[str, Path] = {}

    def add(name: str, writer: Callable[[Path], None]) -> None:
        path = root / f"u4-{name}.mkv"
        if not path.exists():
            writer(path)
        comparisons[name] = path

    add("insert-60", lambda path: _write_insert(path, 60))
    add("insert-540", lambda path: _write_insert(path, 540))
    add("insert-570", lambda path: _write_insert(path, 570))
    add("insert-60-low-motion", lambda path: _write_insert(path, 60, low_motion=True))
    add("replacement-4", lambda path: _write_replacement(path, 4))
    add("replacement-30", lambda path: _write_replacement(path, 30))
    add(
        "false-cue",
        lambda path: _write_media(path, audio_graph=_splice_graph(delayed=(10,), delay_ms=100)),
    )
    add("false-cue-low-motion", _write_low_motion_cue)
    add(
        "budget",
        lambda path: _write_media(
            path,
            audio_graph=_splice_graph(delayed=(1, 5, 9, 13), delay_ms=100),
        ),
    )
    add("active-tail", _write_active_tail)
    add("multipath", lambda path: _write_media(path, audio_graph=_multipath_graph()))
    add("same-frame", lambda path: _write_media(path, audio_graph=_splice_graph(delayed=(10,))))
    add(
        "many-same-frame",
        lambda path: _write_media(path, audio_graph=_splice_graph(delayed=(2, 5, 8, 11, 14, 17))),
    )
    add(
        "run-resolved",
        lambda path: _write_media(path, audio_graph=_span_delay_graph(6, 7, 100)),
    )
    add(
        "loudness",
        lambda path: _write_media(
            path,
            audio_graph=(
                r"[1:a]atrim=start=0:end=100,asetpts=PTS-STARTPTS[a0];"
                r"[1:a]atrim=start=100:end=130,asetpts=PTS-STARTPTS,volume=3.16227766[a1];"
                r"[1:a]atrim=start=130:end=200,asetpts=PTS-STARTPTS[a2];"
                r"[1:a]atrim=start=200:end=230,asetpts=PTS-STARTPTS,volume=0.31622777[a3];"
                r"[1:a]atrim=start=230:end=600,asetpts=PTS-STARTPTS[a4];"
                r"[a0][a1][a2][a3][a4]concat=n=5:v=0:a=1[a]"
            ),
        ),
    )
    add(
        "compression",
        lambda path: _write_media(
            path,
            audio_graph=(
                r"[1:a]atrim=start=0:end=200,asetpts=PTS-STARTPTS[a0];"
                r"[1:a]atrim=start=200:end=350,asetpts=PTS-STARTPTS,"
                r"acompressor=threshold=0.2:ratio=8:attack=20:release=200[a1];"
                r"[1:a]atrim=start=350:end=600,asetpts=PTS-STARTPTS[a2];"
                r"[a0][a1][a2]concat=n=3:v=0:a=1[a]"
            ),
        ),
    )
    add(
        "surround",
        lambda path: _write_media(
            path,
            audio_graph="[1:a]pan=stereo|FL=c0|FR=0.35*c0[a]",
        ),
    )
    add(
        "music-stem",
        lambda path: _write_media(
            path,
            audio_graph=(
                r"[2:a]volume=0.5:enable=between(t\,400\,460)[stem];"
                "[1:a][stem]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
            ),
            audio_sources=(_OTHER_AUDIO,),
        ),
    )
    add(
        "budget-7",
        lambda path: _write_media(
            path,
            audio_graph=_splice_graph(delayed=(1, 3, 5, 7, 9, 11, 13), delay_ms=100),
        ),
    )
    return _MediaSet(
        reference=reference,
        comparisons=comparisons,
        multipath_reference=multipath_reference,
    )


@pytest.fixture(scope="session")
def u4_media() -> Iterator[_MediaSet]:
    root = Path("generated") / "alignment-u4"
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield _write_media_set(root)
    finally:
        shutil.rmtree(root)


def _align_pair(
    media: _MediaSet,
    name: str,
    generated_dir: Path,
) -> AlignmentResult:
    comparison = media.comparisons[name]
    reference = media.multipath_reference if name == "multipath" else media.reference
    config = AlignmentConfig(cache_results=False, max_offset_seconds=30.0)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated_dir,
        fps_num=_FPS,
    )
    (result,) = asyncio.run(align_clips_from_request(request, config, vs_loader=DefaultVSLoader()))
    return result


def _assert_label(result: AlignmentResult, *, state: str, reason: str) -> None:
    assert result.applied is (state == "trusted_automatic")
    assert result.diagnostic == reason
    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.state == state
    assert result.audio_attempt.decision.primary_reason == reason


@pytest.mark.integration
@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("insert-60", "competing_offset_confirmed_by_video"),
        ("insert-540", "competing_offset_confirmed_by_video"),
        ("insert-570", "competing_offset_confirmed_by_video"),
    ],
)
def test_length_changing_inserts_are_not_applied(
    u4_media: _MediaSet, tmp_path: Path, name: str, reason: str
) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="provisional", reason=reason)


@pytest.mark.integration
def test_low_motion_insert_remains_a_competing_offset_hint(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    result = _align_pair(u4_media, "insert-60-low-motion", tmp_path / "generated")
    _assert_label(result, state="provisional", reason="competing_offset")
    assert result.audio_attempt is not None
    assert any(
        target.kind == "run" and target.resolution == "unresolved"
        for target in result.audio_attempt.video_check.targets
    )


@pytest.mark.integration
@pytest.mark.parametrize("name", ["replacement-4", "replacement-30"])
def test_same_length_replacements_apply(u4_media: _MediaSet, tmp_path: Path, name: str) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="trusted_automatic", reason="audio_video_confirmed")
    assert result.frame_offset == 0


@pytest.mark.integration
def test_repeated_cue_is_resolved_by_identical_moving_video(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    result = _align_pair(u4_media, "false-cue", tmp_path / "generated")
    _assert_label(result, state="trusted_automatic", reason="audio_video_confirmed")
    assert result.audio_attempt is not None
    assert result.audio_attempt.video_check.targets


@pytest.mark.integration
def test_low_motion_credible_disagreement_stays_unresolved(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    result = _align_pair(u4_media, "false-cue-low-motion", tmp_path / "generated")
    _assert_label(result, state="provisional", reason="unresolved_audio_disagreement")


@pytest.mark.integration
@pytest.mark.parametrize("name", ["budget", "budget-7"])
def test_budget_exhaustion_leaves_later_credible_targets_unexamined(
    u4_media: _MediaSet, tmp_path: Path, name: str
) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="provisional", reason="unresolved_audio_disagreement")
    assert result.audio_attempt is not None
    targets = result.audio_attempt.video_check.targets
    assert len(targets) >= 4
    assert any(target.resolution == "unexamined" for target in targets)
    assert all(target.kind == "chunk" for target in targets)
    if name == "budget-7":
        assert result.audio_attempt.audio.credible_chunks == 20
        assert result.audio_attempt.audio.agreeing_chunks == 13
        assert len(targets) >= 7


@pytest.mark.integration
def test_active_noncredible_shifted_tail_is_resolved_by_video(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    result = _align_pair(u4_media, "active-tail", tmp_path / "generated")
    _assert_label(result, state="provisional", reason="competing_offset_confirmed_by_video")
    assert result.audio_attempt is not None
    assert any(
        index >= 18 and not credible
        for index, credible in enumerate(result.audio_attempt.chunks.credible)
    )
    assert any(
        target.resolution == "alternative_confirmed"
        for target in result.audio_attempt.video_check.targets
    )


@pytest.mark.integration
@pytest.mark.parametrize("name", ["multipath", "same-frame", "many-same-frame", "run-resolved"])
def test_mix_caused_disagreements_still_apply(
    u4_media: _MediaSet, tmp_path: Path, name: str
) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="trusted_automatic", reason="audio_video_confirmed")
    assert result.frame_offset == 0
    assert result.audio_attempt is not None
    attempt = result.audio_attempt
    if name in {"multipath", "run-resolved"}:
        assert attempt.audio.credible_chunks == 20
        assert attempt.audio.agreeing_chunks == 18
        assert [(target.kind, target.resolution) for target in attempt.video_check.targets] == [
            ("run", "resolved")
        ]
    elif name == "same-frame":
        assert attempt.audio.agreeing_chunks == 19
        assert attempt.video_check.targets == ()
        assert len(attempt.video_check.same_frame_context) == 1
    else:
        assert attempt.audio.status == "no_single_offset"
        assert attempt.audio.agreeing_chunks == 14
        assert len(attempt.video_check.same_frame_context) == 6
        assert attempt.video_check.targets == ()


@pytest.mark.integration
@pytest.mark.parametrize("name", ["loudness", "compression", "surround", "music-stem"])
def test_refusal_principle_mix_changes_still_apply(
    u4_media: _MediaSet, tmp_path: Path, name: str
) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="trusted_automatic", reason="audio_video_confirmed")
    assert result.frame_offset == 0
