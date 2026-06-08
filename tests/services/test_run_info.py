from __future__ import annotations

import tomllib
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from frame_compare.services.run_info import (
    RunInfo,
    RunInfoTmdbPrefetchFacts,
    serialize_run_info,
    write_run_info,
)


def _parsed_toml(content: str) -> dict[str, object]:
    return tomllib.loads(content)


def test_serialize_run_info_uses_utc_z_created_at() -> None:
    content = serialize_run_info(
        RunInfo(
            created_at=datetime(2026, 6, 8, 12, 34, 56, tzinfo=timezone(timedelta(hours=-4))),
            folder_name="Fight Club (1999)",
            naming_source="tmdb",
            source_filenames=["source.mkv", "encode.mkv"],
        )
    )

    parsed = _parsed_toml(content)
    assert parsed["created_at"] == "2026-06-08T16:34:56Z"


def test_serialize_run_info_treats_naive_clock_as_utc() -> None:
    content = serialize_run_info(
        RunInfo(
            created_at=datetime(2026, 6, 8, 12, 34, 56),
            folder_name="source",
            naming_source="filename_stems",
            source_filenames=["source.mkv"],
        )
    )

    parsed = _parsed_toml(content)
    assert parsed["created_at"] == "2026-06-08T12:34:56Z"


def test_serialize_run_info_writes_resolved_tmdb_facts_without_nulls() -> None:
    content = serialize_run_info(
        RunInfo(
            created_at=datetime(2026, 6, 8, 12, 34, 56, tzinfo=UTC),
            folder_name="Fight Club (1999)",
            naming_source="tmdb",
            source_filenames=["source.mkv"],
            tmdb=RunInfoTmdbPrefetchFacts(
                enabled=True,
                attempted=True,
                resolved=True,
                failed=False,
                tmdb_id=550,
                title="Fight Club",
                year=1999,
                media_type="movie",
            ),
        )
    )

    parsed = _parsed_toml(content)
    assert parsed["version"] == 1
    assert parsed["folder_name"] == "Fight Club (1999)"
    assert parsed["naming_source"] == "tmdb"
    assert parsed["source_filenames"] == ["source.mkv"]
    assert parsed["frame_compare_version"]
    assert parsed["tmdb"] == {
        "enabled": True,
        "attempted": True,
        "resolved": True,
        "failed": False,
        "tmdb_id": 550,
        "title": "Fight Club",
        "year": 1999,
        "media_type": "movie",
    }
    assert "null" not in content.lower()
    assert '""' not in content


def test_serialize_run_info_writes_disabled_tmdb_skip_without_optional_result_keys() -> None:
    content = serialize_run_info(
        RunInfo(
            created_at=datetime(2026, 6, 8, 12, 34, 56, tzinfo=UTC),
            folder_name="source",
            naming_source="filename_stems",
            source_filenames=["source.mkv"],
            tmdb=RunInfoTmdbPrefetchFacts(
                enabled=False,
                attempted=False,
                resolved=False,
                failed=False,
                skipped_reason="disabled",
            ),
        )
    )

    parsed = _parsed_toml(content)
    assert parsed["tmdb"] == {
        "enabled": False,
        "attempted": False,
        "resolved": False,
        "failed": False,
        "skip_reason": "disabled",
    }
    assert "tmdb_id" not in content
    assert "title" not in content
    assert "year" not in content
    assert "null" not in content.lower()


def test_serialize_run_info_writes_failed_tmdb_attempt() -> None:
    content = serialize_run_info(
        RunInfo(
            created_at=datetime(2026, 6, 8, 12, 34, 56, tzinfo=UTC),
            folder_name="source",
            naming_source="filename_stems",
            source_filenames=["source.mkv"],
            tmdb=RunInfoTmdbPrefetchFacts(
                enabled=True,
                attempted=True,
                resolved=False,
                failed=True,
                error_type="TmdbRateLimitedError",
            ),
        )
    )

    parsed = _parsed_toml(content)
    assert parsed["tmdb"] == {
        "enabled": True,
        "attempted": True,
        "resolved": False,
        "failed": True,
        "error_type": "TmdbRateLimitedError",
    }
    assert "null" not in content.lower()


def test_write_run_info_creates_root_file(tmp_path: Path) -> None:
    run_info_path = tmp_path / "run_info.toml"

    write_run_info(
        run_info_path,
        RunInfo(
            created_at=datetime(2026, 6, 8, 12, 34, 56, tzinfo=UTC),
            folder_name="source",
            naming_source="filename_stems",
            source_filenames=["source.mkv"],
        ),
    )

    parsed = _parsed_toml(run_info_path.read_text(encoding="utf-8"))
    assert parsed["created_at"] == "2026-06-08T12:34:56Z"
