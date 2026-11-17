"""Tests for run folder naming and reservation."""

from datetime import datetime
from pathlib import Path
from typing import cast

import pytest

from frame_compare.errors import PathEscapesRootError
from frame_compare.services.errors import GeneratedDataReservationError
from frame_compare.services.metadata_parsing import parse_filename_with_release_identity
from frame_compare.services.release_identity import ShortNameSource
from frame_compare.services.run_folder import reserve_run_folder
from frame_compare.services.types import TmdbMetadata

_EBP = "Black.Sails.S01E08.1080p.Bluray.DD5.1.x264-EbP.mkv"
_GNOME = "Black.Sails.S01E08.VIII.1080p.AMZN.WEB-DL.DDP.5.1.H.264-GNOME.mkv"
_NOGRP = "Black.Sails.S01E08.VIII.1080p.BluRay.REMUX.AVC.DTS-HD.MA.5.1-NOGRP.mkv"
_DUB = "Constructed.DemonSlayer-Kitsune.english-dub-only.mkv"
_NOW = datetime(2026, 11, 16, 13, 25, 42).astimezone()
_BASE = "Black Sails S01E08 - EbP, GNOME"
_MINUTE = " (2026-11-16 13.25)"
_SECOND = " (2026-11-16 13.25.42)"
_SOURCE = [ShortNameSource(None, "source", True, "source")]


def _sources(*filenames: str) -> list[ShortNameSource]:
    return [
        ShortNameSource(
            parse_filename_with_release_identity(name)[1],
            Path(name).stem,
            False,
            Path(name).stem,
        )
        for name in filenames
    ]


def _explicit(*labels: str) -> list[ShortNameSource]:
    return [ShortNameSource(None, label, True, label) for label in labels]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ('Movie: The <Test> "Edition"', "Movie The Test Edition"),
        ("Movie   Name_with spaces...", "Movie Name with spaces"),
        ("", "Reference"),
        (" " * 70, "Reference"),
        ("." * 150, "Reference"),
        ("CON", "CON run"),
        ("nul", "nul run"),
        ("COM1.txt", "COM1 txt run"),
        ("COM¹", "COM¹ run"),
        ("LPT²", "LPT² run"),
        ("CONIN$", "CONIN$ run"),
        ("CONOUT$", "CONOUT$ run"),
        ("NUL .txt", "NUL txt run"),
    ],
)
def test_reserve_run_folder_sanitizes_names(tmp_path: Path, label: str, expected: str) -> None:
    reservation = reserve_run_folder(tmp_path, _explicit(label), now=_NOW)

    assert reservation.folder_name == expected
    assert reservation.path.is_dir()


def test_reserve_run_folder_uses_tmdb_series_title_and_reference_episode(tmp_path: Path) -> None:
    metadata = TmdbMetadata(123, "Les Voiles Noires", "Black Sails", 2014, "tv")

    result = reserve_run_folder(tmp_path, _sources(_EBP, _GNOME), metadata, now=_NOW)

    assert result.path == tmp_path / "Les Voiles Noires S01E08 - EbP, GNOME"
    assert result.naming_source == "tmdb"
    assert result.path.is_dir()


@pytest.mark.parametrize(
    ("filenames", "name", "naming_source"),
    [
        ((_EBP, _GNOME, _NOGRP), f"{_BASE}, NOGRP", "parsed_metadata"),
        (
            (_EBP, _DUB),
            "Black Sails S01E08 + Constructed DemonSlayer Kitsune - EbP +1",
            "filename_stems",
        ),
    ],
)
def test_reserve_run_folder_derives_titles_from_prepared_filenames(
    tmp_path: Path, filenames: tuple[str, ...], name: str, naming_source: str
) -> None:
    result = reserve_run_folder(tmp_path, _sources(*filenames), now=_NOW)

    assert result.folder_name == name
    assert result.naming_source == naming_source
    assert result.path.is_dir()


def test_reserve_run_folder_preserves_explicit_labels_when_no_title_parses(tmp_path: Path) -> None:
    result = reserve_run_folder(tmp_path, _explicit("Reference encode", "Candidate"), now=_NOW)

    assert result.folder_name == "Reference encode, Candidate"
    assert result.naming_source == "filename_stems"


@pytest.mark.parametrize(
    ("labels", "name"),
    [
        (("???", "GNOME"), "Reference, GNOME"),
        (("???", "Reference"), "Reference Reference, Comparison 1 Reference"),
    ],
)
def test_reserve_run_folder_keeps_sources_distinct_after_sanitizing(
    tmp_path: Path, labels: tuple[str, ...], name: str
) -> None:
    result = reserve_run_folder(tmp_path, _explicit(*labels), now=_NOW)

    assert result.path == tmp_path / name
    assert result.path.is_dir()
    assert result.naming_source == "filename_stems"


def test_reserve_run_folder_counts_role_label_omitted_for_length(tmp_path: Path) -> None:
    title = "A Motion Picture With An Unusually Long Name"
    metadata = TmdbMetadata(1, title, "Original", 2026, "movie")

    result = reserve_run_folder(tmp_path, _explicit("GNOME", "???"), metadata, now=_NOW)

    assert result.folder_name == f"{title} (2026) - GNOME +1"
    assert result.path.is_dir()


def test_reserve_run_folder_empty_sources_uses_canonical_fallback(tmp_path: Path) -> None:
    result = reserve_run_folder(tmp_path, [], now=_NOW)

    assert result.path == tmp_path / "unnamed_run"
    assert result.naming_source == "unnamed"
    assert result.path.is_dir()


@pytest.mark.parametrize(
    ("existing", "suffix"),
    [
        ([""], _MINUTE),
        (["", _MINUTE], _SECOND),
        (["", _MINUTE, _SECOND], " (2026-11-16 13.25.42 abcdef12)"),
    ],
)
def test_reserve_run_folder_claims_timestamp_then_uuid_after_collisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: list[str], suffix: str
) -> None:
    for claimed in existing:
        (tmp_path / f"{_BASE}{claimed}").mkdir()

    class FixedUuid:
        hex = "abcdef1234567890"

    monkeypatch.setattr("frame_compare.services.run_folder.uuid.uuid4", lambda: FixedUuid())

    result = reserve_run_folder(tmp_path, _sources(_EBP, _GNOME), now=_NOW)

    assert result.path == tmp_path / f"{_BASE}{suffix}"
    assert result.base_name == _BASE
    assert result.path.is_dir()


def test_reserve_run_folder_drops_trailing_labels_before_cutting_title(tmp_path: Path) -> None:
    metadata = TmdbMetadata(1, "The Longest Movie Title", "Original", 2026, "movie")
    sources = _explicit("First encode", "Second encode", "An unreasonably long third encode")

    result = reserve_run_folder(tmp_path, sources, metadata, now=_NOW)

    assert result.folder_name == "The Longest Movie Title (2026) - First encode, Second encode +1"
    assert result.path.is_dir()


@pytest.mark.parametrize("separator", [" ", ".", "-", ","])
def test_reserve_run_folder_fits_collisions_at_title_token_boundaries(
    tmp_path: Path, separator: str
) -> None:
    title = separator.join(("This", "title", "must", "fit", "without", "splitting", "a", "word"))
    metadata = TmdbMetadata(1, title, "Original", 2026, "movie")
    sources = _explicit("X", "Y")

    first = reserve_run_folder(tmp_path, sources, metadata, now=_NOW)
    second = reserve_run_folder(tmp_path, sources, metadata, now=_NOW)

    assert first.folder_name == f"{title} (2026) - X, Y"
    assert second.folder_name.endswith(f" - +2{_MINUTE}")
    shortened_title = second.folder_name.removesuffix(f" - +2{_MINUTE}")
    assert shortened_title in [
        separator.join(title.split(separator)[:count])
        for count in range(1, len(title.split(separator)) + 1)
    ]
    assert len(second.folder_name) <= 64
    assert second.path.is_dir()


def test_reserve_run_folder_keeps_labels_when_title_is_one_overlong_token(tmp_path: Path) -> None:
    metadata = TmdbMetadata(1, "A" * 200, "Original", 2026, "movie")

    result = reserve_run_folder(tmp_path, _explicit("Source A", "Source B"), metadata, now=_NOW)

    assert result.folder_name == "Source A, Source B"
    assert result.path.is_dir()


def test_reserve_run_folder_maps_destination_failure_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_mkdir = Path.mkdir

    def _fail_reservation(
        path: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
    ) -> None:
        if path == tmp_path / "source":
            raise PermissionError("destination is read-only")
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", _fail_reservation)

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(tmp_path, _SOURCE, now=_NOW)

    assert exc_info.value.code == "FC-3018"
    assert str(tmp_path) in str(exc_info.value)
    assert "permissions" in (exc_info.value.hint or "")
    assert not any(tmp_path.iterdir())


def test_reserve_run_folder_creates_missing_real_owner_chain(tmp_path: Path) -> None:
    generated_root = tmp_path / "missing" / "generated"

    reservation = reserve_run_folder(generated_root, _SOURCE, now=_NOW)

    assert generated_root.is_dir()
    assert reservation.path == generated_root / "source"
    assert reservation.path.is_dir()


def test_reserve_run_folder_rejects_unresolved_owner_before_creating_directories(
    tmp_path: Path,
) -> None:
    unresolved_parent = tmp_path / "missing-parent"
    resolved_generated_root = tmp_path / "generated"
    generated_root = unresolved_parent / ".." / resolved_generated_root.name

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(generated_root, _SOURCE, now=_NOW)

    assert exc_info.value.code == "FC-3018"
    assert not unresolved_parent.exists()
    assert not resolved_generated_root.exists()


def test_reserve_run_folder_maps_non_directory_owner_without_collision_retries(
    tmp_path: Path,
) -> None:
    generated_root = tmp_path / "generated"
    generated_root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(generated_root, _SOURCE, now=_NOW)

    assert exc_info.value.code == "FC-3018"
    details = exc_info.value.context.details
    assert details is not None
    assert details["path"] == str(generated_root)
    error = details["error"]
    assert isinstance(error, str)
    assert "generated-data root ancestor is not a real directory" in error


def test_reserve_run_folder_rejects_unresolved_symlink_owner_without_writing_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    generated_root = tmp_path / "generated-link"
    generated_root.symlink_to(target, target_is_directory=True)

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(generated_root, _SOURCE, now=_NOW)

    assert exc_info.value.code == "FC-3018"
    assert not (target / "source").exists()


def test_reserve_run_folder_rejects_redirected_owner_ancestor_before_writing_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(target, target_is_directory=True)
    generated_root = linked_parent / "generated"

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(generated_root, _SOURCE, now=_NOW)

    assert exc_info.value.code == "FC-3018"
    assert not (target / "generated").exists()


def test_reserve_run_folder_rejects_junctioned_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    monkeypatch.setattr(Path, "is_junction", lambda path: path == generated_root)

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(generated_root, _SOURCE, now=_NOW)

    assert exc_info.value.code == "FC-3018"
    assert not (generated_root / "source").exists()


def test_reserve_run_folder_rejects_symlinked_candidate_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "source").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathEscapesRootError):
        reserve_run_folder(tmp_path, _SOURCE, now=_NOW)


def test_reserve_run_folder_rejects_junctioned_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "Movie (2024) - source"
    tmdb = TmdbMetadata(
        tmdb_id=1,
        title="Movie",
        original_title="Movie",
        year=2024,
        media_type="movie",
    )

    monkeypatch.setattr(Path, "is_junction", lambda path: path == candidate)

    with pytest.raises(PathEscapesRootError):
        reserve_run_folder(tmp_path, _SOURCE, tmdb_metadata=tmdb, now=_NOW)

    assert not candidate.exists()


def test_reserve_run_folder_maps_resolve_failure_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_resolve = Path.resolve

    def _fail_owner_resolve(path: Path, strict: bool = False) -> Path:
        if path == tmp_path:
            raise RuntimeError("symlink loop")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", _fail_owner_resolve)

    with pytest.raises(GeneratedDataReservationError) as exc_info:
        reserve_run_folder(tmp_path, _SOURCE, now=_NOW)

    assert exc_info.value.code == "FC-3018"
    assert str(tmp_path) in str(exc_info.value)
    assert "symlink loop" in cast(str, (exc_info.value.context.details or {}).get("error", ""))
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        TmdbMetadata(1, "Inception", "Inception", 2010, "movie"),
        TmdbMetadata(1, "", "Inception", 2010, "movie"),
    ],
)
def test_folder_title_and_single_source_label_do_not_repeat(
    tmp_path: Path, metadata: TmdbMetadata | None
) -> None:
    result = reserve_run_folder(tmp_path, _sources("Inception.2010.mkv"), metadata, now=_NOW)
    assert result.folder_name == "Inception (2010) - Reference"


def test_single_long_folder_label_keeps_its_words(tmp_path: Path) -> None:
    result = reserve_run_folder(
        tmp_path,
        _explicit("A detailed encode label " * 8),
        TmdbMetadata(1, "Film", "Film", 2024, "movie"),
        now=_NOW,
    )
    assert result.folder_name == "Film (2024) - A detailed encode label A detailed encode label A"
    assert len(result.folder_name) <= 64


@pytest.mark.parametrize(
    ("filename", "label", "metadata", "expected", "naming_source"),
    [
        (
            "Inception.mkv",
            "Inception",
            TmdbMetadata(1, "Inception", "Inception", 2010, "movie"),
            "Inception (2010) - Reference",
            "tmdb",
        ),
        (
            "Movie.2010.1080p.BluRay.x264.mkv",
            "Movie (2010)",
            None,
            "Movie (2010) - BluRay",
            "parsed_metadata",
        ),
    ],
)
def test_reserve_run_folder_compares_only_short_name_with_title(
    tmp_path: Path,
    filename: str,
    label: str,
    metadata: TmdbMetadata | None,
    expected: str,
    naming_source: str,
) -> None:
    parsed = _sources(filename)[0]
    source = ShortNameSource(parsed.identity, label, False, parsed.stem)
    result = reserve_run_folder(tmp_path, [source], metadata, now=_NOW)
    assert result.folder_name == expected
    assert result.naming_source == naming_source
