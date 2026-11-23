from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest
from tools.windows_portable import portable_bundle as bundle
from tools.windows_portable import portable_runtime as runtime
from tools.windows_portable.portable_archive import checked_zip
from tools.windows_portable.write_bundle_inventory import _archive_inventory

_QT_FFMPEG_FILES = {
    "avcodec-63.dll",
    "avformat-63.dll",
    "avutil-61.dll",
    "swresample-7.dll",
    "swscale-10.dll",
    "plugins/multimedia/ffmpegmediaplugin.dll",
}


def _zip(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return path


def _wheel(path: Path, name: str, version: str, files: dict[str, bytes]) -> Path:
    distribution = f"{name.replace('-', '_')}-{version}.dist-info"
    record = f"{distribution}/RECORD"
    files = files | {
        f"{distribution}/METADATA": f"Name: {name}\nVersion: {version}\n".encode(),
        f"{distribution}/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\n",
    }
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    for filename, data in files.items():
        digest = base64.urlsafe_b64encode(bytes.fromhex(runtime.sha(data))).decode().rstrip("=")
        writer.writerow((filename, f"sha256={digest}", len(data)))
    writer.writerow((record, "", ""))
    return _zip(path, files | {record: text.getvalue().encode()})


@pytest.mark.parametrize(
    ("attack", "error"),
    [
        ("traversal", "Unsafe portable member path"),
        ("ads", "Unsafe portable member path"),
        ("short-name", "Unsafe portable member path"),
        ("device", "Unsafe portable member path"),
        ("case", "Case-colliding"),
        ("file-parent", "file as parent"),
        ("symlink", "Unsafe or duplicate"),
        ("reparse", "Unsafe or duplicate"),
        ("zip-bomb", "expanded size limits"),
        ("unknown-extra", "Unsupported or ambiguous portable ZIP extra"),
    ],
)
def test_portable_zip_rejects_ambiguous_and_expensive_members(
    tmp_path: Path, attack: str, error: str
) -> None:
    candidate = tmp_path / "input.zip"
    with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as archive:
        if attack == "zip-bomb":
            archive.writestr("bomb", b"\0" * (2 * 1024 * 1024))
        elif attack == "case":
            archive.writestr("Python/a", b"file")
            archive.writestr("python/b", b"file")
        elif attack == "file-parent":
            archive.writestr("python", b"file")
            archive.writestr("python/b", b"file")
        elif attack in {"reparse", "symlink", "unknown-extra"}:
            entry = zipfile.ZipInfo("member")
            if attack == "unknown-extra":
                entry.extra = b"\x6e\x75\x00\x00"
            else:
                entry.external_attr = stat.S_IFLNK << 16 if attack == "symlink" else 0x400
            archive.writestr(entry, b"link")
        else:
            name = {
                "traversal": "python/../foreign",
                "ads": "python/file:stream",
                "short-name": "PROGRA~1/file",
                "device": "python/CON.dll",
            }[attack]
            archive.writestr(name, b"file")
    with pytest.raises(ValueError, match=error), checked_zip(candidate):
        pytest.fail("unsafe archive was accepted")


def test_portable_zip_rejects_extra_deflate_output_behind_a_valid_prefix(tmp_path: Path) -> None:
    candidate = _zip(tmp_path / "input.zip", {"payload": b"XY"})
    raw = bytearray(candidate.read_bytes())
    central = raw.index(b"PK\x01\x02")
    import zlib

    # Make the local header and directory agree on a size and CRC for just
    # the first byte. The stream still expands to both bytes.
    for crc_offset, size_offset in ((14, 22), (central + 16, central + 24)):
        struct.pack_into("<I", raw, crc_offset, zlib.crc32(b"X"))
        struct.pack_into("<I", raw, size_offset, 1)
    candidate.write_bytes(raw)
    with pytest.raises(ValueError, match="exceeds declared size"), checked_zip(candidate):
        pytest.fail("a truncated view of the payload was accepted")


def test_wheel_staging_refuses_unexpected_install_scheme(tmp_path: Path) -> None:
    wheel = _wheel(
        tmp_path / "sample-1-py3-none-any.whl",
        "sample",
        "1",
        {"sample-1.data/scripts/evil.cmd": b"payload"},
    )
    pin = runtime.Pin(
        f"https://files.pythonhosted.org/{wheel.name}",
        wheel.stat().st_size,
        runtime.sha(wheel.read_bytes()),
    )
    with pytest.raises(ValueError, match="Unsupported portable wheel path"):
        runtime._stage_wheel(wheel, pin, tmp_path / "staged")


def _anitopy_archive(path: Path, *, attack: str | None = None) -> None:
    base = "anitopy-2.1.1"
    with tarfile.open(path, "w:gz") as archive:
        for directory in (base, f"{base}/anitopy", f"{base}/anitopy.egg-info"):
            entry = tarfile.TarInfo(directory)
            entry.type = tarfile.DIRTYPE
            archive.addfile(entry)
        files = {
            f"anitopy/{name}.py": b"raise RuntimeError('must never execute')"
            for name in (
                "__init__",
                "anitopy",
                "element",
                "keyword",
                "parser",
                "parser_helper",
                "parser_number",
                "token",
                "tokenizer",
            )
        }
        files |= dict.fromkeys(
            (
                "LICENSE",
                "MANIFEST.in",
                "PKG-INFO",
                "README.rst",
                "setup.cfg",
                "anitopy.egg-info/PKG-INFO",
                "anitopy.egg-info/SOURCES.txt",
                "anitopy.egg-info/dependency_links.txt",
                "anitopy.egg-info/top_level.txt",
                "setup.py",
            ),
            b"raise RuntimeError('must never execute')",
        )
        for relative, contents in files.items():
            entry = tarfile.TarInfo(f"{base}/{relative}")
            entry.size = len(contents)
            archive.addfile(entry, io.BytesIO(contents))
        if attack:
            entry = tarfile.TarInfo(f"{base}/anitopy/linked.py")
            entry.type = tarfile.SYMTYPE
            entry.linkname = "../../outside"
            archive.addfile(entry)


def test_anitopy_wheel_is_deterministic_and_contains_only_runtime_files(tmp_path: Path) -> None:
    source = tmp_path / "source.tar.gz"
    _anitopy_archive(source)
    wheel = runtime._convert_anitopy(source, tmp_path)
    again = tmp_path / "again"
    again.mkdir()
    assert wheel.read_bytes() == runtime._convert_anitopy(source, again).read_bytes()
    with checked_zip(wheel) as archive:
        files = archive.namelist()
        assert len(files) == 13
        assert "anitopy/__init__.py" in files
        assert all(not name.endswith(("setup.py", "setup.cfg")) for name in files)
        assert "anitopy-2.1.1.dist-info/licenses/LICENSE" in files


@pytest.mark.parametrize(
    ("attack", "message"), [("link", "Unsafe"), ("bomb", "oversized anitopy source archive")]
)
def test_anitopy_rejects_special_files_and_gzip_bombs(
    tmp_path: Path, attack: str, message: str
) -> None:
    source = tmp_path / "source.tar.gz"
    if attack == "link":
        _anitopy_archive(source, attack=attack)
    else:
        source.write_bytes(gzip.compress(b"\0" * (256 * 1024 + 1)))
    with pytest.raises(ValueError, match=message):
        runtime._convert_anitopy(source, tmp_path)


def _seed(path: Path, cache: Path) -> runtime.Pin:
    digest = runtime.sha(path.read_bytes())
    pin = runtime.Pin(f"https://files.pythonhosted.org/{path.name}", path.stat().st_size, digest)
    (cache / (digest + "-" + path.name)).write_bytes(path.read_bytes())
    return pin


def _lock_package(name: str, version: str, pin: runtime.Pin) -> str:
    return (
        f'[[package]]\nname = "{name}"\nversion = "{version}"\n'
        'source = {registry = "https://pypi.org/simple"}\n'
        f'wheels = [{{url = "{pin.url}", size = {pin.bytes}, hash = "sha256:{pin.sha256}"}}]\n'
    )


@pytest.mark.parametrize("manifest_version", [2, 3], ids=["historical", "current"])
def test_portable_assembly_is_inert_and_safely_packaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest_version: int
) -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv is required to exercise the offline wheel install")
    cache = tmp_path / "pins"
    cache.mkdir()
    vs_wheel = _wheel(
        tmp_path / "vapoursynth-81-cp312-abi3-win_amd64.whl",
        "vapoursynth",
        "81",
        {"vapoursynth/libvapoursynth.dll": b"native"},
    )
    lsmas = _wheel(
        tmp_path / "vapoursynth_lsmas-1-py3-none-win_amd64.whl",
        "vapoursynth-lsmas",
        "1",
        {"vapoursynth/plugins/LSMASHSource.dll": b"native"},
    )
    qt = _wheel(
        tmp_path / "pyside6_webengine-1-py3-none-win_amd64.whl",
        "pyside6-webengine",
        "1",
        {
            "PySide6/QtWebEngine.dll": b"trim",
            "PySide6/__pycache__/example.cpython-310.pyc": b"old",
            "pyside6_webengine-1.dist-info/licenses/LICENSE": b"notice",
        },
    )
    qt_addons = _wheel(
        tmp_path / "pyside6_addons-1-py3-none-win_amd64.whl",
        "pyside6-addons",
        "1",
        {
            **{f"PySide6/{name}": b"excluded Qt FFmpeg file" for name in _QT_FFMPEG_FILES},
            "PySide6/QtMultimedia.pyd": b"retained binding",
            "PySide6/Qt6Multimedia.dll": b"retained Qt library",
            "PySide6/plugins/multimedia/windowsmediaplugin.dll": b"retained Windows plugin",
        },
    )
    marker = tmp_path / "executed"
    demo = _wheel(
        tmp_path / "sample-1-py3-none-any.whl",
        "sample",
        "1",
        {
            "sample/__init__.py": f"from pathlib import Path\nPath({str(marker)!r}).touch()\n".encode(),
            "sample.pth": b"import sample",
            "sample-1.dist-info/entry_points.txt": b"[console_scripts]\nsample = sample:main\n",
        },
    )
    manifest_records = []
    for name, destination, files in (
        ("ffmpeg", "ffmpeg", {"LICENSE.txt": b"license", "bin/ffmpeg.exe": b"never execute"}),
        (
            "python",
            "python",
            {
                "LICENSE.txt": b"license",
                "python315.zip": b"stdlib",
                "python315._pth": b"original",
                "python.exe": b"never execute",
                "_sqlite3.pyd": b"optional extension",
                "sqlite3.dll": b"optional native library",
                "_ssl.pyd": b"retained extension",
            },
        ),
        ("vs", "vs/core", {f"wheel/{vs_wheel.name}": vs_wheel.read_bytes()}),
    ):
        pin = _seed(_zip(tmp_path / f"{name}.zip", files), cache)
        manifest_records.append(
            {
                "id": name,
                "url": pin.url,
                "bytes": pin.bytes,
                "sha256": pin.sha256,
                "install": {"type": "extract", "destination": destination},
            }
        )
    packages = [
        ("vapoursynth", "81", vs_wheel),
        ("vapoursynth-lsmas", "1", lsmas),
        ("pyside6-webengine", "1", qt),
        ("pyside6-addons", "1", qt_addons),
        ("sample", "1", demo),
    ]
    lock = "".join(
        _lock_package(name, version, _seed(path, cache)) for name, version, path in packages
    ).encode()
    requirements = b"".join(
        f"{name}=={version} \\\n".encode()
        for name, version, _ in packages
        if name != "vapoursynth-lsmas"
    )
    source = tmp_path / "source"
    live_manifest = source / runtime.MANIFEST
    live_notice = live_manifest.parent / "licenses" / "TEST.txt"
    live_notice.parent.mkdir(parents=True)
    older_notice = b"selected notice\r\n"
    live_notice.write_bytes(older_notice)
    for record in manifest_records:
        record["license"] = {
            "files": [{"path": "licenses/TEST.txt", "sha256": runtime.sha(older_notice)}]
        }
    manifest_data = {
        "manifest_version": manifest_version,
        "bundle": {"python_version": "3.15.2"},
        "artifacts": manifest_records,
    }
    manifest = json.dumps(manifest_data).encode()
    live_manifest.write_bytes(manifest)
    (source / "uv.lock").write_bytes(lock)

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(source), *args], timeout=30, text=True
        ).strip()

    def commit(message: str) -> str:
        git("add", ".")
        git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            message,
        )
        return git("rev-parse", "HEAD")

    git("init", "-q")
    git("config", "core.autocrlf", "false")
    selected = commit("selected runtime")
    newer_notice = b"newer notice\n"
    live_notice.write_bytes(newer_notice)
    custom_manifest = manifest.replace(
        runtime.sha(older_notice).encode(), runtime.sha(newer_notice).encode()
    )
    newer_manifest = json.loads(custom_manifest)
    if manifest_version == 2:
        # The live checkout moves on to v3 while replay still takes v2 from Git.
        newer_manifest["manifest_version"] = 3
    live_manifest.write_text(json.dumps(newer_manifest), encoding="utf-8")
    assert commit("newer runtime") != selected
    custom_manifest_path = tmp_path / "custom-manifest.json"
    custom_manifest_path.write_bytes(custom_manifest)

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    def export_requirements(repo: Path, commit: str, output: Path) -> bytes:
        assert repo == source
        assert commit == selected
        output.write_bytes(requirements)
        return requirements

    monkeypatch.setattr(runtime, "export", export_requirements)

    def run_runtime(mode: str, *args: str) -> None:
        monkeypatch.setattr(
            sys,
            "argv",
            ["portable_runtime.py", mode, "--repo", str(source), "--commit-sha", selected, *args],
        )
        runtime.main()

    run_runtime("snapshot-manifest", "--output", str(snapshot))
    assert (snapshot / runtime.MANIFEST.name).read_bytes() == manifest
    assert (snapshot / "licenses" / "TEST.txt").read_bytes() == older_notice
    monkeypatch.setattr(runtime, "TRIM", (1, 4))
    output = tmp_path / "runtime"
    custom = tmp_path / "custom"
    for destination, manifest_input in (
        (output, snapshot / runtime.MANIFEST.name),
        (custom, custom_manifest_path),
    ):
        destination.mkdir()
        run_runtime(
            "assemble",
            "--manifest",
            str(manifest_input),
            "--cache",
            str(cache),
            "--output",
            str(destination),
        )
        assert (destination / "manifest.json").read_bytes() == manifest_input.read_bytes()
    assert (output / "manifest.json").read_bytes() == manifest
    assert (custom / "manifest.json").read_bytes() == custom_manifest

    site = output / runtime.SITE
    assert not marker.exists()
    assert (site / "sample/__init__.py").is_file()
    assert not (site / "Scripts").exists()
    assert not (site / "bin").exists()
    assert not (site / ".lock").exists()
    assert not list(site.rglob("direct_url.json"))
    assert not list(site.rglob("*.pyc"))
    assert not (site / "PySide6/QtWebEngine.dll").exists()
    assert "QtWebEngine.dll" not in (site / "pyside6_webengine-1.dist-info/RECORD").read_text()
    record_path = "pyside6_addons-1.dist-info/RECORD"
    with zipfile.ZipFile(qt_addons) as original_wheel:
        original_record = {
            row[0]: row[1:]
            for row in csv.reader(original_wheel.read(record_path).decode().splitlines())
        }
    for projection in (output, custom):
        addons_record = {
            row[0]: row[1:]
            for row in csv.reader(
                (projection / runtime.SITE / record_path).read_text().splitlines()
            )
        }
        for name in _QT_FFMPEG_FILES:
            relative = f"PySide6/{name}"
            projected = projection / runtime.SITE / relative
            if manifest_version == 3:
                assert not projected.exists()
                assert relative not in addons_record
            else:
                assert projected.read_bytes() == b"excluded Qt FFmpeg file"
                assert addons_record[relative] == original_record[relative]
        for relative in (
            "PySide6/QtMultimedia.pyd",
            "PySide6/Qt6Multimedia.dll",
            "PySide6/plugins/multimedia/windowsmediaplugin.dll",
        ):
            assert addons_record[relative] == original_record[relative]
    assert (output / "python/python315._pth").read_bytes() == runtime.embedded_search_path("315")
    sqlite_files = {
        "python/_sqlite3.pyd": b"optional extension",
        "python/sqlite3.dll": b"optional native library",
    }
    for projection in (output, custom):
        for name, data in sqlite_files.items():
            if manifest_version == 3:
                assert not (projection / name).exists()
            else:
                assert (projection / name).read_bytes() == data
    assert (output / "python/_ssl.pyd").read_bytes() == b"retained extension"
    assert (output / "licenses/python-LICENSE.txt").read_bytes() == b"license"
    assert (
        output / "licenses/python/pyside6_webengine-1.dist-info__licenses/LICENSE"
    ).read_bytes() == b"notice"

    inventory = output / "bundle_inventory.json"
    inventory.write_text(json.dumps({"archive": _archive_inventory(output, inventory)}))
    archive_path = tmp_path / "portable.zip"
    bundle.write_bundle(output, archive_path)
    with checked_zip(archive_path) as archive:
        assert archive.read(bundle.PREFIX + "manifest.json") == manifest
        assert archive.read(bundle.PREFIX + "python/python315._pth") == (
            runtime.embedded_search_path("315")
        )
        assert archive.read(bundle.PREFIX + "licenses/python-LICENSE.txt") == b"license"
        assert archive.read(bundle.PREFIX + "python/_ssl.pyd") == b"retained extension"
        for name, data in sqlite_files.items():
            member = bundle.PREFIX + name
            if manifest_version == 3:
                assert member not in archive.namelist()
            else:
                assert archive.read(member) == data
        pyside_prefix = bundle.PREFIX + "app/site-packages/PySide6/"
        for name in _QT_FFMPEG_FILES:
            member = pyside_prefix + name
            if manifest_version == 3:
                assert member not in archive.namelist()
            else:
                assert archive.read(member) == b"excluded Qt FFmpeg file"
        assert archive.read(pyside_prefix + "QtMultimedia.pyd") == b"retained binding"
        assert archive.read(pyside_prefix + "Qt6Multimedia.dll") == b"retained Qt library"
        assert archive.read(pyside_prefix + "plugins/multimedia/windowsmediaplugin.dll") == (
            b"retained Windows plugin"
        )
        assert archive.read(bundle.PREFIX + "ffmpeg/bin/ffmpeg.exe") == b"never execute"
        assert bundle.PREFIX in archive.namelist()

    pinned_demo = _seed(demo, cache)
    (cache / (pinned_demo.sha256 + "-" + demo.name)).write_bytes(b"wrong")
    with pytest.raises(ValueError, match="Cached size or SHA-256 mismatch"):
        runtime.assemble(tmp_path / "tampered", manifest, lock, requirements, cache)


@pytest.mark.parametrize("version", [1, "3"])
def test_invalid_manifest_version_fails_before_runtime_inputs(
    tmp_path: Path, version: int | str
) -> None:
    manifest = json.dumps({"manifest_version": version, "artifacts": []}).encode()
    with pytest.raises(ValueError, match="Unsupported portable manifest version"):
        runtime.assemble(tmp_path / "out", manifest, b"", b"", tmp_path / "cache")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("drift", "expected"),
    [
        ("unlisted", r"unlisted=\['smoke-output\.txt'\]"),
        ("missing", r"missing=\['launcher\.ps1'\]"),
        ("changed-contents", r"Bundle file contents differ from inventory: launcher\.ps1"),
        ("wrong-byte-count", r"Bundle file contents differ from inventory: launcher\.ps1"),
        ("extra-directory", r"Bundle directories differ from inventory: unlisted=\['empty'\]"),
        ("missing-directories", r"Bundle inventory is missing archive\.directories"),
    ],
)
def test_portable_pack_rejects_inventory_drift(tmp_path: Path, drift: str, expected: str) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    listed_file = root / "launcher.ps1"
    listed_file.write_bytes(b"launcher")
    inventory = root / "bundle_inventory.json"
    archive_inventory = _archive_inventory(root, inventory)
    if drift == "missing-directories":
        del archive_inventory["directories"]
    inventory.write_text(json.dumps({"archive": archive_inventory}))
    if drift == "unlisted":
        (root / "smoke-output.txt").write_text("unexpected")
    elif drift == "missing":
        listed_file.unlink()
    elif drift == "changed-contents":
        listed_file.write_bytes(b"LAUNCHER")
    elif drift == "wrong-byte-count":
        recorded = json.loads(inventory.read_text())
        recorded["archive"]["files"][0]["bytes"] += 1
        inventory.write_text(json.dumps(recorded))
    elif drift == "extra-directory":
        (root / "empty").mkdir()
    destination = tmp_path / "output.zip"
    with pytest.raises(ValueError, match=expected):
        bundle.write_bundle(root, destination)
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == [root]


def test_portable_pack_preserves_competing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    launcher = b"launcher"
    (root / "launcher.ps1").write_bytes(launcher)
    inventory = root / "bundle_inventory.json"
    inventory.write_text(json.dumps({"archive": _archive_inventory(root, inventory)}))
    destination = tmp_path / "output.zip"
    competing_bytes = b"another writer's output"

    def occupy_destination(temporary: Path) -> None:
        with checked_zip(temporary) as archive:
            assert archive.read(bundle.PREFIX + "launcher.ps1") == launcher
        with destination.open("xb") as competing:
            competing.write(competing_bytes)

    if sys.platform == "win32":
        rename = Path.rename

        def compete_at_rename(temporary: Path, target: Path) -> Path:
            occupy_destination(temporary)
            return rename(temporary, target)

        monkeypatch.setattr(Path, "rename", compete_at_rename)
    else:
        hardlink_to = Path.hardlink_to

        def compete_at_hardlink(target: Path, temporary: Path) -> None:
            occupy_destination(temporary)
            hardlink_to(target, temporary)

        monkeypatch.setattr(Path, "hardlink_to", compete_at_hardlink)

    with pytest.raises(FileExistsError):
        bundle.write_bundle(root, destination)
    assert destination.read_bytes() == competing_bytes
    assert set(tmp_path.iterdir()) == {root, destination}
