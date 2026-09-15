"""P5B experiment for one bounded, grid-preserving extraction recipe."""

from __future__ import annotations

import json
import math
import os
import platform
from collections.abc import Iterator
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from frame_compare.services import alignment_audio
from frame_compare.services.alignment_audio import AudioStreamInfo
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.types import AlignmentChannelStrategy, AlignmentConfig
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.runtime_contract import media_runtime_fingerprint, runtime_kind
from tests.integration.alignment_oracle import (
    compare_with_oracle,
    continuous_decode,
    deterministic_signal,
    recipe_identity,
    sha256_file,
    write_pcm_wave,
)
from tests.integration.test_alignment_continuous_decode_oracle import (
    _mux_audio,
    _run_audio_pair,
)
from tests.integration.test_alignment_ten_second_preroll import (
    test_ten_second_preroll_preserves_clean_and_negative_holdouts as _p5a_clean_holdouts,
)
from tests.integration.test_alignment_ten_second_preroll import (
    test_ten_second_preroll_preserves_p3_weak_and_edit_holdout_matrix as _p5a_matrix_holdouts,
)

_WINDOW_SAMPLES = 2048
_FLOAT32_BYTES = np.dtype(np.float32).itemsize


def test_tracked_p5b_evidence_records_stop_without_production_change() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "alignment_oracle" / "p5b-results.json"
    raw = path.read_text(encoding="utf-8")
    evidence = json.loads(raw)
    assert evidence["production"] == {
        "extraction_recipe_changed": False,
        "estimator_policy_changed": False,
        "shared_cache_identity_changed": False,
    }
    assert evidence["disposition"].startswith("STOP")
    assert not evidence["aac_seek_grid_holdouts"]["native_macos_arm64"]["48000_to_8000"][
        "design_within_allowance"
    ]
    assert not evidence["aac_seek_grid_holdouts"]["docker_linux_arm64"]["44100_to_48000"][
        "design_within_allowance"
    ]
    assert "/Users/" not in raw
    assert "raw_samples" not in raw


def _version_line(executable: str) -> str:
    process = run_subprocess([executable, "-version"], timeout_seconds=10)
    return process.stdout.decode("utf-8", errors="replace").splitlines()[0]


def _record_evidence(section: str, payload: dict[str, object]) -> None:
    destination = os.environ.get("FRAME_COMPARE_P5B_EVIDENCE_PATH")
    if not destination:
        return
    path = Path(destination)
    if path.exists() and path.stat().st_size:
        evidence = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    else:
        evidence = {
            "schema_version": 1,
            "purpose": "p5b_grid_preserving_extraction_scalar_evidence",
            "environment": {
                "platform": platform.platform(),
                "runtime_kind": runtime_kind(),
                "alignment_runtime_fingerprint": media_runtime_fingerprint("alignment"),
                "ffmpeg": _version_line("ffmpeg"),
                "ffprobe": _version_line("ffprobe"),
            },
            "sections": {},
        }
    cast(dict[str, object], evidence["sections"])[section] = payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _grid_preserving_extract(
    video_path: Path,
    stream: AudioStreamInfo,
    *,
    sample_rate: int,
    start_sample: int,
    sample_count: int,
    channel_strategy: AlignmentChannelStrategy,
) -> np.ndarray:
    """Retain a decoded boundary packet, resample, then crop on output PTS."""
    preroll_samples = min(start_sample, alignment_audio._SEEK_PREROLL_SECONDS * sample_rate)
    window_start = stream.timeline.start_time + Fraction(start_sample, sample_rate)
    seek_time = max(
        Fraction(0),
        window_start - Fraction(preroll_samples, sample_rate) - stream.timeline.input_start_time,
    )
    if seek_time > 0 and stream.timeline.time_base is not None:
        seek_time = max(
            Fraction(0),
            (seek_time // stream.timeline.time_base) * stream.timeline.time_base
            - stream.timeline.time_base,
        )
    filters = []
    channel_args: list[str]
    if channel_strategy == "mono_downmix":
        channel_args = ["-ac", "1"]
    else:
        channel_args = []
        filters.append(alignment_audio._best_channel_audio_filter(stream))
    output_start = round(window_start * sample_rate)
    filters.extend(
        (
            f"aresample={sample_rate}",
            f"asettb=1/{sample_rate}",
            f"atrim=start_pts={output_start}:end_pts={output_start + sample_count}",
            "asetpts=PTS-STARTPTS",
            f"atrim=end_sample={sample_count}",
        )
    )
    seek_args = (
        ["-ss", alignment_audio._seconds_arg(seek_time), "-noaccurate_seek"]
        if seek_time > 0
        else []
    )
    if seek_time > 0 or stream.timeline.start_time != 0:
        seek_args.append("-copyts")
    process = run_subprocess(
        [
            "ffmpeg",
            *seek_args,
            "-i",
            str(video_path),
            "-map",
            f"0:a:{stream.audio_stream_index}",
            "-vn",
            *channel_args,
            "-af",
            ",".join(filters),
            "-fs",
            str(sample_count * _FLOAT32_BYTES),
            "-f",
            "f32le",
            "-",
        ],
        timeout_seconds=120.0,
    )
    if not process.stdout or len(process.stdout) % _FLOAT32_BYTES:
        raise AssertionError("P5B experiment returned invalid PCM")
    samples = np.frombuffer(process.stdout, dtype=np.float32)
    if samples.size > sample_count:
        raise AssertionError("P5B experiment exceeded the production output cap")
    return samples


@contextmanager
def _use_design(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    with monkeypatch.context() as context:
        context.setattr(alignment_audio, "extract_audio_window", _grid_preserving_extract)
        yield


@pytest.mark.integration
def test_grid_preserving_design_records_primary_and_grid_gate(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    measurements: dict[str, object] = {}
    with _use_design(monkeypatch):
        for source_rate, requested_rate, start_seconds in (
            (44100, 48000, 2),
            (48000, 8000, 0),
            (44100, 48000, 0),
        ):
            case = f"{source_rate}_to_{requested_rate}_start_{start_seconds}"
            wave = tmp_path / f"{case}.wav"
            media = tmp_path / f"{case}.mkv"
            write_pcm_wave(
                wave,
                deterministic_signal(
                    seed=9201 if start_seconds else source_rate + requested_rate + 1,
                    sample_rate=source_rate,
                    duration_seconds=12,
                ),
                sample_rate=source_rate,
            )
            _mux_audio(
                media,
                wave,
                source_rate=source_rate,
                codec="aac",
                start_seconds=start_seconds,
            )
            stream = alignment_audio.select_reference_audio_stream(media)
            total = math.floor((stream.timeline.duration or Fraction(12)) * requested_rate)
            starts = (
                0,
                5 * requested_rate - 1,
                5 * requested_rate,
                6 * requested_rate,
                total - 4096,
            )
            cells: list[dict[str, object]] = []
            with continuous_decode(
                media,
                stream,
                sample_rate=requested_rate,
                channel_strategy="mono_downmix",
            ) as oracle:
                for start in starts:
                    bounded = _grid_preserving_extract(
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
                    cells.append(
                        {
                            "start_sample": start,
                            "bounded_count": result.bounded_count,
                            "oracle_count": result.oracle_count,
                            "lag_samples": result.measured_lag,
                            "correlation": result.correlation,
                        }
                    )
            allowance = math.ceil(requested_rate / min(requested_rate, 8000))
            measurements[case] = {
                "media_sha256": sha256_file(media),
                "allowance_samples": allowance,
                "maximum_absolute_lag_samples": max(
                    abs(cast(int, cell["lag_samples"])) for cell in cells
                ),
                "minimum_correlation": min(cast(float, cell["correlation"]) for cell in cells),
                "all_counts_truthful": all(
                    cell["bounded_count"] == cell["oracle_count"] == _WINDOW_SAMPLES
                    for cell in cells
                ),
                "cells": cells,
            }

        source_rate = 44100
        requested_rate = 48000
        wave = tmp_path / "asymmetric.wav"
        reference = tmp_path / "asymmetric-reference.mkv"
        comparison = tmp_path / "asymmetric-comparison.mkv"
        write_pcm_wave(
            wave,
            deterministic_signal(seed=9201, sample_rate=source_rate, duration_seconds=12),
            sample_rate=source_rate,
        )
        _mux_audio(reference, wave, source_rate=source_rate, codec="aac")
        _mux_audio(comparison, wave, source_rate=source_rate, codec="aac", start_seconds=2)
        observations = _run_audio_pair(
            tmp_path,
            reference,
            comparison,
            config=AlignmentConfig(
                cache_results=False,
                sample_rate=requested_rate,
                max_offset_seconds=1.0,
            ),
        )
    observation = observations[0]
    asymmetric = {
        "sample_offset": observation.sample_offset,
        "frame_offset": (
            samples_to_frames(observation.sample_offset, requested_rate, Fraction(24))
            if observation.sample_offset is not None
            else None
        ),
        "score": observation.score,
        "peak_ratio": observation.peak_ratio,
        "coverage_ratio": observation.coverage_ratio,
    }
    _record_evidence(
        "primary_and_grid_gate",
        {
            "design": (
                "one-tick backward noaccurate input seek; decoded preroll resampled before "
                "crop on asettb=1/rate selected-stream output PTS"
            ),
            "recipe_identity": recipe_identity("p5b-grid-preserving-v1"),
            "same_timeout_seconds": 120,
            "same_output_sample_cap": True,
            "measurements": measurements,
            "asymmetric_positive_start_aac": asymmetric,
        },
    )
    assert cast(dict[str, object], measurements["44100_to_48000_start_2"])["all_counts_truthful"]
    assert asymmetric["frame_offset"] == 0
    assert cast(float, asymmetric["score"]) >= 0.90


@pytest.mark.integration
def test_grid_preserving_design_preserves_clean_signal_and_stream_holdouts(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _use_design(monkeypatch):
        _p5a_clean_holdouts(
            tmp_path,
            require_ffmpeg,
            monkeypatch,
        )
    _record_evidence("clean_signal_stream_holdouts", {"outcomes_preserved": True})


@pytest.mark.integration
@pytest.mark.slow
def test_grid_preserving_design_preserves_weak_and_edit_holdout_matrix(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _use_design(monkeypatch):
        _p5a_matrix_holdouts(
            tmp_path,
            require_ffmpeg,
            monkeypatch,
        )
    _record_evidence(
        "weak_and_edit_holdout_matrix",
        {
            "weak_dissent_cases": 80,
            "weak_dissent_accepted": 80,
            "localized_edit_cases": 80,
            "localized_edit_false_accepts": 0,
        },
    )
