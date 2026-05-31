"""Audio alignment cache persistence tests."""

# pyright: reportPrivateUsage=false

from pathlib import Path

import pytest
import tomli_w

from frame_compare.services.alignment_cache import (
    CACHE_VERSION,
    load_cached_offsets,
    save_offsets_cache,
)
from frame_compare.services.types import AlignmentResult
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError


def _make_result(
    *,
    comparison_clip: str = "comp_a.mkv",
    frame_offset: int = 42,
    time_offset_seconds: float = 1.751,
    correlation_score: float = 0.987,
) -> AlignmentResult:
    return AlignmentResult(
        reference_clip="ref.mkv",
        comparison_clip=comparison_clip,
        frame_offset=frame_offset,
        time_offset_seconds=time_offset_seconds,
        correlation_score=correlation_score,
        algorithm="cross_correlation",
        source="computed",
    )


def _touch_clip(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def _freshness_fields(
    reference: Path,
    comparison: Path,
    *,
    sample_rate: int = 8000,
    max_offset_seconds: float = 30.0,
) -> dict[str, object]:
    reference_stat = reference.stat()
    comparison_stat = comparison.stat()
    return {
        "reference_path": str(reference.resolve()),
        "reference_size_bytes": reference_stat.st_size,
        "reference_mtime_ns": reference_stat.st_mtime_ns,
        "comparison_path": str(comparison.resolve()),
        "comparison_size_bytes": comparison_stat.st_size,
        "comparison_mtime_ns": comparison_stat.st_mtime_ns,
        "sample_rate": sample_rate,
        "max_offset_seconds": max_offset_seconds,
    }


def _entry_dict(
    reference: Path,
    comparison: Path,
    *,
    frame_offset: int = 42,
    time_offset_seconds: float = 1.751,
    correlation_score: float = 0.987,
    algorithm: str = "cross_correlation",
    sample_rate: int = 8000,
    max_offset_seconds: float = 30.0,
) -> dict[str, object]:
    return {
        "reference_clip": reference.name,
        "comparison_clip": comparison.name,
        "frame_offset": frame_offset,
        "time_offset_seconds": time_offset_seconds,
        "correlation_score": correlation_score,
        "algorithm": algorithm,
        **_freshness_fields(
            reference,
            comparison,
            sample_rate=sample_rate,
            max_offset_seconds=max_offset_seconds,
        ),
    }


def _load(
    cache_dir: Path,
    reference: Path,
    comparisons: list[Path],
    *,
    sample_rate: int = 8000,
    max_offset_seconds: float = 30.0,
):
    return load_cached_offsets(
        cache_dir,
        reference,
        comparisons,
        sample_rate=sample_rate,
        max_offset_seconds=max_offset_seconds,
    )


def _save(
    cache_dir: Path,
    reference: Path,
    comparisons: list[Path],
    results: list[AlignmentResult],
    *,
    sample_rate: int = 8000,
    max_offset_seconds: float = 30.0,
) -> None:
    save_offsets_cache(
        cache_dir,
        reference=reference,
        comparisons=comparisons,
        sample_rate=sample_rate,
        max_offset_seconds=max_offset_seconds,
        results=results,
    )


def test_load_cached_offsets_missing_returns_none(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")

    assert _load(tmp_path, reference, []) is None


def test_load_cached_offsets_valid_returns_dict(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")
    _save(tmp_path, reference, [comparison], [_make_result()])

    res = _load(tmp_path, reference, [comparison])

    assert res is not None
    assert "ref:comp_a" in res
    assert res["ref:comp_a"].frame_offset == 42
    assert res["ref:comp_a"].source == "cached"
    assert res["ref:comp_a"].algorithm == "cross_correlation"


def test_load_cached_offsets_valid_no_match_returns_empty(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    cached_comparison = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")
    requested_comparison = _touch_clip(tmp_path / "comp_b.mkv", b"comp_b")
    _save(tmp_path, reference, [cached_comparison], [_make_result()])

    res = _load(tmp_path, reference, [requested_comparison])

    assert res == {}


def test_load_cached_offsets_missing_freshness_fields_is_cache_miss(tmp_path: Path) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": CACHE_VERSION,
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 42,
            "time_offset_seconds": 1.751,
            "correlation_score": 0.987,
            "algorithm": "cross_correlation",
        },
    }
    cache_file.write_text(tomli_w.dumps(data), encoding="utf-8")
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")

    res = _load(tmp_path, reference, [comparison])

    assert res == {}


def test_load_cached_offsets_same_stem_replacement_is_cache_miss(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp.mkv", b"old")
    _save(
        tmp_path,
        reference,
        [comparison],
        [_make_result(comparison_clip="comp.mkv")],
    )

    comparison.write_bytes(b"new payload with different size")

    res = _load(tmp_path, reference, [comparison])

    assert res == {}


def test_load_cached_offsets_sample_rate_drift_does_not_affect_other_entries(
    tmp_path: Path,
) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison_a = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")
    comparison_b = _touch_clip(tmp_path / "comp_b.mkv", b"comp_b")
    _save(
        tmp_path,
        reference,
        [comparison_a, comparison_b],
        [
            _make_result(comparison_clip="comp_a.mkv"),
            _make_result(comparison_clip="comp_b.mkv", frame_offset=7, time_offset_seconds=0.291),
        ],
        sample_rate=8000,
    )

    drifted = _load(tmp_path, reference, [comparison_a], sample_rate=16000)
    fresh = _load(tmp_path, reference, [comparison_b], sample_rate=8000)

    assert drifted == {}
    assert fresh is not None
    assert fresh["ref:comp_b"].frame_offset == 7


def test_load_cached_offsets_max_offset_drift_is_cache_miss(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")
    _save(
        tmp_path,
        reference,
        [comparison],
        [_make_result()],
        max_offset_seconds=30.0,
    )

    res = _load(tmp_path, reference, [comparison], max_offset_seconds=45.0)

    assert res == {}


def test_load_cached_offsets_corruption_raises(tmp_path: Path) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text("not valid toml {{{ ", encoding="utf-8")
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")

    with pytest.raises(CacheCorruptionError):
        _load(tmp_path, reference, [])


def test_load_cached_offsets_version_mismatch_raises(tmp_path: Path) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text('version = "999"', encoding="utf-8")
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")

    with pytest.raises(CacheVersionMismatchError):
        _load(tmp_path, reference, [])


def test_load_cached_offsets_malformed_entry_raises_cache_corruption(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": CACHE_VERSION,
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            **_freshness_fields(reference, comparison),
        },
    }
    cache_file.write_text(tomli_w.dumps(data), encoding="utf-8")

    with pytest.raises(CacheCorruptionError):
        _load(tmp_path, reference, [comparison])


def test_load_cached_offsets_invalid_algorithm_raises_cache_corruption(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": CACHE_VERSION,
        "ref:comp_a": _entry_dict(reference, comparison, algorithm="unsupported_alg_name"),
    }
    cache_file.write_text(tomli_w.dumps(data), encoding="utf-8")

    with pytest.raises(CacheCorruptionError):
        _load(tmp_path, reference, [comparison])


def test_save_offsets_cache_writes_toml_with_freshness(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp.mkv", b"comp")

    _save(
        tmp_path,
        reference,
        [comparison],
        [_make_result(comparison_clip="comp.mkv", frame_offset=10, time_offset_seconds=0.4)],
    )

    cache_file = tmp_path / "audio_offsets.toml"
    assert cache_file.exists()
    content = cache_file.read_text(encoding="utf-8")
    assert f'version = "{CACHE_VERSION}"' in content
    assert '["ref:comp"]' in content
    assert "reference_path" in content
    assert "comparison_mtime_ns" in content
    assert "sample_rate = 8000" in content


def test_save_offsets_cache_preserves_unrelated_current_entries(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison_a = _touch_clip(tmp_path / "comp_a.mkv", b"comp_a")
    comparison_b = _touch_clip(tmp_path / "comp_b.mkv", b"comp_b")
    _save(tmp_path, reference, [comparison_a], [_make_result()])

    _save(
        tmp_path,
        reference,
        [comparison_a, comparison_b],
        [_make_result(comparison_clip="comp_b.mkv", frame_offset=10, time_offset_seconds=0.4)],
    )

    content = (tmp_path / "audio_offsets.toml").read_text(encoding="utf-8")
    assert '["ref:comp_a"]' in content
    assert '["ref:comp_b"]' in content


def test_save_offsets_cache_discards_stale_schema_version_when_writing_fresh_cache(
    tmp_path: Path,
) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text(
        tomli_w.dumps({"version": "1", "ref:comp_a": {"frame_offset": 42}}),
        encoding="utf-8",
    )
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp_b.mkv", b"comp_b")

    _save(
        tmp_path,
        reference,
        [comparison],
        [_make_result(comparison_clip="comp_b.mkv", frame_offset=10, time_offset_seconds=0.4)],
    )

    content = cache_file.read_text(encoding="utf-8")
    assert f'version = "{CACHE_VERSION}"' in content
    assert 'version = "1"' not in content
    assert '["ref:comp_a"]' not in content
    assert '["ref:comp_b"]' in content


def test_save_offsets_cache_discards_invalid_existing_cache(tmp_path: Path) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    stale = _touch_clip(tmp_path / "stale.mkv", b"stale")
    cache_file = tmp_path / "audio_offsets.toml"
    existing = {
        "version": CACHE_VERSION,
        "ref:stale": _entry_dict(reference, stale, algorithm="unsupported_alg_name"),
    }
    cache_file.write_text(tomli_w.dumps(existing), encoding="utf-8")
    comparison = _touch_clip(tmp_path / "comp.mkv", b"comp")

    _save(
        tmp_path,
        reference,
        [comparison],
        [_make_result(comparison_clip="comp.mkv", frame_offset=10, time_offset_seconds=0.4)],
    )

    content = cache_file.read_text(encoding="utf-8")
    assert '["ref:stale"]' not in content
    assert '["ref:comp"]' in content
    assert 'algorithm = "cross_correlation"' in content


def test_save_offsets_cache_logs_corrupt_existing_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text("not valid toml", encoding="utf-8")
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp.mkv", b"comp")

    warnings: list[tuple[str, dict[str, object]]] = []

    def _warning(event: str, **kwargs: object) -> None:
        warnings.append((event, dict(kwargs)))

    monkeypatch.setattr("frame_compare.services.alignment_cache.log.warning", _warning)

    _save(
        tmp_path,
        reference,
        [comparison],
        [_make_result(comparison_clip="comp.mkv", frame_offset=1, time_offset_seconds=0.04)],
    )

    assert any(event == "audio_offsets_cache_corrupt_on_write" for event, _ in warnings)


def test_save_offsets_cache_uses_atomic_bytes_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = _touch_clip(tmp_path / "ref.mkv", b"ref")
    comparison = _touch_clip(tmp_path / "comp.mkv", b"comp")
    results = [_make_result(comparison_clip="comp.mkv", frame_offset=10, time_offset_seconds=0.4)]

    calls: list[Path] = []

    def _fake_write(path: Path, content: bytes) -> None:
        calls.append(path)
        path.write_bytes(content)

    monkeypatch.setattr("frame_compare.services.alignment_cache.write_bytes_atomic", _fake_write)

    _save(tmp_path, reference, [comparison], results)

    assert calls == [tmp_path / "audio_offsets.toml"]
