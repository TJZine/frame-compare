"""U4 acceptance matrix over deterministic ten-minute L-SMASH media."""

from __future__ import annotations

import asyncio
import math
import shutil
import statistics
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.analysis.window import SelectionWindow
from frame_compare.orchestration import preparation
from frame_compare.orchestration.context import (
    ClipActiveRect,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.execution_types import AlignPhaseOutput, PrepState
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.services import alignment_video
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_audio import (
    collection_argv,
    probe_streams,
    select_audio_pair,
)
from frame_compare.services.alignment_video import VideoClipRequest
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.alignment_policy import position_winner
from frame_compare.utils.alignment_review_projection import build_audio_review_presentation
from frame_compare.utils.subproc import run_subprocess
from frame_compare.utils.types import AlignmentClipIdentity
from frame_compare.vs.env import detect_plugins, ensure_vs_environment
from frame_compare.vs.errors import VapourSynthError, VapourSynthNotFoundError
from frame_compare.vs.loader import DefaultVSLoader
from tests.orchestration.phase_task_helpers import _create_config, _run_align_phase, _workspace
from tests.orchestration.preparation_test_support import (
    create_config as _create_prep_config,
)
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

if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
    pytest.skip("ffmpeg/ffprobe not available", allow_module_level=True)

_DURATION = 600
_CHUNK_SECONDS = 30
_CHUNK_COUNT = _DURATION // _CHUNK_SECONDS
_FPS = 24
_NTSC_RATE = "24000/1001"
_RETIMED_TRIM_FRAMES = 48
_VIDEO_SIZE = "128x72"
_SAMPLE_RATE = 48000
_BASE_AUDIO = f"anoisesrc=color=white:sample_rate={_SAMPLE_RATE}:duration={_DURATION}:seed=1101"
_OTHER_AUDIO = f"anoisesrc=color=pink:sample_rate={_SAMPLE_RATE}:duration={_DURATION}:seed=3303"
_MUSIC_CUE = (
    "aevalsrc=0.70*sin(2*PI*(180*t+18*t*t))+"
    "0.35*sin(2*PI*(270*t+11*t*t))+0.20*sin(2*PI*(360*t+7*t*t)):s=48000:d=25"
)
_MUSIC_STEM = "aevalsrc=0.18*sin(2*PI*196*t)+0.12*sin(2*PI*294*t)+0.08*sin(2*PI*392*t):s=48000:d=30"
_SURROUND_SOURCES = tuple(
    f"anoisesrc=color=white:sample_rate={_SAMPLE_RATE}:duration={_DURATION}:seed={seed}"
    for seed in (1101, 2202, 3303, 4404, 5505, 6606)
)


@dataclass(frozen=True)
class _MediaSet:
    reference: Path
    comparisons: dict[str, Path]
    multipath_reference: Path
    references: dict[str, Path]


def _run_ffmpeg(argv: list[str], *, timeout_seconds: int = 600) -> None:
    run_subprocess(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *argv],
        timeout_seconds=timeout_seconds,
    )


def _source(kind: str, duration: float, *, fps: str = str(_FPS)) -> str:
    if kind == "video":
        return f"testsrc2=size={_VIDEO_SIZE}:rate={fps}:duration={duration}"
    return kind


def _write_media(
    path: Path,
    *,
    audio_graph: str = "[1:a]anull[a]",
    video_graph: str = "[0:v]null[v]",
    base_audio: str = _BASE_AUDIO,
    audio_sources: tuple[str, ...] = (),
    video_sources: tuple[str, ...] = (),
    fps: str = str(_FPS),
) -> None:
    video_inputs = (_source("video", _DURATION, fps=fps), *video_sources)
    audio_inputs = (base_audio, *audio_sources)
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
    advanced: tuple[int, ...] = (),
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
        elif index in advanced:
            seconds = delay_ms / 1000
            piece += f",atrim=start={seconds},apad=pad_dur={seconds},atrim=duration=30"
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
        low_motion_start, low_motion_end = (
            (0, at_seconds) if at_seconds <= _DURATION // 2 else (at_seconds - 2, _DURATION)
        )
        base_video = (
            "[0:v]drawbox=x=0:y=0:w=128:h=72:color=black:t=fill:"
            f"enable=between(t\\,{low_motion_start}\\,{low_motion_end}),"
            "split=2[base_a][base_b]"
        )
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


def _write_flat_video(path: Path) -> None:
    _write_media(path, video_graph="[0:v]drawbox=x=0:y=0:w=128:h=72:color=black:t=fill[v]")


def _write_low_motion_cue(path: Path) -> None:
    video = r"[0:v]drawbox=x=0:y=0:w=128:h=72:color=black:t=fill:enable=between(t\,299\,331)[v]"
    _write_media(path, video_graph=video, audio_graph=_splice_graph(delayed=(10,), delay_ms=100))


def _write_retimed(path: Path, reference: Path, *, fps: str, setpts: str, asetrate: int) -> None:
    """Trim the first 48 frames, then speed video and audio to ``fps`` (U4b)."""
    _run_ffmpeg(
        [
            "-i",
            str(reference),
            "-vf",
            f"trim=start_frame={_RETIMED_TRIM_FRAMES},setpts=PTS-STARTPTS,setpts={setpts}",
            "-af",
            f"atrim=start=2,asetpts=PTS-STARTPTS,asetrate={asetrate},aresample={_SAMPLE_RATE}",
            "-r",
            fps,
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
            str(path),
        ]
    )


def _write_retimed_25(path: Path, reference: Path) -> None:
    _write_retimed(path, reference, fps="25", setpts="PTS*24/25", asetrate=50000)


def _write_retimed_25_ntsc(path: Path, reference: Path) -> None:
    _write_retimed(path, reference, fps="25", setpts="PTS*960/1001", asetrate=50050)


def _write_retimed_ntsc(path: Path, reference: Path) -> None:
    _write_retimed(path, reference, fps="24", setpts="PTS*1000/1001", asetrate=48048)


def _write_retimed_insert(path: Path) -> None:
    staged = path.with_name(f".{path.stem}.insert{path.suffix}")
    try:
        _write_insert(staged, 300)
        _write_retimed_25(path, staged)
    finally:
        staged.unlink(missing_ok=True)


def _write_active_tail(path: Path) -> None:
    _write_insert(path, 540, noisy_tail=True)


def _write_active_tail_inconclusive(path: Path) -> None:
    _write_insert(path, 540, noisy_tail=True)
    temporary = path.with_name(f".{path.stem}.flat{path.suffix}")
    path.replace(temporary)
    try:
        _run_ffmpeg(
            [
                "-i",
                str(temporary),
                "-vf",
                r"drawbox=x=0:y=0:w=128:h=72:color=black:t=fill:enable=gte(t\,539)",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "18",
                "-c:a",
                "copy",
                str(path),
            ]
        )
    finally:
        temporary.unlink(missing_ok=True)


def _write_local_surround(path: Path) -> None:
    channels = "".join(f"[{index}:a]" for index in range(1, 7))
    normal = "pan=stereo|FL=0.80*c0+0.50*c2+0.30*c4+0.10*c3|FR=0.80*c1+0.50*c2+0.30*c5+0.10*c3"
    changed = "pan=stereo|FL=0.55*c0+0.70*c2+0.15*c4+0.10*c3|FR=0.55*c1+0.70*c2+0.15*c5+0.10*c3"
    _write_media(
        path,
        base_audio=_SURROUND_SOURCES[0],
        video_graph=(
            "[0:v]drawbox=x=0:y=0:w=128:h=18:color=white:t=fill,"
            "drawbox=x=0:y=54:w=128:h=18:color=white:t=fill,"
            "drawbox=x=0:y=0:w=32:h=72:color=white:t=fill,"
            "drawbox=x=96:y=0:w=32:h=72:color=white:t=fill[v]"
        ),
        audio_sources=_SURROUND_SOURCES[1:],
        audio_graph=(
            f"{channels}amerge=inputs=6,asplit=3[s0][s1][s2];"
            f"[s0]atrim=start=0:end=270,asetpts=PTS-STARTPTS,{normal}[a0];"
            f"[s1]atrim=start=270:end=300,asetpts=PTS-STARTPTS,{changed}[a1];"
            f"[s2]atrim=start=300:end=600,asetpts=PTS-STARTPTS,{normal}[a2];"
            "[a0][a1][a2]concat=n=3:v=0:a=1[a]"
        ),
    )


def _write_repeated_music_cue(path: Path, *, reference: bool) -> None:
    if reference:
        audio_graph = (
            "[1:a]atrim=start=0:end=305,asetpts=PTS-STARTPTS[a0];"
            "[2:a]asetpts=PTS-STARTPTS[a1];"
            "[1:a]atrim=start=330:end=600,asetpts=PTS-STARTPTS[a2];"
            "[a0][a1][a2]concat=n=3:v=0:a=1[a]"
        )
    else:
        audio_graph = (
            "[1:a]atrim=start=0:end=300,asetpts=PTS-STARTPTS[a0];"
            "[2:a]asetpts=PTS-STARTPTS[a1];"
            "[1:a]atrim=start=325:end=600,asetpts=PTS-STARTPTS[a2];"
            "[a0][a1][a2]concat=n=3:v=0:a=1[a]"
        )
    _write_media(path, audio_graph=audio_graph, audio_sources=(_MUSIC_CUE,))


def _write_surround(path: Path, *, downmix: bool) -> None:
    channels = "".join(f"[{index}:a]" for index in range(1, 7))
    layout = (
        "pan=stereo|FL=0.80*c0+0.50*c2+0.30*c4+0.10*c3|FR=0.80*c1+0.50*c2+0.30*c5+0.10*c3"
        if downmix
        else "pan=5.1|FL=c0|FR=c1|FC=c2|LFE=c3|BL=c4|BR=c5"
    )
    _write_media(
        path,
        base_audio=_SURROUND_SOURCES[0],
        audio_sources=_SURROUND_SOURCES[1:],
        audio_graph=f"{channels}amerge=inputs=6,{layout}[a]",
    )


def _write_music_stem(path: Path) -> None:
    _write_media(
        path,
        audio_sources=(_MUSIC_STEM,),
        audio_graph=(
            "[1:a]atrim=start=0:end=270,asetpts=PTS-STARTPTS[a0];"
            "[1:a]atrim=start=270:end=300,asetpts=PTS-STARTPTS[base];"
            "[2:a]asetpts=PTS-STARTPTS[stem];"
            "[base][stem]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix];"
            "[1:a]atrim=start=300:end=600,asetpts=PTS-STARTPTS[a2];"
            "[a0][mix][a2]concat=n=3:v=0:a=1[a]"
        ),
    )


def _atomic_write(path: Path, writer: Callable[[Path], None]) -> None:
    temporary = path.with_name(f".{path.stem}.tmp{path.suffix}")
    temporary.unlink(missing_ok=True)
    try:
        writer(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_media_set(root: Path) -> _MediaSet:
    reference = root / "u4-reference.mkv"
    references = {
        "repeated-music-cue": root / "u4-repeated-music-cue-reference.mkv",
        "surround": root / "u4-surround-reference.mkv",
        "surround-local": root / "u4-surround-reference.mkv",
        "flat-video": root / "u4-flat-video-reference.mkv",
        "retimed-ntsc": root / "u4-retimed-ntsc-reference.mkv",
        "retimed-25-ntsc": root / "u4-retimed-ntsc-reference.mkv",
    }
    if not reference.exists():
        _atomic_write(reference, _write_media)
    multipath_reference = root / "u4-multipath-reference.mkv"
    if not multipath_reference.exists():
        _atomic_write(
            multipath_reference,
            lambda path: _write_media(path, audio_graph=_multipath_graph(reverse_chunks=())),
        )
    if not references["repeated-music-cue"].exists():
        _atomic_write(
            references["repeated-music-cue"],
            lambda path: _write_repeated_music_cue(path, reference=True),
        )
    if not references["surround"].exists():
        _atomic_write(references["surround"], lambda path: _write_surround(path, downmix=False))
    if not references["flat-video"].exists():
        _atomic_write(references["flat-video"], _write_flat_video)
    if not references["retimed-ntsc"].exists():
        _atomic_write(
            references["retimed-ntsc"],
            lambda path: _write_media(path, fps=_NTSC_RATE),
        )
    comparisons: dict[str, Path] = {}

    def add(name: str, writer: Callable[[Path], None]) -> None:
        path = root / f"u4-{name}.mkv"
        if not path.exists():
            _atomic_write(path, writer)
        comparisons[name] = path

    add("insert-60", lambda path: _write_insert(path, 60))
    add("insert-540", lambda path: _write_insert(path, 540))
    add("insert-570", lambda path: _write_insert(path, 570))
    add("insert-60-low-motion", lambda path: _write_insert(path, 60, low_motion=True))
    add("insert-540-low-motion", lambda path: _write_insert(path, 540, low_motion=True))
    add("insert-570-low-motion", lambda path: _write_insert(path, 570, low_motion=True))
    add("replacement-4", lambda path: _write_replacement(path, 4))
    add("replacement-30", lambda path: _write_replacement(path, 30))
    add("repeated-music-cue", lambda path: _write_repeated_music_cue(path, reference=False))
    add("false-cue-low-motion", _write_low_motion_cue)
    add(
        "budget",
        lambda path: _write_media(
            path,
            audio_graph=_splice_graph(delayed=(1, 5, 9, 13), delay_ms=100),
        ),
    )
    add("active-tail", _write_active_tail)
    add("active-tail-inconclusive", _write_active_tail_inconclusive)
    add(
        "authority-fail", lambda path: _write_media(path, audio_graph=_span_delay_graph(6, 10, 100))
    )
    add("flat-video", _write_flat_video)
    add("multipath", lambda path: _write_media(path, audio_graph=_multipath_graph()))
    add("same-frame", lambda path: _write_media(path, audio_graph=_splice_graph(delayed=(10,))))
    add(
        "six-same-frame",
        lambda path: _write_media(
            path,
            audio_graph=_splice_graph(delayed=(8, 10, 12), advanced=(9, 11, 13)),
        ),
    )
    add(
        "many-same-frame",
        lambda path: _write_media(
            path,
            audio_graph=_splice_graph(
                delayed=(7, 9, 11, 13, 15, 17, 19),
                advanced=(8, 10, 12, 14, 16, 18),
            ),
        ),
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
    add("surround", lambda path: _write_surround(path, downmix=True))
    add("surround-local", _write_local_surround)
    add("music-stem", _write_music_stem)
    add(
        "budget-7",
        lambda path: _write_media(
            path,
            audio_graph=_splice_graph(delayed=(1, 3, 5, 7, 9, 11, 13), delay_ms=100),
        ),
    )
    add("retimed-25", lambda path: _write_retimed_25(path, reference))
    add("retimed-ntsc", lambda path: _write_retimed_ntsc(path, references["retimed-ntsc"]))
    add("retimed-25-ntsc", lambda path: _write_retimed_25_ntsc(path, references["retimed-ntsc"]))
    add("retimed-insert", _write_retimed_insert)
    add("insert-300", lambda path: _write_insert(path, 300))
    return _MediaSet(
        reference=reference,
        comparisons=comparisons,
        multipath_reference=multipath_reference,
        references=references,
    )


@pytest.fixture(scope="session")
def u4_media(tmp_path_factory: pytest.TempPathFactory) -> _MediaSet:
    return _write_media_set(tmp_path_factory.mktemp("alignment-u4"))


def _align_pair(
    media: _MediaSet,
    name: str,
    generated_dir: Path,
) -> AlignmentResult:
    comparison = media.comparisons[name]
    reference = (
        media.multipath_reference
        if name == "multipath"
        else media.references.get(name, media.reference)
    )
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


_PHASE_CONFIG = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[analysis]
random_frame_count = 0
random_seed = 7
user_frames = [100]

[audio_alignment]
enable = true
max_offset_seconds = 30.0
use_vsview = false
force_interactive = false
cache_results = true
channel_strategy = "mono_downmix"
previous_offsets = "disabled"

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def _real_clip(
    path: Path,
    label: str,
    *,
    crop: bool,
    source_fps: Fraction = Fraction(_FPS),
    fps: Fraction = Fraction(_FPS),
    num_frames: int = _DURATION * _FPS,
) -> ClipState:
    stat = path.stat()
    active_rect = (
        ClipActiveRect(
            x=32,
            y=18,
            width=64,
            height=36,
            source="metadata",
            detection_mode="provided",
        )
        if crop
        else None
    )
    probe = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path=path, size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns),
        width=128,
        height=72,
        num_frames=num_frames,
        fps=fps,
        is_hdr=False,
    )
    return ClipState(
        path=path,
        label=label,
        probe=probe,
        source_fps=source_fps,
        effective_fps=probe.fps,
        active_rect=active_rect,
    )


def _probe_frame_count(path: Path) -> int:
    """Return the real decoded video frame count of a generated file."""
    probe = run_subprocess(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "csv=p=0",
            str(path),
        ],
        timeout_seconds=300,
    )
    return int(probe.stdout.decode().strip())


def _phase_context(
    media: _MediaSet,
    name: str,
    root: Path,
    *,
    crop: bool,
    reference_fps: Fraction = Fraction(_FPS),
    comparison_source_fps: Fraction | None = None,
) -> RunContext:
    reference_path = (
        media.multipath_reference
        if name == "multipath"
        else media.references.get(name, media.reference)
    )
    workspace = _workspace(root)
    run_dir = workspace.generated_root / "run"
    workspace = replace(
        workspace,
        run_dir=run_dir,
        generated_dir=run_dir,
        screenshots_dir=run_dir / "screenshots",
    )
    if comparison_source_fps is None:
        reference = _real_clip(reference_path, "Reference", crop=crop)
        comparison = _real_clip(media.comparisons[name], "Comparison", crop=crop)
    else:
        reference = _real_clip(
            reference_path,
            "Reference",
            crop=crop,
            source_fps=reference_fps,
            fps=reference_fps,
            num_frames=_probe_frame_count(reference_path),
        )
        comparison = _real_clip(
            media.comparisons[name],
            "Comparison",
            crop=crop,
            source_fps=comparison_source_fps,
            fps=reference_fps,
            num_frames=_probe_frame_count(media.comparisons[name]),
        )
    return RunContext(
        config=_create_config(root, _PHASE_CONFIG),
        workspace=workspace,
        reference=reference,
        comparisons=[comparison],
        analysis_selection_domain="u4-phase",
        selection_window=SelectionWindow(0, reference.probe.num_frames),
        analysis_clip=reference,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    (
        "name",
        "state",
        "reason",
        "authority_passed",
        "confirmed_offset",
        "target_resolutions",
        "same_frame_count",
        "crop",
    ),
    [
        (
            "authority-fail",
            "provisional",
            "no_single_offset",
            False,
            0,
            ("resolved",),
            0,
            False,
        ),
        (
            "flat-video",
            "provisional",
            "video_check_inconclusive",
            None,
            None,
            (),
            0,
            False,
        ),
        (
            "insert-60-low-motion",
            "provisional",
            "competing_offset",
            True,
            -96,
            ("unresolved",),
            0,
            False,
        ),
        (
            "budget",
            "provisional",
            "unresolved_audio_disagreement",
            True,
            0,
            ("resolved", "resolved", "resolved", "unexamined"),
            0,
            False,
        ),
        (
            "active-tail",
            "provisional",
            "competing_offset_confirmed_by_video",
            True,
            0,
            ("alternative_confirmed", "alternative_confirmed"),
            0,
            False,
        ),
        (
            "active-tail-inconclusive",
            "trusted_automatic",
            "audio_video_confirmed",
            True,
            0,
            ("local_video_inconclusive", "local_video_inconclusive"),
            0,
            False,
        ),
        (
            "six-same-frame",
            "trusted_automatic",
            "audio_video_confirmed",
            True,
            0,
            (),
            6,
            False,
        ),
        (
            "many-same-frame",
            "trusted_automatic",
            "audio_video_confirmed",
            True,
            0,
            (),
            13,
            False,
        ),
        ("surround-local", "trusted_automatic", "audio_video_confirmed", True, 0, (), 0, True),
    ],
)
def test_real_phase_v6_cache_matrix(
    u4_media: _MediaSet,
    tmp_path: Path,
    name: str,
    state: str,
    reason: str,
    authority_passed: bool | None,
    confirmed_offset: int | None,
    target_resolutions: tuple[str, ...],
    same_frame_count: int,
    crop: bool,
) -> None:
    ctx = _phase_context(u4_media, name, tmp_path, crop=crop)

    output = _run_align_phase(ctx, selected_frames=[100], vs_loader=DefaultVSLoader())
    comparison = output.comparisons[0]
    attempt = comparison.audio_attempt

    assert attempt is not None
    assert attempt.decision.state == state
    assert attempt.decision.primary_reason == reason
    assert (comparison.alignment is not None) is (state == "trusted_automatic")
    assert output.reference.trim.trim_start_frames == 0
    assert comparison.trim.trim_start_frames == 0
    assert attempt.video_check.confirmed_offset == confirmed_offset
    assert tuple(target.resolution for target in attempt.video_check.targets) == target_resolutions
    assert len(attempt.video_check.same_frame_context) == same_frame_count
    if name in {"six-same-frame", "many-same-frame"}:
        expected_raw_agreeing = 14 if name == "six-same-frame" else 7
        assert attempt.audio.status == "no_single_offset"
        assert attempt.audio.credible_chunks == 20
        assert attempt.audio.agreeing_chunks == expected_raw_agreeing
        assert attempt.authority_recount is not None
        assert attempt.authority_recount.authority_agreeing_chunks == 20
    assert (
        attempt.authority_recount.passed if attempt.authority_recount is not None else None
    ) is authority_passed

    cache_path = ctx.workspace.shared_alignment_cache_dir / "alignment_reuse.toml"
    assert cache_path.exists() is (state == "trusted_automatic")
    if state == "trusted_automatic":
        cache = tomllib.loads(cache_path.read_text(encoding="utf-8"))
        source_sets = cache["source_sets"]
        assert isinstance(source_sets, dict) and len(source_sets) == 1
        source_set = next(iter(source_sets.values()))
        assert isinstance(source_set, dict)
        entries = source_set["entries"]
        assert isinstance(entries, dict) and len(entries) == 1
        entry = next(iter(entries.values()))
        assert isinstance(entry, dict)
        assert entry["frame_offset"] == 0
        assert entry["comparison_clip"] == ctx.comparisons[0].path.name


_RETIMED_RECIPE = (
    "ffmpeg -i <role_input> -map 0:a:<selected_ordinal> -vn "
    "[channel] -af <channel>[,aresample=<r1>,asetrate=<r2>],aresample=8000 -f f32le -"
)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("name", "reference_fps", "comparison_source_fps", "expected_scale"),
    [
        ("retimed-25", Fraction(_FPS), Fraction(25), Fraction(25, 24)),
        (
            "retimed-ntsc",
            Fraction(24000, 1001),
            Fraction(24),
            Fraction(1001, 1000),
        ),
        ("retimed-insert", Fraction(_FPS), Fraction(25), Fraction(25, 24)),
    ],
)
def test_retimed_sources_align_on_the_effective_timeline(
    u4_media: _MediaSet,
    tmp_path: Path,
    name: str,
    reference_fps: Fraction,
    comparison_source_fps: Fraction,
    expected_scale: Fraction,
) -> None:
    if name == "retimed-insert":
        retimed_root = tmp_path / "retimed"
        control_root = tmp_path / "control"
        retimed_root.mkdir()
        control_root.mkdir()
        ctx = _phase_context(
            u4_media,
            name,
            retimed_root,
            crop=False,
            reference_fps=reference_fps,
            comparison_source_fps=comparison_source_fps,
        )
        output = _run_align_phase(ctx, selected_frames=[100], vs_loader=DefaultVSLoader())
        attempt = output.comparisons[0].audio_attempt
        assert attempt is not None
        assert attempt.decision.state != "trusted_automatic"
        assert attempt.selected_streams[1].timeline_scale == expected_scale
        assert attempt.extraction_recipe == _RETIMED_RECIPE

        control_ctx = _phase_context(u4_media, "insert-300", control_root, crop=False)
        control_output = _run_align_phase(
            control_ctx, selected_frames=[100], vs_loader=DefaultVSLoader()
        )
        control_attempt = control_output.comparisons[0].audio_attempt
        assert control_attempt is not None
        assert control_attempt.decision.state != "trusted_automatic"
        assert attempt.decision.primary_reason == control_attempt.decision.primary_reason
        return

    ctx = _phase_context(
        u4_media,
        name,
        tmp_path,
        crop=False,
        reference_fps=reference_fps,
        comparison_source_fps=comparison_source_fps,
    )
    output = _run_align_phase(ctx, selected_frames=[100], vs_loader=DefaultVSLoader())
    comparison = output.comparisons[0]
    attempt = comparison.audio_attempt

    assert attempt is not None
    assert attempt.decision.state == "trusted_automatic"
    assert attempt.decision.primary_reason == "audio_video_confirmed"
    assert comparison.alignment is not None
    assert comparison.alignment.relative_offset_frames == 48
    assert output.reference.trim.trim_start_frames == 48
    assert comparison.trim.trim_start_frames == 0
    assert attempt.selected_streams[0].timeline_scale == 1
    assert attempt.selected_streams[1].timeline_scale == expected_scale
    assert attempt.extraction_recipe == _RETIMED_RECIPE

    cache_path = ctx.workspace.shared_alignment_cache_dir / "alignment_reuse.toml"
    assert cache_path.exists()
    cache = tomllib.loads(cache_path.read_text(encoding="utf-8"))
    source_sets = cache["source_sets"]
    assert isinstance(source_sets, dict) and len(source_sets) == 1
    source_set = next(iter(source_sets.values()))
    assert isinstance(source_set, dict)
    entries = source_set["entries"]
    assert isinstance(entries, dict) and len(entries) == 1
    entry = next(iter(entries.values()))
    assert isinstance(entry, dict)
    assert entry["frame_offset"] == 48
    assert entry["comparison_clip"] == ctx.comparisons[0].path.name


@pytest.mark.integration
def test_unretimed_source_keeps_the_plain_recipe(u4_media: _MediaSet, tmp_path: Path) -> None:
    ctx = _phase_context(u4_media, "six-same-frame", tmp_path, crop=False)
    output = _run_align_phase(ctx, selected_frames=[100], vs_loader=DefaultVSLoader())
    attempt = output.comparisons[0].audio_attempt

    assert attempt is not None
    assert attempt.decision.state == "trusted_automatic"
    assert attempt.selected_streams[0].timeline_scale == 1
    assert attempt.selected_streams[1].timeline_scale == 1

    reference_probe = probe_streams(ctx.reference.path)
    comparison_probe = probe_streams(ctx.comparisons[0].path)
    selection, _ = select_audio_pair(
        reference_probe,
        comparison_probe,
        reference_path=ctx.reference.path,
        comparison_path=ctx.comparisons[0].path,
        reference_override=None,
        comparison_override=None,
    )
    argv = collection_argv(
        ctx.reference.path,
        selection.stream,
        channel_strategy="mono_downmix",
        timeline_scale=Fraction(1),
    )
    audio_filters = argv[argv.index("-af") + 1]
    assert audio_filters.count("aresample") == 1
    assert "asetrate" not in audio_filters


_MATCH_FPS_PREP_CONFIG = (
    _PHASE_CONFIG + '\n[sources]\nreference = "00-reference.mkv"\nmatch_fps = "assume_reference"\n'
)


def _configured_prep_alignment(
    media: _MediaSet, name: str, root: Path
) -> tuple[PrepState, AlignPhaseOutput]:
    """Run one pair through match_fps preparation into the real align phase (U5)."""
    reference_path = media.references.get(name, media.reference)
    input_dir = root / "comparison_videos"
    input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(reference_path, input_dir / "00-reference.mkv")
    shutil.copy2(media.comparisons[name], input_dir / "01-comparison.mkv")
    _create_prep_config(root, content=_MATCH_FPS_PREP_CONFIG)
    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=root),
            RunDependencies(vs_loader=DefaultVSLoader()),
        )
    )
    assert [clip.path.name for clip in prep.clips] == ["00-reference.mkv", "01-comparison.mkv"]
    ctx = RunContext(
        config=prep.config,
        workspace=prep.workspace,
        reference=prep.clips[0],
        comparisons=prep.clips[1:],
        analysis_selection_domain=prep.analysis_selection_domain,
        selection_window=prep.selection_window,
        analysis_clip=prep.analysis_clip,
    )
    output = _run_align_phase(ctx, selected_frames=[100], vs_loader=DefaultVSLoader())
    return prep, output


@pytest.mark.integration
@pytest.mark.parametrize(
    ("name", "comparison_source_fps", "expected_scale"),
    [
        ("retimed-ntsc", Fraction(24), Fraction(1001, 1000)),
        ("retimed-25-ntsc", Fraction(25), Fraction(1001, 960)),
    ],
)
def test_configured_match_fps_retimed_pairs_align(
    u4_media: _MediaSet,
    tmp_path: Path,
    name: str,
    comparison_source_fps: Fraction,
    expected_scale: Fraction,
) -> None:
    prep, output = _configured_prep_alignment(u4_media, name, tmp_path)
    reference, comparison = prep.clips
    assert reference.source_fps == Fraction(24000, 1001)
    assert reference.effective_fps == Fraction(24000, 1001)
    assert comparison.source_fps == comparison_source_fps
    assert comparison.effective_fps == Fraction(24000, 1001)

    attempt = output.comparisons[0].audio_attempt
    assert attempt is not None
    assert attempt.decision.state == "trusted_automatic"
    assert attempt.decision.primary_reason == "audio_video_confirmed"
    assert output.comparisons[0].alignment is not None
    assert output.comparisons[0].alignment.relative_offset_frames == 48
    assert output.reference.trim.trim_start_frames == 48
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert attempt.selected_streams[0].timeline_scale == 1
    assert attempt.selected_streams[1].timeline_scale == expected_scale
    assert attempt.extraction_recipe == _RETIMED_RECIPE


@pytest.mark.integration
def test_configured_match_fps_retimed_insert_still_refuses(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    retimed_root = tmp_path / "retimed"
    control_root = tmp_path / "control"
    retimed_root.mkdir()
    control_root.mkdir()
    retimed_prep, retimed_output = _configured_prep_alignment(
        u4_media, "retimed-insert", retimed_root
    )
    attempt = retimed_output.comparisons[0].audio_attempt
    assert attempt is not None
    assert attempt.decision.state != "trusted_automatic"
    assert retimed_prep.clips[0].source_fps == Fraction(24)
    assert retimed_prep.clips[1].source_fps == Fraction(25)
    assert retimed_prep.clips[1].effective_fps == Fraction(24)
    assert attempt.selected_streams[1].timeline_scale == Fraction(25, 24)
    assert attempt.extraction_recipe == _RETIMED_RECIPE

    _, control_output = _configured_prep_alignment(u4_media, "insert-300", control_root)
    control_attempt = control_output.comparisons[0].audio_attempt
    assert control_attempt is not None
    assert control_attempt.decision.state != "trusted_automatic"
    assert attempt.decision.primary_reason == control_attempt.decision.primary_reason


def _video_request(path: Path) -> VideoClipRequest:
    stat = path.stat()
    return VideoClipRequest(
        path=path,
        identity=AlignmentClipIdentity(path, stat.st_size, stat.st_mtime_ns),
    )


def _audio_channel_count(path: Path) -> int:
    probe = run_subprocess(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=channels",
            "-of",
            "csv=p=0",
            str(path),
        ],
        timeout_seconds=30,
    )
    return int(probe.stdout.decode().strip())


def _audio_difference_level(reference: Path, comparison: Path, start_seconds: int) -> float:
    result = run_subprocess(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-ss",
            str(start_seconds),
            "-t",
            str(_CHUNK_SECONDS),
            "-i",
            str(reference),
            "-ss",
            str(start_seconds),
            "-t",
            str(_CHUNK_SECONDS),
            "-i",
            str(comparison),
            "-filter_complex",
            "[0:a][1:a]amerge=inputs=2,pan=mono|c0=c0-c1,volumedetect[difference]",
            "-map",
            "[difference]",
            "-f",
            "null",
            "-",
        ],
        timeout_seconds=60,
    )
    for line in result.stderr.decode().splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:", 1)[1].split()[0])
    raise AssertionError(f"ffmpeg did not report a mean difference level for {start_seconds}s")


def _assert_label(result: AlignmentResult, *, state: str, reason: str) -> None:
    assert result.applied is (state == "trusted_automatic")
    assert result.diagnostic == reason
    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.state == state
    assert result.audio_attempt.decision.primary_reason == reason


def _assert_audio(
    result: AlignmentResult,
    *,
    global_lag: int,
    subframe: float,
    rounded_frame: int,
    credible: int,
    agreeing: int,
    active: int | None = None,
    authority_agreeing: int | None = None,
    authority_status: str | None = None,
    authority_passed: bool | None = None,
    raw_status: str | None = None,
) -> None:
    assert result.audio_attempt is not None
    audio = result.audio_attempt.audio
    assert audio.global_lag == global_lag
    assert audio.subframe_estimate == pytest.approx(subframe, abs=0.01)
    assert audio.rounded_frame == rounded_frame
    if active is not None:
        assert audio.active_chunks == active
    assert audio.credible_chunks == credible
    assert audio.agreeing_chunks == agreeing
    if raw_status is not None:
        assert audio.status == raw_status
    if authority_agreeing is not None:
        assert result.audio_attempt.authority_recount is not None
        recount = result.audio_attempt.authority_recount
        assert recount.authority_agreeing_chunks == authority_agreeing
        if authority_status is not None:
            assert recount.authority_status == authority_status
        if authority_passed is not None:
            assert recount.passed is authority_passed


def _near_region_end(n: int, frames: range) -> bool:
    return min(abs(n - frames.start), abs(n - (frames.stop - 1))) <= 3


def _assert_video(
    result: AlignmentResult,
    *,
    confirmed_offset: int,
    wins: int = 12,
    informative: int = 12,
    finite_margin: bool = False,
    regions: tuple[range, range, tuple[range, ...]] | None = None,
) -> None:
    assert result.audio_attempt is not None
    video = result.audio_attempt.video_check
    review = build_audio_review_presentation(result.audio_attempt)
    assert video.observation == "observed"
    assert video.confirmed_offset == confirmed_offset
    assert len(video.positions) == 12
    if regions is None:
        assert review.video_wins == wins
        assert review.video_informative == informative
    else:
        c_frames, other_frames, flat_frames = regions
        for position in video.positions:
            winner, _ = position_winner(position.score_by_offset, video.scored_offsets)
            n = position.reference_frame
            if _near_region_end(n, c_frames) or _near_region_end(n, other_frames):
                continue
            if any(n in flat for flat in flat_frames):
                assert winner is None
            elif n in c_frames:
                assert winner == confirmed_offset
            elif n in other_frames:
                assert winner != confirmed_offset
        assert review.video_wins == review.video_informative
    assert review.video_margin is not None
    assert review.video_margin >= 1.5
    if finite_margin:
        assert math.isfinite(review.video_margin)
    else:
        assert math.isinf(review.video_margin)


def _assert_targets(
    result: AlignmentResult,
    expected: tuple[tuple[str, int, int, tuple[int, ...], str, int], ...],
) -> None:
    assert result.audio_attempt is not None
    actual = tuple(
        (
            target.kind,
            target.first_chunk_index,
            target.last_chunk_index,
            target.alternative_offsets,
            target.resolution,
            len(target.positions),
        )
        for target in result.audio_attempt.video_check.targets
    )
    assert actual == expected


@pytest.mark.integration
@pytest.mark.parametrize(
    ("name", "reason", "global_lag", "rounded_frame", "target"),
    [
        (
            "insert-60",
            "competing_offset_confirmed_by_video",
            -32000,
            -96,
            ("run", 0, 1, (-1, 0, 1), "alternative_confirmed", 4),
        ),
        (
            "insert-540",
            "competing_offset_confirmed_by_video",
            0,
            0,
            ("run", 18, 19, (-97, -96, -95), "alternative_confirmed", 4),
        ),
        (
            "insert-570",
            "competing_offset_confirmed_by_video",
            0,
            0,
            ("chunk", 19, 19, (-97, -96, -95), "alternative_confirmed", 4),
        ),
    ],
)
def test_length_changing_inserts_are_not_applied(
    u4_media: _MediaSet,
    tmp_path: Path,
    name: str,
    reason: str,
    global_lag: int,
    rounded_frame: int,
    target: tuple[str, int, int, tuple[int, ...], str, int],
) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="provisional", reason=reason)
    _assert_audio(
        result,
        global_lag=global_lag,
        subframe=global_lag / 8000 * _FPS,
        rounded_frame=rounded_frame,
        credible=20,
        agreeing=18 if name != "insert-570" else 19,
    )
    if name == "insert-570":
        _assert_video(result, confirmed_offset=rounded_frame)
    else:
        at_seconds = 60 if name == "insert-60" else 540
        B = at_seconds * _FPS
        E = _DURATION * _FPS
        regions = (
            (range(B, E), range(0, B), ())
            if name == "insert-60"
            else (range(0, B), range(B, E), ())
        )
        _assert_video(
            result,
            confirmed_offset=rounded_frame,
            regions=regions,
            finite_margin=name == "insert-60",
        )
    _assert_targets(result, (target,))


@pytest.mark.integration
@pytest.mark.parametrize(
    ("seconds", "reason", "global_lag", "target"),
    (
        (60, "competing_offset", -32000, ("run", 0, 1, (-1, 0, 1), "unresolved", 4)),
        (540, "competing_offset", 0, ("run", 18, 19, (-97, -96, -95), "unresolved", 4)),
        (
            570,
            "unresolved_audio_disagreement",
            0,
            ("chunk", 19, 19, (-97, -96, -95), "unresolved", 4),
        ),
    ),
)
def test_low_motion_insert_remains_a_provisional_hint(
    u4_media: _MediaSet,
    tmp_path: Path,
    seconds: int,
    reason: str,
    global_lag: int,
    target: tuple[str, int, int, tuple[int, ...], str, int],
) -> None:
    result = _align_pair(u4_media, f"insert-{seconds}-low-motion", tmp_path / "generated")
    _assert_label(result, state="provisional", reason=reason)
    _assert_audio(
        result,
        global_lag=global_lag,
        subframe=global_lag / 8000 * _FPS,
        rounded_frame=-96 if seconds == 60 else 0,
        credible=20,
        agreeing=19 if seconds == 570 else 18,
    )
    if seconds == 540:
        _assert_video(
            result,
            confirmed_offset=0,
            wins=11,
            informative=11,
        )
    else:
        E = _DURATION * _FPS
        if seconds == 60:
            B = 60 * _FPS
            regions = (range(B, E), range(0, B), (range(0, B),))
        else:
            B = 570 * _FPS
            regions = (range(0, B), range(B, E), (range(568 * _FPS, E),))
        _assert_video(
            result,
            confirmed_offset=-96 if seconds == 60 else 0,
            regions=regions,
            finite_margin=seconds == 60,
        )
    _assert_targets(result, (target,))


@pytest.mark.integration
@pytest.mark.parametrize("name", ["replacement-4", "replacement-30"])
def test_same_length_replacements_apply(u4_media: _MediaSet, tmp_path: Path, name: str) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="trusted_automatic", reason="audio_video_confirmed")
    assert result.frame_offset == 0
    _assert_audio(
        result,
        global_lag=0,
        subframe=0.0,
        rounded_frame=0,
        credible=20,
        agreeing=20,
    )
    _assert_video(
        result,
        confirmed_offset=0,
        wins=11 if name == "replacement-30" else 12,
        informative=11 if name == "replacement-30" else 12,
    )
    _assert_targets(result, ())


@pytest.mark.integration
def test_repeated_music_cue_is_resolved_by_identical_moving_video(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    result = _align_pair(u4_media, "repeated-music-cue", tmp_path / "generated")
    _assert_label(result, state="trusted_automatic", reason="audio_video_confirmed")
    assert result.frame_offset == 0
    assert result.audio_attempt is not None
    _assert_audio(
        result,
        global_lag=0,
        subframe=0.0,
        rounded_frame=0,
        credible=20,
        agreeing=19,
        authority_agreeing=19,
        authority_status="agreed",
        authority_passed=True,
        raw_status="agreed",
    )
    _assert_video(result, confirmed_offset=0)
    _assert_targets(
        result,
        (("chunk", 10, 10, (119, 120, 121), "resolved", 4),),
    )
    target = result.audio_attempt.video_check.targets[0]
    expected_positions = ((12, 7199), (13, 7439), (14, 7679), (15, 7919))
    assert len(target.positions) == len(expected_positions)
    for position, expected in zip(target.positions, expected_positions, strict=True):
        position_index, reference_frame = expected
        assert position.position_index == position_index
        assert position.reference_frame == reference_frame
        assert position.confirmed_score < position.alternative_score
        assert position.winner == "confirmed"


@pytest.mark.integration
def test_low_motion_credible_disagreement_stays_unresolved(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    result = _align_pair(u4_media, "false-cue-low-motion", tmp_path / "generated")
    _assert_label(result, state="provisional", reason="unresolved_audio_disagreement")
    _assert_audio(
        result,
        global_lag=0,
        subframe=0.0,
        rounded_frame=0,
        credible=20,
        agreeing=19,
    )
    _assert_video(result, confirmed_offset=0, wins=11, informative=11)
    _assert_targets(result, (("chunk", 10, 10, (-3, -2, -1), "unresolved", 4),))


@pytest.mark.integration
@pytest.mark.parametrize("name", ["budget", "budget-7"])
def test_budget_exhaustion_leaves_later_credible_targets_unexamined(
    u4_media: _MediaSet, tmp_path: Path, name: str
) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="provisional", reason="unresolved_audio_disagreement")
    disagreement_indices = (1, 5, 9, 13) if name == "budget" else (1, 3, 5, 7, 9, 11, 13)
    _assert_audio(
        result,
        global_lag=0,
        subframe=0.0,
        rounded_frame=0,
        credible=20,
        agreeing=16 if name == "budget" else 13,
        authority_agreeing=16 if name == "budget" else 13,
        authority_status="agreed" if name == "budget" else "no_single_offset",
        authority_passed=name == "budget",
        raw_status="agreed" if name == "budget" else "no_single_offset",
    )
    _assert_video(result, confirmed_offset=0)
    assert result.audio_attempt is not None
    assert tuple(
        (run.first_index, run.last_index, run.lag, run.chunk_count)
        for run in result.audio_attempt.runs
        if run.lag != 0
    ) == tuple((index, index, -800, 1) for index in disagreement_indices)
    expected = (
        (
            ("chunk", 13, 13, (-3, -2, -1), "resolved", 4),
            ("chunk", 1, 1, (-3, -2, -1), "resolved", 4),
            ("chunk", 5, 5, (-3, -2, -1), "resolved", 4),
            ("chunk", 9, 9, (-3, -2, -1), "unexamined", 0),
        )
        if name == "budget"
        else (
            ("chunk", 11, 11, (-3, -2, -1), "resolved", 4),
            ("chunk", 13, 13, (-3, -2, -1), "resolved", 4),
            ("chunk", 5, 5, (-3, -2, -1), "resolved", 4),
            ("chunk", 1, 1, (-3, -2, -1), "unexamined", 0),
            ("chunk", 3, 3, (-3, -2, -1), "unexamined", 0),
            ("chunk", 7, 7, (-3, -2, -1), "unexamined", 0),
            ("chunk", 9, 9, (-3, -2, -1), "unexamined", 0),
        )
    )
    _assert_targets(result, expected)
    assert sum(len(target.positions) for target in result.audio_attempt.video_check.targets) == 12


@pytest.mark.integration
def test_active_noncredible_shifted_tail_is_resolved_by_video(
    u4_media: _MediaSet, tmp_path: Path
) -> None:
    result = _align_pair(u4_media, "active-tail", tmp_path / "generated")
    _assert_label(result, state="provisional", reason="competing_offset_confirmed_by_video")
    _assert_audio(
        result,
        global_lag=0,
        subframe=0.0,
        rounded_frame=0,
        active=20,
        credible=18,
        agreeing=18,
    )
    B = 540 * _FPS
    E = _DURATION * _FPS
    _assert_video(result, confirmed_offset=0, regions=(range(0, B), range(B, E), ()))
    assert result.audio_attempt is not None
    assert tuple(
        index for index, credible in enumerate(result.audio_attempt.chunks.credible) if not credible
    ) == (18, 19)
    _assert_targets(
        result,
        (
            ("chunk", 19, 19, (-97, -96, -95), "alternative_confirmed", 2),
            ("chunk", 18, 18, (-97, -96, -95), "alternative_confirmed", 2),
        ),
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
    if name == "multipath":
        _assert_audio(
            result,
            global_lag=0,
            subframe=0.0,
            rounded_frame=0,
            active=20,
            credible=20,
            agreeing=18,
            authority_agreeing=18,
            authority_status="agreed",
            authority_passed=True,
        )
        _assert_video(result, confirmed_offset=0)
        assert tuple(
            (run.first_index, run.last_index, run.lag, run.chunk_count)
            for run in attempt.runs
            if run.lag != 0
        ) == ((8, 9, -240, 2),)
        _assert_targets(result, (("run", 8, 9, (-2, -1), "resolved", 4),))
    elif name == "run-resolved":
        _assert_audio(
            result,
            global_lag=0,
            subframe=0.0,
            rounded_frame=0,
            active=20,
            credible=20,
            agreeing=18,
            authority_agreeing=18,
            authority_status="agreed",
            authority_passed=True,
        )
        _assert_video(result, confirmed_offset=0)
        assert tuple(
            (run.first_index, run.last_index, run.lag, run.chunk_count)
            for run in attempt.runs
            if run.lag != 0
        ) == ((6, 7, -800, 2),)
        _assert_targets(result, (("run", 6, 7, (-3, -2, -1), "resolved", 4),))
    elif name == "same-frame":
        _assert_audio(
            result,
            global_lag=0,
            subframe=0.0,
            rounded_frame=0,
            active=20,
            credible=20,
            agreeing=19,
            authority_agreeing=20,
            authority_status="agreed",
            authority_passed=True,
        )
        _assert_video(result, confirmed_offset=0)
        assert tuple(
            (run.first_index, run.last_index, run.lag, run.chunk_count)
            for run in attempt.runs
            if run.lag != 0
        ) == ((10, 10, -80, 1),)
        assert tuple(
            (item.chunk_index, item.lag_samples, item.rounded_frame)
            for item in attempt.video_check.same_frame_context
        ) == ((10, -80, 0),)
        assert attempt.video_check.targets == ()
    else:
        _assert_audio(
            result,
            global_lag=0,
            subframe=0.0,
            rounded_frame=0,
            active=20,
            credible=20,
            agreeing=7,
            authority_agreeing=20,
            authority_status="agreed",
            authority_passed=True,
            raw_status="no_single_offset",
        )
        _assert_video(result, confirmed_offset=0)
        assert tuple(
            (run.first_index, run.last_index, run.lag, run.chunk_count)
            for run in attempt.runs
            if run.lag != 0
        ) == tuple((index, index, -80 if index % 2 else 80, 1) for index in range(7, 20))
        assert tuple(
            (item.chunk_index, item.lag_samples, item.rounded_frame)
            for item in attempt.video_check.same_frame_context
        ) == tuple((index, -80 if index % 2 else 80, 0) for index in range(7, 20))
        assert attempt.video_check.targets == ()


@pytest.mark.integration
@pytest.mark.parametrize("name", ["loudness", "compression", "surround", "music-stem"])
def test_refusal_principle_mix_changes_still_apply(
    u4_media: _MediaSet, tmp_path: Path, name: str
) -> None:
    result = _align_pair(u4_media, name, tmp_path / "generated")
    _assert_label(result, state="trusted_automatic", reason="audio_video_confirmed")
    assert result.frame_offset == 0
    _assert_audio(
        result,
        global_lag=0,
        subframe=0.0,
        rounded_frame=0,
        active=20,
        credible=20,
        agreeing=20,
        authority_agreeing=20,
        authority_status="agreed",
        authority_passed=True,
    )
    _assert_video(result, confirmed_offset=0)
    _assert_targets(result, ())
    if name == "surround":
        assert _audio_channel_count(u4_media.references["surround"]) == 6
        assert _audio_channel_count(u4_media.comparisons["surround"]) == 2
    if name == "music-stem":
        levels = tuple(
            _audio_difference_level(u4_media.reference, u4_media.comparisons[name], start)
            for start in range(0, _DURATION, _CHUNK_SECONDS)
        )
        outside = levels[:9] + levels[10:]
        assert len(levels) == _CHUNK_COUNT
        assert levels[9] > -20.0
        assert max(outside) < -20.0


@pytest.mark.integration
def test_video_check_cost_measurement(u4_media: _MediaSet, tmp_path: Path) -> None:
    result = _align_pair(u4_media, "replacement-4", tmp_path / "generated")
    assert result.audio_attempt is not None
    reference = _video_request(u4_media.reference)
    comparison = _video_request(u4_media.comparisons["replacement-4"])
    loader = DefaultVSLoader()
    warmup = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=result.audio_attempt,
        fps_reference=Fraction(_FPS, 1),
        loader=loader,
    )
    assert warmup.observation.confirmed_offset == 0

    samples: list[float] = []
    for _ in range(3):
        started = time.perf_counter()
        measured = alignment_video.check_video_alignment(
            reference=reference,
            comparison=comparison,
            attempt=result.audio_attempt,
            fps_reference=Fraction(_FPS, 1),
            loader=loader,
        )
        samples.append(time.perf_counter() - started)
        assert measured.observation.confirmed_offset == 0
    mean = statistics.fmean(samples)
    print(
        "U4_VIDEO_CHECK_COST "
        f"samples={','.join(f'{sample:.3f}s' for sample in samples)} mean={mean:.3f}s"
    )
