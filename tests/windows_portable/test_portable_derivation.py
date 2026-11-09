from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import stat
import struct
import tarfile
import zipfile
from pathlib import Path

import pytest
from tools.windows_portable import portable_bundle as bundle
from tools.windows_portable import portable_runtime as runtime
from tools.windows_portable.portable_archive import checked_zip


def _zip(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return path


def _wheel(
    path: Path, name: str, version: str, files: dict[str, bytes], *, forged: str | None = None
) -> Path:
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
        writer.writerow((forged or filename, f"sha256={digest}", len(data)))
        forged = None
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


@pytest.mark.parametrize(
    ("file", "forged", "error"),
    [
        ("sample/normal.py", "../escape", "Unsafe portable member path"),
        ("sample-1.data/purelib/evil.py", None, "Unsupported wheel member"),
        ("sample-1.data/scripts/evil.cmd", None, "Unsupported wheel member"),
    ],
)
def test_wheel_rejects_unreviewed_record_and_data_paths(
    tmp_path: Path, file: str, forged: str | None, error: str
) -> None:
    root = runtime.Layout(tmp_path / "output")
    path = _wheel(tmp_path / "input.whl", "sample", "1", {file: b"payload"}, forged=forged)
    with pytest.raises(ValueError, match=error):
        runtime._install_wheel(root, path, "sample-1-py3-none-any.whl", "sample", "1")
    assert not (tmp_path / "escape").exists()


def test_identical_qt_shared_files_are_the_only_allowed_wheel_collisions(tmp_path: Path) -> None:
    root = runtime.Layout(tmp_path)
    filename = f"{runtime.SITE}/PySide6/__init__.py"
    root.generate(filename, b"first", "pyside6")
    root.generate(filename, b"first", "pyside6-addons")
    with pytest.raises(ValueError, match="different bytes"):
        root.generate(filename, b"other", "pyside6-essentials")
    with pytest.raises(ValueError, match="multiple owners"):
        root.generate(filename, b"first", "example")
    with pytest.raises(ValueError, match="Case-colliding"):
        root.generate(filename.replace("PySide6", "pyside6"), b"first", "pyside6-pdf")
    assert (tmp_path / filename).read_bytes() == b"first"


def test_webengine_projection_authenticates_the_trimmed_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = runtime.Layout(tmp_path)
    qt = f"{runtime.SITE}/PySide6"
    root.generate(f"{qt}/QtWebEngineCore.dll", b"unused", "pyside6-webengine")
    root.generate(f"{qt}/resources/icudtl.dat", b"unused", "pyside6-webengine")
    root.generate(f"{qt}/Qt6Core.dll", b"keep", "pyside6-essentials")
    with pytest.raises(ValueError, match="Unexpected Qt WebEngine deployment surface"):
        runtime._trim_webengine(root)
    monkeypatch.setattr(runtime, "TRIM", (2, 12))
    runtime._trim_webengine(root)
    assert root.paths.files == {f"{qt}/Qt6Core.dll"}


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


def test_only_static_anitopy_runtime_files_are_projected(tmp_path: Path) -> None:
    source = tmp_path / "source.tar.gz"
    _anitopy_archive(source)
    layout = runtime.Layout(tmp_path / "out")
    runtime._install_anitopy(layout, source, "anitopy-2.1.1.tar.gz")
    assert len(layout.records) == 12
    assert f"{runtime.SITE}/anitopy/__init__.py" in layout.records
    assert all(not name.endswith(("setup.py", "setup.cfg")) for name in layout.records)
    assert f"{runtime.SITE}/anitopy-2.1.1.dist-info/licenses/LICENSE" in layout.records


@pytest.mark.parametrize(
    ("attack", "message"), [("link", "Unsafe"), ("bomb", "expanded size limit")]
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
        runtime._install_anitopy(runtime.Layout(tmp_path / "out"), source, "anitopy-2.1.1.tar.gz")


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


def test_catalog_is_derived_from_pins_and_cannot_approve_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
            "pyside6_webengine-1.dist-info/licenses/LICENSE": b"notice",
        },
    )
    demo = _wheel(
        tmp_path / "sample-1-py3-none-any.whl",
        "sample",
        "1",
        {
            "sample/__init__.py": b"raise RuntimeError('must never execute')",
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
                "python313.zip": b"stdlib",
                "python313._pth": b"original",
                "python.exe": b"never execute",
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
    manifest = runtime.json_bytes({"artifacts": manifest_records})
    monkeypatch.setattr(runtime, "TRIM", (1, 4))
    output = tmp_path / "runtime"
    first = runtime.derive(output, manifest, lock, requirements, cache)
    assert first == runtime.derive(tmp_path / "again", manifest, lock, requirements, cache)
    assert (output / "python/python313._pth").read_bytes() == runtime.EMBEDDED_SEARCH_PATH
    assert (output / f"{runtime.SITE}/Scripts/sample.cmd").is_file()
    assert (
        output / "licenses/python/pyside6_webengine-1.dist-info__licenses/LICENSE"
    ).read_bytes() == b"notice"

    records = json.loads(first)
    assert records["manifest_sha256"] == runtime.sha(manifest)
    assert records["uv_lock_sha256"] == runtime.sha(lock)
    assert records["provenance"]["packages"]["vapoursynth"]["sha256"] == runtime.sha(
        vs_wheel.read_bytes()
    )
    approved = first
    monkeypatch.setattr(runtime, "git_blob", lambda *_args: approved)
    runtime._assert_catalog(first, tmp_path, "fixture")
    for change in ("manifest_sha256", "uv_lock_sha256", "files", "policy"):
        forged = records | {change: []}
        approved = runtime.json_bytes(forged)
        with pytest.raises(ValueError, match="stale or differs"):
            runtime._assert_catalog(first, tmp_path, "fixture")
    # The producer cannot install a new native executable by refreshing its own
    # hash and inventory, or by passing its forged catalog as the approved file.
    producer = tmp_path / "producer"
    runtime.derive(producer, manifest, lock, requirements, cache)
    (producer / "python/python.exe").write_bytes(b"altered bytes")
    (producer / "bundle_inventory.json").write_text(json.dumps(records))
    candidate = tmp_path / "producer.zip"
    bundle.write_bundle(producer, candidate)
    with pytest.raises(ValueError, match="Unexpected portable member|independently derived bytes"):
        bundle.assert_bundle(candidate, output)

    pinned_demo = _seed(demo, cache)
    (cache / (pinned_demo.sha256 + "-" + demo.name)).write_bytes(b"wrong")
    with pytest.raises(ValueError, match="Cached size or SHA-256 mismatch"):
        runtime.derive(tmp_path / "tampered", manifest, lock, requirements, cache)


def test_catalog_checkout_binds_the_pins_and_tool_bytes(repo_root: Path) -> None:
    catalog = json.loads((repo_root / runtime.CATALOG).read_bytes())
    for file, key in ((runtime.MANIFEST, "manifest_sha256"), (Path("uv.lock"), "uv_lock_sha256")):
        assert catalog[key] == runtime.sha((repo_root / file).read_bytes())
    for name, digest in catalog["tools"].items():
        assert digest == runtime.sha((repo_root / runtime.OWNER / name).read_bytes())
    assert catalog["policy"] == runtime.POLICY
    assert len(catalog["files"]) > 8000
    assert len(catalog["directories"]) > 700
