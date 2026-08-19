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


_FONT_ASSET_DIR = Path(__file__).resolve().parents[2] / "src/frame_compare/assets/fonts"
_BUNDLED_FONT_BYTES = (_FONT_ASSET_DIR / "Inter-Regular.ttf").read_bytes()
_BUNDLED_FONT_LICENSE = (_FONT_ASSET_DIR / "Inter-OFL.txt").read_text(encoding="utf-8").encode()


def _record_row(name: str, data: bytes) -> str:
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
    include_bundled_font: bool = True,
    include_bundled_license: bool = True,
    bundled_font_bytes: bytes | None = None,
    duplicate_member: str | None = None,
) -> None:
    wheel = dist_dir / "frame_compare-0.1.0-py3-none-any.whl"
    contents: dict[str, bytes] = {
        "frame_compare/__init__.py": b'__version__ = "0.1.0"\n',
        f"{metadata_dist_info}/METADATA": METADATA.encode(),
        f"{license_dist_info}/licenses/LICENSE": b"GPL text",
    }
    if include_wheel:
        contents[f"{wheel_dist_info}/WHEEL"] = WHEEL.encode()
    if include_bundled_font:
        contents["frame_compare/assets/fonts/Inter-Regular.ttf"] = (
            _BUNDLED_FONT_BYTES if bundled_font_bytes is None else bundled_font_bytes
        )
    if include_bundled_license:
        contents["frame_compare/assets/fonts/Inter-OFL.txt"] = _BUNDLED_FONT_LICENSE
    if include_record:
        record_name = f"{record_dist_info}/RECORD"
        record = "\n".join(
            [*(_record_row(name, data) for name, data in contents.items()), f"{record_name},,"]
        )
        contents[record_name] = f"{record}\n".encode()

    with zipfile.ZipFile(wheel, "w") as archive:
        for name, value in contents.items():
            archive.writestr(name, value)
        if duplicate_member is not None:
            duplicate_name = f"{metadata_dist_info}/{duplicate_member}"
            archive.writestr(duplicate_name, contents[duplicate_name])


def _replace_wheel_member(wheel: Path, member_name: str, value: str) -> None:
    replacement = value.encode()
    with zipfile.ZipFile(wheel) as archive:
        members = [(info, archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(wheel, "w") as archive:
        for info, data in members:
            archive.writestr(info, replacement if info.filename == member_name else data)


def _read_wheel_member(wheel: Path, member_name: str) -> str:
    with zipfile.ZipFile(wheel) as archive:
        return archive.read(member_name).decode()


def _add_tar_bytes(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(data)
    archive.addfile(member, io.BytesIO(data))


def _add_tar_text(archive: tarfile.TarFile, name: str, value: str) -> None:
    _add_tar_bytes(archive, name, value.encode())


def _write_sdist(
    dist_dir: Path,
    *,
    extra_name: str | None = None,
    extra_member_type: bytes | None = None,
    include_bundled_font: bool = True,
    include_bundled_license: bool = True,
    bundled_font_bytes: bytes | None = None,
    bundled_asset_root: str | None = None,
) -> None:
    sdist = dist_dir / "frame_compare-0.1.0.tar.gz"
    root = "frame_compare-0.1.0"
    asset_root = root if bundled_asset_root is None else bundled_asset_root
    with tarfile.open(sdist, "w:gz") as archive:
        root_directory = tarfile.TarInfo(root)
        root_directory.type = tarfile.DIRTYPE
        archive.addfile(root_directory)
        _add_tar_text(archive, f"{root}/PKG-INFO", METADATA)
        _add_tar_text(archive, f"{root}/LICENSE", "GPL text")
        _add_tar_text(archive, f"{root}/README.md", "# Frame Compare")
        _add_tar_text(archive, f"{root}/pyproject.toml", "[project]")
        _add_tar_text(archive, f"{root}/src/frame_compare/__init__.py", "")
        if include_bundled_font:
            _add_tar_bytes(
                archive,
                f"{asset_root}/src/frame_compare/assets/fonts/Inter-Regular.ttf",
                _BUNDLED_FONT_BYTES if bundled_font_bytes is None else bundled_font_bytes,
            )
        if include_bundled_license:
            _add_tar_bytes(
                archive,
                f"{asset_root}/src/frame_compare/assets/fonts/Inter-OFL.txt",
                _BUNDLED_FONT_LICENSE,
            )
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


def test_distribution_verifier_rejects_wheel_missing_bundled_font(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path, include_bundled_font=False)
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "must contain exactly one bundled Inter font file" in result.stderr


def test_distribution_verifier_rejects_sdist_missing_bundled_license(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, include_bundled_license=False)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "must contain exactly one bundled Inter OFL notice file" in result.stderr


def test_distribution_verifier_rejects_bundled_assets_outside_sdist_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, bundled_asset_root="other")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "must contain exactly one bundled Inter font file" in result.stderr


def test_distribution_verifier_rejects_corrupted_bundled_font(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path, bundled_font_bytes=b"corrupted font")
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "bundled Inter font SHA-256 mismatch" in result.stderr


def test_distribution_verifier_rejects_payload_modified_after_record_generation(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    _replace_wheel_member(wheel, "frame_compare/__init__.py", '__version__ = "0.1.1"\n')

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "RECORD mismatch for 'frame_compare/__init__.py'" in result.stderr


def test_distribution_verifier_rejects_stale_record_entry(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    record_name = "frame_compare-0.1.0.dist-info/RECORD"
    record = _read_wheel_member(wheel, record_name)
    _replace_wheel_member(wheel, record_name, f"{record}stale.py,sha256=unused,0\n")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "RECORD paths differ" in result.stderr
    assert "stale.py" in result.stderr


def test_distribution_verifier_rejects_incorrect_record_size(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    record_name = "frame_compare-0.1.0.dist-info/RECORD"
    record = _read_wheel_member(wheel, record_name)
    rows = record.splitlines()
    payload_row = next(row for row in rows if row.startswith("frame_compare/__init__.py,"))
    path, digest, size = payload_row.split(",")
    rows[rows.index(payload_row)] = f"{path},{digest},{int(size) + 1}"
    _replace_wheel_member(wheel, record_name, f"{'\n'.join(rows)}\n")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "RECORD mismatch for 'frame_compare/__init__.py'" in result.stderr


def test_distribution_verifier_rejects_missing_record_entry(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    record_name = "frame_compare-0.1.0.dist-info/RECORD"
    rows = _read_wheel_member(wheel, record_name).splitlines()
    rows = [row for row in rows if not row.startswith("frame_compare/__init__.py,")]
    _replace_wheel_member(wheel, record_name, f"{'\n'.join(rows)}\n")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "RECORD paths differ" in result.stderr
    assert "frame_compare/__init__.py" in result.stderr


def test_distribution_verifier_rejects_malformed_record_row(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    record_name = "frame_compare-0.1.0.dist-info/RECORD"
    record = _read_wheel_member(wheel, record_name)
    _replace_wheel_member(wheel, record_name, f"{record}malformed\n")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "RECORD contains a malformed row" in result.stderr


def test_distribution_verifier_rejects_duplicate_record_path(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    record_name = "frame_compare-0.1.0.dist-info/RECORD"
    record = _read_wheel_member(wheel, record_name)
    first_row = record.splitlines()[0]
    _replace_wheel_member(wheel, record_name, f"{record}{first_row}\n")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "RECORD contains duplicate path" in result.stderr


def test_distribution_verifier_rejects_duplicate_payload_member(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    payload_name = "frame_compare/__init__.py"
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(wheel, "a") as archive,
    ):
        archive.writestr(payload_name, archive.read(payload_name))

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "contains duplicate archive members" in result.stderr


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
