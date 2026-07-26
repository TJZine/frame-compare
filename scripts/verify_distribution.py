"""Validate Frame Compare wheel and source-distribution release contents."""

from __future__ import annotations

import argparse
import email.policy
import tarfile
import zipfile
from collections.abc import Iterable
from email.message import Message
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import NoReturn

EXPECTED_NAME = "frame-compare"
EXPECTED_LICENSE = "GPL-3.0-only"
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


def _verify_wheel(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        names = _validate_member_names(archive.namelist(), artifact=wheel)
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        license_names = [name for name in names if name.endswith(".dist-info/licenses/LICENSE")]
        if len(metadata_names) != 1:
            _fail(f"{wheel.name} must contain exactly one dist-info METADATA file")
        if len(license_names) != 1:
            _fail(f"{wheel.name} must contain exactly one packaged project LICENSE")
        if not any(name.startswith("frame_compare/") for name in names):
            _fail(f"{wheel.name} does not contain the frame_compare package")
        metadata = _metadata_from_bytes(archive.read(metadata_names[0]), artifact=wheel)
    return str(metadata["Version"])


def _verify_sdist(sdist: Path) -> str:
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        names = _validate_member_names((member.name for member in members), artifact=sdist)
        linked = [member.name for member in members if member.issym() or member.islnk()]
        if linked:
            _fail(f"{sdist.name} contains links: {linked!r}")
        metadata_names = [name for name in names if name.endswith("/PKG-INFO")]
        if len(metadata_names) != 1:
            _fail(f"{sdist.name} must contain exactly one PKG-INFO file")
        required_suffixes = (
            "/LICENSE",
            "/README.md",
            "/pyproject.toml",
            "/src/frame_compare/__init__.py",
        )
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                _fail(f"{sdist.name} is missing required content ending in {suffix!r}")
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
