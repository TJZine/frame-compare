from __future__ import annotations

import os
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from frame_compare.services.errors import HistoryAccessError, HistoryOpenError
from frame_compare.services.run_result_record import (
    CompletedRunFacts,
    FailedRunFacts,
    RunResultRecord,
    completed_record,
    failed_record,
    list_history,
    parse_run_result,
    read_run_result,
    resolve_history_report,
    resolve_run_directory,
    serialize_run_result,
    write_run_result,
)
from frame_compare.utils.types import WorkspacePaths


def _workspace(root: Path, run_dir: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=root,
        input_dir=root / "moved-inputs",
        run_dir=run_dir,
        screenshots_dir=run_dir / "screenshots",
        generated_dir=run_dir / "generated",
        config_dir=root / "config",
        config_file=root / "config" / "config.toml",
        analysis_cache_dir=root / "generated" / "cache" / "analysis",
    )


def _record(root: Path, run_dir: Path, *, seconds: int = 10) -> RunResultRecord:
    started = datetime(2026, 7, 14, 12, tzinfo=UTC)
    report = run_dir / "report.html"
    report.write_text("ok", encoding="utf-8")
    return completed_record(
        workspace=_workspace(root, run_dir),
        facts=CompletedRunFacts(
            report_path=report,
            screenshot_dir=run_dir / "screenshots",
            clip_count=2,
            selected_frame_count=3,
            warnings=("secret=/Users/private token=abc",),
            metrics_cache_status="hit",
            phase_timings={"render": 2.0, "align": 1.0},
            slowpics_url="https://slow.pics/c/safe",
            slowpics_confirmation_status="confirmed",
        ),
        started_at=started,
        completed_at=started + timedelta(seconds=seconds),
    )


def test_v1_round_trip_is_deterministic_and_redacted(tmp_path: Path) -> None:
    run_dir = tmp_path / "generated" / "run"
    run_dir.mkdir(parents=True)
    record = _record(tmp_path, run_dir)

    first = serialize_run_result(record)
    second = serialize_run_result(record)
    write_run_result(run_dir, record)

    assert first == second
    assert "secret" not in first
    assert "/Users/private" not in first
    assert "token=abc" not in first
    assert 'report_path = "generated/run/report.html"' in first
    assert first.index("align = 1.0") < first.index("render = 2.0")
    assert read_run_result(run_dir / "run_result.toml") == record


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", 2),
        ("status", "mystery"),
        ("started_at", "yesterday"),
        ("duration_seconds", -1),
        ("clip_count", -1),
        ("report_path", "../escape.html"),
    ],
)
def test_schema_rejects_unsupported_or_malformed_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    run_dir = tmp_path / "generated" / "run"
    run_dir.mkdir(parents=True)
    payload = tomllib.loads(serialize_run_result(_record(tmp_path, run_dir)))
    payload[field] = value

    with pytest.raises(ValueError):
        parse_run_result(payload)


@pytest.mark.parametrize(
    "url",
    [
        "http://slow.pics/c/nope",
        "https://example.com/c/nope",
        "https://slow.pics:444/c/nope",
        "https://user:pass@slow.pics/c/nope",
        "https://slow.pics/c/nope?token=secret",
        "https://slow.pics/c/nope#secret",
        "https://slow.pics/not-a-comparison",
        "https://slow.pics/c/nope\nignored",
    ],
)
def test_schema_rejects_unsafe_slowpics_urls(tmp_path: Path, url: str) -> None:
    run_dir = tmp_path / "generated" / "run"
    run_dir.mkdir(parents=True)
    payload = tomllib.loads(serialize_run_result(_record(tmp_path, run_dir)))
    payload["slowpics"]["url"] = url

    with pytest.raises(ValueError):
        parse_run_result(payload)


def test_atomic_write_failure_leaves_no_partial_or_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "generated" / "run"
    run_dir.mkdir(parents=True)
    record = _record(tmp_path, run_dir)

    def fail_replace(_source: str, _target: Path) -> None:
        raise PermissionError("private-path-sentinel")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(PermissionError):
        write_run_result(run_dir, record)

    assert not (run_dir / "run_result.toml").exists()
    assert [path for path in run_dir.iterdir() if path.name.startswith(".run_result.toml.")] == []


def test_naive_lifecycle_times_follow_existing_run_info_utc_convention(tmp_path: Path) -> None:
    run_dir = tmp_path / "generated" / "run"
    run_dir.mkdir(parents=True)
    started = datetime(2026, 7, 14, 12)

    record = completed_record(
        workspace=_workspace(tmp_path, run_dir),
        facts=CompletedRunFacts(
            report_path=None,
            screenshot_dir=None,
            clip_count=1,
            selected_frame_count=1,
            warnings=(),
            metrics_cache_status="skipped",
            phase_timings={},
            slowpics_url=None,
            slowpics_confirmation_status="not_applicable",
        ),
        started_at=started,
        completed_at=started + timedelta(seconds=1),
    )

    assert record.started_at == datetime(2026, 7, 14, 12, tzinfo=UTC)


def test_failed_record_preserves_only_bounded_generic_warning_facts(tmp_path: Path) -> None:
    started = datetime(2026, 7, 14, 12, tzinfo=UTC)
    record = failed_record(
        error=RuntimeError("secret failure"),
        started_at=started,
        completed_at=started + timedelta(seconds=1),
        facts=FailedRunFacts(warnings=("token=secret", "path=/Users/private")),
    )

    serialized = serialize_run_result(record)
    assert record.warning_count == 2
    assert record.warning_summaries == (
        "A run warning was reported.",
        "A run warning was reported.",
    )
    assert "token=secret" not in serialized
    assert "/Users/private" not in serialized

    payload = tomllib.loads(serialized)
    payload["failure"]["message"] = "Caller supplied but punctuation-safe text"
    with pytest.raises(ValueError, match="failure.message"):
        parse_run_result(payload)


def test_history_lists_valid_legacy_and_malformed_independently(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    valid = generated / "valid"
    legacy = generated / "legacy"
    broken = generated / "broken"
    for path in (valid, legacy, broken, generated / "cache"):
        path.mkdir(parents=True)
    write_run_result(valid, _record(tmp_path, valid, seconds=20))
    (broken / "run_result.toml").write_text("version = 99\n", encoding="utf-8")

    entries = list_history(tmp_path, generated)

    assert [(entry.name, entry.status) for entry in entries] == [
        ("valid", "completed_with_warnings"),
        ("broken", "unavailable"),
        ("legacy", "unknown"),
    ]
    assert entries[1].warning == "A run result record is unreadable or unsupported."
    assert not (legacy / "run_result.toml").exists()
    assert (broken / "run_result.toml").read_text(encoding="utf-8") == "version = 99\n"


def test_history_order_ties_use_exact_name(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    for name in ("b", "A", "z"):
        run_dir = generated / name
        run_dir.mkdir(parents=True)
        write_run_result(run_dir, _record(tmp_path, run_dir))

    assert [entry.name for entry in list_history(tmp_path, generated)] == ["A", "b", "z"]


def test_legacy_history_uses_persisted_run_info_time(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    older = generated / "older"
    newer = generated / "newer"
    older.mkdir(parents=True)
    newer.mkdir()
    (older / "run_info.toml").write_text('created_at = "2026-07-13T12:00:00Z"\n', encoding="utf-8")
    (newer / "run_info.toml").write_text('created_at = "2026-07-14T12:00:00Z"\n', encoding="utf-8")

    entries = list_history(tmp_path, generated)

    assert [entry.name for entry in entries] == ["newer", "older"]
    assert entries[0].started_at == datetime(2026, 7, 14, 12, tzinfo=UTC)


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "a\\b", "/tmp/x", "C:\\x"])
def test_exact_run_name_validation_rejects_paths(tmp_path: Path, name: str) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    with pytest.raises(HistoryAccessError):
        resolve_run_directory(generated, name)


def test_history_open_rejects_traversal_absolute_and_symlink_escape(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    run_dir = generated / "run"
    run_dir.mkdir(parents=True)
    external = tmp_path / "external.html"
    external.write_text("outside", encoding="utf-8")
    record = _record(tmp_path, run_dir)

    for unsafe in ("../external.html", str(external)):
        payload = tomllib.loads(serialize_run_result(record))
        payload["report_path"] = unsafe
        (run_dir / "run_result.toml").write_text(
            __import__("tomli_w").dumps(payload), encoding="utf-8"
        )
        with pytest.raises(HistoryOpenError):
            resolve_history_report(tmp_path, generated, "run")

    link = run_dir / "linked.html"
    link.symlink_to(external)
    safe_payload = tomllib.loads(serialize_run_result(record))
    safe_payload["report_path"] = "generated/run/linked.html"
    (run_dir / "run_result.toml").write_text(
        __import__("tomli_w").dumps(safe_payload), encoding="utf-8"
    )
    with pytest.raises(HistoryOpenError):
        resolve_history_report(tmp_path, generated, "run")


def test_history_open_rejects_missing_and_workspace_external_to_generated_reports(
    tmp_path: Path,
) -> None:
    generated = tmp_path / "generated"
    run_dir = generated / "run"
    run_dir.mkdir(parents=True)
    record = _record(tmp_path, run_dir)
    report = run_dir / "report.html"
    report.unlink()
    write_run_result(run_dir, record)

    with pytest.raises(HistoryOpenError, match="missing"):
        resolve_history_report(tmp_path, generated, "run")

    outside_generated = tmp_path / "reports" / "report.html"
    outside_generated.parent.mkdir()
    outside_generated.write_text("safe workspace file", encoding="utf-8")
    payload = tomllib.loads(serialize_run_result(record))
    payload["report_path"] = "reports/report.html"
    (run_dir / "run_result.toml").write_text(__import__("tomli_w").dumps(payload), encoding="utf-8")

    with pytest.raises(HistoryOpenError, match="outside"):
        resolve_history_report(tmp_path, generated, "run")

    entries = list_history(tmp_path, generated)
    assert len(entries) == 1
    assert entries[0].report_available is False


def test_history_ignores_symlinked_run_escape(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (generated / "escape").symlink_to(outside, target_is_directory=True)

    assert list_history(tmp_path, generated) == []


def test_history_rejects_symlinked_record_authority(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    run_dir = generated / "run"
    run_dir.mkdir(parents=True)
    external_record = tmp_path / "external-result.toml"
    external_record.write_text(serialize_run_result(_record(tmp_path, run_dir)), encoding="utf-8")
    (run_dir / "run_result.toml").symlink_to(external_record)

    entries = list_history(tmp_path, generated)
    assert [(entry.name, entry.status) for entry in entries] == [("run", "unavailable")]
    with pytest.raises(HistoryOpenError, match="unavailable"):
        resolve_history_report(tmp_path, generated, "run")


def test_history_ignores_contained_directory_symlink_alias(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    target = generated / "target"
    target.mkdir(parents=True)
    write_run_result(target, _record(tmp_path, target))
    (generated / "alias").symlink_to(target, target_is_directory=True)

    assert [entry.name for entry in list_history(tmp_path, generated)] == ["target"]
    with pytest.raises(HistoryAccessError):
        resolve_run_directory(generated, "alias")
