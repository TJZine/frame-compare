"""Tests for run folder naming utilities."""

from pathlib import Path
from unittest.mock import patch

from frame_compare.services.run_folder import (
    _combine_filename_stems,
    derive_run_folder_name,
    find_common_metadata,
    get_existing_run_folders,
    reserve_run_folder,
    sanitize_folder_name,
)
from frame_compare.services.types import ParsedMetadata, TmdbMetadata

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
    assert len(result) <= 64


def test_sanitize_folder_name_truncation_never_returns_empty() -> None:
    long_name = "." * 150
    result = sanitize_folder_name(long_name)
    assert result != ""
    assert result == "unnamed_run"


def test_sanitize_folder_name_avoids_windows_reserved_device_name() -> None:
    assert sanitize_folder_name("CON") == "CON run"
    assert sanitize_folder_name("nul") == "nul run"
    assert sanitize_folder_name("COM1.txt") == "COM1 txt run"


# ─── find_common_metadata Tests ───────────────────────────────────────────────


def test_find_common_metadata_single_file() -> None:
    title, year = find_common_metadata(["Movie.Name.2024.BluRay.1080p.mkv"])
    assert title == "Movie Name"
    assert year == 2024


def test_find_common_metadata_matching_titles() -> None:
    title, year = find_common_metadata(
        [
            "Movie.Name.2024.WEB-DL.1080p.mkv",
            "Movie.Name.2024.BluRay.2160p.mkv",
        ]
    )
    assert title == "Movie Name"
    assert year == 2024


def test_find_common_metadata_different_titles() -> None:
    title, year = find_common_metadata(
        [
            "Movie.A.2024.mkv",
            "Movie.B.2024.mkv",
        ]
    )
    # Titles don't match, but year might
    assert title is None
    assert year == 2024


def test_find_common_metadata_empty_list() -> None:
    title, year = find_common_metadata([])
    assert title is None
    assert year is None


def test_find_common_metadata_preserves_non_empty_title_when_first_is_empty(monkeypatch) -> None:
    responses = iter(
        [
            ParsedMetadata(title="", year=2024),
            ParsedMetadata(title="Movie Name", year=2024),
            ParsedMetadata(title="Movie Name", year=2024),
        ]
    )
    monkeypatch.setattr(
        "frame_compare.services.run_folder.parse_filename",
        lambda _filename: next(responses),
    )
    title, year = find_common_metadata(["a.mkv", "b.mkv", "c.mkv"])
    assert title == "Movie Name"
    assert year == 2024


# ─── _combine_filename_stems Tests ────────────────────────────────────────────


def test_combine_filename_stems_deduplicates() -> None:
    result = _combine_filename_stems(
        [
            "Movie.2024.mkv",
            "Movie.2024.mp4",
        ]
    )
    # Identical stems should collapse to a single entry.
    assert "+" not in result


def test_combine_filename_stems_limits_to_two() -> None:
    result = _combine_filename_stems(
        [
            "Movie1.mkv",
            "Movie2.mkv",
            "Movie3.mkv",
            "Movie4.mkv",
        ]
    )
    assert "+2 more" in result


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


def test_derive_run_folder_name_avoids_reserved_tmdb_title_without_year() -> None:
    tmdb = TmdbMetadata(
        tmdb_id=1,
        title="NUL",
        original_title="NUL",
        year=0,
        media_type="movie",
    )
    result = derive_run_folder_name(
        filenames=["random.filename.mkv"],
        tmdb_metadata=tmdb,
    )
    assert result == "NUL run"


def test_derive_run_folder_name_avoids_reserved_parsed_metadata_title(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "frame_compare.services.run_folder.parse_filename",
        lambda _filename: ParsedMetadata(title="CON", year=None),
    )

    result = derive_run_folder_name(
        filenames=["CON.mkv"],
        tmdb_metadata=None,
    )

    assert result == "CON run"


def test_derive_run_folder_name_avoids_reserved_filename_stem_fallback(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "frame_compare.services.run_folder.parse_filename",
        lambda _filename: ParsedMetadata(title="", year=None),
    )

    result = derive_run_folder_name(
        filenames=["AUX.mkv"],
        tmdb_metadata=None,
    )

    assert result == "AUX run"


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
    assert result == "Fight Club (1999)_2"


def test_derive_run_folder_name_collision_respects_max_length() -> None:
    long_title = "A" * 64
    tmdb = TmdbMetadata(
        tmdb_id=1,
        title=long_title,
        original_title=long_title,
        year=0,
        media_type="movie",
    )
    result = derive_run_folder_name(
        filenames=["source.mkv"],
        tmdb_metadata=tmdb,
        existing_folders=[long_title],
    )
    assert len(result) <= 64
    assert result.endswith("_2")


def test_derive_run_folder_name_retries_when_numeric_name_exists() -> None:
    result = derive_run_folder_name(
        filenames=["Fight.Club.1999.mkv"],
        tmdb_metadata=None,
        existing_folders=[
            "Fight Club (1999)",
            "Fight Club (1999)_2",
        ],
    )

    assert result == "Fight Club (1999)_3"


def test_derive_run_folder_name_no_collision() -> None:
    result = derive_run_folder_name(
        filenames=["Fight.Club.1999.mkv"],
        tmdb_metadata=None,
        existing_folders=["Other Movie (2020)"],
    )
    # No timestamp needed
    assert "_20" not in result  # No timestamp pattern


def test_derive_run_folder_name_empty_filenames() -> None:
    result = derive_run_folder_name(filenames=[], existing_folders=[])
    assert result == "unnamed_run"


def test_derive_run_folder_name_empty_filenames_retries_when_base_exists() -> None:
    result = derive_run_folder_name(
        filenames=[],
        existing_folders=["unnamed_run"],
    )

    assert result == "unnamed_run_2"


def test_derive_run_folder_name_falls_back_to_random_suffix_after_numeric_window() -> None:
    existing_folders = ["Fight Club (1999)", *(f"Fight Club (1999)_{i}" for i in range(2, 102))]
    with patch("frame_compare.services.run_folder.uuid.uuid4") as uuid4:
        uuid4.return_value.hex = "abcdef1234567890"
        result = derive_run_folder_name(
            filenames=["Fight.Club.1999.mkv"],
            existing_folders=existing_folders,
        )

    assert result == "Fight Club (1999)_abcdef12"


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


def test_get_existing_run_folders_existing_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "not_a_dir"
    path.write_text("x", encoding="utf-8")
    result = get_existing_run_folders(path)
    assert result == []


# ─── reserve_run_folder Tests ───────────────────────────────────────────


def test_reserve_run_folder_creates_non_colliding_dir(tmp_path: Path) -> None:
    tmdb = TmdbMetadata(
        tmdb_id=550,
        title="Fight Club",
        original_title="Fight Club",
        year=1999,
        media_type="movie",
    )
    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=["random.filename.mkv"],
        tmdb_metadata=tmdb,
    )
    assert result.path == tmp_path / "Fight Club (1999)"
    assert result.folder_name == "Fight Club (1999)"
    assert result.base_name == "Fight Club (1999)"
    assert result.naming_source == "tmdb"
    assert result.path.exists()
    assert result.path.is_dir()


def test_reserve_run_folder_handles_collisions_atomically(tmp_path: Path) -> None:
    # Pre-create the directory to simulate a collision
    (tmp_path / "Fight Club (1999)").mkdir()

    tmdb = TmdbMetadata(
        tmdb_id=550,
        title="Fight Club",
        original_title="Fight Club",
        year=1999,
        media_type="movie",
    )

    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=["random.filename.mkv"],
        tmdb_metadata=tmdb,
    )

    assert result.path == tmp_path / "Fight Club (1999)_2"
    assert result.folder_name == "Fight Club (1999)_2"
    assert result.base_name == "Fight Club (1999)"
    assert result.naming_source == "tmdb"
    assert result.path.exists()
    assert result.path.is_dir()


def test_reserve_run_folder_empty_filenames_uses_canonical_fallback(tmp_path: Path) -> None:
    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=[],
        tmdb_metadata=None,
    )

    assert result.path == tmp_path / "unnamed_run"
    assert result.folder_name == "unnamed_run"
    assert result.naming_source == "unnamed"
    assert result.path.exists()
    assert result.path.is_dir()


def test_reserve_run_folder_reports_parsed_metadata_source(tmp_path: Path) -> None:
    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=["Inception.2010.BluRay.1080p.mkv"],
        tmdb_metadata=None,
    )

    assert result.naming_source == "parsed_metadata"
    assert result.folder_name == "Inception (2010)"


def test_reserve_run_folder_reports_filename_stems_source(tmp_path: Path) -> None:
    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=["video1.mkv", "video2.mkv"],
        tmdb_metadata=None,
    )

    assert result.naming_source == "filename_stems"
