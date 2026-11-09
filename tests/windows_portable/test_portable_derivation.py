from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import shutil
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


def test_portable_assembly_is_inert_and_reproducible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    manifest = json.dumps({"artifacts": manifest_records}).encode()
    monkeypatch.setattr(runtime, "TRIM", (1, 4))
    output = tmp_path / "runtime"
    producer = tmp_path / "producer"
    runtime.assemble(output, manifest, lock, requirements, cache)
    runtime.assemble(producer, manifest, lock, requirements, cache)

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
    assert (output / "python/python313._pth").read_bytes() == runtime.EMBEDDED_SEARCH_PATH
    assert (
        output / "licenses/python/pyside6_webengine-1.dist-info__licenses/LICENSE"
    ).read_bytes() == b"notice"

    first_zip = tmp_path / "first.zip"
    second_zip = tmp_path / "second.zip"
    bundle.write_bundle(output, first_zip)
    bundle.write_bundle(producer, second_zip)
    assert first_zip.read_bytes() == second_zip.read_bytes()
    bundle.assert_bundle(second_zip, output)

    # Rehashing an altered file in a producer inventory cannot override the
    # independently assembled tree.
    (producer / "python/python.exe").write_bytes(b"altered bytes")
    (producer / "bundle_inventory.json").write_text('{"files": []}')
    candidate = tmp_path / "producer.zip"
    bundle.write_bundle(producer, candidate)
    with pytest.raises(ValueError, match="Unexpected portable member|independently derived bytes"):
        bundle.assert_bundle(candidate, output)

    pinned_demo = _seed(demo, cache)
    (cache / (pinned_demo.sha256 + "-" + demo.name)).write_bytes(b"wrong")
    with pytest.raises(ValueError, match="Cached size or SHA-256 mismatch"):
        runtime.assemble(tmp_path / "tampered", manifest, lock, requirements, cache)
