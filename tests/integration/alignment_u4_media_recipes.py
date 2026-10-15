"""Deterministic U4 media recipes: this source alone owns producer identity."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from frame_compare.utils.subproc import run_subprocess

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


@dataclass(frozen=True, slots=True)
class MediaRecipe:
    writer: Callable[[Path], None]
    requires: tuple[str, ...] = ()


def _recipes() -> dict[str, MediaRecipe]:
    recipes = {
        "reference": MediaRecipe(_write_media),
        "multipath-reference": MediaRecipe(
            lambda path: _write_media(path, audio_graph=_multipath_graph(reverse_chunks=()))
        ),
        "repeated-music-cue-reference": MediaRecipe(
            lambda path: _write_repeated_music_cue(path, reference=True)
        ),
        "surround-reference": MediaRecipe(lambda path: _write_surround(path, downmix=False)),
        "flat-video-reference": MediaRecipe(_write_flat_video),
        "retimed-ntsc-reference": MediaRecipe(lambda path: _write_media(path, fps=_NTSC_RATE)),
    }

    def add(name: str, writer: Callable[[Path], None], *, requires: tuple[str, ...] = ()) -> None:
        recipes[name] = MediaRecipe(writer, requires)

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
    add(
        "retimed-25",
        lambda path: _write_retimed_25(path, path.parent / "u4-reference.mkv"),
        requires=("reference",),
    )
    add(
        "retimed-ntsc",
        lambda path: _write_retimed_ntsc(path, path.parent / "u4-retimed-ntsc-reference.mkv"),
        requires=("retimed-ntsc-reference",),
    )
    add(
        "retimed-25-ntsc",
        lambda path: _write_retimed_25_ntsc(path, path.parent / "u4-retimed-ntsc-reference.mkv"),
        requires=("retimed-ntsc-reference",),
    )
    add("retimed-insert", _write_retimed_insert)
    add("insert-300", lambda path: _write_insert(path, 300))
    return recipes


RECIPES: Mapping[str, MediaRecipe] = _recipes()
PAIRS: Mapping[str, tuple[str, str]] = {
    **{name: ("reference", name) for name in RECIPES if not name.endswith("reference")},
    "multipath": ("multipath-reference", "multipath"),
    "repeated-music-cue": ("repeated-music-cue-reference", "repeated-music-cue"),
    "surround": ("surround-reference", "surround"),
    "surround-local": ("surround-reference", "surround-local"),
    "flat-video": ("flat-video-reference", "flat-video"),
    "retimed-ntsc": ("retimed-ntsc-reference", "retimed-ntsc"),
    "retimed-25-ntsc": ("retimed-ntsc-reference", "retimed-25-ntsc"),
}
