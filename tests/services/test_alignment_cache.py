"""Audio alignment cache persistence tests."""

# pyright: reportPrivateUsage=false

from pathlib import Path

import pytest
import tomli_w

from frame_compare.services.alignment_cache import load_cached_offsets, save_offsets_cache
from frame_compare.services.types import AlignmentResult
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError


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


def test_save_offsets_cache_discards_stale_schema_version_when_writing_fresh_cache(
    tmp_path: Path,
) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    existing = {
        "version": "0",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 42,
            "time_offset_seconds": 1.751,
            "correlation_score": 0.987,
            "algorithm": "cross_correlation",
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
    assert 'version = "1"' in content
    assert 'version = "0"' not in content
    assert '["ref:comp_a"]' not in content
    assert '["ref:comp_b"]' in content


def test_save_offsets_cache_discards_invalid_existing_cache(tmp_path: Path) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    existing = {
        "version": "1",
        "ref:stale": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "stale.mkv",
            "frame_offset": 42,
            "time_offset_seconds": 1.751,
            "correlation_score": 0.987,
            "algorithm": "unsupported_alg_name",
        },
    }
    cache_file.write_text(tomli_w.dumps(existing), encoding="utf-8")

    save_offsets_cache(
        tmp_path,
        [
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=10,
                time_offset_seconds=0.4,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )

    content = cache_file.read_text(encoding="utf-8")
    assert '["ref:stale"]' not in content
    assert '["ref:comp"]' in content
    assert 'algorithm = "cross_correlation"' in content


def test_save_offsets_cache_logs_corrupt_existing_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text("not valid toml", encoding="utf-8")

    warnings: list[tuple[str, dict[str, object]]] = []

    def _warning(event: str, **kwargs: object) -> None:
        warnings.append((event, dict(kwargs)))

    monkeypatch.setattr("frame_compare.services.alignment_cache.log.warning", _warning)

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

    monkeypatch.setattr("frame_compare.services.alignment_cache.write_bytes_atomic", _fake_write)

    save_offsets_cache(tmp_path, res)
    assert calls == [tmp_path / "audio_offsets.toml"]
