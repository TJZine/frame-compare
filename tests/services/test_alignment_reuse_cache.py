"""Shared alignment reuse cache owner tests."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Callable, Generator
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
    save_reusable_offsets,
    source_set_cache_key,
)
from frame_compare.services.types import (
    AlignmentProvenance,
    AlignmentResult,
)
from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
)
from frame_compare.utils.file_lock import FileLockTimeoutError
from frame_compare.utils.types import (
    AlignmentCacheSettings,
    AlignmentClipIdentity,
    AlignmentClipRequest,
    AlignmentRequest,
)
from tests.alignment_review_test_support import trusted_audio_attempt

_DEFAULT_STABILITY = AlignmentStabilitySummary(
    "insufficient_evidence", 0, None, None, None, None, None, None
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
        source_fps_num=24000,
        source_fps_den=1001,
        source_frame_count=100,
        selected_audio_stream=stream,
    )


def _settings() -> AlignmentCacheSettings:
    return AlignmentCacheSettings(
        max_offset_seconds=30.0,
        channel_strategy="mono_downmix",
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
    frame_offset: int = 42,
    correlation_score: float = 0.987,
    source: str = "computed",
    comparison_clip: str | None = None,
) -> AlignmentResult:
    comparison = request.comparisons[comparison_index]
    return AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name if comparison_clip is None else comparison_clip,
        frame_offset=frame_offset,
        time_offset_seconds=1.751,
        correlation_score=correlation_score,
        algorithm="cross_correlation",
        source=source,  # type: ignore[arg-type]
        stability=_DEFAULT_STABILITY,
        audio_attempt=trusted_audio_attempt(frame_offset=frame_offset)
        if source == "computed"
        else None,
    )


def _provenance(
    request: AlignmentRequest,
    *,
    result: AlignmentResult | None = None,
    provenance: str = "computed_this_run",
    comparison_index: int = 0,
    computed_result: AlignmentResult | None = None,
) -> AlignmentProvenance:
    return AlignmentProvenance(
        result=_result(request, comparison_index=comparison_index) if result is None else result,
        comparison_cache_key=comparison_cache_key(request.comparisons[comparison_index]),
        provenance=provenance,  # type: ignore[arg-type]
        computed_result=computed_result,
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


def test_stability_summary_round_trips_in_current_cache_schema(tmp_path: Path) -> None:
    request = _request(tmp_path)
    summary = AlignmentStabilitySummary(
        classification="possible_discontinuity",
        valid_windows=4,
        offset_min_frames=178,
        offset_max_frames=202,
        first_offset_frames=178,
        last_offset_frames=202,
        largest_adjacent_jump_frames=24,
        change_position_seconds=2832.0,
    )
    result = replace(_result(request), stability=summary)

    save_reusable_offsets(request, [_provenance(request, result=result)])
    loaded = load_reusable_offset_entries(request)

    assert loaded is not None
    assert loaded[comparison_cache_key(request.comparisons[0])].result.stability == summary
    assert _cache_data(request)["version"] == CACHE_VERSION


def test_shared_reuse_cache_does_not_write_computed_entry_without_stability(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    result = replace(_result(request), stability=None)

    save_reusable_offsets(request, [_provenance(request, result=result)])

    assert not (request.shared_alignment_cache_dir / CACHE_FILE_NAME).exists()


def test_computed_this_run_provisional_result_is_not_write_eligible(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    attempt = trusted_audio_attempt(frame_offset=42)
    provisional = replace(
        attempt,
        decision=replace(
            attempt.decision,
            state="provisional",
            primary_reason="audio_only",
        ),
    )
    result = replace(
        _result(request),
        frame_offset=None,
        time_offset_seconds=None,
        applied=False,
        diagnostic="audio_only",
        audio_attempt=provisional,
    )

    save_reusable_offsets(request, [_provenance(request, result=result)])

    assert not (request.shared_alignment_cache_dir / CACHE_FILE_NAME).exists()


def test_computed_this_run_without_trusted_attempt_is_not_write_eligible(
    tmp_path: Path,
) -> None:
    """Second layer: an applied same-run result still needs trusted evidence to be written."""
    request = _request(tmp_path)
    result = replace(_result(request), audio_attempt=None)

    save_reusable_offsets(request, [_provenance(request, result=result)])

    assert not (request.shared_alignment_cache_dir / CACHE_FILE_NAME).exists()


def test_source_set_cache_key_changes_with_media_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    original = source_set_cache_key(request)

    observed_scopes: list[str] = []

    def fingerprint(scope: str) -> str:
        observed_scopes.append(scope)
        return "a" * 64

    monkeypatch.setattr(
        reuse_cache,
        "media_runtime_fingerprint",
        fingerprint,
    )

    assert source_set_cache_key(request) != original
    assert observed_scopes == ["alignment"]


def test_source_set_cache_key_changes_with_estimator_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    original = source_set_cache_key(request)

    monkeypatch.setattr(reuse_cache, "ALIGNMENT_ESTIMATOR_POLICY", "next-policy")

    assert source_set_cache_key(request) != original


def test_stale_estimator_policy_shared_entry_misses_without_schema_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(
            reuse_cache,
            "ALIGNMENT_ESTIMATOR_POLICY",
            "stale-alignment-policy",
        )
        save_reusable_offsets(
            request,
            [
                _provenance(
                    request,
                    result=_result(request),
                )
            ],
        )

    assert _cache_data(request)["version"] == CACHE_VERSION == "2"
    assert load_reusable_offset_entries(request) is None


def test_alignment_cache_keys_intentionally_reuse_same_stat_identity(tmp_path: Path) -> None:
    """Content hashing is deliberately excluded from performance-first keys."""
    request = _request(tmp_path)
    original_source_set_key = source_set_cache_key(request)
    original_comparison_key = comparison_cache_key(request.comparisons[0])

    reference_path = request.reference.path
    reference_mtime_ns = request.reference.identity.mtime_ns
    reference_path.write_bytes(b"replaceme")
    os.utime(reference_path, ns=(reference_mtime_ns, reference_mtime_ns))

    comparison_path = request.comparisons[0].path
    comparison_mtime_ns = request.comparisons[0].identity.mtime_ns
    comparison_path.write_bytes(b"substitute")
    os.utime(comparison_path, ns=(comparison_mtime_ns, comparison_mtime_ns))

    replaced = replace(
        request,
        reference=_clip(reference_path, label="Reference", stream=0),
        comparisons=[_clip(comparison_path, label="Encode", stream=1)],
    )

    assert source_set_cache_key(replaced) == original_source_set_key
    assert comparison_cache_key(replaced.comparisons[0]) == original_comparison_key


def test_shared_reuse_cache_round_trips_computed_entry(tmp_path: Path) -> None:
    request = _request(tmp_path)
    _write_computed(request)

    entries = load_reusable_offset_entries(request)
    assert entries is not None
    entry = next(iter(entries.values()))
    assert len(entries) == 1
    result = entry.result
    assert entry.accepted_at == "2026-06-06T12:00:00Z"
    assert entry.origin == "computed"
    assert result.correlation_score == 0.876
    assert result.frame_offset == 42

    content = (request.shared_alignment_cache_dir / CACHE_FILE_NAME).read_text(encoding="utf-8")
    assert f'version = "{CACHE_VERSION}"' in content
    assert 'origin = "computed"' in content
    assert 'accepted_at = "2026-06-06T12:00:00Z"' in content


def test_shared_reuse_cache_settings_key_uses_estimator_recipe_identity(
    tmp_path: Path,
) -> None:
    """The settings key is exactly the estimator policy plus probe/recipe facts."""
    request = _request(tmp_path)
    _write_computed(request)

    data = _cache_data(request)
    settings = _first_entry(data)["settings"]
    assert isinstance(settings, dict)
    assert settings == {
        "estimator_policy": "whole-track-chunked-phat-video-check-motion-20260929",
        "max_offset_seconds": 30.0,
        "channel_strategy": "mono_downmix",
    }
    comparison = _first_entry(data)["comparison"]
    assert isinstance(comparison, dict)
    assert comparison["selected_audio_stream"] == 1


def test_shared_cache_persists_confirmed_entry_while_shared_computed_stays_computed(
    tmp_path: Path,
) -> None:
    """A is shared-computed, B is confirmed in VSView: both persist with their origins."""
    request = _request(tmp_path)
    second = _clip(_touch_clip(tmp_path / "comp_b.mkv", b"second"), label="Encode 2", stream=2)
    complete_request = replace(request, comparisons=[request.comparisons[0], second])
    shared = replace(
        _result(complete_request, comparison_index=0, correlation_score=0.876),
        audio_attempt=None,
    )
    confirmed = AlignmentResult(
        reference_clip=complete_request.reference.path.name,
        comparison_clip=second.path.name,
        frame_offset=47,
        time_offset_seconds=1.96,
        correlation_score=1.0,
        algorithm=None,
        source="manual",
    )
    save_reusable_offsets(
        complete_request,
        [
            _provenance(
                complete_request,
                comparison_index=0,
                result=shared,
                provenance="shared_computed_offsets",
            ),
            _provenance(
                complete_request,
                comparison_index=1,
                result=confirmed,
                provenance="interactive_confirmed_this_run",
            ),
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    entries = load_reusable_offset_entries(complete_request)

    assert entries is not None
    shared_entry = entries[comparison_cache_key(complete_request.comparisons[0])]
    confirmed_entry = entries[comparison_cache_key(complete_request.comparisons[1])]
    assert shared_entry.origin == "computed"
    assert shared_entry.result.frame_offset == 42
    assert confirmed_entry.origin == "interactive_confirmed"
    assert confirmed_entry.result.frame_offset == 47


def test_shared_reuse_cache_round_trips_interactive_confirmed_entry_with_score_one(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    save_reusable_offsets(
        request,
        [
            _provenance(
                request,
                result=_result(request, correlation_score=0.123, source="manual"),
                provenance="interactive_confirmed_this_run",
            )
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    entries = load_reusable_offset_entries(request)
    assert entries is not None
    entry = next(iter(entries.values()))
    result = entry.result
    assert entry.accepted_at == "2026-06-06T12:00:00Z"
    assert entry.origin == "interactive_confirmed"
    assert result.correlation_score == 1.0
    assert entry.computed_result is None


def test_shared_reuse_cache_round_trips_interactive_entry_with_computed_fallback(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    summary = AlignmentStabilitySummary("possible_drift", 4, 40, 42, 40, 42, 1, None)
    computed = replace(
        _result(request, frame_offset=42, correlation_score=0.876), stability=summary
    )
    confirmed = AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=request.comparisons[0].path.name,
        frame_offset=47,
        time_offset_seconds=1.96,
        correlation_score=1.0,
        algorithm=None,
        source="manual",
    )
    save_reusable_offsets(
        request,
        [
            _provenance(
                request,
                result=confirmed,
                provenance="interactive_confirmed_this_run",
                computed_result=computed,
            )
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    entries = load_reusable_offset_entries(request)

    assert entries is not None
    entry = next(iter(entries.values()))
    assert entry.origin == "interactive_confirmed"
    assert entry.result.frame_offset == 47
    assert entry.result.stability == summary
    assert entry.computed_result is not None
    assert entry.computed_result.frame_offset == 42
    assert entry.computed_result.correlation_score == pytest.approx(0.876)
    assert entry.computed_result.stability == summary


def test_incomplete_requested_source_set_is_not_written_or_reused(tmp_path: Path) -> None:
    request = _request(tmp_path)
    second = _clip(_touch_clip(tmp_path / "comp_b.mkv", b"second"), label="Encode 2", stream=2)
    complete_request = replace(request, comparisons=[request.comparisons[0], second])

    save_reusable_offsets(
        complete_request,
        [_provenance(complete_request, comparison_index=0)],
        accepted_at="2026-06-06T12:00:00Z",
    )

    assert load_reusable_offset_entries(complete_request) is None


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
            settings=replace(request.settings, max_offset_seconds=60.0),
        ),
        lambda request, _path: replace(
            request,
            settings=replace(request.settings, channel_strategy="best_channel"),
        ),
    ],
)
def test_shared_reuse_cache_identity_drift_is_miss(
    tmp_path: Path,
    mutate: Callable[[AlignmentRequest, Path], AlignmentRequest],
) -> None:
    request = _request(tmp_path)
    _write_computed(request)

    assert load_reusable_offset_entries(mutate(request, tmp_path)) is None


@pytest.mark.parametrize(
    ("request_variant", "table_name", "field_name", "field_value"),
    [
        ("default", "reference", "trim_end_frame_inclusive", 120),
        ("default", "comparison", "trim_end_frame_inclusive", 95),
        ("no_streams", "reference", "selected_audio_stream", 0),
        ("no_streams", "comparison", "selected_audio_stream", 1),
        ("default", "settings", "unrecognized_future_setting", "reserved"),
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

    _write_computed(base_request)
    data = _cache_data(base_request)
    entry = _first_entry(data)
    table = entry[table_name]
    assert isinstance(table, dict)
    table[field_name] = field_value
    _persist_cache_data(base_request, data)

    assert load_reusable_offset_entries(base_request) is None


@pytest.mark.parametrize(
    ("request_variant", "table_name", "field_name"),
    [
        ("trim_end_present", "reference", "trim_end_frame_inclusive"),
        ("trim_end_present", "comparison", "trim_end_frame_inclusive"),
        ("default", "reference", "selected_audio_stream"),
        ("default", "comparison", "selected_audio_stream"),
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

    assert load_reusable_offset_entries(base_request) is None


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

    assert load_reusable_offset_entries(request) is None
    assert warnings == ["alignment_reuse_cache_unreadable"]


def test_shared_reuse_cache_replaces_v1_without_migrating_entries(tmp_path: Path) -> None:
    request = _request(tmp_path)
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(
        'version = "1"\n[source_sets.legacy]\nmarker = "must-not-survive"\n',
        encoding="utf-8",
    )

    save_reusable_offsets(request, [_provenance(request)])

    data = _cache_data(request)
    assert data["version"] == "2"
    source_sets = data["source_sets"]
    assert isinstance(source_sets, dict)
    assert "legacy" not in source_sets


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


def test_repeated_accepted_cache_writes_have_identical_bytes(
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

    assert first == second


def test_shared_reuse_cache_locks_entire_read_modify_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    cache_file = request.shared_alignment_cache_dir / CACHE_FILE_NAME
    events: list[str] = []

    @contextmanager
    def _fake_lock(path: Path) -> Generator[None]:
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


@pytest.mark.parametrize(
    ("boundary", "error"),
    [
        ("write_bytes_atomic", OSError("disk full")),
        ("exclusive_file_lock", FileLockTimeoutError("timed out acquiring lock file")),
    ],
)
def test_shared_reuse_cache_write_boundary_failure_warns_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str, error: Exception
) -> None:
    request = _request(tmp_path)
    warnings: list[str] = []

    def fail(*_args: object) -> None:
        raise error

    def warning(event: str, **_kwargs: object) -> None:
        warnings.append(event)

    monkeypatch.setattr(reuse_cache, boundary, fail)
    monkeypatch.setattr(reuse_cache.log, "warning", warning)
    _write_computed(request)
    assert warnings == ["alignment_reuse_cache_write_failed"]


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
            lambda request: request,
            "settings",
            "max_offset_seconds",
            True,
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

    assert load_reusable_offset_entries(request) is None
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


def test_shared_reuse_cache_identity_excludes_display_labels(tmp_path: Path) -> None:
    request = _request(tmp_path)
    relabeled = replace(
        request,
        reference=replace(request.reference, label="Custom Reference"),
        comparisons=[replace(request.comparisons[0], label="Custom Encode")],
    )

    assert source_set_cache_key(relabeled) == source_set_cache_key(request)
    assert comparison_cache_key(relabeled.comparisons[0]) == comparison_cache_key(
        request.comparisons[0]
    )


def test_shared_reuse_cache_identity_excludes_source_frame_count(tmp_path: Path) -> None:
    request = _request(tmp_path)
    changed_bounds = replace(
        request,
        reference=replace(request.reference, source_frame_count=101),
        comparisons=[replace(request.comparisons[0], source_frame_count=99)],
    )

    assert source_set_cache_key(changed_bounds) == source_set_cache_key(request)
    assert comparison_cache_key(changed_bounds.comparisons[0]) == comparison_cache_key(
        request.comparisons[0]
    )


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

    loaded = load_reusable_offset_entries(request)

    assert loaded is not None
    assert len(loaded) == 1
