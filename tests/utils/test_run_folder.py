"""Tests for run folder naming utilities."""

from pathlib import Path
from unittest.mock import patch

import pytest

from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.run_folder import (
    _combine_filename_stems,
    derive_run_folder_name,
    find_common_metadata,
    get_existing_run_folders,
    sanitize_folder_name,
)


# ─── sanitize_folder_name Tests ───────────────────────────────────────────────


def test_sanitize_folder_name_removes_illegal_chars() -> None:
    result = sanitize_folder_name('Movie: The <Test> "Edition"')
    assert "<" not in result
    assert ">" not in result
    assert ":" not in result
    assert '"' not in result


def test_sanitize_folder_name_collapses_spaces() -> None:
    result = sanitize_folder_name("Movie   Name    Here")
    assert result == "Movie Name Here"


def test_sanitize_folder_name_empty_returns_default() -> None:
    assert sanitize_folder_name("") == "unnamed_run"
    assert sanitize_folder_name("   ") == "unnamed_run"


def test_sanitize_folder_name_trims_trailing_periods() -> None:
    result = sanitize_folder_name("Movie Name...")
    assert not result.endswith(".")


def test_sanitize_folder_name_limits_length() -> None:
    long_name = "A" * 200
    result = sanitize_folder_name(long_name)
    assert len(result) <= 100


# ─── find_common_metadata Tests ───────────────────────────────────────────────


def test_find_common_metadata_single_file() -> None:
    title, year = find_common_metadata(["Movie.Name.2024.BluRay.1080p.mkv"])
    assert title == "Movie Name"
    assert year == 2024


def test_find_common_metadata_matching_titles() -> None:
    title, year = find_common_metadata([
        "Movie.Name.2024.WEB-DL.1080p.mkv",
        "Movie.Name.2024.BluRay.2160p.mkv",
    ])
    assert title == "Movie Name"
    assert year == 2024


def test_find_common_metadata_different_titles() -> None:
    title, year = find_common_metadata([
        "Movie.A.2024.mkv",
        "Movie.B.2024.mkv",
    ])
    # Titles don't match, but year might
    assert title is None
    assert year == 2024


def test_find_common_metadata_empty_list() -> None:
    title, year = find_common_metadata([])
    assert title is None
    assert year is None


# ─── _combine_filename_stems Tests ────────────────────────────────────────────


def test_combine_filename_stems_deduplicates() -> None:
    result = _combine_filename_stems([
        "Movie.2024.WEB-DL.mkv",
        "Movie.2024.BluRay.mkv",
    ])
    # Should not repeat "Movie 2024"
    assert result.count("+") <= 1


def test_combine_filename_stems_limits_to_two() -> None:
    result = _combine_filename_stems([
        "Movie1.mkv",
        "Movie2.mkv",
        "Movie3.mkv",
        "Movie4.mkv",
    ])
    assert "+2 more" in result or "+" in result


def test_combine_filename_stems_empty_list() -> None:
    result = _combine_filename_stems([])
    assert result == "unnamed_run"


# ─── derive_run_folder_name Tests ─────────────────────────────────────────────


def test_derive_run_folder_name_uses_tmdb_first() -> None:
    tmdb = TmdbMetadata(
        tmdb_id=550,
        title="Fight Club",
        original_title="Fight Club",
        year=1999,
        media_type="movie",
    )
    result = derive_run_folder_name(
        filenames=["random.filename.mkv"],
        tmdb_metadata=tmdb,
    )
    assert result == "Fight Club (1999)"


def test_derive_run_folder_name_falls_back_to_guessit() -> None:
    result = derive_run_folder_name(
        filenames=["Inception.2010.BluRay.1080p.mkv"],
        tmdb_metadata=None,
    )
    assert "Inception" in result
    assert "2010" in result


def test_derive_run_folder_name_combines_stems_as_fallback() -> None:
    result = derive_run_folder_name(
        filenames=["video1.mkv", "video2.mkv"],
        tmdb_metadata=None,
    )
    # Fallback to combined stems
    assert "video1" in result.lower() or "video2" in result.lower()


def test_derive_run_folder_name_handles_collision() -> None:
    result = derive_run_folder_name(
        filenames=["Fight.Club.1999.mkv"],
        tmdb_metadata=None,
        existing_folders=["Fight Club (1999)"],
    )
    # Should append timestamp
    assert "Fight Club" in result
    assert "_" in result  # Timestamp separator


def test_derive_run_folder_name_no_collision() -> None:
    result = derive_run_folder_name(
        filenames=["Fight.Club.1999.mkv"],
        tmdb_metadata=None,
        existing_folders=["Other Movie (2020)"],
    )
    # No timestamp needed
    assert "_20" not in result  # No timestamp pattern


def test_derive_run_folder_name_empty_filenames() -> None:
    with patch("frame_compare.utils.run_folder._format_timestamp", return_value="20260208-020749"):
        result = derive_run_folder_name(filenames=[])
    assert result == "unnamed_run_20260208-020749"


# ─── get_existing_run_folders Tests ───────────────────────────────────────────


def test_get_existing_run_folders_returns_directories_only(tmp_path: Path) -> None:
    # Create mix of files and directories
    (tmp_path / "run_folder_1").mkdir()
    (tmp_path / "run_folder_2").mkdir()
    (tmp_path / "video.mkv").touch()

    result = get_existing_run_folders(tmp_path)

    assert "run_folder_1" in result
    assert "run_folder_2" in result
    assert "video.mkv" not in result


def test_get_existing_run_folders_nonexistent_dir() -> None:
    result = get_existing_run_folders(Path("/nonexistent/path"))
    assert result == []
