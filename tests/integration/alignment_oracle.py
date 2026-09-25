"""Independent continuous-decode oracle and P3 policy specification support.

This module is test-only.  The oracle deliberately decodes from stream origin without
``-ss`` or ``atrim`` and slices the resulting output sample grid in Python.  Production
alignment code never imports it.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import subprocess
import wave
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

import numpy as np

from frame_compare.services.alignment_audio import AudioStreamInfo
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.types import AlignmentChannelStrategy

ORACLE_TIMEOUT_SECONDS = 180
ORACLE_RAW_BYTE_LIMIT = 256 * 1024 * 1024
BASE_SCORE_FLOOR = 0.90
BASE_PEAK_RATIO_FLOOR = 1.50


def mux_audio(
    path: Path,
    wave_path: Path,
    *,
    source_rate: int,
    codec: str,
    start_seconds: int = 0,
    fps: str = "24",
    duration_seconds: int = 12,
) -> None:
    """Create a tiny deterministic A/V fixture for continuous-pipeline tests."""
    codec_args = ["-c:a", "pcm_s16le"] if codec == "pcm" else ["-c:a", "aac", "-b:a", "192k"]
    audio_input = ["-itsoffset", str(start_seconds)] if start_seconds else []
    subprocess.run(  # noqa: S603 - fixed test fixture executable
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=16x16:r={fps}:d={duration_seconds + abs(start_seconds)}",
            *audio_input,
            "-i",
            str(wave_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "ffv1",
            *codec_args,
            "-copyts",
            "-avoid_negative_ts",
            "disabled",
            str(path),
        ],
        check=True,
        timeout=45,
    )


@dataclass(frozen=True, slots=True)
class PolicyObservation:
    """One preclassified primary-window observation for the test-only P4 evaluator."""

    logical_id: str
    start_sample: int
    end_sample: int
    sample_offset: int | None
    score: float | None
    peak_ratio: float | None
    coverage_ratio: float
    status: Literal["correlated", "failed"] = "correlated"


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    """Scalar result from the exact predeclared quality/coverage proposal."""

    accepted: bool
    reason: str
    frame_offset: int | None
    correlated: int
    credible: int
    voting_qualified: int
    winning_qualified: int
    independent_support: int


@dataclass(frozen=True, slots=True)
class OracleComparison:
    """Scalar bounded-versus-continuous comparison for one source window."""

    start_sample: int
    sample_count: int
    bounded_count: int
    oracle_count: int
    measured_lag: int
    correlation: float
    maximum_absolute_delta: float


@dataclass(frozen=True, slots=True)
class PacketSummary:
    """Bounded scalar ffprobe observations for one selected audio stream."""

    packet_count: int
    first_pts_seconds: float | None
    last_pts_seconds: float | None
    minimum_duration_seconds: float | None
    maximum_duration_seconds: float | None


def _pairwise_disjoint(items: Sequence[PolicyObservation]) -> bool:
    ordered = sorted(items, key=lambda item: (item.start_sample, item.end_sample))
    return all(left.end_sample <= right.start_sample for left, right in itertools.pairwise(ordered))


def _independent_support(
    observations: Sequence[PolicyObservation],
    *,
    duration_samples: int,
    require_endpoint_coverage: bool,
) -> int:
    """Return the largest eligible disjoint subset, including tier coverage rules."""
    if duration_samples <= 0:
        return 0
    best = 0
    for count in range(1, len(observations) + 1):
        for subset in itertools.combinations(observations, count):
            if not _pairwise_disjoint(subset):
                continue
            if require_endpoint_coverage:
                early = any(item.start_sample <= duration_samples // 3 for item in subset)
                late = any(item.end_sample * 3 >= duration_samples * 2 for item in subset)
                if not (early and late):
                    continue
            best = max(best, count)
    return best


def evaluate_predeclared_policy(
    observations: Sequence[PolicyObservation],
    *,
    sample_rate: int,
    fps: Fraction,
    duration_seconds: Fraction,
    confidence_threshold: float = BASE_SCORE_FLOOR,
    ambiguity_peak_ratio: float = BASE_PEAK_RATIO_FLOOR,
    minimum_valid_windows: int = 1,
    consensus_minimum_ratio: float = 1.0,
) -> PolicyEvaluation:
    """Evaluate P3's frozen proposal without importing future production policy."""
    duration_samples = round(duration_seconds * sample_rate)
    correlated = [item for item in observations if item.status == "correlated"]
    credible = [
        item
        for item in correlated
        if item.sample_offset is not None
        and item.score is not None
        and item.peak_ratio is not None
        and math.isfinite(item.score)
        and not math.isnan(item.peak_ratio)
        and item.score >= BASE_SCORE_FLOOR
        and item.peak_ratio >= BASE_PEAK_RATIO_FLOOR
    ]
    credible_bins = {
        samples_to_frames(item.sample_offset, sample_rate, fps)
        for item in credible
        if item.sample_offset is not None
    }
    if len(credible_bins) > 1:
        return PolicyEvaluation(
            False, "credible_conflict", None, len(correlated), len(credible), 0, 0, 0
        )
    effective_score = max(BASE_SCORE_FLOOR, confidence_threshold)
    effective_peak = max(BASE_PEAK_RATIO_FLOOR, ambiguity_peak_ratio)
    voting = [
        item
        for item in credible
        if item.score is not None
        and item.peak_ratio is not None
        and item.score >= effective_score
        and item.peak_ratio >= effective_peak
        and item.coverage_ratio >= 0.90
    ]
    if not voting:
        return PolicyEvaluation(
            False, "no_candidate", None, len(correlated), len(credible), 0, 0, 0
        )
    groups: dict[int, list[PolicyObservation]] = {}
    for item in voting:
        assert item.sample_offset is not None
        frame = samples_to_frames(item.sample_offset, sample_rate, fps)
        groups.setdefault(frame, []).append(item)
    winner_frame, winner = max(groups.items(), key=lambda pair: (len(pair[1]), -abs(pair[0])))
    if len(voting) < minimum_valid_windows:
        reason = "insufficient_valid_windows"
    elif len(winner) / len(voting) < consensus_minimum_ratio:
        reason = "insufficient_consensus"
    else:
        support = _independent_support(
            winner,
            duration_samples=duration_samples,
            require_endpoint_coverage=duration_seconds > 30,
        )
        required_support = 1 if duration_seconds <= 30 else 2 if duration_seconds < 90 else 3
        if support < required_support:
            reason = "insufficient_temporal_support"
        else:
            return PolicyEvaluation(
                True,
                "accepted",
                winner_frame,
                len(correlated),
                len(credible),
                len(voting),
                len(winner),
                support,
            )
    return PolicyEvaluation(
        False,
        reason,
        winner_frame,
        len(correlated),
        len(credible),
        len(voting),
        len(winner),
        _independent_support(
            winner,
            duration_samples=duration_samples,
            require_endpoint_coverage=duration_seconds > 30,
        ),
    )


def _best_channel_filter(stream: AudioStreamInfo | None) -> str:
    if stream is None:
        return "pan=mono|c0=c0"
    if stream.channel_layout is not None and "5.1" in stream.channel_layout:
        return "pan=mono|c0=FC"
    if stream.channel_layout in {"stereo", "2.0"}:
        return "pan=mono|c0=FL"
    if stream.channels == 1 or stream.channel_layout == "mono":
        return "pan=mono|c0=c0"
    if stream.channels is not None and stream.channels >= 3:
        return "pan=mono|c0=c2"
    return "pan=mono|c0=c0"


def continuous_decode_argv(
    media: Path,
    stream: AudioStreamInfo,
    *,
    sample_rate: int,
    channel_strategy: AlignmentChannelStrategy,
) -> list[str]:
    """Build the independent origin-decode command; no bounded seek/trim is allowed."""
    filters = [f"aresample={sample_rate}"]
    channel_args: list[str] = []
    if channel_strategy == "mono_downmix":
        channel_args = ["-ac", "1"]
    else:
        filters.insert(0, _best_channel_filter(stream))
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(media),
        "-map",
        f"0:a:{stream.audio_stream_index}",
        "-vn",
        *channel_args,
        "-af",
        ",".join(filters),
        "-f",
        "f32le",
        "-",
    ]


def probe_packet_summary(media: Path, stream: AudioStreamInfo) -> PacketSummary:
    """Observe packet PTS/durations without retaining the packet listing."""
    process = subprocess.run(  # noqa: S603 - fixed executable/argument array
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            f"a:{stream.audio_stream_index}",
            "-show_entries",
            "packet=pts_time,duration_time",
            "-of",
            "json",
            str(media),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(process.stdout)
    packets = payload.get("packets", [])
    pts = [float(packet["pts_time"]) for packet in packets if "pts_time" in packet]
    durations = [float(packet["duration_time"]) for packet in packets if "duration_time" in packet]
    return PacketSummary(
        packet_count=len(packets),
        first_pts_seconds=pts[0] if pts else None,
        last_pts_seconds=pts[-1] if pts else None,
        minimum_duration_seconds=min(durations) if durations else None,
        maximum_duration_seconds=max(durations) if durations else None,
    )


@contextmanager
def continuous_decode(
    media: Path,
    stream: AudioStreamInfo,
    *,
    sample_rate: int,
    channel_strategy: AlignmentChannelStrategy,
) -> Generator[np.ndarray]:
    """Decode one selected stream from origin into a bounded independent array."""
    with TemporaryDirectory(prefix="frame-compare-continuous-oracle-") as directory:
        raw_path = Path(directory) / "oracle.f32le"
        argv = continuous_decode_argv(
            media,
            stream,
            sample_rate=sample_rate,
            channel_strategy=channel_strategy,
        )
        with raw_path.open("wb") as output:
            subprocess.run(  # noqa: S603 - fixed executable/argument array in test-only code
                argv,
                stdout=output,
                stderr=subprocess.PIPE,
                check=True,
                timeout=ORACLE_TIMEOUT_SECONDS,
            )
        raw_size = raw_path.stat().st_size
        if raw_size > ORACLE_RAW_BYTE_LIMIT:
            raise AssertionError("continuous oracle exceeded the per-case raw-data cap")
        if raw_size % np.dtype(np.float32).itemsize:
            raise AssertionError("continuous oracle returned an invalid float32 payload")
        yield np.fromfile(raw_path, dtype=np.float32)


def compare_with_oracle(
    bounded: np.ndarray,
    oracle: np.ndarray,
    *,
    start_sample: int,
    sample_count: int,
) -> OracleComparison:
    """Compare a bounded source window with its own continuous-decode slice."""
    expected = np.asarray(oracle[start_sample : start_sample + sample_count])
    actual = np.asarray(bounded)
    bounded_count = int(actual.size)
    oracle_count = int(expected.size)
    common = min(actual.size, expected.size)
    if common == 0:
        raise AssertionError("oracle comparison requires non-empty arrays")
    actual = actual[:common]
    expected = expected[:common]
    lag = int(np.argmax(np.correlate(expected, actual, mode="full"))) - (actual.size - 1)
    if lag > 0:
        aligned_expected = expected[lag:]
        aligned_actual = actual[:-lag]
    elif lag < 0:
        aligned_expected = expected[:lag]
        aligned_actual = actual[-lag:]
    else:
        aligned_expected = expected
        aligned_actual = actual
    correlation = float(np.corrcoef(aligned_actual, aligned_expected)[0, 1])
    return OracleComparison(
        start_sample=start_sample,
        sample_count=sample_count,
        bounded_count=bounded_count,
        oracle_count=oracle_count,
        measured_lag=lag,
        correlation=correlation,
        maximum_absolute_delta=float(np.max(np.abs(aligned_actual - aligned_expected))),
    )


def deterministic_signal(*, seed: int, sample_rate: int, duration_seconds: int) -> np.ndarray:
    """Return seeded broadband/speech-like mono audio with an explicit identity."""
    count = sample_rate * duration_seconds
    time = np.arange(count, dtype=np.float32) / np.float32(sample_rate)
    noise = np.random.default_rng(seed).standard_normal(count, dtype=np.float32)
    signal = 0.22 * noise + 0.15 * np.sin(2 * np.pi * (173 * time + 5 * time * time))
    return np.clip(signal, -0.95, 0.95).astype(np.float32)


def write_pcm_wave(path: Path, samples: np.ndarray, *, sample_rate: int) -> None:
    """Write deterministic signed 16-bit PCM without a media dependency."""
    quantized = np.clip(np.rint(samples * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(quantized.tobytes())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recipe_identity(recipe: object) -> str:
    payload = json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def json_record(value: object) -> dict[str, object]:
    """Convert a scalar evidence dataclass into a JSON-ready dictionary."""
    return dict(asdict(value))  # type: ignore[arg-type]
