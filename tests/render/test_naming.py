import asyncio
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from frame_compare.render.errors import EncodingError, ScreenshotOutputCollisionError
from frame_compare.render.naming import (
    generate_screenshot_name,
    generate_screenshot_path,
    validate_screenshot_paths,
)


def test_generate_name_sanitizes_surrogate_escape():
    name = generate_screenshot_name("Source\udcff", 10)

    assert name == "10 - Source_.png"
    assert not any("\ud800" <= character <= "\udfff" for character in name)


def test_generate_name_negative_frame_raises():
    with pytest.raises(ValueError, match="frame_number must be non-negative"):
        generate_screenshot_name("Test", -1)


def test_generate_name_empty_extension_raises():
    with pytest.raises(ValueError, match="extension must not be empty"):
        generate_screenshot_name("Test", 1, extension="")


def test_generate_path_sanitizes(tmp_path):
    assert generate_screenshot_path(tmp_path, "Bad:Name", 1) == tmp_path / "1 - Bad_Name.png"


def test_generate_path_bounds_long_browser_file_paths(tmp_path):
    # Fix the directory length so the filename budget does not depend on the temp root.
    padding = "n" * (200 - len(os.path.abspath(tmp_path)) - len("/screenshots") - 1)
    output_dir = tmp_path / padding / "screenshots"
    assert len(os.path.abspath(output_dir)) == 200
    common_prefix = "Very.Long.Release.Name." * 8

    first = generate_screenshot_path(output_dir, f"{common_prefix}source-a", 42)
    second = generate_screenshot_path(output_dir, f"{common_prefix}source-b", 42)

    assert len(os.path.abspath(first).encode("utf-16-le")) // 2 <= 259
    assert len(os.path.abspath(second).encode("utf-16-le")) // 2 <= 259
    assert first != second
    assert first == generate_screenshot_path(output_dir, f"{common_prefix}source-a", 42)
    assert first.name.startswith("42 - V")
    assert first.suffix == ".png"


def test_generate_path_counts_non_bmp_characters_as_two_windows_units(tmp_path):
    output_dir = tmp_path / "screenshots"

    path = generate_screenshot_path(output_dir, "😀" * 200, 42)

    assert len(os.path.abspath(path).encode("utf-16-le")) // 2 <= 259
    assert path.suffix == ".png"


def test_generate_path_sanitizes_surrogate_escape_in_long_label(tmp_path):
    output_dir = tmp_path / "screenshots"

    path = generate_screenshot_path(output_dir, ("Source\udcff" * 200), 42)

    assert len(os.path.abspath(path).encode("utf-16-le")) // 2 <= 259
    assert path.name.startswith("42 - Source_")
    assert path.suffix == ".png"
    assert not any("\ud800" <= character <= "\udfff" for character in path.name)


def test_generate_path_counts_surrogate_escaped_output_dir(tmp_path):
    output_dir = tmp_path / "screenshots\udcff"

    path = generate_screenshot_path(output_dir, "Ref", 42)

    assert path == output_dir / "42 - Ref.png"


def test_generate_path_bounds_multibyte_component_for_large_frame(tmp_path):
    output_dir = tmp_path / "screenshots"
    source_stem = "界" * 82
    first = generate_screenshot_path(output_dir, source_stem, 100000)
    second = generate_screenshot_path(output_dir, f"{source_stem}a", 100000)

    try:
        component_limit = int(os.pathconf(tmp_path, "PC_NAME_MAX"))
    except (AttributeError, OSError, ValueError):
        component_limit = 255

    assert len(os.fsencode(first.name)) <= component_limit
    assert len(os.fsencode(second.name)) <= component_limit
    assert len(os.path.abspath(first).encode("utf-16-le")) // 2 <= 259
    assert first != second
    assert first == generate_screenshot_path(output_dir, source_stem, 100000)


@pytest.mark.parametrize(
    "label, frame, extension, expected",
    [
        pytest.param("Test", 1, "jpg", "1 - Test.jpg", id="custom_extension"),
        pytest.param("My Source", 50, "png", "50 - My Source.png", id="preserves_spaces"),
        pytest.param(
            "Bad:Name?.mkv", 10, "png", "10 - Bad_Name_.mkv.png", id="sanitizes_special_chars"
        ),
        pytest.param("A:::B", 1, "png", "1 - A___B.png", id="preserves_replacement_underscores"),
        pytest.param(" **Test** ", 1, "png", "1 - __Test__.png", id="strips_leading_trailing"),
        pytest.param("", 1, "png", "1 - comparison.png", id="empty_becomes_unnamed"),
        pytest.param(
            "<>:/\\|?*",
            1,
            "png",
            "1 - ________.png",
            id="all_special_preserves_replacement_underscores",
        ),
        pytest.param("My-Source", 1, "png", "1 - My-Source.png", id="preserves_hyphen"),
        pytest.param("CON", 1, "png", "1 - CON.png", id="preserves_windows_reserved_name_stem"),
    ],
)
def test_generate_name_cases(label: str, frame: int, extension: str, expected: str) -> None:
    assert generate_screenshot_name(label, frame, extension=extension) == expected


@pytest.mark.parametrize(
    "names",
    [
        ("Movie", "movie"),
        ("Ç", "ç"),
        ("é", "e\u0301"),
        ("Straße", "Strasse"),
        ("Ç", "c"),
        ("straße", "strasze"),
    ],
)
def test_output_identity_uses_actual_unicode_rules_and_cleans_reservations(
    tmp_path: Path, names: tuple[str, str]
) -> None:
    paths = [tmp_path / f"10 - {name}.png" for name in names]
    # Establish physical equivalence independently of validation's implementation.
    paths[0].write_bytes(b"original")
    aliases = paths[1].exists() and paths[1].samefile(paths[0])
    paths[0].unlink()
    if aliases:
        with pytest.raises(ScreenshotOutputCollisionError):
            validate_screenshot_paths(paths)
    else:
        validate_screenshot_paths(paths)
    assert list(tmp_path.iterdir()) == []


def test_output_identity_preserves_existing_files(tmp_path: Path) -> None:
    first = tmp_path / "10 - original.png"
    second = tmp_path / "10 - existing-link.png"
    first.write_bytes(b"existing screenshot")
    second.hardlink_to(first)
    with pytest.raises(ScreenshotOutputCollisionError):
        validate_screenshot_paths([tmp_path / "10 - new.png", first, second])
    assert first.read_bytes() == second.read_bytes() == b"existing screenshot"
    assert sorted(path.name for path in tmp_path.iterdir()) == [second.name, first.name]


def test_reservation_failure_is_typed_and_removes_prior_reservations(tmp_path: Path) -> None:
    paths = [tmp_path / "1 - first.png", tmp_path / "1 - second.png"]
    original_open = Path.open

    def fail_second(path: Path, *args, **kwargs):
        if path == paths[1]:
            raise PermissionError("private operating-system text")
        return original_open(path, *args, **kwargs)

    with (
        patch.object(Path, "open", fail_second),
        pytest.raises(EncodingError) as caught,
    ):
        validate_screenshot_paths(paths)
    assert "private operating-system text" not in str(caught.value)
    assert list(tmp_path.iterdir()) == []


def test_cancellation_removes_reservations_before_admitting_next_path(tmp_path: Path) -> None:
    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint

    paths = [tmp_path / "1 - first.png", tmp_path / "1 - second.png"]
    original_open = Path.open
    opened: list[Path] = []

    def cancel_after_first(path: Path, *args, **kwargs):
        opened.append(path)
        file = original_open(path, *args, **kwargs)
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        return file

    async def validate_and_deliver_cancellation() -> None:
        with patch.object(Path, "open", cancel_after_first), pytest.raises(_RunInterrupt):
            validate_screenshot_paths(paths)
        assert opened == paths[:1]
        assert list(tmp_path.iterdir()) == []
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(validate_and_deliver_cancellation())


def test_reservation_metadata_failure_removes_exclusive_creation(tmp_path: Path) -> None:
    with (
        patch("frame_compare.render.naming.os.fstat", side_effect=OSError("metadata failed")),
        pytest.raises(EncodingError),
    ):
        validate_screenshot_paths([tmp_path / "1 - first.png"])
    assert list(tmp_path.iterdir()) == []


def test_cleanup_preserves_replacement_file(tmp_path: Path) -> None:
    path = tmp_path / "1 - first.png"
    retained_reservation = tmp_path / "reservation.png"
    replacement = tmp_path / "replacement.png"
    replacement.write_bytes(b"another owner")
    replacement_status = replacement.stat()
    replacement_identity = (replacement_status.st_dev, replacement_status.st_ino)

    def replace_closed_reservation() -> None:
        if not path.exists():
            return
        # The final cancellation checkpoint follows the reservation's close.
        # Retain its file so the replacement cannot reuse its physical identity.
        path.rename(retained_reservation)
        replacement.rename(path)

    with patch("frame_compare.render.naming.raise_if_cancelling", replace_closed_reservation):
        validate_screenshot_paths([path])
    reserved_status = retained_reservation.stat()
    assert (reserved_status.st_dev, reserved_status.st_ino) != replacement_identity
    surviving_status = path.stat()
    assert (surviving_status.st_dev, surviving_status.st_ino) == replacement_identity
    assert path.read_bytes() == b"another owner"
