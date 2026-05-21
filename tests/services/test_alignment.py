"Unit tests for audio alignment service."

# pyright: reportPrivateUsage=false

from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import tomli_w

from frame_compare.errors import (
    AudioAlignmentError,
    CacheCorruptionError,
    CacheVersionMismatchError,
    FFmpegError,
    FFmpegNotFoundError,
    VSPreviewError,
)
from frame_compare.services.alignment import (
    _cross_correlate,
    _extract_audio,
    _probe_fps,
    _samples_to_frames,
    align_clips,
    load_cached_offsets,
    save_offsets_cache,
)
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.progress_protocol import ProgressReporter


def test_alignment_result_is_frozen():
    """Test that AlignmentResult is immutable."""
    res = AlignmentResult("ref", "comp", 0, 0.0, 1.0, "cross_correlation", "computed")
    with pytest.raises(FrozenInstanceError):
        res.frame_offset = 10  # type: ignore


def test_alignment_config_defaults():
    """Test AlignmentConfig default values."""
    cfg = AlignmentConfig()
    assert cfg.enable is True
    assert cfg.sample_rate == 8000
    assert cfg.max_offset_seconds == 30.0
    assert cfg.use_vspreview is False
    assert cfg.force_interactive is False
    assert cfg.cache_results is True


def test_cross_correlate_identical_signals():
    """Test alignment of identical signals."""
    ref = np.array([1.0, 0.5, 0.0, -0.5], dtype=np.float32)
    comp = ref.copy()
    offset, score = _cross_correlate(ref, comp)
    assert offset == 0
    assert score == pytest.approx(1.0, abs=1e-6)  # type: ignore


def test_cross_correlate_positive_shift():
    """Test alignment where comparison starts after reference."""
    ref = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)
    comp = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)
    offset, _ = _cross_correlate(ref, comp)
    assert offset == 2


def test_cross_correlate_negative_shift():
    """Test alignment where comparison starts before reference."""
    ref = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)
    comp = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)
    offset, _ = _cross_correlate(ref, comp)
    assert offset == -2


def test_cross_correlate_zero_norm_raises():
    """Test that zero-norm signals raise AudioAlignmentError."""
    ref = np.zeros(10, dtype=np.float32)
    comp = np.ones(10, dtype=np.float32)
    with pytest.raises(AudioAlignmentError, match="zero-norm"):
        _cross_correlate(ref, comp)


def test_samples_to_frames_integer_fps():
    """Test sample to frame conversion with integer FPS."""
    assert _samples_to_frames(8000, 8000, Fraction(24, 1)) == 24


def test_samples_to_frames_fractional_fps():
    """Test sample to frame conversion with fractional FPS."""
    # 24000/1001 * (8008/8000) = 23.976... * 1.001 = 24.0
    assert _samples_to_frames(8008, 8000, Fraction(24000, 1001)) == 24


@patch("frame_compare.services.alignment.run_subprocess")
def test_probe_fps_fraction(mock_run: MagicMock):
    """Test probing FPS when it returns a fraction."""
    mock_run.return_value.stdout = b"24000/1001\n"
    res = _probe_fps(Path("test.mkv"))
    assert res == Fraction(24000, 1001)
    mock_run.assert_called_once_with(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "csv=p=0",
            "test.mkv",
        ],
        timeout_seconds=15.0,
    )


@patch("frame_compare.services.alignment.run_subprocess")
def test_probe_fps_integer(mock_run: MagicMock):
    """Test probing FPS when it returns an integer."""
    mock_run.return_value.stdout = b"24\n"
    res = _probe_fps(Path("test.mkv"))
    assert res == Fraction(24, 1)


@patch("frame_compare.services.alignment.run_subprocess")
def test_probe_fps_empty_output_preserves_ffmpeg_error(mock_run: MagicMock):
    """Empty ffprobe output should preserve the original FFmpegError details."""
    proc = MagicMock()
    proc.stdout = b""
    proc.returncode = 7
    mock_run.return_value = proc

    with pytest.raises(FFmpegError) as exc_info:
        _probe_fps(Path("test.mkv"))
    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details.get("returncode") == 7
    assert "ffprobe returned empty output" in str(exc_info.value.context.details.get("stderr", ""))


@patch("frame_compare.services.alignment.run_subprocess")
def test_probe_fps_not_found_raises(mock_run: MagicMock):
    """Test probing FPS when ffprobe is missing."""
    mock_run.side_effect = FileNotFoundError()
    with pytest.raises(FFmpegNotFoundError):
        _probe_fps(Path("test.mkv"))


@patch("frame_compare.services.alignment.run_subprocess")
def test_probe_fps_nonzero_exit_raises(mock_run: MagicMock):
    """Test probing FPS when ffprobe fails."""
    from subprocess import CalledProcessError

    mock_run.side_effect = CalledProcessError(1, ["ffprobe"], stderr=b"error")
    with pytest.raises(FFmpegError):
        _probe_fps(Path("test.mkv"))


@patch("frame_compare.services.alignment.run_subprocess")
def test_extract_audio_ffmpeg_not_found(mock_run: MagicMock):
    """Test audio extraction when ffmpeg is missing."""
    mock_run.side_effect = FileNotFoundError()
    with pytest.raises(FFmpegNotFoundError):
        _extract_audio(Path("test.mkv"), 8000)


@patch("frame_compare.services.alignment.run_subprocess")
def test_probe_fps_timeout_raises(mock_run: MagicMock):
    """Test probing FPS timeout surfaces as FFmpegError."""
    from subprocess import TimeoutExpired

    mock_run.side_effect = TimeoutExpired(cmd=["ffprobe"], timeout=15.0)
    with pytest.raises(FFmpegError) as exc_info:
        _probe_fps(Path("test.mkv"))
    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details.get("returncode") == 124
    assert "timed out" in str(exc_info.value.context.details.get("stderr", ""))


@patch("frame_compare.services.alignment.run_subprocess")
def test_extract_audio_ffmpeg_fails(mock_run: MagicMock):
    """Test audio extraction when ffmpeg fails."""
    from subprocess import CalledProcessError

    mock_run.side_effect = CalledProcessError(1, ["ffmpeg"], stderr=b"error")
    with pytest.raises(FFmpegError):
        _extract_audio(Path("test.mkv"), 8000)


@patch("frame_compare.services.alignment.run_subprocess")
def test_extract_audio_timeout_raises(mock_run: MagicMock):
    """Test audio extraction timeout surfaces as FFmpegError."""
    from subprocess import TimeoutExpired

    mock_run.side_effect = TimeoutExpired(cmd=["ffmpeg"], timeout=120.0)
    with pytest.raises(FFmpegError) as exc_info:
        _extract_audio(Path("test.mkv"), 8000)
    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details.get("returncode") == 124
    assert "timed out" in str(exc_info.value.context.details.get("stderr", ""))


@patch("frame_compare.services.alignment.run_subprocess")
def test_extract_audio_empty_raises(mock_run: MagicMock):
    """Test audio extraction when output is empty."""
    mock_run.return_value.stdout = b""
    with pytest.raises(AudioAlignmentError, match="empty audio"):
        _extract_audio(Path("test.mkv"), 8000)
    mock_run.assert_called_once_with(
        [
            "ffmpeg",
            "-i",
            "test.mkv",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "f32le",
            "-",
        ],
        timeout_seconds=120.0,
    )


def test_cross_correlate_respects_max_offset_window():
    """Bounded offset search should not select peaks outside the configured window."""
    reference = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)
    comparison = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)

    offset, _ = _cross_correlate(reference, comparison, max_offset_samples=1)

    assert abs(offset) <= 1


def test_cross_correlate_empty_signal_raises() -> None:
    """Empty signals must fail fast with a clear alignment error."""
    ref = np.array([], dtype=np.float32)
    comp = np.ones(10, dtype=np.float32)

    with pytest.raises(AudioAlignmentError, match="empty audio signal"):
        _cross_correlate(ref, comp)


def test_load_cached_offsets_missing_returns_none(tmp_path: Path):
    """Test cache loading when file is missing."""
    assert load_cached_offsets(tmp_path, [Path("ref.mkv")]) is None


def test_load_cached_offsets_valid_returns_dict(tmp_path: Path):
    """Test cache loading with valid TOML."""
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 42,
            "time_offset_seconds": 1.751,
            "correlation_score": 0.987,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    res = load_cached_offsets(tmp_path, [Path("ref.mkv"), Path("comp_a.mkv")])
    assert res is not None
    assert "ref:comp_a" in res
    assert res["ref:comp_a"].frame_offset == 42
    assert res["ref:comp_a"].source == "cached"
    assert res["ref:comp_a"].algorithm == "cross_correlation"


def test_load_cached_offsets_legacy_method_key_returns_dict(tmp_path: Path) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 42,
            "time_offset_seconds": 1.751,
            "correlation_score": 0.987,
            "method": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    res = load_cached_offsets(tmp_path, [Path("ref.mkv"), Path("comp_a.mkv")])
    assert res is not None
    assert res["ref:comp_a"].algorithm == "cross_correlation"
    assert res["ref:comp_a"].source == "cached"


def test_load_cached_offsets_valid_no_match_returns_empty(tmp_path: Path):
    """Test cache loading when requested keys are not in valid file."""
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "other:x": {
            "reference_clip": "other.mkv",
            "comparison_clip": "x.mkv",
            "frame_offset": 0,
            "time_offset_seconds": 0.0,
            "correlation_score": 1.0,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    res = load_cached_offsets(tmp_path, [Path("ref.mkv"), Path("comp_a.mkv")])
    assert res == {}


def test_load_cached_offsets_corruption_raises(tmp_path: Path):
    """Test cache loading with invalid TOML."""
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text("not valid toml {{{ ")
    with pytest.raises(CacheCorruptionError):
        load_cached_offsets(tmp_path, [Path("ref.mkv")])


def test_load_cached_offsets_version_mismatch_raises(tmp_path: Path):
    """Test cache loading with version mismatch."""
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text('version = "999"')
    with pytest.raises(CacheVersionMismatchError):
        load_cached_offsets(tmp_path, [Path("ref.mkv")])


def test_load_cached_offsets_malformed_entry_raises_cache_corruption(tmp_path: Path):
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            # missing required keys like frame_offset
            "reference_clip": "ref.mkv",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    with pytest.raises(CacheCorruptionError):
        load_cached_offsets(tmp_path, [Path("ref.mkv"), Path("comp_a.mkv")])


def test_load_cached_offsets_invalid_algorithm_raises_cache_corruption(tmp_path: Path):
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 42,
            "time_offset_seconds": 1.751,
            "correlation_score": 0.987,
            "algorithm": "unsupported_alg_name",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    with pytest.raises(CacheCorruptionError):
        load_cached_offsets(tmp_path, [Path("ref.mkv"), Path("comp_a.mkv")])


def test_save_offsets_cache_writes_toml(tmp_path: Path):
    """Test saving offsets to cache."""
    res = [
        AlignmentResult(
            reference_clip="ref.mkv",
            comparison_clip="comp.mkv",
            frame_offset=10,
            time_offset_seconds=0.4,
            correlation_score=0.9,
            algorithm="cross_correlation",
            source="computed",
        )
    ]
    save_offsets_cache(tmp_path, res)
    cache_file = tmp_path / "audio_offsets.toml"
    assert cache_file.exists()
    content = cache_file.read_text()
    assert 'version = "1"' in content
    assert '["ref:comp"]' in content


def test_save_offsets_cache_normalizes_legacy_method_keys(tmp_path: Path) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    existing = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 42,
            "time_offset_seconds": 1.751,
            "correlation_score": 0.987,
            "method": "cross_correlation",
        },
    }
    cache_file.write_text(tomli_w.dumps(existing), encoding="utf-8")

    save_offsets_cache(
        tmp_path,
        [
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp_b.mkv",
                frame_offset=10,
                time_offset_seconds=0.4,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )

    content = cache_file.read_text(encoding="utf-8")
    assert 'method = "cross_correlation"' not in content
    assert content.count('algorithm = "cross_correlation"') == 2


def test_save_offsets_cache_logs_corrupt_existing_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text("not valid toml", encoding="utf-8")

    warnings: list[tuple[str, dict[str, object]]] = []

    def _warning(event: str, **kwargs: object) -> None:
        warnings.append((event, dict(kwargs)))

    monkeypatch.setattr("frame_compare.services.alignment.log.warning", _warning)

    save_offsets_cache(
        tmp_path,
        [
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=1,
                time_offset_seconds=0.04,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )

    assert any(event == "audio_offsets_cache_corrupt_on_write" for event, _ in warnings)


def test_save_offsets_cache_uses_atomic_bytes_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    res = [
        AlignmentResult(
            reference_clip="ref.mkv",
            comparison_clip="comp.mkv",
            frame_offset=10,
            time_offset_seconds=0.4,
            correlation_score=0.9,
            algorithm="cross_correlation",
            source="computed",
        )
    ]

    calls: list[Path] = []

    def _fake_write(path: Path, content: bytes) -> None:
        calls.append(path)
        path.write_bytes(content)

    monkeypatch.setattr("frame_compare.services.alignment.write_bytes_atomic", _fake_write)

    save_offsets_cache(tmp_path, res)
    assert calls == [tmp_path / "audio_offsets.toml"]


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
def test_align_clips_full_cache_hit_skips_probe_and_extract(
    mock_extract: MagicMock, mock_probe: MagicMock, tmp_path: Path
):
    """Test that full cache hit skips FFmpeg/FFprobe calls."""
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 10,
            "time_offset_seconds": 0.417,
            "correlation_score": 0.95,
            "algorithm": "cross_correlation",
        },
        "ref:comp_b": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_b.mkv",
            "frame_offset": 20,
            "time_offset_seconds": 0.834,
            "correlation_score": 0.92,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_probe.side_effect = AssertionError("should not be called")
    mock_extract.side_effect = AssertionError("should not be called")

    config = AlignmentConfig()
    results = align_clips(ref, [comp_a, comp_b], config, tmp_path)

    assert len(results) == 2
    assert results[0].comparison_clip == "comp_a.mkv"
    assert results[0].frame_offset == 10
    assert results[1].comparison_clip == "comp_b.mkv"
    assert results[1].frame_offset == 20


def test_align_clips_duplicate_stems_fail_before_starting_progress(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "dup.mkv"
    comp_b = tmp_path / "dup.mp4"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    reporter = MagicMock(spec=ProgressReporter)

    with pytest.raises(AudioAlignmentError, match="Duplicate comparison clip stems detected"):
        align_clips(ref, [comp_a, comp_b], AlignmentConfig(), tmp_path, progress=reporter)

    reporter.start_phase.assert_not_called()
    reporter.complete_phase.assert_not_called()


def test_align_clips_completes_progress_when_cache_load_raises(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    (tmp_path / "audio_offsets.toml").write_text("not valid toml {{{ ", encoding="utf-8")
    reporter = MagicMock(spec=ProgressReporter)

    with pytest.raises(CacheCorruptionError):
        align_clips(ref, [comp], AlignmentConfig(), tmp_path, progress=reporter)


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
@patch("frame_compare.services.alignment._cross_correlate")
def test_align_clips_partial_cache_hit_computes_only_missing_and_preserves_order(
    mock_corr: MagicMock, mock_extract: MagicMock, mock_probe: MagicMock, tmp_path: Path
):
    """Test partial cache hit behavior and result ordering."""
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    # Cache only comp_a
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 10,
            "time_offset_seconds": 0.417,
            "correlation_score": 0.95,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_probe.return_value = Fraction(24, 1)
    # Return dummy arrays

    def extract_side_effect(path: Path, sr: int) -> np.ndarray:
        return np.ones(10, dtype=np.float32)

    mock_extract.side_effect = extract_side_effect
    mock_corr.return_value = (0, 0.99)

    config = AlignmentConfig()
    # Request comp_a and comp_b
    results = align_clips(ref, [comp_a, comp_b], config, tmp_path)

    assert len(results) == 2
    assert results[0].comparison_clip == "comp_a.mkv"
    assert results[0].frame_offset == 10  # from cache
    assert results[1].comparison_clip == "comp_b.mkv"
    assert results[1].frame_offset == 0  # from mock computation

    # Check that extract was called for ref and comp_b, but NOT comp_a
    called_paths = [call[0][0] for call in mock_extract.call_args_list]  # type: ignore
    assert ref in called_paths
    assert comp_b in called_paths
    assert comp_a not in called_paths


@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
@patch("frame_compare.services.alignment._cross_correlate")
def test_align_clips_launches_vspreview_when_enabled(
    mock_corr: MagicMock,
    mock_extract: MagicMock,
    mock_probe: MagicMock,
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
):
    """When configured, align_clips should generate/launch a VSPreview verification session."""
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    mock_probe.return_value = Fraction(24, 1)

    def extract_side_effect(path: Path, sr: int) -> np.ndarray:
        return np.ones(10, dtype=np.float32)

    mock_extract.side_effect = extract_side_effect
    mock_corr.return_value = (0, 0.99)
    mock_is_available.return_value = True
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=False)
    align_clips(ref, [comp_a, comp_b], config, tmp_path)

    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    assert kwargs["reference"] == ref
    assert kwargs["comparisons"] == [comp_a, comp_b]
    suggested = kwargs["suggested_offsets_by_key"]
    assert suggested == {"ref:comp_a": 0, "ref:comp_b": 0}


@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
def test_align_clips_full_cache_hit_still_launches_vspreview_when_enabled(
    mock_extract: MagicMock,
    mock_probe: MagicMock,
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Cached/manual-only runs should still build/launch VSPreview verification."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 12,
            "time_offset_seconds": 0.5,
            "correlation_score": 0.95,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_probe.side_effect = AssertionError("should not be called")
    mock_extract.side_effect = AssertionError("should not be called")
    mock_is_available.return_value = True
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 12
    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    assert kwargs["suggested_offsets_by_key"] == {"ref:comp": 12}
    assert kwargs["config"].enabled is True


@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
def test_align_clips_force_interactive_raises_when_vspreview_unavailable(
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Force-interactive mode must fail fast if VSPreview is unavailable."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 2,
            "time_offset_seconds": 0.083,
            "correlation_score": 0.98,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_is_available.return_value = False

    config = AlignmentConfig(
        enable=True,
        use_vspreview=True,
        force_interactive=True,
        cache_results=True,
    )
    with pytest.raises(AudioAlignmentError, match="Interactive alignment requested"):
        align_clips(ref, [comp], config, tmp_path)

    mock_launch.assert_not_called()


@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
def test_align_clips_vspreview_unavailable_generates_script_without_launch(
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """When optional VSPreview is unavailable, adapter should be called with enabled=False."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 7,
            "time_offset_seconds": 0.292,
            "correlation_score": 0.96,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_is_available.return_value = False
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    align_clips(ref, [comp], config, tmp_path)

    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    assert kwargs["config"].enabled is False


@patch("frame_compare.services.alignment.log.warning")
@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
def test_align_clips_optional_vspreview_probe_failure_generates_script_without_launch(
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    mock_warn: MagicMock,
    tmp_path: Path,
) -> None:
    """Optional VSPreview probe failures should be visible but non-fatal."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 7,
            "time_offset_seconds": 0.292,
            "correlation_score": 0.96,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_is_available.side_effect = RuntimeError("broken import metadata")
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 7
    mock_warn.assert_called_once()
    warn_args, warn_kwargs = mock_warn.call_args
    assert warn_args == ("vspreview_availability_probe_failed",)
    assert warn_kwargs["exception_type"] == "RuntimeError"
    assert warn_kwargs["error"] == "broken import metadata"
    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert launch_kwargs["config"].enabled is False


@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
def test_align_clips_force_interactive_launches_when_vspreview_available(
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Force-interactive mode should launch VSPreview when available."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 3,
            "time_offset_seconds": 0.125,
            "correlation_score": 0.99,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_is_available.return_value = True
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(
        enable=True,
        use_vspreview=False,
        force_interactive=True,
        cache_results=True,
    )
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 3
    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    assert kwargs["config"].enabled is True


@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
def test_align_clips_force_interactive_probe_failure_raises_alignment_error(
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Forced interactive mode should fail deliberately when availability cannot be checked."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 3,
            "time_offset_seconds": 0.125,
            "correlation_score": 0.99,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_is_available.side_effect = RuntimeError("broken import metadata")

    config = AlignmentConfig(
        enable=True,
        use_vspreview=False,
        force_interactive=True,
        cache_results=True,
    )
    with pytest.raises(AudioAlignmentError, match="availability check failed") as exc_info:
        align_clips(ref, [comp], config, tmp_path)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    mock_launch.assert_not_called()


@patch("frame_compare.services.alignment.log.warning")
@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
def test_align_clips_vspreview_errors_are_warning_only_when_not_forced(
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    mock_warn: MagicMock,
    tmp_path: Path,
) -> None:
    """Adapter launch failures are warning-only for optional VSPreview mode."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 1,
            "time_offset_seconds": 0.042,
            "correlation_score": 0.91,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_is_available.return_value = True
    mock_launch.side_effect = VSPreviewError("adapter failure")

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 1
    mock_warn.assert_called_once()
    _, kwargs = mock_warn.call_args
    assert "VSPreview error: adapter failure" in kwargs["error"]
    assert kwargs["force_interactive"] is False


@patch("frame_compare.services.alignment.launch_alignment_verification_session")
@patch("frame_compare.services.alignment.is_vspreview_available")
def test_align_clips_vspreview_errors_raise_when_force_interactive(
    mock_is_available: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Adapter launch failures should fail-fast in force-interactive mode."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 1,
            "time_offset_seconds": 0.042,
            "correlation_score": 0.91,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_is_available.return_value = True
    mock_launch.side_effect = VSPreviewError("adapter failure")

    config = AlignmentConfig(
        enable=True,
        use_vspreview=False,
        force_interactive=True,
        cache_results=True,
    )
    with pytest.raises(VSPreviewError, match="adapter failure"):
        align_clips(ref, [comp], config, tmp_path)
