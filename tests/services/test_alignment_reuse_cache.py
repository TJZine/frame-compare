"""Shared alignment reuse cache owner tests."""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
import tomli_w

import frame_compare.services.alignment_reuse_cache as reuse_cache
from frame_compare.services.alignment_reuse_cache import (
    CACHE_FILE_NAME,
    CACHE_VERSION,
    comparison_cache_key,
    load_reusable_offset_entries,
    load_reusable_offsets,
    save_reusable_offsets,
)
from frame_compare.services.types import AlignmentProvenance, AlignmentResult
from frame_compare.utils.types import (
    AlignmentCacheSettings,
    AlignmentClipIdentity,
    AlignmentClipRequest,
    AlignmentRequest,
)


def _touch_clip(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def _clip(path: Path, *, label: str, stream: int | None = None) -> AlignmentClipRequest:
    stat = path.stat()
    return AlignmentClipRequest(
        path=path,
        label=label,
        identity=AlignmentClipIdentity(
            path=path.resolve(),
            size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        ),
        trim_start_frames=0,
        trim_end_frame_inclusive=None,
        effective_fps_num=24000,
        effective_fps_den=1001,
        selected_audio_stream=stream,
    )


def _settings() -> AlignmentCacheSettings:
    return AlignmentCacheSettings(
        sample_rate=8000,
        max_offset_seconds=30.0,
        correlation_mode="raw_fft",
        preprocessing_mode="none",
        channel_strategy="mono_downmix",
        confidence_threshold=0.25,
        ambiguity_peak_ratio=1.5,
        window_length_seconds=8.0,
        window_stride_seconds=2.0,
        minimum_valid_windows=2,
        consensus_minimum_ratio=0.75,
        refinement_mode="local",
        refinement_sample_rate=16000,
    )


def _request(tmp_path: Path) -> AlignmentRequest:
    cache_dir = tmp_path / "generated" / "cache" / "alignment"
    reference = _clip(_touch_clip(tmp_path / "ref.mkv", b"reference"), label="Reference", stream=0)
    comparison = _clip(_touch_clip(tmp_path / "comp.mkv", b"comparison"), label="Encode", stream=1)
    return AlignmentRequest(
        reference=reference,
        selected_reference_relationship="auto",
        comparisons=[comparison],
        previous_offsets="always",
        generated_dir=tmp_path / "generated",
        shared_alignment_cache_dir=cache_dir,
        settings=_settings(),
    )


def _result(
    request: AlignmentRequest,
    *,
    comparison_index: int = 0,
    correlation_score: float = 0.987,
    source: str = "computed",
    comparison_clip: str | None = None,
) -> AlignmentResult:
    comparison = request.comparisons[comparison_index]
    return AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name if comparison_clip is None else comparison_clip,
        frame_offset=42,
        time_offset_seconds=1.751,
        correlation_score=correlation_score,
        algorithm="cross_correlation",
        source=source,  # type: ignore[arg-type]
    )


def _provenance(
    request: AlignmentRequest,
    *,
    result: AlignmentResult | None = None,
    provenance: str = "computed_this_run",
    comparison_index: int = 0,
) -> AlignmentProvenance:
    return AlignmentProvenance(
        result=_result(request, comparison_index=comparison_index) if result is None else result,
        comparison_cache_key=comparison_cache_key(request.comparisons[comparison_index]),
        provenance=provenance,  # type: ignore[arg-type]
    )


def _write_computed(request: AlignmentRequest) -> None:
    save_reusable_offsets(
        request,
        [
            _provenance(
                request,
                result=_result(request, correlation_score=0.876),
            )
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )


def _cache_data(request: AlignmentRequest) -> dict[str, object]:
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    return tomllib.loads(cache_file.read_text(encoding="utf-8"))


def _persist_cache_data(request: AlignmentRequest, data: dict[str, object]) -> None:
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    cache_file.write_text(tomli_w.dumps(data), encoding="utf-8")


def _first_entry(data: dict[str, object]) -> dict[str, object]:
    source_sets = data["source_sets"]
    assert isinstance(source_sets, dict)
    source_set = next(iter(source_sets.values()))
    assert isinstance(source_set, dict)
    entries = source_set["entries"]
    assert isinstance(entries, dict)
    entry = next(iter(entries.values()))
    assert isinstance(entry, dict)
    return entry


def test_shared_reuse_cache_round_trips_computed_entry(tmp_path: Path) -> None:
    request = _request(tmp_path)
    _write_computed(request)

    entries = load_reusable_offset_entries(request)
    loaded = load_reusable_offsets(request)

    assert entries is not None
    entry = next(iter(entries.values()))
    assert loaded is not None
    assert len(loaded) == 1
    result = next(iter(loaded.values()))
    assert entry.accepted_at == "2026-06-06T12:00:00Z"
    assert entry.origin == "computed"
    assert result.source == "cached"
    assert result.algorithm == "cross_correlation"
    assert result.correlation_score == 0.876
    assert result.frame_offset == 42

    content = (request.shared_alignment_cache_dir / CACHE_FILE_NAME).read_text(encoding="utf-8")
    assert f'version = "{CACHE_VERSION}"' in content
    assert 'origin = "computed"' in content
    assert 'accepted_at = "2026-06-06T12:00:00Z"' in content


def test_shared_reuse_cache_round_trips_vspreview_confirmed_entry_with_score_one(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    save_reusable_offsets(
        request,
        [
            _provenance(
                request,
                result=_result(request, correlation_score=0.123, source="manual"),
                provenance="vspreview_confirmed_this_run",
            )
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    entries = load_reusable_offset_entries(request)
    loaded = load_reusable_offsets(request)

    assert entries is not None
    entry = next(iter(entries.values()))
    assert loaded is not None
    result = next(iter(loaded.values()))
    assert entry.accepted_at == "2026-06-06T12:00:00Z"
    assert entry.origin == "vspreview_confirmed"
    assert result.source == "cached"
    assert result.algorithm is None
    assert result.correlation_score == 1.0


def test_shared_reuse_cache_requires_complete_source_set(tmp_path: Path) -> None:
    request = _request(tmp_path)
    second = _clip(_touch_clip(tmp_path / "comp_b.mkv", b"second"), label="Encode 2", stream=2)
    complete_request = replace(request, comparisons=[request.comparisons[0], second])

    save_reusable_offsets(
        complete_request,
        [_provenance(complete_request, comparison_index=0)],
        accepted_at="2026-06-06T12:00:00Z",
    )

    assert load_reusable_offsets(complete_request) is None


def test_shared_reuse_cache_can_load_requested_subset_from_full_source_set(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    second = _clip(_touch_clip(tmp_path / "comp_b.mkv", b"second"), label="Encode 2", stream=2)
    complete_request = replace(request, comparisons=[request.comparisons[0], second])

    save_reusable_offsets(
        complete_request,
        [
            _provenance(complete_request, comparison_index=0),
            _provenance(complete_request, comparison_index=1),
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    subset_entries = load_reusable_offset_entries(
        complete_request,
        comparisons=[second],
    )

    assert subset_entries is not None
    assert list(subset_entries) == [comparison_cache_key(second)]
    assert subset_entries[comparison_cache_key(second)].accepted_at == "2026-06-06T12:00:00Z"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request, path: replace(
            request,
            reference=replace(
                request.reference,
                identity=replace(
                    request.reference.identity, path=(path / "other-ref.mkv").resolve()
                ),
            ),
        ),
        lambda request, _path: replace(
            request,
            reference=replace(
                request.reference,
                identity=replace(request.reference.identity, size_bytes=999),
            ),
        ),
        lambda request, _path: replace(
            request,
            reference=replace(
                request.reference,
                identity=replace(request.reference.identity, mtime_ns=999),
            ),
        ),
        lambda request, _path: replace(
            request,
            comparisons=[
                replace(request.comparisons[0], trim_start_frames=5),
            ],
        ),
        lambda request, _path: replace(
            request,
            comparisons=[
                replace(request.comparisons[0], effective_fps_num=24, effective_fps_den=1),
            ],
        ),
        lambda request, _path: replace(request, selected_reference_relationship="configured"),
        lambda request, _path: replace(
            request,
            comparisons=[
                replace(request.comparisons[0], selected_audio_stream=3),
            ],
        ),
        lambda request, _path: replace(
            request,
            settings=replace(request.settings, sample_rate=16000),
        ),
        lambda request, _path: replace(
            request,
            settings=replace(request.settings, correlation_mode="gcc_phat"),
        ),
    ],
)
def test_shared_reuse_cache_identity_drift_is_miss(
    tmp_path: Path,
    mutate: Callable[[AlignmentRequest, Path], AlignmentRequest],
) -> None:
    request = _request(tmp_path)
    _write_computed(request)

    assert load_reusable_offsets(mutate(request, tmp_path)) is None


@pytest.mark.parametrize(
    ("request_variant", "table_name", "field_name", "field_value"),
    [
        ("default", "reference", "trim_end_frame_inclusive", 120),
        ("default", "comparison", "trim_end_frame_inclusive", 95),
        ("no_streams", "reference", "selected_audio_stream", 0),
        ("no_streams", "comparison", "selected_audio_stream", 1),
        ("no_refinement", "settings", "refinement_sample_rate", 16000),
    ],
)
def test_shared_reuse_cache_optional_fields_present_in_cache_but_absent_in_request_miss(
    tmp_path: Path,
    request_variant: str,
    table_name: str,
    field_name: str,
    field_value: object,
) -> None:
    base_request = _request(tmp_path)
    if request_variant == "no_streams":
        base_request = replace(
            base_request,
            reference=replace(base_request.reference, selected_audio_stream=None),
            comparisons=[replace(base_request.comparisons[0], selected_audio_stream=None)],
        )
    elif request_variant == "no_refinement":
        base_request = replace(
            base_request,
            settings=replace(base_request.settings, refinement_sample_rate=None),
        )

    _write_computed(base_request)
    data = _cache_data(base_request)
    entry = _first_entry(data)
    table = entry[table_name]
    assert isinstance(table, dict)
    table[field_name] = field_value
    _persist_cache_data(base_request, data)

    assert load_reusable_offsets(base_request) is None


@pytest.mark.parametrize(
    ("request_variant", "table_name", "field_name"),
    [
        ("trim_end_present", "reference", "trim_end_frame_inclusive"),
        ("trim_end_present", "comparison", "trim_end_frame_inclusive"),
        ("default", "reference", "selected_audio_stream"),
        ("default", "comparison", "selected_audio_stream"),
        ("default", "settings", "refinement_sample_rate"),
    ],
)
def test_shared_reuse_cache_optional_fields_present_in_request_but_absent_in_cache_miss(
    tmp_path: Path,
    request_variant: str,
    table_name: str,
    field_name: str,
) -> None:
    base_request = _request(tmp_path)
    if request_variant == "trim_end_present":
        base_request = replace(
            base_request,
            reference=replace(base_request.reference, trim_end_frame_inclusive=120),
            comparisons=[replace(base_request.comparisons[0], trim_end_frame_inclusive=95)],
        )

    _write_computed(base_request)
    data = _cache_data(base_request)
    entry = _first_entry(data)
    table = entry[table_name]
    assert isinstance(table, dict)
    table.pop(field_name, None)
    _persist_cache_data(base_request, data)

    assert load_reusable_offsets(base_request) is None


def test_shared_reuse_cache_corrupt_data_warns_and_misses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("not valid toml {{{", encoding="utf-8")
    warnings: list[str] = []

    def _warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr("frame_compare.services.alignment_reuse_cache.log.warning", _warning)

    assert load_reusable_offsets(request) is None
    assert warnings == ["alignment_reuse_cache_unreadable"]


def test_shared_reuse_cache_version_mismatch_warns_and_misses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text('version = "999"', encoding="utf-8")
    warnings: list[str] = []

    def _warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr("frame_compare.services.alignment_reuse_cache.log.warning", _warning)

    assert load_reusable_offsets(request) is None
    assert warnings == ["alignment_reuse_cache_version_mismatch"]


def test_shared_reuse_cache_malformed_source_sets_warns_and_misses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(
        tomli_w.dumps({"version": CACHE_VERSION, "source_sets": "not-a-table"}),
        encoding="utf-8",
    )
    warnings: list[str] = []

    def _warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr("frame_compare.services.alignment_reuse_cache.log.warning", _warning)

    assert load_reusable_offsets(request) is None
    assert warnings == ["alignment_reuse_cache_malformed_source_sets"]


def test_shared_reuse_cache_missing_source_sets_warns_and_misses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(tomli_w.dumps({"version": CACHE_VERSION}), encoding="utf-8")
    warnings: list[str] = []

    def _warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr("frame_compare.services.alignment_reuse_cache.log.warning", _warning)

    assert load_reusable_offsets(request) is None
    assert warnings == ["alignment_reuse_cache_missing_source_sets"]


@pytest.mark.parametrize(
    "provenance",
    ["shared_previous_offsets", "preexisting_manual_override"],
)
def test_shared_reuse_cache_does_not_write_ineligible_provenance(
    tmp_path: Path,
    provenance: str,
) -> None:
    request = _request(tmp_path)

    save_reusable_offsets(
        request,
        [
            _provenance(
                request,
                result=_result(request, source="cached"),
                provenance=provenance,
            )
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    assert not (request.shared_alignment_cache_dir / CACHE_FILE_NAME).exists()


@pytest.mark.parametrize(
    "result",
    [
        AlignmentResult(
            reference_clip="ref.mkv",
            comparison_clip="comp.mkv",
            frame_offset=42,
            time_offset_seconds=1.751,
            correlation_score=0.987,
            algorithm="cross_correlation",
            source="computed",
            applied=False,
        ),
        AlignmentResult(
            reference_clip="ref.mkv",
            comparison_clip="comp.mkv",
            frame_offset=None,
            time_offset_seconds=1.751,
            correlation_score=0.987,
            algorithm="cross_correlation",
            source="computed",
        ),
        AlignmentResult(
            reference_clip="ref.mkv",
            comparison_clip="comp.mkv",
            frame_offset=42,
            time_offset_seconds=None,
            correlation_score=0.987,
            algorithm="cross_correlation",
            source="computed",
        ),
    ],
)
def test_shared_reuse_cache_does_not_write_unapplied_or_incomplete_results(
    tmp_path: Path,
    result: AlignmentResult,
) -> None:
    request = _request(tmp_path)

    save_reusable_offsets(
        request,
        [_provenance(request, result=result)],
        accepted_at="2026-06-06T12:00:00Z",
    )

    assert not (request.shared_alignment_cache_dir / CACHE_FILE_NAME).exists()


def test_shared_reuse_cache_uses_atomic_deterministic_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    calls: list[tuple[Path, bytes]] = []

    def _fake_write(path: Path, content: bytes) -> None:
        calls.append((path, content))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    monkeypatch.setattr(
        "frame_compare.services.alignment_reuse_cache.write_bytes_atomic", _fake_write
    )

    _write_computed(request)
    first = calls[0][1]
    _write_computed(request)
    second = calls[1][1]

    assert [call[0] for call in calls] == [
        request.shared_alignment_cache_dir / CACHE_FILE_NAME,
        request.shared_alignment_cache_dir / CACHE_FILE_NAME,
    ]
    assert first == second


def test_shared_reuse_cache_locks_entire_read_modify_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    events: list[str] = []

    @contextmanager
    def _fake_lock(path: Path) -> Iterator[None]:
        assert path == cache_file.with_name(f"{cache_file.name}.lock")
        events.append("lock_enter")
        try:
            yield
        finally:
            events.append("lock_exit")

    def _fake_initial_write_data(path: Path) -> dict[str, object]:
        assert path == cache_file
        assert events == ["lock_enter"]
        events.append("read")
        return {"version": CACHE_VERSION, "source_sets": {}}

    def _fake_write(path: Path, content: bytes) -> None:
        assert path == cache_file
        assert events == ["lock_enter", "read"]
        parsed = tomllib.loads(content.decode("utf-8"))
        assert parsed["version"] == CACHE_VERSION
        assert isinstance(parsed["source_sets"], dict)
        assert parsed["source_sets"]
        events.append("write")

    monkeypatch.setattr(reuse_cache, "exclusive_file_lock", _fake_lock)
    monkeypatch.setattr(reuse_cache, "_initial_write_data", _fake_initial_write_data)
    monkeypatch.setattr(reuse_cache, "write_bytes_atomic", _fake_write)

    _write_computed(request)

    assert events == ["lock_enter", "read", "write", "lock_exit"]


def test_shared_reuse_cache_write_failure_warns_without_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    warnings: list[str] = []

    def _raise_write(_path: Path, _content: bytes) -> None:
        raise OSError("disk full")

    def _warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr(
        "frame_compare.services.alignment_reuse_cache.write_bytes_atomic", _raise_write
    )
    monkeypatch.setattr("frame_compare.services.alignment_reuse_cache.log.warning", _warning)

    _write_computed(request)

    assert warnings == ["alignment_reuse_cache_write_failed"]


def test_shared_reuse_cache_invalid_entry_warns_and_misses(tmp_path: Path) -> None:
    request = _request(tmp_path)
    _write_computed(request)
    data = _cache_data(request)
    entry = _first_entry(data)
    entry["origin"] = "manual"
    _persist_cache_data(request, data)

    assert load_reusable_offsets(request) is None


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("frame_offset", True),
        ("time_offset_seconds", False),
        ("correlation_score", True),
    ],
)
def test_shared_reuse_cache_boolean_numeric_fields_warn_and_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    field_value: bool,
) -> None:
    request = _request(tmp_path)
    _write_computed(request)
    data = _cache_data(request)
    entry = _first_entry(data)
    entry[field_name] = field_value
    _persist_cache_data(request, data)
    warnings: list[str] = []

    def _warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr("frame_compare.services.alignment_reuse_cache.log.warning", _warning)

    assert load_reusable_offsets(request) is None
    assert warnings == ["alignment_reuse_cache_invalid_entry"]


@pytest.mark.parametrize(
    ("request_mutate", "table_name", "field_name", "field_value"),
    [
        (
            lambda request: request,
            "comparison",
            "selected_audio_stream",
            True,
        ),
        (
            lambda request: replace(
                request,
                settings=replace(request.settings, window_length_seconds=0.0),
            ),
            "settings",
            "window_length_seconds",
            False,
        ),
    ],
)
def test_shared_reuse_cache_boolean_identity_fields_warn_and_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request_mutate: Callable[[AlignmentRequest], AlignmentRequest],
    table_name: str,
    field_name: str,
    field_value: bool,
) -> None:
    request = request_mutate(_request(tmp_path))
    _write_computed(request)
    data = _cache_data(request)
    entry = _first_entry(data)
    table = entry[table_name]
    assert isinstance(table, dict)
    table[field_name] = field_value
    _persist_cache_data(request, data)
    warnings: list[str] = []

    def _warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr("frame_compare.services.alignment_reuse_cache.log.warning", _warning)

    assert load_reusable_offsets(request) is None
    assert warnings == ["alignment_reuse_cache_invalid_entry"]


def test_shared_reuse_cache_writes_by_typed_comparison_identity_not_result_label(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)

    save_reusable_offsets(
        request,
        [
            _provenance(
                request,
                result=_result(request, comparison_clip="Encode (display label)"),
            )
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    data = _cache_data(request)
    entry = _first_entry(data)

    assert entry["comparison_clip"] == request.comparisons[0].path.name


def test_shared_reuse_cache_ignores_unrelated_ineligible_provenance_items(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)

    save_reusable_offsets(
        request,
        [
            _provenance(request),
            AlignmentProvenance(
                result=_result(request, source="cached"),
                comparison_cache_key="unrelated-comparison",
                provenance="shared_previous_offsets",
            ),
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    loaded = load_reusable_offsets(request)

    assert loaded is not None
    assert len(loaded) == 1
