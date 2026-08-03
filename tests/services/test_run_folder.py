"""Tests for run folder naming utilities."""

from pathlib import Path

import pytest

from frame_compare.errors import PathEscapesRootError
from frame_compare.services.errors import GeneratedDataReservationError
from frame_compare.services.run_folder import (
    _combine_filename_stems,
    find_common_metadata,
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


def test_reserve_run_folder_retries_numeric_collisions(tmp_path: Path) -> None:
    (tmp_path / "Fight Club (1999)").mkdir()
    (tmp_path / "Fight Club (1999)_2").mkdir()

    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=["Fight.Club.1999.mkv"],
        tmdb_metadata=None,
    )

    assert result.folder_name == "Fight Club (1999)_3"
    assert result.path.is_dir()


def test_reserve_run_folder_collision_suffix_preserves_length_limit(tmp_path: Path) -> None:
    long_title = "A" * 64
    (tmp_path / long_title).mkdir()
    tmdb = TmdbMetadata(
        tmdb_id=1,
        title=long_title,
        original_title=long_title,
        year=0,
        media_type="movie",
    )

    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=["source.mkv"],
        tmdb_metadata=tmdb,
    )

    assert len(result.folder_name) == 64
    assert result.folder_name.endswith("_2")
    assert result.path.is_dir()


def test_reserve_run_folder_uses_uuid_after_numeric_window(tmp_path: Path, monkeypatch) -> None:
    base_name = "Fight Club (1999)"
    (tmp_path / base_name).mkdir()
    for attempt in range(2, 102):
        (tmp_path / f"{base_name}_{attempt}").mkdir()

    class FixedUuid:
        hex = "abcdef1234567890"

    monkeypatch.setattr(
        "frame_compare.services.run_folder.uuid.uuid4",
        lambda: FixedUuid(),
    )

    result = reserve_run_folder(
        input_dir=tmp_path,
        filenames=["Fight.Club.1999.mkv"],
        tmdb_metadata=None,
    )

    assert result.folder_name == "Fight Club (1999)_abcdef12"
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


def test_reserve_run_folder_maps_destination_failure_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_mkdir = Path.mkdir

    def _fail_reservation(path: Path, *args: object, **kwargs: object) -> None:
        if path == tmp_path / "source":
            raise PermissionError("destination is read-only")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _fail_reservation)

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(tmp_path, ["source.mkv"])

    assert exc_info.value.code == "FC-3018"
    assert str(tmp_path) in str(exc_info.value)
    assert "permissions" in (exc_info.value.hint or "")
    assert not any(tmp_path.iterdir())


def test_reserve_run_folder_rejects_symlinked_candidate_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "source").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathEscapesRootError):
        reserve_run_folder(tmp_path, ["source.mkv"])


def test_reserve_run_folder_rejects_junctioned_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "Movie (2024)"
    tmdb = TmdbMetadata(
        tmdb_id=1,
        title="Movie",
        original_title="Movie",
        year=2024,
        media_type="movie",
    )

    monkeypatch.setattr(Path, "is_junction", lambda path: path == candidate)

    with pytest.raises(PathEscapesRootError):
        reserve_run_folder(tmp_path, ["source.mkv"], tmdb_metadata=tmdb)

    assert not candidate.exists()


def test_reserve_run_folder_maps_resolve_failure_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_resolve = Path.resolve

    def _fail_owner_resolve(path: Path, *args: object, **kwargs: object) -> Path:
        if path == tmp_path:
            raise RuntimeError("symlink loop")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", _fail_owner_resolve)

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(tmp_path, ["source.mkv"])

    assert exc_info.value.code == "FC-3018"
    assert str(tmp_path) in str(exc_info.value)
    assert "symlink loop" in (exc_info.value.context.details or {}).get("error", "")
    assert not any(tmp_path.iterdir())
