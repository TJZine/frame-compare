from __future__ import annotations

import base64
import hashlib
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

METADATA = """\
Metadata-Version: 2.4
Name: frame-compare
Version: 0.1.0
License-Expression: GPL-3.0-only
"""

WHEEL = """\
Wheel-Version: 1.0
Generator: frame-compare-test
Root-Is-Purelib: true
Tag: py3-none-any
"""


def _record_row(name: str, value: str) -> str:
    data = value.encode()
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{name},sha256={digest},{len(data)}"


def _write_wheel(
    dist_dir: Path,
    *,
    include_wheel: bool = True,
    include_record: bool = True,
    metadata_dist_info: str = "frame_compare-0.1.0.dist-info",
    wheel_dist_info: str = "frame_compare-0.1.0.dist-info",
    record_dist_info: str = "frame_compare-0.1.0.dist-info",
    license_dist_info: str = "frame_compare-0.1.0.dist-info",
    duplicate_member: str | None = None,
) -> None:
    wheel = dist_dir / "frame_compare-0.1.0-py3-none-any.whl"
    contents = {
        "frame_compare/__init__.py": '__version__ = "0.1.0"\n',
        f"{metadata_dist_info}/METADATA": METADATA,
        f"{license_dist_info}/licenses/LICENSE": "GPL text",
    }
    if include_wheel:
        contents[f"{wheel_dist_info}/WHEEL"] = WHEEL
    if include_record:
        record_name = f"{record_dist_info}/RECORD"
        record = "\n".join(
            [*(_record_row(name, value) for name, value in contents.items()), f"{record_name},,"]
        )
        contents[record_name] = f"{record}\n"

    with zipfile.ZipFile(wheel, "w") as archive:
        for name, value in contents.items():
            archive.writestr(name, value)
        if duplicate_member is not None:
            duplicate_name = f"{metadata_dist_info}/{duplicate_member}"
            archive.writestr(duplicate_name, contents[duplicate_name])


def _add_tar_text(archive: tarfile.TarFile, name: str, value: str) -> None:
    data = value.encode()
    member = tarfile.TarInfo(name)
    member.size = len(data)
    archive.addfile(member, io.BytesIO(data))


def _write_sdist(
    dist_dir: Path,
    *,
    extra_name: str | None = None,
    extra_member_type: bytes | None = None,
) -> None:
    sdist = dist_dir / "frame_compare-0.1.0.tar.gz"
    root = "frame_compare-0.1.0"
    with tarfile.open(sdist, "w:gz") as archive:
        root_directory = tarfile.TarInfo(root)
        root_directory.type = tarfile.DIRTYPE
        archive.addfile(root_directory)
        _add_tar_text(archive, f"{root}/PKG-INFO", METADATA)
        _add_tar_text(archive, f"{root}/LICENSE", "GPL text")
        _add_tar_text(archive, f"{root}/README.md", "# Frame Compare")
        _add_tar_text(archive, f"{root}/pyproject.toml", "[project]")
        _add_tar_text(archive, f"{root}/src/frame_compare/__init__.py", "")
        if extra_name is not None:
            _add_tar_text(archive, f"{root}/{extra_name}", "unexpected")
        if extra_member_type is not None:
            special = tarfile.TarInfo(f"{root}/special-member")
            special.type = extra_member_type
            special.devmajor = 1
            special.devminor = 3
            archive.addfile(special)


def _run_verifier(repo_root: Path, dist_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "verify_distribution.py"), str(dist_dir)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_distribution_verifier_accepts_expected_artifacts(tmp_path: Path, repo_root: Path) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode == 0
    assert "distribution verification passed: version=0.1.0" in result.stdout
    assert result.stderr == ""


def test_distribution_verifier_rejects_local_environment_state(
    tmp_path: Path, repo_root: Path
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, extra_name=".venv/bin/python")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "contains local or sensitive state" in result.stderr


@pytest.mark.parametrize(
    ("include_wheel", "include_record", "missing_label"),
    [
        (False, True, "WHEEL"),
        (True, False, "RECORD"),
    ],
)
def test_distribution_verifier_rejects_missing_required_wheel_metadata(
    tmp_path: Path,
    repo_root: Path,
    *,
    include_wheel: bool,
    include_record: bool,
    missing_label: str,
) -> None:
    _write_wheel(tmp_path, include_wheel=include_wheel, include_record=include_record)
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert f"exactly one dist-info {missing_label} file" in result.stderr


@pytest.mark.parametrize("member", ["WHEEL", "RECORD"])
def test_distribution_verifier_rejects_duplicate_required_wheel_metadata(
    tmp_path: Path,
    repo_root: Path,
    member: str,
) -> None:
    with pytest.warns(UserWarning, match="Duplicate name"):
        _write_wheel(tmp_path, duplicate_member=member)
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert f"exactly one dist-info {member} file" in result.stderr


@pytest.mark.parametrize("member", ["WHEEL", "RECORD", "LICENSE"])
def test_distribution_verifier_rejects_mismatched_dist_info_directories(
    tmp_path: Path,
    repo_root: Path,
    member: str,
) -> None:
    dist_info = "frame_compare-0.1.0.dist-info"
    other_dist_info = "other-0.1.0.dist-info"
    _write_wheel(
        tmp_path,
        wheel_dist_info=other_dist_info if member == "WHEEL" else dist_info,
        record_dist_info=other_dist_info if member == "RECORD" else dist_info,
        license_dist_info=other_dist_info if member == "LICENSE" else dist_info,
    )
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert f"{member} is not in the METADATA dist-info directory" in result.stderr


def test_distribution_verifier_rejects_nested_dist_info_directory(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    nested_dist_info = "nested/frame_compare-0.1.0.dist-info"
    _write_wheel(
        tmp_path,
        metadata_dist_info=nested_dist_info,
        wheel_dist_info=nested_dist_info,
        record_dist_info=nested_dist_info,
        license_dist_info=nested_dist_info,
    )
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "dist-info directory must be at the archive root" in result.stderr


@pytest.mark.parametrize(
    "member_type",
    [tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE],
    ids=["fifo", "character-device", "block-device"],
)
def test_distribution_verifier_rejects_special_sdist_members(
    tmp_path: Path,
    repo_root: Path,
    member_type: bytes,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, extra_member_type=member_type)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "contains unsupported member types" in result.stderr
