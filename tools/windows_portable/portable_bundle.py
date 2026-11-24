"""Source projection and canonical portable ZIP handling with the host interpreter."""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from portable_archive import PathIndex, copy_exact
from portable_runtime import SITE, Layout, _unpack_archive, git_blob, record_bytes

PREFIX = "frame-compare-portable-win-x64/"


def install_project(repo: Path, root: Path, commit: str) -> None:
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


def write_bundle(root: Path, destination: Path) -> None:
    index = bundle_tree(root)
    inventory_name = "bundle_inventory.json"
    inventory_bytes = (root / inventory_name).read_bytes()
    inventory = json.loads(inventory_bytes.decode("utf-8"))["archive"]
    records = {entry["path"]: entry for entry in inventory["files"]}
    listed = set(records)
    actual = set(index.files) - {inventory_name}
    if listed != actual:
        raise ValueError(
            f"Bundle files differ from inventory: unlisted={sorted(actual - listed)}, "
            f"missing={sorted(listed - actual)}"
        )
    if "directories" not in inventory:
        raise ValueError("Bundle inventory is missing archive.directories")
    directories = set(inventory["directories"])
    if directories != index.directories:
        raise ValueError(
            "Bundle directories differ from inventory: "
            f"unlisted={sorted(index.directories - directories)}, "
            f"missing={sorted(directories - index.directories)}"
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            with zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=False
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
                    if name == inventory_name:
                        archive.writestr(info, inventory_bytes)
                        continue
                    member = root / name
                    with member.open("rb") as source, archive.open(info, "w") as target:
                        digest = copy_exact(source, member.stat().st_size, target)
                    record = records[name]
                    if info.file_size != record["bytes"] or digest != record["sha256"]:
                        raise ValueError(f"Bundle file contents differ from inventory: {name}")
        if sys.platform == "win32":
            temporary_path.rename(destination)
        else:
            # POSIX rename replaces an existing destination. A hard link fails if it exists.
            destination.hardlink_to(temporary_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("install-project", "pack"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--commit-sha")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "install-project":
        if args.repo is None:
            parser.error("install-project requires --repo")
        if args.commit_sha is None or not re.fullmatch(r"[a-f0-9]{40}", args.commit_sha):
            parser.error("--commit-sha must be a complete lowercase 40-character commit SHA")
        install_project(args.repo, args.root, args.commit_sha)
        return
    if args.output is None:
        parser.error("portable packaging requires --output")
    write_bundle(args.root, args.output)


if __name__ == "__main__":
    main()
