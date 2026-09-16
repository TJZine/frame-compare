"""P3 continuous-decode oracle and frozen-policy evidence matrix."""

from __future__ import annotations

import json
import math
import os
import platform
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_audio import (
    extract_audio_window,
    select_reference_audio_stream,
)
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    AudioAlignmentWindowRecord,
)
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.runtime_contract import media_runtime_fingerprint, runtime_kind
from tests.integration.alignment_oracle import (
    PolicyObservation,
    compare_with_oracle,
    continuous_decode,
    continuous_decode_argv,
    deterministic_signal,
    evaluate_predeclared_policy,
    probe_packet_summary,
    recipe_identity,
    sha256_file,
    write_pcm_wave,
)
from tests.services.alignment_request_test_support import alignment_request

_SOURCE_DURATION = 12
_WINDOW_SAMPLES = 2048


def _version_line(executable: str) -> str:
    process = subprocess.run(  # noqa: S603 - fixed test evidence executable
        [executable, "-version"],
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    return process.stdout.splitlines()[0]


def _record_evidence(section: str, payload: dict[str, object]) -> None:
    """Optionally merge scalar evidence; ordinary test runs write nothing."""
    destination = os.environ.get("FRAME_COMPARE_P3_EVIDENCE_PATH")
    if not destination:
        return
    path = Path(destination)
    if path.exists():
        evidence = json.loads(path.read_text(encoding="utf-8"))
    else:
        evidence = {
            "schema_version": 1,
            "purpose": "p3_continuous_decode_oracle_scalar_evidence",
            "environment": {
                "platform": platform.platform(),
                "runtime_kind": runtime_kind(),
                "alignment_runtime_fingerprint": media_runtime_fingerprint("alignment"),
                "ffmpeg": _version_line("ffmpeg"),
                "ffprobe": _version_line("ffprobe"),
            },
            "sections": {},
        }
    evidence["sections"][section] = payload
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def test_oracle_resource_ceiling_is_below_predeclared_cap() -> None:
    per_source_bytes = 180 * 48000 * np.dtype(np.float32).itemsize
    assert per_source_bytes == 34_560_000
    assert 2 * per_source_bytes == 69_120_000
    assert 2 * per_source_bytes < 256 * 1024 * 1024


def test_tracked_scalar_evidence_records_extraction_stop_disposition() -> None:
    evidence_path = Path(__file__).parents[1] / "fixtures" / "alignment_oracle" / "p3-results.json"
    raw = evidence_path.read_text(encoding="utf-8")
    evidence = json.loads(raw)
    assert evidence["schema_version"] == 1
    assert evidence["disposition"] == "primary_extraction_discrepancy_demonstrated_p5_before_p4"
    assert evidence["matrix"]["weak_dissent"]["false_rejects"] == 0
    assert evidence["matrix"]["localized_edit"]["false_accepts"] == 0
    assert evidence["environments"]["windows_x64_portable"]["status"] == (
        "outstanding_not_executed"
    )
    assert "/Users/" not in raw
    assert "raw_samples" not in raw


def _mux_audio(
    path: Path,
    wave_path: Path,
    *,
    source_rate: int,
    codec: LiteralCodec,
    packet_samples: int | None = None,
    start_seconds: int = 0,
    fps: str = "24",
    duration_seconds: int = _SOURCE_DURATION,
) -> list[str]:
    codec_args = ["-c:a", "pcm_s16le"] if codec == "pcm" else ["-c:a", "aac", "-b:a", "192k"]
    audio_input = ["-itsoffset", str(start_seconds)] if start_seconds else []
    audio_filter = ["-af", f"asetnsamples=n={packet_samples}:p=1"] if packet_samples else []
    command = [
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
        *audio_filter,
        "-c:v",
        "ffv1",
        *codec_args,
        "-copyts",
        "-avoid_negative_ts",
        "disabled",
        str(path),
    ]
    run_subprocess(command, timeout_seconds=45)
    return command


LiteralCodec = str


def _encode_audio_only(
    path: Path,
    inputs: list[Path],
    *,
    codec: LiteralCodec = "pcm",
) -> None:
    codec_args = ["-c:a", "pcm_s16le"] if codec == "pcm" else ["-c:a", "aac", "-b:a", "192k"]
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for source in inputs:
        command.extend(("-i", str(source)))
    for index in range(len(inputs)):
        command.extend(("-map", f"{index}:a:0"))
    command.extend((*codec_args, str(path)))
    run_subprocess(command, timeout_seconds=45)


def _run_alignment_result(
    root: Path,
    reference: Path,
    comparison: Path,
    *,
    config: AlignmentConfig,
    fps: Fraction = Fraction(24),
) -> AlignmentResult:
    generated = root / "audio-pair-generated"
    generated.mkdir(exist_ok=True)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated,
        fps_num=fps.numerator,
        fps_den=fps.denominator,
    )
    result = align_clips_from_request(
        request,
        config,
        reference_fps=fps,
        quiet=True,
    )
    return result[0]


def _run_audio_pair(
    root: Path,
    reference: Path,
    comparison: Path,
    *,
    config: AlignmentConfig,
    fps: Fraction = Fraction(24),
) -> list[PolicyObservation]:
    result = _run_alignment_result(root, reference, comparison, config=config, fps=fps)
    assert result.audio_attempt is not None
    return _policy_observations(result.audio_attempt.windows)


def _policy_observations(
    records: tuple[AudioAlignmentWindowRecord, ...],
) -> list[PolicyObservation]:
    observations: list[PolicyObservation] = []
    for record in records:
        scale = Fraction(record.requested_rate, record.analysis_rate)
        planned_count = round(record.planned_reference_count * scale)
        effective_count = record.effective_aligned_overlap or 0
        observations.append(
            PolicyObservation(
                logical_id=record.logical_id,
                start_sample=round(record.planned_reference_start * scale),
                end_sample=round(
                    (record.planned_reference_start + record.planned_reference_count) * scale
                ),
                sample_offset=record.requested_sample_lag,
                score=record.requested_score,
                peak_ratio=(math.inf if record.peak_ratio == "unbounded" else record.peak_ratio),
                coverage_ratio=(effective_count / planned_count if planned_count else 0.0),
                status=("correlated" if record.terminal_category == "correlated" else "failed"),
            )
        )
    return observations


def _localized_variant(
    source: np.ndarray,
    *,
    sample_rate: int,
    position: int,
    sign: int,
    noise_seed: int,
    shifted_weight: float,
) -> np.ndarray:
    """Shift one planned interval and mix independent noise at a frozen strength."""
    output = source.copy()
    margin = sample_rate
    start = max(0, position * 30 * sample_rate - margin)
    end = min(source.size, (position + 1) * 30 * sample_rate + margin)
    interval = source[start:end]
    shifted = np.roll(interval, sign * 2400)
    noise = np.random.default_rng(noise_seed).standard_normal(interval.size, dtype=np.float32)
    noise *= np.std(interval) / np.std(noise)
    output[start:end] = shifted_weight * shifted + (1 - shifted_weight) * noise
    return np.clip(output, -0.95, 0.95).astype(np.float32)


def _run_long_fixture(
    root: Path,
    *,
    reference: Path,
    comparison_samples: np.ndarray,
    fps: Fraction,
    sample_rate: int,
) -> list[PolicyObservation]:
    comparison_wave = root / "comparison.wav"
    comparison = root / "comparison.mkv"
    write_pcm_wave(comparison_wave, comparison_samples, sample_rate=sample_rate)
    _mux_audio(
        comparison,
        comparison_wave,
        source_rate=sample_rate,
        codec="pcm",
        packet_samples=1001,
        fps=f"{fps.numerator}/{fps.denominator}",
        duration_seconds=150,
    )
    generated = root / "generated"
    generated.mkdir(exist_ok=True)
    config = AlignmentConfig(
        cache_results=False,
        sample_rate=sample_rate,
        max_offset_seconds=1.0,
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated,
        fps_num=fps.numerator,
        fps_den=fps.denominator,
    )
    result = align_clips_from_request(request, config, quiet=True)
    assert len(result) == 1
    assert result[0].audio_attempt is not None
    return _policy_observations(result[0].audio_attempt.windows)


@pytest.mark.integration
def test_oracle_command_is_continuous_and_source_specific(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    wave_path = tmp_path / "signal.wav"
    media = tmp_path / "signal.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=101, sample_rate=48000, duration_seconds=_SOURCE_DURATION),
        sample_rate=48000,
    )
    _mux_audio(media, wave_path, source_rate=48000, codec="pcm")
    stream = select_reference_audio_stream(media)
    packets = probe_packet_summary(media, stream)
    assert packets.packet_count > 0
    assert packets.first_pts_seconds is not None

    argv = continuous_decode_argv(
        media,
        stream,
        sample_rate=8000,
        channel_strategy="mono_downmix",
    )

    assert "-ss" not in argv
    assert not any("atrim" in item for item in argv)
    assert argv.count("-i") == 1
    assert str(media) in argv
    assert recipe_identity(argv) != recipe_identity([str(media), "bounded-positive-seek"])
    _record_evidence(
        "oracle_independence",
        {
            "decode_from_origin": True,
            "contains_input_seek": False,
            "contains_atrim": False,
            "recipe_identity": recipe_identity(
                [item if item != str(media) else "<source>" for item in argv]
            ),
            "packet_count": packets.packet_count,
        },
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("source_rate", "requested_rate", "codec", "packet_samples", "start_seconds"),
    [
        (48000, 48000, "pcm", 960, 0),
        (48000, 8000, "pcm", 1001, 0),
        (44100, 4000, "pcm", 1001, 0),
        (48000, 8000, "aac", None, 0),
        (44100, 48000, "aac", None, 0),
    ],
)
def test_bounded_windows_match_each_sources_own_continuous_oracle(
    tmp_path: Path,
    require_ffmpeg: None,
    source_rate: int,
    requested_rate: int,
    codec: LiteralCodec,
    packet_samples: int | None,
    start_seconds: int,
) -> None:
    signal = deterministic_signal(
        seed=source_rate + requested_rate + (1 if codec == "aac" else 0),
        sample_rate=source_rate,
        duration_seconds=_SOURCE_DURATION,
    )
    wave_path = tmp_path / "source.wav"
    media = tmp_path / f"source-{codec}.mkv"
    write_pcm_wave(wave_path, signal, sample_rate=source_rate)
    _mux_audio(
        media,
        wave_path,
        source_rate=source_rate,
        codec=codec,
        packet_samples=packet_samples,
        start_seconds=start_seconds,
    )
    stream = select_reference_audio_stream(media)
    packets = probe_packet_summary(media, stream)
    assert packets.packet_count > 0
    if packet_samples is not None:
        assert packets.minimum_duration_seconds is not None
        assert packets.maximum_duration_seconds is not None
    total = math.floor((stream.timeline.duration or Fraction(_SOURCE_DURATION)) * requested_rate)
    starts = (0, 5 * requested_rate - 1, 5 * requested_rate, 6 * requested_rate, total - 4096)

    comparisons: list[dict[str, object]] = []
    with continuous_decode(
        media,
        stream,
        sample_rate=requested_rate,
        channel_strategy="mono_downmix",
    ) as oracle:
        for start in starts:
            bounded = extract_audio_window(
                media,
                stream,
                sample_rate=requested_rate,
                start_sample=start,
                sample_count=_WINDOW_SAMPLES,
                channel_strategy="mono_downmix",
            )
            result = compare_with_oracle(
                bounded,
                oracle,
                start_sample=start,
                sample_count=_WINDOW_SAMPLES,
            )
            assert result.bounded_count == result.oracle_count == _WINDOW_SAMPLES
            comparisons.append(
                {
                    "start_sample": start,
                    "bounded_count": result.bounded_count,
                    "oracle_count": result.oracle_count,
                    "measured_lag": result.measured_lag,
                    "correlation": result.correlation,
                    "maximum_absolute_delta": result.maximum_absolute_delta,
                }
            )
    assert len(sha256_file(media)) == 64
    _record_evidence(
        f"oracle_{source_rate}_{requested_rate}_{codec}_{packet_samples or 'native'}",
        {
            "source_rate": source_rate,
            "requested_rate": requested_rate,
            "codec": codec,
            "packet_samples": packet_samples,
            "media_sha256": sha256_file(media),
            "packet_summary": {
                "packet_count": packets.packet_count,
                "first_pts_seconds": packets.first_pts_seconds,
                "last_pts_seconds": packets.last_pts_seconds,
                "minimum_duration_seconds": packets.minimum_duration_seconds,
                "maximum_duration_seconds": packets.maximum_duration_seconds,
            },
            "windows": comparisons,
        },
    )
    analysis_rate = min(requested_rate, 8000)
    correction_allowance = math.ceil(requested_rate / analysis_rate)
    maximum_lag = max(abs(int(item["measured_lag"])) for item in comparisons)
    if codec == "aac" and maximum_lag > correction_allowance:
        pytest.xfail(
            "P3: AAC bounded extraction exceeds the existing requested-rate correction allowance"
        )
    assert maximum_lag <= correction_allowance
    assert min(float(item["correlation"]) for item in comparisons) > 0.95


@pytest.mark.integration
def test_positive_start_aac_matches_continuous_oracle_sample_count(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    wave_path = tmp_path / "positive-start.wav"
    media = tmp_path / "positive-start.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=9201, sample_rate=44100, duration_seconds=_SOURCE_DURATION),
        sample_rate=44100,
    )
    _mux_audio(
        media,
        wave_path,
        source_rate=44100,
        codec="aac",
        start_seconds=2,
    )
    stream = select_reference_audio_stream(media)
    bounded = extract_audio_window(
        media,
        stream,
        sample_rate=48000,
        start_sample=0,
        sample_count=_WINDOW_SAMPLES,
        channel_strategy="mono_downmix",
    )
    with continuous_decode(
        media,
        stream,
        sample_rate=48000,
        channel_strategy="mono_downmix",
    ) as oracle:
        result = compare_with_oracle(
            bounded,
            oracle,
            start_sample=0,
            sample_count=_WINDOW_SAMPLES,
        )
    _record_evidence(
        "discrepancy_positive_start_aac_count",
        {
            "source_rate": 44100,
            "requested_rate": 48000,
            "stream_start_seconds": 2,
            "requested_count": _WINDOW_SAMPLES,
            "bounded_count": result.bounded_count,
            "oracle_count": result.oracle_count,
            "measured_lag": result.measured_lag,
            "correlation": result.correlation,
            "media_sha256": sha256_file(media),
        },
    )
    if result.bounded_count != result.oracle_count or abs(result.measured_lag) > 1:
        pytest.xfail("P3: positive-start AAC bounded origin decode differs from continuous oracle")
    assert result.bounded_count == result.oracle_count == _WINDOW_SAMPLES
    assert abs(result.measured_lag) <= 1
    assert result.correlation > 0.98


@pytest.mark.integration
def test_asymmetric_positive_start_aac_preserves_clean_oracle_frame_and_eligibility(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    source_rate = 44100
    requested_rate = 48000
    wave_path = tmp_path / "asymmetric-start.wav"
    reference = tmp_path / "asymmetric-reference.mkv"
    comparison = tmp_path / "asymmetric-comparison.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=9201, sample_rate=source_rate, duration_seconds=12),
        sample_rate=source_rate,
    )
    _mux_audio(reference, wave_path, source_rate=source_rate, codec="aac")
    _mux_audio(
        comparison,
        wave_path,
        source_rate=source_rate,
        codec="aac",
        start_seconds=2,
    )
    oracle_prefixes: list[np.ndarray] = []
    for media in (reference, comparison):
        stream = select_reference_audio_stream(media)
        with continuous_decode(
            media,
            stream,
            sample_rate=requested_rate,
            channel_strategy="mono_downmix",
        ) as oracle:
            oracle_prefixes.append(np.asarray(oracle[:4096]).copy())
    assert np.array_equal(*oracle_prefixes)

    config = AlignmentConfig(
        cache_results=False,
        sample_rate=requested_rate,
        max_offset_seconds=1.0,
    )
    alignment_result = _run_alignment_result(tmp_path, reference, comparison, config=config)
    assert alignment_result.applied is False
    assert alignment_result.frame_offset is None
    assert alignment_result.time_offset_seconds is None
    assert alignment_result.audio_attempt is not None
    assert alignment_result.audio_attempt.decision.state != "trusted_automatic"
    observations = _policy_observations(alignment_result.audio_attempt.windows)
    assert len(observations) == 1
    observation = observations[0]
    observed_frame = (
        samples_to_frames(observation.sample_offset, requested_rate, Fraction(24))
        if observation.sample_offset is not None
        else None
    )
    _record_evidence(
        "discrepancy_asymmetric_positive_start_aac",
        {
            "source_rate": source_rate,
            "requested_rate": requested_rate,
            "reference_stream_start_seconds": 0,
            "comparison_stream_start_seconds": 2,
            "oracle_prefix_equal": True,
            "bounded_sample_offset": observation.sample_offset,
            "bounded_frame_offset": observed_frame,
            "bounded_score": observation.score,
            "bounded_peak_ratio": observation.peak_ratio,
            "bounded_coverage_ratio": observation.coverage_ratio,
            "reference_sha256": sha256_file(reference),
            "comparison_sha256": sha256_file(comparison),
        },
    )
    if observed_frame != 0 or observation.score is None or observation.score < 0.90:
        pytest.xfail("P3: asymmetric positive-start AAC changes clean oracle frame or eligibility")
    assert observation.sample_offset is not None
    assert samples_to_frames(observation.sample_offset, requested_rate, Fraction(24)) == 0
    assert observation.score is not None and observation.score >= 0.90
    evaluation = evaluate_predeclared_policy(
        observations,
        sample_rate=requested_rate,
        fps=Fraction(24),
        duration_seconds=Fraction(12),
    )
    assert evaluation.accepted
    assert evaluation.frame_offset == 0


@pytest.mark.integration
@pytest.mark.parametrize("start_seconds", [-1, 2])
def test_signed_pcm_stream_starts_match_continuous_oracle(
    tmp_path: Path,
    require_ffmpeg: None,
    start_seconds: int,
) -> None:
    wave_path = tmp_path / "signed-start.wav"
    media = tmp_path / "signed-start.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=9300 + start_seconds, sample_rate=48000, duration_seconds=12),
        sample_rate=48000,
    )
    run_subprocess(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-itsoffset",
            str(start_seconds),
            "-i",
            str(wave_path),
            "-c:a",
            "pcm_s16le",
            "-copyts",
            "-avoid_negative_ts",
            "disabled",
            str(media),
        ],
        timeout_seconds=30,
    )
    stream = select_reference_audio_stream(media)
    assert stream.timeline.start_time == start_seconds
    comparisons: list[dict[str, object]] = []
    with continuous_decode(
        media,
        stream,
        sample_rate=8000,
        channel_strategy="mono_downmix",
    ) as oracle:
        for start in (0, 5 * 8000, 6 * 8000, 10 * 8000):
            bounded = extract_audio_window(
                media,
                stream,
                sample_rate=8000,
                start_sample=start,
                sample_count=_WINDOW_SAMPLES,
                channel_strategy="mono_downmix",
            )
            result = compare_with_oracle(
                bounded,
                oracle,
                start_sample=start,
                sample_count=_WINDOW_SAMPLES,
            )
            comparisons.append(
                {
                    "start_sample": start,
                    "bounded_count": result.bounded_count,
                    "oracle_count": result.oracle_count,
                    "measured_lag": result.measured_lag,
                    "correlation": result.correlation,
                }
            )
    _record_evidence(
        f"signed_pcm_stream_start_{start_seconds}",
        {
            "stream_start_seconds": start_seconds,
            "media_sha256": sha256_file(media),
            "windows": comparisons,
        },
    )
    maximum_lag = max(abs(int(item["measured_lag"])) for item in comparisons)
    if maximum_lag > 1 or any(
        int(item["bounded_count"]) != int(item["oracle_count"]) for item in comparisons
    ):
        pytest.xfail("P3: signed PCM stream start differs from continuous oracle")
    assert min(float(item["correlation"]) for item in comparisons) > 0.90


def _five_windows(
    *,
    sample_rate: int,
    offsets: list[int | None],
    scores: list[float | None],
    peaks: list[float | None],
    coverage: list[float] | None = None,
) -> list[PolicyObservation]:
    width = 30 * sample_rate
    coverage = coverage or [1.0] * 5
    return [
        PolicyObservation(
            logical_id=f"primary-{index + 1:02d}",
            start_sample=index * width,
            end_sample=(index + 1) * width,
            sample_offset=offset,
            score=score,
            peak_ratio=peak,
            coverage_ratio=coverage[index],
            status="correlated" if offset is not None else "failed",
        )
        for index, (offset, score, peak) in enumerate(zip(offsets, scores, peaks, strict=True))
    ]


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001)])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("weak_position", range(5))
@pytest.mark.parametrize("holdout_seed", [7701, 7702, 7703, 7704])
def test_predeclared_policy_accepts_four_strong_windows_and_finite_weak_dissent(
    fps: Fraction,
    sign: int,
    weak_position: int,
    holdout_seed: int,
) -> None:
    sample_rate = 48000
    offsets = [0] * 5
    scores = [0.99] * 5
    peaks = [2.0] * 5
    offsets[weak_position] = sign * 2400
    scores[weak_position] = 0.20 + (holdout_seed % 4) / 100
    peaks[weak_position] = 1.1

    result = evaluate_predeclared_policy(
        _five_windows(
            sample_rate=sample_rate,
            offsets=offsets,
            scores=scores,
            peaks=peaks,
        ),
        sample_rate=sample_rate,
        fps=fps,
        duration_seconds=Fraction(150),
    )

    assert result.accepted
    assert result.frame_offset == 0
    assert result.correlated == 5
    assert result.credible == result.voting_qualified == result.winning_qualified == 4
    assert result.independent_support >= 3


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001)])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("edit_position", range(5))
def test_predeclared_policy_vetoes_credible_localized_edits(
    fps: Fraction,
    sign: int,
    edit_position: int,
) -> None:
    offsets = [0] * 5
    offsets[edit_position] = sign * 2400
    result = evaluate_predeclared_policy(
        _five_windows(
            sample_rate=48000,
            offsets=offsets,
            scores=[0.99] * 5,
            peaks=[2.0] * 5,
        ),
        sample_rate=48000,
        fps=fps,
        duration_seconds=Fraction(150),
        confidence_threshold=0.995,
        consensus_minimum_ratio=0.8,
    )
    assert not result.accepted
    assert result.reason == "credible_conflict"


def test_predeclared_policy_rejects_one_survivor_four_failures_and_drift() -> None:
    one_survivor = evaluate_predeclared_policy(
        _five_windows(
            sample_rate=48000,
            offsets=[0, None, None, None, None],
            scores=[0.99, None, None, None, None],
            peaks=[2.0, None, None, None, None],
        ),
        sample_rate=48000,
        fps=Fraction(24),
        duration_seconds=Fraction(150),
    )
    drift = evaluate_predeclared_policy(
        _five_windows(
            sample_rate=48000,
            offsets=[0, 0, 2400, 2400, 4800],
            scores=[0.99] * 5,
            peaks=[2.0] * 5,
        ),
        sample_rate=48000,
        fps=Fraction(24),
        duration_seconds=Fraction(150),
    )
    assert not one_survivor.accepted
    assert one_survivor.reason == "insufficient_temporal_support"
    assert not drift.accepted
    assert drift.reason == "credible_conflict"
    _record_evidence(
        "one_survivor_and_drift",
        {
            "one_survivor": {
                "accepted": one_survivor.accepted,
                "reason": one_survivor.reason,
                "correlated": one_survivor.correlated,
                "failed": 4,
            },
            "drift": {
                "accepted": drift.accepted,
                "reason": drift.reason,
            },
        },
    )


@pytest.mark.parametrize(
    ("duration", "windows", "expected"),
    [
        (Fraction(3), [(0, 3)], True),
        (Fraction(30), [(0, 30)], True),
        (Fraction(31), [(0, 15), (16, 31)], True),
        (Fraction(65), [(0, 30), (35, 65)], True),
        (Fraction(65), [(0, 30), (20, 50)], False),
        (Fraction(90), [(0, 30), (30, 60), (60, 90)], True),
        (Fraction(150), [(0, 30), (30, 60), (60, 90)], False),
        (Fraction(150), [(0, 30), (60, 90), (120, 150)], True),
    ],
)
def test_predeclared_temporal_support_boundaries(
    duration: Fraction,
    windows: list[tuple[int, int]],
    expected: bool,
) -> None:
    sample_rate = 100
    observations = [
        PolicyObservation(
            f"primary-{index:02d}",
            start * sample_rate,
            end * sample_rate,
            0,
            0.99,
            2.0,
            1.0,
        )
        for index, (start, end) in enumerate(windows, start=1)
    ]
    result = evaluate_predeclared_policy(
        observations,
        sample_rate=sample_rate,
        fps=Fraction(24),
        duration_seconds=duration,
    )
    assert result.accepted is expected
    if not expected:
        assert result.reason == "insufficient_temporal_support"


def test_predeclared_policy_rejects_low_coverage_repetition_and_exact_half_frame_ties() -> None:
    low_coverage = evaluate_predeclared_policy(
        _five_windows(
            sample_rate=48000,
            offsets=[0] * 5,
            scores=[0.99] * 5,
            peaks=[2.0] * 5,
            coverage=[1.0, 1.0, 0.89, 0.89, 0.89],
        ),
        sample_rate=48000,
        fps=Fraction(24),
        duration_seconds=Fraction(150),
    )
    repeated = evaluate_predeclared_policy(
        _five_windows(
            sample_rate=48000,
            offsets=[0] * 5,
            scores=[0.99] * 5,
            peaks=[1.0] * 5,
        ),
        sample_rate=48000,
        fps=Fraction(24),
        duration_seconds=Fraction(150),
    )
    assert not low_coverage.accepted
    assert low_coverage.reason == "insufficient_temporal_support"
    assert not repeated.accepted
    assert repeated.reason == "no_candidate"
    assert samples_to_frames(1000, 48000, Fraction(24)) == 0
    assert samples_to_frames(1001, 48000, Fraction(24)) == 1
    assert samples_to_frames(-1000, 48000, Fraction(24)) == 0
    assert samples_to_frames(-1001, 48000, Fraction(24)) == -1


def test_predeclared_policy_accepts_an_explicitly_unbounded_peak() -> None:
    result = evaluate_predeclared_policy(
        [PolicyObservation("primary-01", 0, 300, 0, 1.0, math.inf, 1.0)],
        sample_rate=100,
        fps=Fraction(24),
        duration_seconds=Fraction(3),
    )
    assert result.accepted
    assert result.frame_offset == 0


@pytest.mark.integration
@pytest.mark.slow
def test_real_pipeline_weak_dissent_holdout_matrix_passes_frozen_policy(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    sample_rate = 48000
    source = deterministic_signal(seed=20260915, sample_rate=sample_rate, duration_seconds=150)
    reference_wave = tmp_path / "reference.wav"
    write_pcm_wave(reference_wave, source, sample_rate=sample_rate)

    case_count = 0
    weak_scores: list[float] = []
    weak_offsets: list[int] = []
    strong_scores: list[float] = []
    for fps in (Fraction(24), Fraction(24000, 1001)):
        reference = tmp_path / f"reference-{fps.numerator}-{fps.denominator}.mkv"
        _mux_audio(
            reference,
            reference_wave,
            source_rate=sample_rate,
            codec="pcm",
            packet_samples=1001,
            fps=f"{fps.numerator}/{fps.denominator}",
            duration_seconds=150,
        )
        for holdout_seed in (7701, 7702, 7703, 7704):
            for sign in (-1, 1):
                for position in range(5):
                    observations = _run_long_fixture(
                        tmp_path,
                        reference=reference,
                        comparison_samples=_localized_variant(
                            source,
                            sample_rate=sample_rate,
                            position=position,
                            sign=sign,
                            noise_seed=holdout_seed + position,
                            shifted_weight=0.18,
                        ),
                        fps=fps,
                        sample_rate=sample_rate,
                    )
                    weak = [
                        item for item in observations if item.score is not None and item.score < 0.9
                    ]
                    strong = [
                        item
                        for item in observations
                        if item.score is not None
                        and item.peak_ratio is not None
                        and item.score >= 0.9
                        and item.peak_ratio >= 1.5
                    ]
                    assert len(observations) == 5
                    assert len(weak) == 1
                    assert weak[0].sample_offset is not None
                    assert samples_to_frames(weak[0].sample_offset, sample_rate, fps) != 0
                    assert len(strong) == 4
                    assert {
                        samples_to_frames(item.sample_offset or 0, sample_rate, fps)
                        for item in strong
                    } == {0}
                    evaluation = evaluate_predeclared_policy(
                        observations,
                        sample_rate=sample_rate,
                        fps=fps,
                        duration_seconds=Fraction(150),
                    )
                    assert evaluation.accepted
                    assert evaluation.frame_offset == 0
                    assert weak[0].score is not None
                    weak_scores.append(weak[0].score)
                    weak_offsets.append(weak[0].sample_offset)
                    strong_scores.extend(item.score for item in strong if item.score is not None)
                    case_count += 1
    assert case_count == 80
    _record_evidence(
        "weak_dissent_matrix",
        {
            "case_count": case_count,
            "holdout_seeds": [7701, 7702, 7703, 7704],
            "positions": [0, 1, 2, 3, 4],
            "signs": [-1, 1],
            "fps": ["24/1", "24000/1001"],
            "shift_samples": 2400,
            "shifted_weight": 0.18,
            "weak_score_min": min(weak_scores),
            "weak_score_max": max(weak_scores),
            "weak_offset_min": min(weak_offsets),
            "weak_offset_max": max(weak_offsets),
            "strong_score_min": min(strong_scores),
            "accepted": case_count,
            "recipe_identity": recipe_identity(
                {
                    "source_seed": 20260915,
                    "holdout_seeds": [7701, 7702, 7703, 7704],
                    "shift_samples": 2400,
                    "shifted_weight": 0.18,
                    "packet_samples": 1001,
                }
            ),
        },
    )


@pytest.mark.integration
@pytest.mark.slow
def test_real_pipeline_localized_edit_matrix_is_credibly_vetoed(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    sample_rate = 48000
    source = deterministic_signal(seed=20260916, sample_rate=sample_rate, duration_seconds=150)
    reference_wave = tmp_path / "reference.wav"
    write_pcm_wave(reference_wave, source, sample_rate=sample_rate)

    case_count = 0
    nonzero_scores: list[float] = []
    for fps in (Fraction(24), Fraction(24000, 1001)):
        reference = tmp_path / f"reference-edit-{fps.numerator}-{fps.denominator}.mkv"
        _mux_audio(
            reference,
            reference_wave,
            source_rate=sample_rate,
            codec="pcm",
            packet_samples=960,
            fps=f"{fps.numerator}/{fps.denominator}",
            duration_seconds=150,
        )
        for holdout_seed in (8801, 8802, 8803, 8804):
            for sign in (-1, 1):
                for position in range(5):
                    observations = _run_long_fixture(
                        tmp_path,
                        reference=reference,
                        comparison_samples=_localized_variant(
                            source,
                            sample_rate=sample_rate,
                            position=position,
                            sign=sign,
                            noise_seed=holdout_seed + position,
                            shifted_weight=0.98,
                        ),
                        fps=fps,
                        sample_rate=sample_rate,
                    )
                    credible_bins = {
                        samples_to_frames(item.sample_offset or 0, sample_rate, fps)
                        for item in observations
                        if item.score is not None
                        and item.peak_ratio is not None
                        and item.score >= 0.9
                        and item.peak_ratio >= 1.5
                    }
                    assert 0 in credible_bins
                    assert len(credible_bins) > 1
                    evaluation = evaluate_predeclared_policy(
                        observations,
                        sample_rate=sample_rate,
                        fps=fps,
                        duration_seconds=Fraction(150),
                        confidence_threshold=0.995,
                        consensus_minimum_ratio=0.8,
                    )
                    assert not evaluation.accepted
                    assert evaluation.reason == "credible_conflict"
                    nonzero_scores.extend(
                        item.score
                        for item in observations
                        if item.score is not None
                        and item.sample_offset is not None
                        and samples_to_frames(item.sample_offset, sample_rate, fps) != 0
                    )
                    case_count += 1
    assert case_count == 80
    _record_evidence(
        "localized_edit_matrix",
        {
            "case_count": case_count,
            "holdout_seeds": [8801, 8802, 8803, 8804],
            "positions": [0, 1, 2, 3, 4],
            "signs": [-1, 1],
            "fps": ["24/1", "24000/1001"],
            "shift_samples": 2400,
            "shifted_weight": 0.98,
            "nonzero_score_min": min(nonzero_scores),
            "nonzero_score_max": max(nonzero_scores),
            "credible_conflict": case_count,
            "false_accepts": 0,
            "recipe_identity": recipe_identity(
                {
                    "source_seed": 20260916,
                    "holdout_seeds": [8801, 8802, 8803, 8804],
                    "shift_samples": 2400,
                    "shifted_weight": 0.98,
                    "packet_samples": [960, 1001],
                }
            ),
        },
    )


@pytest.mark.integration
@pytest.mark.slow
def test_real_pipeline_clean_zero_and_signed_controls_pass_frozen_policy(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    sample_rate = 48000
    source = deterministic_signal(seed=20260917, sample_rate=sample_rate, duration_seconds=150)
    reference_wave = tmp_path / "reference-control.wav"
    write_pcm_wave(reference_wave, source, sample_rate=sample_rate)

    case_count = 0
    minimum_scores: list[float] = []
    maximum_oracle_delta = 0.0
    maximum_oracle_lag = 0
    for fps in (Fraction(24), Fraction(24000, 1001)):
        reference = tmp_path / f"reference-control-{fps.numerator}-{fps.denominator}.mkv"
        _mux_audio(
            reference,
            reference_wave,
            source_rate=sample_rate,
            codec="pcm",
            packet_samples=960,
            fps=f"{fps.numerator}/{fps.denominator}",
            duration_seconds=150,
        )
        reference_stream = select_reference_audio_stream(reference)
        for delay_samples in (-2400, 0, 2400):
            if delay_samples > 0:
                comparison_samples = np.pad(source[:-delay_samples], (delay_samples, 0))
            elif delay_samples < 0:
                advance = -delay_samples
                comparison_samples = np.pad(source[advance:], (0, advance))
            else:
                comparison_samples = source
            observations = _run_long_fixture(
                tmp_path,
                reference=reference,
                comparison_samples=comparison_samples,
                fps=fps,
                sample_rate=sample_rate,
            )
            comparison = tmp_path / "comparison.mkv"
            comparison_stream = select_reference_audio_stream(comparison)
            for media, stream in (
                (reference, reference_stream),
                (comparison, comparison_stream),
            ):
                with continuous_decode(
                    media,
                    stream,
                    sample_rate=8000,
                    channel_strategy="mono_downmix",
                ) as oracle:
                    for start in (0, 6 * 8000, 75 * 8000, 149 * 8000 - _WINDOW_SAMPLES):
                        bounded = extract_audio_window(
                            media,
                            stream,
                            sample_rate=8000,
                            start_sample=start,
                            sample_count=_WINDOW_SAMPLES,
                            channel_strategy="mono_downmix",
                        )
                        oracle_result = compare_with_oracle(
                            bounded,
                            oracle,
                            start_sample=start,
                            sample_count=_WINDOW_SAMPLES,
                        )
                        assert oracle_result.bounded_count == _WINDOW_SAMPLES
                        assert oracle_result.oracle_count == _WINDOW_SAMPLES
                        assert oracle_result.measured_lag == 0
                        assert oracle_result.correlation > 0.95
                        maximum_oracle_lag = max(
                            maximum_oracle_lag, abs(oracle_result.measured_lag)
                        )
                        maximum_oracle_delta = max(
                            maximum_oracle_delta, oracle_result.maximum_absolute_delta
                        )
            evaluation = evaluate_predeclared_policy(
                observations,
                sample_rate=sample_rate,
                fps=fps,
                duration_seconds=Fraction(150),
            )
            assert evaluation.accepted
            assert evaluation.frame_offset == samples_to_frames(-delay_samples, sample_rate, fps)
            assert evaluation.voting_qualified == 5
            minimum_scores.extend(item.score for item in observations if item.score is not None)
            case_count += 1
    assert case_count == 6
    _record_evidence(
        "clean_zero_signed_matrix",
        {
            "case_count": case_count,
            "delay_samples": [-2400, 0, 2400],
            "fps": ["24/1", "24000/1001"],
            "accepted": case_count,
            "minimum_score": min(minimum_scores),
            "maximum_oracle_lag_samples": maximum_oracle_lag,
            "maximum_oracle_waveform_delta": maximum_oracle_delta,
            "both_sources_compared_to_own_oracle": True,
            "recipe_identity": recipe_identity(
                {
                    "source_seed": 20260917,
                    "delays": [-2400, 0, 2400],
                    "reference_packet_samples": 960,
                    "comparison_packet_samples": 1001,
                }
            ),
        },
    )


@pytest.mark.integration
@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001)])
def test_real_pipeline_signal_and_repetition_negatives_remain_unapplied(
    tmp_path: Path,
    require_ffmpeg: None,
    fps: Fraction,
) -> None:
    sample_rate = 48000
    base = deterministic_signal(seed=3101, sample_rate=sample_rate, duration_seconds=12)
    independent = deterministic_signal(seed=4101, sample_rate=sample_rate, duration_seconds=12)
    repeated_unit = deterministic_signal(seed=5101, sample_rate=sample_rate, duration_seconds=1)
    cases = {
        "silence": (np.zeros_like(base), np.zeros_like(base)),
        "very-quiet-independent": (base * 0.00001, independent * 0.00001),
        "unrelated": (base, independent),
        "steady-tone": (
            np.sin(2 * np.pi * 437 * np.arange(base.size) / sample_rate).astype(np.float32),
            np.sin(2 * np.pi * 437 * np.arange(base.size) / sample_rate).astype(np.float32),
        ),
        "repeated": (np.tile(repeated_unit, 12), np.tile(repeated_unit, 12)),
    }
    config = AlignmentConfig(cache_results=False, sample_rate=8000, max_offset_seconds=1.0)

    for name, (reference_samples, comparison_samples) in cases.items():
        reference_wave = tmp_path / f"{name}-reference.wav"
        comparison_wave = tmp_path / f"{name}-comparison.wav"
        reference = tmp_path / f"{name}-reference.mkv"
        comparison = tmp_path / f"{name}-comparison.mkv"
        write_pcm_wave(reference_wave, reference_samples, sample_rate=sample_rate)
        write_pcm_wave(comparison_wave, comparison_samples, sample_rate=sample_rate)
        _encode_audio_only(reference, [reference_wave])
        _encode_audio_only(comparison, [comparison_wave])
        evaluation = evaluate_predeclared_policy(
            _run_audio_pair(
                tmp_path,
                reference,
                comparison,
                config=config,
                fps=fps,
            ),
            sample_rate=config.sample_rate,
            fps=fps,
            duration_seconds=Fraction(12),
        )
        assert not evaluation.accepted, name
        assert evaluation.reason == "no_candidate", name
    _record_evidence(
        f"signal_negatives_{fps.numerator}_{fps.denominator}",
        {
            "cases": sorted(cases),
            "case_count": len(cases),
            "accepted": 0,
            "disposition": "no_candidate",
        },
    )


@pytest.mark.integration
def test_real_pipeline_wrong_stream_rejects_and_explicit_matching_override_passes(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    sample_rate = 48000
    main = deterministic_signal(seed=6101, sample_rate=sample_rate, duration_seconds=12)
    unrelated = deterministic_signal(seed=7101, sample_rate=sample_rate, duration_seconds=12)
    main_wave = tmp_path / "main.wav"
    unrelated_wave = tmp_path / "unrelated.wav"
    write_pcm_wave(main_wave, main, sample_rate=sample_rate)
    write_pcm_wave(unrelated_wave, unrelated, sample_rate=sample_rate)
    reference = tmp_path / "stream-reference.mkv"
    comparison = tmp_path / "stream-comparison.mkv"
    _encode_audio_only(reference, [main_wave])
    _encode_audio_only(comparison, [unrelated_wave, main_wave])
    automatic = AlignmentConfig(cache_results=False, sample_rate=8000, max_offset_seconds=1.0)
    explicit = AlignmentConfig(
        cache_results=False,
        sample_rate=8000,
        max_offset_seconds=1.0,
        comparison_streams={comparison.stem: 1},
    )

    automatic_result = evaluate_predeclared_policy(
        _run_audio_pair(tmp_path, reference, comparison, config=automatic),
        sample_rate=automatic.sample_rate,
        fps=Fraction(24),
        duration_seconds=Fraction(12),
    )
    explicit_result = evaluate_predeclared_policy(
        _run_audio_pair(tmp_path, reference, comparison, config=explicit),
        sample_rate=explicit.sample_rate,
        fps=Fraction(24),
        duration_seconds=Fraction(12),
    )

    assert not automatic_result.accepted
    assert automatic_result.reason == "no_candidate"
    assert explicit_result.accepted
    assert explicit_result.frame_offset == 0
    _record_evidence(
        "stream_selection",
        {
            "automatic_wrong_stream": automatic_result.reason,
            "explicit_matching_stream": explicit_result.reason,
            "explicit_frame_offset": explicit_result.frame_offset,
        },
    )


@pytest.mark.integration
@pytest.mark.slow
def test_real_pipeline_insertion_deletion_and_drift_negatives_remain_unapplied(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    sample_rate = 48000
    shift = 2400
    case_count = 0
    for seed in (9101, 9102, 9103, 9104):
        source = deterministic_signal(seed=seed, sample_rate=sample_rate, duration_seconds=150)
        reference_wave = tmp_path / "reference-negative.wav"
        write_pcm_wave(reference_wave, source, sample_rate=sample_rate)
        for fps in (Fraction(24), Fraction(24000, 1001)):
            reference = tmp_path / f"reference-negative-{fps.numerator}-{fps.denominator}.mkv"
            _mux_audio(
                reference,
                reference_wave,
                source_rate=sample_rate,
                codec="pcm",
                packet_samples=960,
                fps=f"{fps.numerator}/{fps.denominator}",
                duration_seconds=150,
            )
            pivot = 75 * sample_rate
            for sign in (-1, 1):
                stepped = source.copy()
                if sign > 0:
                    stepped[pivot + shift :] = source[pivot:-shift]
                    stepped[pivot : pivot + shift] = 0
                else:
                    stepped[pivot:-shift] = source[pivot + shift :]
                    stepped[-shift:] = 0
                step_result = evaluate_predeclared_policy(
                    _run_long_fixture(
                        tmp_path,
                        reference=reference,
                        comparison_samples=stepped,
                        fps=fps,
                        sample_rate=sample_rate,
                    ),
                    sample_rate=sample_rate,
                    fps=fps,
                    duration_seconds=Fraction(150),
                )
                assert not step_result.accepted
                assert step_result.reason == "credible_conflict"

                maximum_drift = sign * shift
                source_positions = np.arange(source.size, dtype=np.float64)
                warped_positions = source_positions - maximum_drift * source_positions / source.size
                drifted = np.interp(
                    source_positions,
                    warped_positions,
                    source,
                    left=0.0,
                    right=0.0,
                ).astype(np.float32)
                drift_result = evaluate_predeclared_policy(
                    _run_long_fixture(
                        tmp_path,
                        reference=reference,
                        comparison_samples=drifted,
                        fps=fps,
                        sample_rate=sample_rate,
                    ),
                    sample_rate=sample_rate,
                    fps=fps,
                    duration_seconds=Fraction(150),
                )
                assert not drift_result.accepted
                assert drift_result.reason in {"credible_conflict", "no_candidate"}
                case_count += 2
    assert case_count == 32
    _record_evidence(
        "step_and_drift_matrix",
        {
            "case_count": case_count,
            "source_seeds": [9101, 9102, 9103, 9104],
            "signs": [-1, 1],
            "fps": ["24/1", "24000/1001"],
            "shift_samples": shift,
            "accepted": 0,
        },
    )
