"""Screenshot file naming utilities."""

import hashlib
import os
import re
from pathlib import Path

from frame_compare.render.errors import EncodingError, ScreenshotOutputCollisionError
from frame_compare.utils.cancellation import raise_if_cancelling

INVALID_LABEL_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f\ud800-\udfff]')
_MAX_LEGACY_WINDOWS_PATH_CHARS = 259
_CONSERVATIVE_FILESYSTEM_COMPONENT_BYTES = 255
_SHORT_NAME_DIGEST_CHARS = 12


def _windows_path_units(path: Path) -> int:
    return len(os.path.abspath(path).encode("utf-16-le", errors="surrogatepass")) // 2


def _filesystem_component_limit(path: Path) -> int:
    for candidate in (path, *path.parents):
        try:
            limit = int(os.pathconf(candidate, "PC_NAME_MAX"))
        except (AttributeError, OSError, ValueError):
            continue
        if limit > 0:
            return limit
    return _CONSERVATIVE_FILESYSTEM_COMPONENT_BYTES


def sanitize_filename_stem(label: str) -> str:
    """Return a legacy-compatible filesystem-safe screenshot label."""
    sanitized = INVALID_LABEL_PATTERN.sub("_", label)
    if os.name == "nt":
        sanitized = sanitized.rstrip(" .")
    sanitized = sanitized.strip()
    return sanitized or "comparison"


def generate_screenshot_name(filename_label: str, frame_number: int, extension: str = "png") -> str:
    """Return a stable screenshot filename as ``{frame} - {safe label}.{extension}``."""
    if frame_number < 0:
        raise ValueError("frame_number must be non-negative")
    extension = extension.lstrip(".")
    if not extension:
        raise ValueError("extension must not be empty")

    sanitized = sanitize_filename_stem(filename_label)
    return f"{frame_number} - {sanitized}.{extension}"


def generate_screenshot_path(output_dir: Path, filename_label: str, frame_number: int) -> Path:
    filename = generate_screenshot_name(filename_label, frame_number)
    output_path = output_dir / filename
    component_limit = _filesystem_component_limit(output_dir)
    if (
        _windows_path_units(output_path) <= _MAX_LEGACY_WINDOWS_PATH_CHARS
        and len(os.fsencode(output_path.name)) <= component_limit
    ):
        return output_path

    sanitized = sanitize_filename_stem(filename_label)
    digest = hashlib.sha256(sanitized.encode("utf-8")).hexdigest()[:_SHORT_NAME_DIGEST_CHARS]
    prefix = f"{frame_number} - "
    suffix = f"~{digest}.png"
    available_label_units = (
        _MAX_LEGACY_WINDOWS_PATH_CHARS
        - _windows_path_units(output_dir)
        - 1
        - len(prefix)
        - len(suffix)
    )
    available_label_bytes = component_limit - len(os.fsencode(prefix)) - len(os.fsencode(suffix))
    shortened: list[str] = []
    used_units = 0
    used_bytes = 0
    for character in sanitized:
        character_units = len(character.encode("utf-16-le", errors="surrogatepass")) // 2
        character_bytes = len(os.fsencode(character))
        if (
            used_units + character_units > available_label_units
            or used_bytes + character_bytes > available_label_bytes
        ):
            break
        shortened.append(character)
        used_units += character_units
        used_bytes += character_bytes
    shortened_label = "".join(shortened).rstrip(" .")
    if available_label_units < 1 or available_label_bytes < 1 or not shortened_label:
        raise ValueError("screenshot output directory is too long for a browser-safe filename")
    return output_dir / f"{prefix}{shortened_label}{suffix}"


def validate_screenshot_paths(paths: list[Path]) -> None:
    """Refuse final paths that address the same file on their destination."""
    exact: set[str] = set()
    for path in paths:
        if str(path) in exact:
            raise ScreenshotOutputCollisionError(path, path)
        exact.add(str(path))

    identities: dict[tuple[int, int], Path] = {}
    reservations: list[tuple[Path, tuple[int, int] | None]] = []
    current_path: Path | None = None
    primary_error: BaseException | None = None
    try:
        for path in paths:
            raise_if_cancelling()
            current_path = path
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Reserve the actual name exclusively. The filesystem determines
                # equivalence, including Unicode normalization/case rules and
                # Windows per-directory flags. Existing files are never opened
                # for writing; all owned reservations are removed before rendering.
                with path.open("xb") as reservation:
                    # Register ownership before inspecting metadata so even an
                    # fstat failure removes the exclusively created reservation.
                    reservations.append((path, None))
                    status = os.fstat(reservation.fileno())
                    identity = (status.st_dev, status.st_ino)
                    reservations[-1] = (path, identity)
            except FileExistsError:
                status = path.stat()
                identity = (status.st_dev, status.st_ino)
            previous = identities.get(identity)
            if previous is not None:
                raise ScreenshotOutputCollisionError(previous, path)
            identities[identity] = path
        raise_if_cancelling()
    except OSError:
        assert current_path is not None
        primary_error = EncodingError(current_path, "Unable to validate screenshot output names")
        raise primary_error from None
    except BaseException as original_error:
        # Preserve control flow through cleanup; do not handle or reclassify it.
        primary_error = original_error
        raise
    finally:
        cleanup_failure: Path | None = None
        for path, identity in reversed(reservations):
            try:
                # Do not remove a replacement owned by another writer when its
                # identity is available. Each output directory belongs to one run;
                # concurrent modification during validation is unsupported.
                if identity is None:
                    path.unlink()
                else:
                    status = path.stat(follow_symlinks=False)
                    if (status.st_dev, status.st_ino) == identity:
                        path.unlink()
            except FileNotFoundError:
                continue
            except OSError:
                cleanup_failure = path
        if cleanup_failure is not None:
            if primary_error is None:
                raise EncodingError(
                    cleanup_failure, "Unable to remove screenshot name reservation"
                ) from None
            primary_error.add_note(
                f"Unable to remove screenshot name reservation: {cleanup_failure}"
            )
