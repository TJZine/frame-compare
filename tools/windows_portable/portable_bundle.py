"""Source projection and canonical portable ZIP handling with the host interpreter."""

from __future__ import annotations

import argparse
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from portable_archive import PathIndex, checked_zip, copy_exact, digest_file
from portable_runtime import SITE, Layout, _unpack_archive, git_blob, record_bytes

PREFIX = "frame-compare-portable-win-x64/"


def install_project(repo: Path, root: Path) -> None:
    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, timeout=30).decode().strip()
    )
    project = tomllib.loads(git_blob(repo, commit, Path("pyproject.toml")).decode())["project"]
    layout = Layout(root)
    with tempfile.TemporaryDirectory(prefix="portable-source-") as temporary:
        archive_path = Path(temporary) / "source.zip"
        subprocess.run(
            [
                "git",
                "archive",
                "--format=zip",
                f"--output={archive_path}",
                commit,
                "src/frame_compare",
            ],
            cwd=repo,
            timeout=60,
            check=True,
        )
        _unpack_archive(layout, archive_path, "app", "")
    if "app/src/frame_compare/__init__.py" not in layout.records:
        raise ValueError("Committed application source is missing from portable layout")

    version = project["version"]
    init = (root / "app/src/frame_compare/__init__.py").read_text(encoding="utf-8")
    if (
        project["name"] != "frame-compare"
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?", version)
        or re.findall(r'^__version__\s*=\s*"([^"]+)"', init, re.M) != [version]
    ):
        raise ValueError("Packaged project version does not match committed source")

    entry_points = {"console_scripts": project["scripts"], **project["entry-points"]}
    if entry_points.get("vsview", {}).get("frame-compare-alignment-review") != (
        "frame_compare.vsview.alignment_review_panel"
    ):
        raise ValueError("Project metadata lacks the portable VSView alignment registration")
    lines: list[str] = []
    for group, entries in sorted(entry_points.items()):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", group):
            raise ValueError(f"Invalid project entry point group: {group}")
        lines.append(f"[{group}]")
        for name, target in sorted(entries.items()):
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not re.fullmatch(
                r"[A-Za-z0-9_.]+(?::[A-Za-z0-9_.]+)?", target
            ):
                raise ValueError(f"Invalid project entry point: {name}")
            lines.append(f"{name} = {target}")
        lines.append("")
    dist = f"frame_compare-{version}.dist-info"
    license_text = git_blob(repo, commit, Path("LICENSE"))
    files = {
        f"{dist}/METADATA": (
            f"Metadata-Version: 2.4\nName: frame-compare\nVersion: {version}\n"
            f"Requires-Python: {project['requires-python']}\nLicense-Expression: GPL-3.0-only\n"
            "License-File: licenses/LICENSE\n\n"
        ).encode(),
        f"{dist}/entry_points.txt": ("\n".join(lines) + "\n").encode(),
        f"{dist}/licenses/LICENSE": license_text,
    }
    record = f"{dist}/RECORD"
    files[record] = record_bytes(files, record)
    for path, data in files.items():
        layout.generate(f"{SITE}/{path}", data)
    layout.generate("licenses/frame-compare-LICENSE.txt", license_text)


def bundle_tree(root: Path) -> PathIndex:
    index = PathIndex()
    for member in root.rglob("*"):
        mode = member.lstat().st_mode
        name = member.relative_to(root).as_posix()
        if member.is_junction() or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError(f"Unsafe portable bundle member: {name}")
        index.add(name, directory=stat.S_ISDIR(mode))
    return index


def assert_bundle(archive_path: Path, root: Path) -> None:
    expected = bundle_tree(root)
    actual = PathIndex()
    with checked_zip(archive_path) as archive:
        for entry in archive.infolist():
            if not entry.filename.startswith(PREFIX):
                raise ValueError("Portable archive member outside its canonical root")
            name = entry.filename.removeprefix(PREFIX).removesuffix("/")
            if not name and entry.is_dir():
                continue
            actual.add(name, directory=entry.is_dir())
            if entry.is_dir():
                if name not in expected.directories:
                    raise ValueError(f"Unexpected portable archive directory: {name}")
                continue
            target = root / name
            if name not in expected.files or entry.file_size != target.stat().st_size:
                raise ValueError(f"Unexpected portable member or wrong size: {name}")
            with archive.open(entry) as source:
                if copy_exact(source, entry.file_size) != digest_file(target):
                    raise ValueError(
                        f"Portable member does not match independently derived bytes: {name}"
                    )
    if actual.files != expected.files or actual.directories != expected.directories:
        raise ValueError("Portable archive omits independently derived files or directories")


def write_bundle(root: Path, destination: Path) -> None:
    index = bundle_tree(root)
    with zipfile.ZipFile(
        destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=False
    ) as archive:
        for name in ["", *sorted(index.directories)]:
            info = zipfile.ZipInfo(PREFIX + (name + "/" if name else ""))
            info.create_system = 3
            info.external_attr = stat.S_IFDIR << 16 | 0x10
            archive.writestr(info, b"")
        for name in sorted(index.files):
            info = zipfile.ZipInfo(PREFIX + name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.compress_level = 6
            with (root / name).open("rb") as source, archive.open(info, "w") as target:
                copy_exact(source, (root / name).stat().st_size, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("install-project", "pack", "verify-and-pack"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "install-project":
        if args.repo is None:
            parser.error("install-project requires --repo")
        install_project(args.repo, args.root)
        return
    if args.output is None:
        parser.error("portable packaging requires --output")
    if args.mode == "verify-and-pack":
        if args.candidate is None:
            parser.error("verify-and-pack requires --candidate")
        assert_bundle(args.candidate, args.root)
        write_bundle(args.root, args.output)
        if digest_file(args.candidate) != digest_file(args.output):
            args.output.unlink()
            raise ValueError("Portable ZIP differs from the independently rebuilt canonical bytes")
    else:
        write_bundle(args.root, args.output)


if __name__ == "__main__":
    main()
