"""P5A test-only experiment for a fixed ten-second extraction preroll.

The experiment changes only the existing test-visible preroll constant before
calling the production extractor. It deliberately does not copy or reimplement
the FFmpeg extraction recipe.
"""

from __future__ import annotations

import json
import math
import os
import platform
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import pytest

from frame_compare.services import alignment_audio
from frame_compare.services.alignment_audio import (
    AudioStreamInfo,
    extract_audio_window,
    select_reference_audio_stream,
)
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.runtime_contract import media_runtime_fingerprint, runtime_kind
from tests.integration.alignment_oracle import (
    PolicyObservation,
    compare_with_oracle,
    continuous_decode,
    deterministic_signal,
    evaluate_predeclared_policy,
    recipe_identity,
    sha256_file,
    write_pcm_wave,
)
from tests.integration.test_alignment_continuous_decode_oracle import (
    _encode_audio_only,
    _localized_variant,
    _mux_audio,
    _run_audio_pair,
)

_WINDOW_SAMPLES = 2048
_FIXED_PREROLL_SECONDS = 10


def _version_line(executable: str) -> str:
    process = run_subprocess([executable, "-version"], timeout_seconds=10)
    return process.stdout.decode("utf-8", errors="replace").splitlines()[0]


def _record_evidence(section: str, payload: dict[str, object]) -> None:
    """Write optional pathless scalar evidence for a selected runtime run."""
    destination = os.environ.get("FRAME_COMPARE_P5_EVIDENCE_PATH")
    if not destination:
        return
    path = Path(destination)
    if path.exists() and path.stat().st_size:
        evidence = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    else:
        evidence = {
            "schema_version": 1,
            "purpose": "p5_ten_second_preroll_scalar_evidence",
            "environment": {
                "platform": platform.platform(),
                "runtime_kind": runtime_kind(),
                "alignment_runtime_fingerprint": media_runtime_fingerprint("alignment"),
                "ffmpeg": _version_line("ffmpeg"),
                "ffprobe": _version_line("ffprobe"),
            },
            "sections": {},
        }
    sections = cast(dict[str, object], evidence["sections"])
    sections[section] = payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


@contextmanager
def _with_preroll(monkeypatch: pytest.MonkeyPatch, seconds: int) -> Generator[None]:
    with monkeypatch.context() as context:
        context.setattr(alignment_audio, "_SEEK_PREROLL_SECONDS", seconds)
        yield


def _pair_observations(
    root: Path,
    reference: Path,
    comparison: Path,
    *,
    config: AlignmentConfig,
    fps: Fraction,
    preroll_seconds: int,
    monkeypatch: pytest.MonkeyPatch,
) -> list[PolicyObservation]:
    with _with_preroll(monkeypatch, preroll_seconds):
        return _run_audio_pair(root, reference, comparison, config=config, fps=fps)


def _frame_offset(sample_offset: int | None, *, sample_rate: int, fps: Fraction) -> int | None:
    if sample_offset is None:
        return None
    return samples_to_frames(sample_offset, sample_rate, fps)


def _extract_variant(
    media: Path,
    stream: AudioStreamInfo,
    *,
    sample_rate: int,
    start_sample: int,
    sample_count: int,
    preroll_seconds: int,
    monkeypatch: pytest.MonkeyPatch,
) -> np.ndarray:
    with _with_preroll(monkeypatch, preroll_seconds):
        return extract_audio_window(
            media,
            stream,
            sample_rate=sample_rate,
            start_sample=start_sample,
            sample_count=sample_count,
            channel_strategy="mono_downmix",
        )


@pytest.mark.integration
def test_ten_second_preroll_changes_only_seek_context(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wave_path = tmp_path / "seek-shape.wav"
    media = tmp_path / "seek-shape.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=10101, sample_rate=48000, duration_seconds=12),
        sample_rate=48000,
    )
    _mux_audio(media, wave_path, source_rate=48000, codec="pcm")
    stream = select_reference_audio_stream(media)
    captured: list[list[str]] = []
    original = alignment_audio.run_subprocess

    def capture(
        argv: Sequence[str],
        *,
        timeout_seconds: float | None = None,
        cwd: Path | None = None,
        check: bool = True,
    ) -> CompletedProcess[bytes]:
        captured.append([str(item) for item in argv])
        return original(
            argv,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
            check=check,
        )

    monkeypatch.setattr(alignment_audio, "run_subprocess", capture)
    for preroll_seconds in (5, _FIXED_PREROLL_SECONDS):
        _extract_variant(
            media,
            stream,
            sample_rate=8000,
            start_sample=88_000,
            sample_count=_WINDOW_SAMPLES,
            preroll_seconds=preroll_seconds,
            monkeypatch=monkeypatch,
        )
    assert len(captured) == 2
    assert captured[0] != captured[1]
    normalized = []
    for argv in captured:
        normalized_argv = list(argv)
        seek_index = normalized_argv.index("-ss")
        normalized_argv[seek_index + 1] = "<seek-context>"
        normalized.append(normalized_argv)
    assert normalized[0] == normalized[1]
    _record_evidence(
        "argv_shape",
        {
            "baseline_preroll_seconds": 5,
            "variant_preroll_seconds": _FIXED_PREROLL_SECONDS,
            "changed_argument": "-ss value only",
            "same_filters_crop_resample_output_cap": True,
            "same_timeout_seconds": 120,
            "recipe_identity": recipe_identity(
                {
                    "source": "deterministic_signal:10101",
                    "codec": "pcm",
                    "sample_rate": 48000,
                    "requested_rate": 8000,
                    "start_sample": 88000,
                    "sample_count": _WINDOW_SAMPLES,
                }
            ),
        },
    )


@pytest.mark.integration
def test_ten_second_preroll_evaluates_positive_start_aac_control(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_rate = 44100
    requested_rate = 48000
    wave_path = tmp_path / "positive-start.wav"
    media = tmp_path / "positive-start.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=9201, sample_rate=source_rate, duration_seconds=12),
        sample_rate=source_rate,
    )
    _mux_audio(
        media,
        wave_path,
        source_rate=source_rate,
        codec="aac",
        start_seconds=2,
    )
    stream = select_reference_audio_stream(media)
    with continuous_decode(
        media,
        stream,
        sample_rate=requested_rate,
        channel_strategy="mono_downmix",
    ) as oracle:
        results: dict[str, dict[str, object]] = {}
        for label, preroll_seconds in (("baseline_5s", 5), ("variant_10s", 10)):
            bounded = _extract_variant(
                media,
                stream,
                sample_rate=requested_rate,
                start_sample=0,
                sample_count=_WINDOW_SAMPLES,
                preroll_seconds=preroll_seconds,
                monkeypatch=monkeypatch,
            )
            comparison = compare_with_oracle(
                bounded,
                oracle,
                start_sample=0,
                sample_count=_WINDOW_SAMPLES,
            )
            results[label] = {
                "bounded_count": comparison.bounded_count,
                "oracle_count": comparison.oracle_count,
                "measured_lag_samples": comparison.measured_lag,
                "correlation": comparison.correlation,
            }
    variant = results["variant_10s"]
    assert variant["oracle_count"] == _WINDOW_SAMPLES
    assert cast(int, variant["bounded_count"]) > 0
    _record_evidence(
        "positive_start_aac",
        {
            "fixture_recipe": recipe_identity(
                {
                    "source_seed": 9201,
                    "source_rate": source_rate,
                    "requested_rate": requested_rate,
                    "codec": "aac",
                    "stream_start_seconds": 2,
                    "requested_count": _WINDOW_SAMPLES,
                }
            ),
            "media_sha256": sha256_file(media),
            "baseline_5s": results["baseline_5s"],
            "variant_10s": results["variant_10s"],
            "variant_matches_continuous_oracle": (
                variant["bounded_count"] == variant["oracle_count"]
                and variant["measured_lag_samples"] == 0
            ),
            "variant_changes_frame_or_eligibility": (
                variant["bounded_count"] != variant["oracle_count"]
                or variant["measured_lag_samples"] != 0
            ),
        },
    )

    reference = tmp_path / "asymmetric-reference.mkv"
    comparison = tmp_path / "asymmetric-comparison.mkv"
    _mux_audio(reference, wave_path, source_rate=source_rate, codec="aac")
    _mux_audio(
        comparison,
        wave_path,
        source_rate=source_rate,
        codec="aac",
        start_seconds=2,
    )
    config = AlignmentConfig(
        cache_results=False, sample_rate=requested_rate, max_offset_seconds=1.0
    )
    pair_results: dict[str, dict[str, object]] = {}
    for label, preroll_seconds in (("baseline_5s", 5), ("variant_10s", 10)):
        observations = _pair_observations(
            tmp_path,
            reference,
            comparison,
            config=config,
            fps=Fraction(24),
            preroll_seconds=preroll_seconds,
            monkeypatch=monkeypatch,
        )
        assert len(observations) == 1
        observation = observations[0]
        pair_results[label] = {
            "sample_offset": observation.sample_offset,
            "frame_offset": _frame_offset(
                observation.sample_offset,
                sample_rate=requested_rate,
                fps=Fraction(24),
            ),
            "score": observation.score,
            "peak_ratio": observation.peak_ratio,
            "coverage_ratio": observation.coverage_ratio,
        }
    variant_pair = pair_results["variant_10s"]
    _record_evidence(
        "asymmetric_positive_start_aac",
        {
            "fixture_recipe": recipe_identity(
                {
                    "source_seed": 9201,
                    "source_rate": source_rate,
                    "requested_rate": requested_rate,
                    "codec": "aac",
                    "reference_start_seconds": 0,
                    "comparison_start_seconds": 2,
                }
            ),
            "reference_media_sha256": sha256_file(reference),
            "comparison_media_sha256": sha256_file(comparison),
            "baseline_5s": pair_results["baseline_5s"],
            "variant_10s": pair_results["variant_10s"],
            "variant_expected_frame_offset": 0,
            "variant_matches_expected_frame": variant_pair["frame_offset"] == 0,
            "variant_quality_eligible": (
                variant_pair["score"] is not None and cast(float, variant_pair["score"]) >= 0.90
            ),
        },
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("source_rate", "requested_rate"),
    [(48000, 8000), (44100, 48000)],
)
def test_ten_second_preroll_rechecks_aac_seek_grid_holdouts(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
    source_rate: int,
    requested_rate: int,
) -> None:
    signal = deterministic_signal(
        seed=source_rate + requested_rate + 1,
        sample_rate=source_rate,
        duration_seconds=12,
    )
    wave_path = tmp_path / "source.wav"
    media = tmp_path / "source-aac.mkv"
    write_pcm_wave(wave_path, signal, sample_rate=source_rate)
    _mux_audio(media, wave_path, source_rate=source_rate, codec="aac")
    stream = select_reference_audio_stream(media)
    total = math.floor((stream.timeline.duration or Fraction(12)) * requested_rate)
    starts = (0, 5 * requested_rate - 1, 5 * requested_rate, 6 * requested_rate, total - 4096)
    results: dict[str, list[dict[str, object]]] = {}
    with continuous_decode(
        media,
        stream,
        sample_rate=requested_rate,
        channel_strategy="mono_downmix",
    ) as oracle:
        for label, preroll_seconds in (("baseline_5s", 5), ("variant_10s", 10)):
            measurements: list[dict[str, object]] = []
            for start in starts:
                bounded = _extract_variant(
                    media,
                    stream,
                    sample_rate=requested_rate,
                    start_sample=start,
                    sample_count=_WINDOW_SAMPLES,
                    preroll_seconds=preroll_seconds,
                    monkeypatch=monkeypatch,
                )
                comparison = compare_with_oracle(
                    bounded,
                    oracle,
                    start_sample=start,
                    sample_count=_WINDOW_SAMPLES,
                )
                measurements.append(
                    {
                        "start_sample": start,
                        "bounded_count": comparison.bounded_count,
                        "oracle_count": comparison.oracle_count,
                        "measured_lag_samples": comparison.measured_lag,
                        "correlation": comparison.correlation,
                    }
                )
            results[label] = measurements
    analysis_rate = min(requested_rate, 8000)
    allowance = math.ceil(requested_rate / analysis_rate)
    for measurements in results.values():
        assert all(item["bounded_count"] == _WINDOW_SAMPLES for item in measurements)
        assert all(item["oracle_count"] == _WINDOW_SAMPLES for item in measurements)
    _record_evidence(
        f"aac_seek_grid_{source_rate}_{requested_rate}",
        {
            "fixture_recipe": recipe_identity(
                {
                    "source_rate": source_rate,
                    "requested_rate": requested_rate,
                    "codec": "aac",
                    "starts": starts,
                    "requested_count": _WINDOW_SAMPLES,
                }
            ),
            "media_sha256": sha256_file(media),
            "existing_correction_allowance_samples": allowance,
            "baseline_5s": results["baseline_5s"],
            "variant_10s": results["variant_10s"],
            "variant_max_abs_lag_samples": max(
                abs(cast(int, item["measured_lag_samples"])) for item in results["variant_10s"]
            ),
            "variant_within_existing_allowance": all(
                abs(cast(int, item["measured_lag_samples"])) <= allowance
                for item in results["variant_10s"]
            ),
        },
    )


@pytest.mark.integration
def test_ten_second_preroll_preserves_clean_and_negative_holdouts(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_rate = 48000
    base = deterministic_signal(seed=3101, sample_rate=sample_rate, duration_seconds=12)
    independent = deterministic_signal(seed=4101, sample_rate=sample_rate, duration_seconds=12)
    repeated_unit = deterministic_signal(seed=5101, sample_rate=sample_rate, duration_seconds=1)
    cases = {
        "clean_zero": (base, base, True),
        "very_quiet_independent": (base * 0.00001, independent * 0.00001, False),
        "unrelated": (base, independent, False),
        "silence": (np.zeros_like(base), np.zeros_like(base), False),
        "steady_tone": (
            np.sin(2 * np.pi * 437 * np.arange(base.size) / sample_rate).astype(np.float32),
            np.sin(2 * np.pi * 437 * np.arange(base.size) / sample_rate).astype(np.float32),
            False,
        ),
        "repeated": (np.tile(repeated_unit, 12), np.tile(repeated_unit, 12), False),
    }
    config = AlignmentConfig(cache_results=False, sample_rate=8000, max_offset_seconds=1.0)
    outcomes: dict[str, object] = {}
    for fps in (Fraction(24), Fraction(24000, 1001)):
        for name, (reference_samples, comparison_samples, expected_acceptance) in cases.items():
            case_id = f"{name}-{fps.numerator}-{fps.denominator}"
            reference_wave = tmp_path / f"{case_id}-reference.wav"
            comparison_wave = tmp_path / f"{case_id}-comparison.wav"
            reference = tmp_path / f"{case_id}-reference.mkv"
            comparison = tmp_path / f"{case_id}-comparison.mkv"
            write_pcm_wave(reference_wave, reference_samples, sample_rate=sample_rate)
            write_pcm_wave(comparison_wave, comparison_samples, sample_rate=sample_rate)
            _encode_audio_only(reference, [reference_wave])
            _encode_audio_only(comparison, [comparison_wave])
            case_outcomes: dict[str, dict[str, object]] = {}
            for label, preroll_seconds in (("baseline_5s", 5), ("variant_10s", 10)):
                observations = _pair_observations(
                    tmp_path,
                    reference,
                    comparison,
                    config=config,
                    fps=fps,
                    preroll_seconds=preroll_seconds,
                    monkeypatch=monkeypatch,
                )
                evaluation = evaluate_predeclared_policy(
                    observations,
                    sample_rate=config.sample_rate,
                    fps=fps,
                    duration_seconds=Fraction(12),
                )
                case_outcomes[label] = {
                    "accepted": evaluation.accepted,
                    "reason": evaluation.reason,
                    "frame_offset": evaluation.frame_offset,
                }
            assert case_outcomes["variant_10s"] == case_outcomes["baseline_5s"]
            assert case_outcomes["variant_10s"]["accepted"] is expected_acceptance
            outcomes[case_id] = case_outcomes

    main_wave = tmp_path / "stream-main.wav"
    unrelated_wave = tmp_path / "stream-unrelated.wav"
    reference = tmp_path / "stream-reference.mkv"
    comparison = tmp_path / "stream-comparison.mkv"
    write_pcm_wave(main_wave, base, sample_rate=sample_rate)
    write_pcm_wave(unrelated_wave, independent, sample_rate=sample_rate)
    _encode_audio_only(reference, [main_wave])
    _encode_audio_only(comparison, [unrelated_wave, main_wave])
    automatic = AlignmentConfig(cache_results=False, sample_rate=8000, max_offset_seconds=1.0)
    explicit = AlignmentConfig(
        cache_results=False,
        sample_rate=8000,
        max_offset_seconds=1.0,
        comparison_streams={comparison.stem: 1},
    )
    stream_outcomes: dict[str, dict[str, object]] = {}
    for name, stream_config in (
        ("automatic_wrong_stream", automatic),
        ("explicit_match", explicit),
    ):
        run_outcomes: dict[str, dict[str, object]] = {}
        for label, preroll_seconds in (("baseline_5s", 5), ("variant_10s", 10)):
            observations = _pair_observations(
                tmp_path,
                reference,
                comparison,
                config=stream_config,
                fps=Fraction(24),
                preroll_seconds=preroll_seconds,
                monkeypatch=monkeypatch,
            )
            evaluation = evaluate_predeclared_policy(
                observations,
                sample_rate=stream_config.sample_rate,
                fps=Fraction(24),
                duration_seconds=Fraction(12),
            )
            run_outcomes[label] = {
                "accepted": evaluation.accepted,
                "reason": evaluation.reason,
                "frame_offset": evaluation.frame_offset,
            }
        assert run_outcomes["variant_10s"] == run_outcomes["baseline_5s"]
        stream_outcomes[name] = run_outcomes
    assert stream_outcomes["automatic_wrong_stream"]["variant_10s"]["accepted"] is False
    assert stream_outcomes["explicit_match"]["variant_10s"]["accepted"] is True
    outcomes["stream_selection"] = stream_outcomes
    _record_evidence(
        "clean_and_negative_holdouts",
        {
            "fixture_recipe": recipe_identity(
                {
                    "source_seed": 3101,
                    "independent_seed": 4101,
                    "repeated_seed": 5101,
                    "source_rate": sample_rate,
                    "requested_rate": config.sample_rate,
                    "duration_seconds": 12,
                    "families": sorted(cases),
                    "fps": ["24/1", "24000/1001"],
                    "stream_selection": True,
                }
            ),
            "outcomes": outcomes,
            "variant_changed_holdout_outcome": False,
        },
    )


@pytest.mark.integration
@pytest.mark.slow
def test_ten_second_preroll_preserves_p3_weak_and_edit_holdout_matrix(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_rate = 48000
    source = deterministic_signal(seed=20260915, sample_rate=sample_rate, duration_seconds=150)
    config = AlignmentConfig(cache_results=False, sample_rate=sample_rate, max_offset_seconds=1.0)
    weak_scores: list[float] = []
    weak_offsets: list[int] = []
    nonzero_scores: list[float] = []
    counts = {"weak_dissent": 0, "localized_edit": 0}
    for fps in (Fraction(24), Fraction(24000, 1001)):
        reference_wave = tmp_path / f"reference-{fps.numerator}-{fps.denominator}.wav"
        reference = tmp_path / f"reference-{fps.numerator}-{fps.denominator}.mkv"
        write_pcm_wave(reference_wave, source, sample_rate=sample_rate)
        _mux_audio(
            reference,
            reference_wave,
            source_rate=sample_rate,
            codec="pcm",
            packet_samples=1001,
            fps=f"{fps.numerator}/{fps.denominator}",
            duration_seconds=150,
        )
        for name, shifted_weight, seeds in (
            ("weak_dissent", 0.18, (7701, 7702, 7703, 7704)),
            ("localized_edit", 0.98, (8801, 8802, 8803, 8804)),
        ):
            for seed in seeds:
                for sign in (-1, 1):
                    for position in range(5):
                        comparison_samples = _localized_variant(
                            source,
                            sample_rate=sample_rate,
                            position=position,
                            sign=sign,
                            noise_seed=seed + position,
                            shifted_weight=shifted_weight,
                        )
                        case_id = (
                            f"{name}-{fps.numerator}-{fps.denominator}-{seed}-{sign}-{position}"
                        )
                        with TemporaryDirectory(dir=tmp_path, prefix="p5-case-") as directory:
                            case_root = Path(directory)
                            comparison_wave = case_root / f"{case_id}.wav"
                            comparison = case_root / f"{case_id}.mkv"
                            write_pcm_wave(
                                comparison_wave,
                                comparison_samples,
                                sample_rate=sample_rate,
                            )
                            _mux_audio(
                                comparison,
                                comparison_wave,
                                source_rate=sample_rate,
                                codec="pcm",
                                packet_samples=1001,
                                fps=f"{fps.numerator}/{fps.denominator}",
                                duration_seconds=150,
                            )
                            observations = _pair_observations(
                                case_root,
                                reference,
                                comparison,
                                config=config,
                                fps=fps,
                                preroll_seconds=_FIXED_PREROLL_SECONDS,
                                monkeypatch=monkeypatch,
                            )
                            assert len(observations) == 5
                            evaluation = evaluate_predeclared_policy(
                                observations,
                                sample_rate=sample_rate,
                                fps=fps,
                                duration_seconds=Fraction(150),
                            )
                        counts[name] += 1
                        if name == "weak_dissent":
                            weak = [
                                item
                                for item in observations
                                if item.score is not None and item.score < 0.9
                            ]
                            strong = [
                                item
                                for item in observations
                                if item.score is not None
                                and item.peak_ratio is not None
                                and item.score >= 0.9
                                and item.peak_ratio >= 1.5
                            ]
                            assert len(weak) == 1
                            assert len(strong) == 4
                            assert weak[0].sample_offset is not None
                            assert samples_to_frames(weak[0].sample_offset, sample_rate, fps) != 0
                            assert {
                                samples_to_frames(item.sample_offset or 0, sample_rate, fps)
                                for item in strong
                            } == {0}
                            assert evaluation.accepted
                            assert evaluation.frame_offset == 0
                            weak_scores.append(cast(float, weak[0].score))
                            weak_offsets.append(cast(int, weak[0].sample_offset))
                        else:
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
                            assert not evaluation.accepted
                            assert evaluation.reason == "credible_conflict"
                            nonzero_scores.extend(
                                cast(float, item.score)
                                for item in observations
                                if item.score is not None
                                and item.sample_offset is not None
                                and samples_to_frames(item.sample_offset, sample_rate, fps) != 0
                            )
    assert counts == {"weak_dissent": 80, "localized_edit": 80}
    _record_evidence(
        "weak_and_edit_holdout_matrix",
        {
            "fixture_recipe": recipe_identity(
                {
                    "source_seed": 20260915,
                    "weak_seeds": [7701, 7702, 7703, 7704],
                    "edit_seeds": [8801, 8802, 8803, 8804],
                    "positions": [0, 1, 2, 3, 4],
                    "signs": [-1, 1],
                    "fps": ["24/1", "24000/1001"],
                    "weak_shifted_weight": 0.18,
                    "edit_shifted_weight": 0.98,
                    "packet_samples": 1001,
                }
            ),
            "weak_dissent": {
                "cases": counts["weak_dissent"],
                "accepted": counts["weak_dissent"],
                "score_range": [min(weak_scores), max(weak_scores)],
                "offset_range_samples": [min(weak_offsets), max(weak_offsets)],
            },
            "localized_edit": {
                "cases": counts["localized_edit"],
                "credible_conflict": counts["localized_edit"],
                "false_accepts": 0,
                "nonzero_score_range": [min(nonzero_scores), max(nonzero_scores)],
            },
            "variant_matches_predeclared_p3_outcomes": True,
        },
    )
