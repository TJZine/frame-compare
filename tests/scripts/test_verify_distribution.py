from __future__ import annotations

import base64
import hashlib
import io
import stat
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


_PACKAGE_SOURCE = _FONT_ASSET_DIR.parents[1]
_REPORT_ASSET_DIR = _PACKAGE_SOURCE / "services/report/assets"
_PACKAGE_FILES = {
    path.relative_to(_PACKAGE_SOURCE.parent).as_posix(): path.read_bytes()
    for path in [*_REPORT_ASSET_DIR.iterdir(), _PACKAGE_SOURCE / "py.typed"]
    if path.is_file()
}


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
    omit_package_file: str | None = None,
    symlink_package_file: str | None = None,
) -> None:
    wheel = dist_dir / "frame_compare-0.1.0-py3-none-any.whl"
    contents: dict[str, bytes] = {
        **{name: data for name, data in _PACKAGE_FILES.items() if name != omit_package_file},
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
            if name == symlink_package_file:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, value)
            else:
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
    extra_path: str | None = None,
    extra_member_type: bytes | None = None,
    include_bundled_font: bool = True,
    include_bundled_license: bool = True,
    bundled_font_bytes: bytes | None = None,
    bundled_asset_root: str | None = None,
    readme_case: str = "regular",
    omit_package_file: str | None = None,
    explicit_root: bool = True,
) -> None:
    sdist = dist_dir / "frame_compare-0.1.0.tar.gz"
    root = "frame_compare-0.1.0"
    asset_root = root if bundled_asset_root is None else bundled_asset_root
    with tarfile.open(sdist, "w:gz") as archive:
        if explicit_root:
            root_directory = tarfile.TarInfo(root)
            root_directory.type = tarfile.DIRTYPE
            archive.addfile(root_directory)
        _add_tar_text(archive, f"{root}/PKG-INFO", METADATA)
        _add_tar_text(archive, f"{root}/LICENSE", "GPL text")
        if readme_case == "outside":
            _add_tar_text(archive, "elsewhere/README.md", "# Frame Compare")
        elif readme_case == "directory":
            directory = tarfile.TarInfo(f"{root}/README.md")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
        else:
            _add_tar_text(archive, f"{root}/README.md", "# Frame Compare")
            if readme_case == "duplicate":
                _add_tar_text(archive, f"{root}/README.md", "second copy")
        for name, data in _PACKAGE_FILES.items():
            if name != omit_package_file:
                _add_tar_bytes(archive, f"{root}/src/{name}", data)
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
        if extra_path is not None:
            _add_tar_text(archive, extra_path, "unexpected")
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


@pytest.mark.parametrize("explicit_root", [True, False], ids=["explicit-root", "implicit-root"])
def test_distribution_verifier_accepts_expected_artifacts(
    tmp_path: Path, repo_root: Path, explicit_root: bool
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, explicit_root=explicit_root)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode == 0
    assert "distribution verification passed: version=0.1.0" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    "case, diagnostic",
    [
        ("missing-font", "must contain exactly one bundled Inter font file"),
        ("missing-license", "must contain exactly one bundled Inter OFL notice file"),
        ("corrupt-font", "bundled Inter font SHA-256 mismatch"),
    ],
)
def test_distribution_verifier_rejects_invalid_bundled_assets(
    tmp_path: Path, repo_root: Path, case: str, diagnostic: str
) -> None:
    _write_wheel(
        tmp_path,
        include_bundled_font=case != "missing-font",
        bundled_font_bytes=b"corrupted font" if case == "corrupt-font" else None,
    )
    _write_sdist(tmp_path, include_bundled_license=case != "missing-license")
    result = _run_verifier(repo_root, tmp_path)
    assert result.returncode != 0
    assert diagnostic in result.stderr


def test_distribution_verifier_rejects_bundled_assets_outside_sdist_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, bundled_asset_root="other")

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "must contain exactly one bundled Inter font file" in result.stderr


def test_distribution_verifier_rejects_truncated_bundled_license(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    _replace_wheel_member(
        wheel,
        "frame_compare/assets/fonts/Inter-OFL.txt",
        "SIL OPEN FONT LICENSE Version 1.1\n",
    )

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert "bundled Inter OFL notice is invalid" in result.stderr


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


@pytest.mark.parametrize(
    "case, diagnostic",
    [
        ("stale", "RECORD paths differ"),
        ("malformed", "RECORD contains a malformed row"),
        ("duplicate", "RECORD contains duplicate path"),
    ],
)
def test_distribution_verifier_rejects_invalid_record_rows(
    tmp_path: Path, repo_root: Path, case: str, diagnostic: str
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path)
    wheel = tmp_path / "frame_compare-0.1.0-py3-none-any.whl"
    record_name = "frame_compare-0.1.0.dist-info/RECORD"
    record = _read_wheel_member(wheel, record_name)
    row = {
        "stale": "stale.py,sha256=unused,0",
        "malformed": "malformed",
        "duplicate": record.splitlines()[0],
    }[case]
    _replace_wheel_member(wheel, record_name, f"{record}{row}\n")
    result = _run_verifier(repo_root, tmp_path)
    assert result.returncode != 0
    assert diagnostic in result.stderr
    if case == "stale":
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
    _write_sdist(tmp_path, extra_path="frame_compare-0.1.0/.venv/bin/python")

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


@pytest.mark.parametrize("member", ["WHEEL", "RECORD", "LICENSE", "nested"])
def test_distribution_verifier_rejects_invalid_dist_info_locations(
    tmp_path: Path, repo_root: Path, member: str
) -> None:
    dist_info = "frame_compare-0.1.0.dist-info"
    metadata_root = f"nested/{dist_info}" if member == "nested" else dist_info
    _write_wheel(
        tmp_path,
        metadata_dist_info=metadata_root,
        wheel_dist_info="other-0.1.0.dist-info" if member == "WHEEL" else metadata_root,
        record_dist_info="other-0.1.0.dist-info" if member == "RECORD" else metadata_root,
        license_dist_info="other-0.1.0.dist-info" if member == "LICENSE" else metadata_root,
    )
    _write_sdist(tmp_path)
    result = _run_verifier(repo_root, tmp_path)
    assert result.returncode != 0
    diagnostic = (
        "dist-info directory must be at the archive root"
        if member == "nested"
        else f"{member} is not in the METADATA dist-info directory"
    )
    assert diagnostic in result.stderr


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


@pytest.mark.parametrize("case", ["outside", "directory", "duplicate"])
def test_distribution_verifier_requires_one_regular_readme_under_sdist_root(
    tmp_path: Path, repo_root: Path, case: str
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, readme_case=case)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert (
        "must contain exactly one README.md file at 'frame_compare-0.1.0/README.md'"
        in result.stderr
    )


@pytest.mark.parametrize(
    "path",
    [
        "frame_compare-0.1.0",
        "frame_compare-0.1.0/src/frame_compare/services/report/assets",
    ],
    ids=["package-root", "report-assets"],
)
def test_distribution_verifier_rejects_file_as_sdist_ancestor(
    tmp_path: Path, repo_root: Path, path: str
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, extra_path=path, explicit_root=False)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert f"non-directory ancestor {path!r}" in result.stderr


@pytest.mark.parametrize(
    ("path", "diagnostic"),
    [
        ("frame_compare-0.1.0/nested/.handoff/local.txt", "contains local or sensitive state"),
        ("frame_compare-0.1.0/nested/.codex/local.txt", "contains local or sensitive state"),
        ("frame_compare-0.1.0/nested/.claude/local.txt", "contains local or sensitive state"),
        ("C:local.txt", "contains an unsafe path"),
    ],
    ids=["handoff", "codex", "claude", "drive-qualified"],
)
def test_distribution_verifier_rejects_extra_local_state_and_drive_paths(
    tmp_path: Path, repo_root: Path, path: str, diagnostic: str
) -> None:
    _write_wheel(tmp_path)
    _write_sdist(tmp_path, extra_path=path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert diagnostic in result.stderr
    assert path in result.stderr


@pytest.mark.parametrize("artifact", ["wheel", "sdist"])
@pytest.mark.parametrize(
    "package_file",
    ["frame_compare/services/report/assets/viewport.js", "frame_compare/py.typed"],
    ids=["viewport-js", "py-typed"],
)
def test_distribution_verifier_rejects_missing_package_files(
    tmp_path: Path, repo_root: Path, artifact: str, package_file: str
) -> None:
    _write_wheel(tmp_path, omit_package_file=package_file if artifact == "wheel" else None)
    _write_sdist(tmp_path, omit_package_file=package_file if artifact == "sdist" else None)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert package_file in result.stderr


def test_distribution_verifier_rejects_wheel_asset_symlink(tmp_path: Path, repo_root: Path) -> None:
    asset = "frame_compare/services/report/assets/viewport.js"
    _write_wheel(tmp_path, symlink_package_file=asset)
    _write_sdist(tmp_path)

    result = _run_verifier(repo_root, tmp_path)

    assert result.returncode != 0
    assert f"must contain a regular file at {asset!r}" in result.stderr
