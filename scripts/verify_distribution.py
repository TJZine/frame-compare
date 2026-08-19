"""Validate Frame Compare wheel and source-distribution release contents."""

from __future__ import annotations

import argparse
import base64
import csv
import email.policy
import hashlib
import io
import tarfile
import zipfile
from collections.abc import Iterable
from email.message import Message
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import NoReturn

EXPECTED_NAME = "frame-compare"
EXPECTED_LICENSE = "GPL-3.0-only"
EXPECTED_BUNDLED_FONT_SHA256 = "40d692fce188e4471e2b3cba937be967878f631ad3ebbbdcd587687c7ebe0c82"
_BUNDLED_FONT_WHEEL_PATH = "frame_compare/assets/fonts/Inter-Regular.ttf"
_BUNDLED_LICENSE_WHEEL_PATH = "frame_compare/assets/fonts/Inter-OFL.txt"
_BUNDLED_FONT_SDIST_SUFFIX = "/src/frame_compare/assets/fonts/Inter-Regular.ttf"
_BUNDLED_LICENSE_SDIST_SUFFIX = "/src/frame_compare/assets/fonts/Inter-OFL.txt"
_BUNDLED_LICENSE_MARKER = b"SIL OPEN FONT LICENSE Version 1.1"
FORBIDDEN_PARTS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
}
FORBIDDEN_NAMES = {
    ".DS_Store",
    ".env",
    ".pypirc",
    "id_ed25519",
    "id_rsa",
}


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"distribution verification failed: {message}")


def _verify_bundled_font(data: bytes, *, artifact: Path) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_BUNDLED_FONT_SHA256:
        _fail(f"{artifact.name} bundled Inter font SHA-256 mismatch")


def _verify_bundled_font_license(data: bytes, *, artifact: Path) -> None:
    if _BUNDLED_LICENSE_MARKER not in data:
        _fail(f"{artifact.name} bundled Inter OFL notice is invalid")


def _single_artifact(dist_dir: Path, pattern: str, label: str) -> Path:
    artifacts = sorted(dist_dir.glob(pattern))
    if len(artifacts) != 1:
        _fail(f"expected exactly one {label} matching {pattern!r}, found {len(artifacts)}")
    return artifacts[0]


def _validate_member_names(names: Iterable[str], *, artifact: Path) -> list[str]:
    validated: list[str] = []
    for name in names:
        if "\\" in name:
            _fail(f"{artifact.name} contains a non-portable path: {name!r}")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            _fail(f"{artifact.name} contains an unsafe path: {name!r}")
        if FORBIDDEN_PARTS.intersection(path.parts) or path.name in FORBIDDEN_NAMES:
            _fail(f"{artifact.name} contains local or sensitive state: {name!r}")
        if path.suffix == ".pyc":
            _fail(f"{artifact.name} contains bytecode: {name!r}")
        validated.append(name)
    return validated


def _metadata_from_bytes(data: bytes, *, artifact: Path) -> Message:
    metadata = BytesParser(policy=email.policy.default).parsebytes(data)
    if metadata["Name"] != EXPECTED_NAME:
        _fail(f"{artifact.name} has unexpected project name {metadata['Name']!r}")
    if metadata["License-Expression"] != EXPECTED_LICENSE:
        _fail(
            f"{artifact.name} has unexpected license expression {metadata['License-Expression']!r}"
        )
    if not metadata["Version"]:
        _fail(f"{artifact.name} has no version metadata")
    return metadata


def _verify_wheel_record(
    archive: zipfile.ZipFile,
    *,
    record_name: str,
    artifact: Path,
) -> None:
    file_names = [info.filename for info in archive.infolist() if not info.is_dir()]
    if len(file_names) != len(set(file_names)):
        _fail(f"{artifact.name} contains duplicate archive members")

    try:
        record_text = archive.read(record_name).decode("utf-8")
        reader = csv.reader(io.StringIO(record_text, newline=""))
        records: dict[str, tuple[str, str]] = {}
        for row in reader:
            if len(row) != 3:
                _fail(f"{artifact.name} RECORD contains a malformed row")
            path, digest, size = row
            if path in records:
                _fail(f"{artifact.name} RECORD contains duplicate path {path!r}")
            records[path] = (digest, size)
    except (UnicodeDecodeError, csv.Error) as error:
        _fail(f"{artifact.name} RECORD is invalid: {error}")

    archived = set(file_names)
    recorded = set(records)
    if archived != recorded:
        missing = sorted(archived - recorded)
        stale = sorted(recorded - archived)
        _fail(f"{artifact.name} RECORD paths differ: missing={missing!r} stale={stale!r}")
    if records[record_name] != ("", ""):
        _fail(f"{artifact.name} RECORD must not hash itself")

    for name in file_names:
        if name == record_name:
            continue
        data = archive.read(name)
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        expected = (f"sha256={digest}", str(len(data)))
        if records[name] != expected:
            _fail(f"{artifact.name} RECORD mismatch for {name!r}")


def _verify_wheel(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        names = _validate_member_names(archive.namelist(), artifact=wheel)
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        wheel_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
        record_names = [name for name in names if name.endswith(".dist-info/RECORD")]
        license_names = [name for name in names if name.endswith(".dist-info/licenses/LICENSE")]
        bundled_font_names = [name for name in names if name == _BUNDLED_FONT_WHEEL_PATH]
        bundled_license_names = [name for name in names if name == _BUNDLED_LICENSE_WHEEL_PATH]
        required_members = {
            "dist-info METADATA": metadata_names,
            "dist-info WHEEL": wheel_names,
            "dist-info RECORD": record_names,
            "packaged project LICENSE": license_names,
            "bundled Inter font": bundled_font_names,
            "bundled Inter OFL notice": bundled_license_names,
        }
        for label, matches in required_members.items():
            if len(matches) != 1:
                _fail(f"{wheel.name} must contain exactly one {label} file")

        metadata_name = metadata_names[0]
        dist_info_dir = PurePosixPath(metadata_name).parent
        if len(dist_info_dir.parts) != 1:
            _fail(f"{wheel.name} dist-info directory must be at the archive root")
        if PurePosixPath(wheel_names[0]).parent != dist_info_dir:
            _fail(f"{wheel.name} WHEEL is not in the METADATA dist-info directory")
        if PurePosixPath(record_names[0]).parent != dist_info_dir:
            _fail(f"{wheel.name} RECORD is not in the METADATA dist-info directory")
        if PurePosixPath(license_names[0]).parent.parent != dist_info_dir:
            _fail(f"{wheel.name} LICENSE is not in the METADATA dist-info directory")
        if not any(name.startswith("frame_compare/") for name in names):
            _fail(f"{wheel.name} does not contain the frame_compare package")
        _verify_bundled_font(archive.read(bundled_font_names[0]), artifact=wheel)
        _verify_bundled_font_license(archive.read(bundled_license_names[0]), artifact=wheel)
        _verify_wheel_record(
            archive,
            record_name=record_names[0],
            artifact=wheel,
        )
        metadata = _metadata_from_bytes(archive.read(metadata_name), artifact=wheel)
    return str(metadata["Version"])


def _verify_sdist(sdist: Path) -> str:
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        names = _validate_member_names((member.name for member in members), artifact=sdist)
        linked = [member.name for member in members if member.issym() or member.islnk()]
        if linked:
            _fail(f"{sdist.name} contains links: {linked!r}")
        unsupported = [
            member.name for member in members if not member.isfile() and not member.isdir()
        ]
        if unsupported:
            _fail(f"{sdist.name} contains unsupported member types: {unsupported!r}")
        metadata_names = [name for name in names if name.endswith("/PKG-INFO")]
        if len(metadata_names) != 1:
            _fail(f"{sdist.name} must contain exactly one PKG-INFO file")
        sdist_root = PurePosixPath(metadata_names[0]).parent
        required_suffixes = (
            "/LICENSE",
            "/README.md",
            "/pyproject.toml",
            "/src/frame_compare/__init__.py",
        )
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                _fail(f"{sdist.name} is missing required content ending in {suffix!r}")
        bundled_font_path = f"{sdist_root}{_BUNDLED_FONT_SDIST_SUFFIX}"
        bundled_license_path = f"{sdist_root}{_BUNDLED_LICENSE_SDIST_SUFFIX}"
        bundled_font_names = [name for name in names if name == bundled_font_path]
        bundled_license_names = [name for name in names if name == bundled_license_path]
        required_assets = {
            "bundled Inter font": bundled_font_names,
            "bundled Inter OFL notice": bundled_license_names,
        }
        for label, matches in required_assets.items():
            if len(matches) != 1:
                _fail(f"{sdist.name} must contain exactly one {label} file")

        bundled_font_member = next(
            member for member in members if member.name == bundled_font_names[0]
        )
        if not bundled_font_member.isfile():
            _fail(f"{sdist.name} bundled Inter font is not a regular file")
        bundled_font_file = archive.extractfile(bundled_font_member)
        if bundled_font_file is None:
            _fail(f"{sdist.name} bundled Inter font is not a regular file")
        _verify_bundled_font(bundled_font_file.read(), artifact=sdist)

        bundled_license_member = next(
            member for member in members if member.name == bundled_license_names[0]
        )
        if not bundled_license_member.isfile():
            _fail(f"{sdist.name} bundled Inter OFL notice is not a regular file")
        bundled_license_file = archive.extractfile(bundled_license_member)
        if bundled_license_file is None:
            _fail(f"{sdist.name} bundled Inter OFL notice is not a regular file")
        _verify_bundled_font_license(bundled_license_file.read(), artifact=sdist)

        metadata_file = archive.extractfile(metadata_names[0])
        if metadata_file is None:
            _fail(f"{sdist.name} PKG-INFO is not a regular file")
        metadata = _metadata_from_bytes(metadata_file.read(), artifact=sdist)
    return str(metadata["Version"])


def verify_distribution(dist_dir: Path) -> None:
    """Validate the single wheel and sdist in ``dist_dir``."""
    if not dist_dir.is_dir():
        _fail(f"artifact directory does not exist: {dist_dir}")
    wheel = _single_artifact(dist_dir, "*.whl", "wheel")
    sdist = _single_artifact(dist_dir, "*.tar.gz", "source distribution")
    wheel_version = _verify_wheel(wheel)
    sdist_version = _verify_sdist(sdist)
    if wheel_version != sdist_version:
        _fail(f"artifact versions differ: wheel={wheel_version}, sdist={sdist_version}")
    print(
        f"distribution verification passed: version={wheel_version} "
        f"wheel={wheel.name} sdist={sdist.name}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist_dir", type=Path, help="Directory containing one wheel and one sdist")
    args = parser.parse_args()
    verify_distribution(args.dist_dir)


if __name__ == "__main__":
    main()
