from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

METADATA = """\
Metadata-Version: 2.4
Name: frame-compare
Version: 0.1.0
License-Expression: GPL-3.0-only
"""


def _write_wheel(dist_dir: Path) -> None:
    wheel = dist_dir / "frame_compare-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("frame_compare/__init__.py", '__version__ = "0.1.0"\n')
        archive.writestr("frame_compare-0.1.0.dist-info/METADATA", METADATA)
        archive.writestr("frame_compare-0.1.0.dist-info/licenses/LICENSE", "GPL text")


def _add_tar_text(archive: tarfile.TarFile, name: str, value: str) -> None:
    data = value.encode()
    member = tarfile.TarInfo(name)
    member.size = len(data)
    archive.addfile(member, io.BytesIO(data))


def _write_sdist(dist_dir: Path, *, extra_name: str | None = None) -> None:
    sdist = dist_dir / "frame_compare-0.1.0.tar.gz"
    root = "frame_compare-0.1.0"
    with tarfile.open(sdist, "w:gz") as archive:
        _add_tar_text(archive, f"{root}/PKG-INFO", METADATA)
        _add_tar_text(archive, f"{root}/LICENSE", "GPL text")
        _add_tar_text(archive, f"{root}/README.md", "# Frame Compare")
        _add_tar_text(archive, f"{root}/pyproject.toml", "[project]")
        _add_tar_text(archive, f"{root}/src/frame_compare/__init__.py", "")
        if extra_name is not None:
            _add_tar_text(archive, f"{root}/{extra_name}", "unexpected")


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
