"""Derive Windows portable runtime files from exact, authenticated inputs.

Invoke with the host interpreter's -I -S options. This tool treats all downloaded
packages as data, including their entry-point definitions and Python sources.
"""

from __future__ import annotations

import argparse
import base64
import configparser
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit

# -I excludes the script directory. Add just the trusted tool directory, never
# the working directory or a staged/downloaded Python path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from portable_archive import (
    MAX_ARCHIVE,
    PathIndex,
    check_path,
    checked_zip,
    copy_exact,
    digest_file,
    read_member,
)

OWNER = Path("tools/windows_portable")
CATALOG = OWNER / "release-runtime-files.json"
MANIFEST = OWNER / "manifest.windows-x64.json"
SITE = "app/site-packages"
EXPORT = (
    "uv",
    "export",
    "--frozen",
    "--no-dev",
    "--no-emit-project",
    "--no-emit-package",
    "vapoursynth-lsmas",
    "--extra",
    "vsview",
    "--format",
    "requirements.txt",
)
TOOL_VERSION = 1
POLICY = "cp313-win-amd64-v1"
TRIM = (125, 359295997)
EMBEDDED_SEARCH_PATH = (
    b"python313.zip\r\n.\r\n..\\app\\site-packages\r\n..\\app\\src\r\nimport site\r\n"
)
NATIVE_DESTINATIONS = {"ffmpeg", "python", "vs/core"}
_SHA = re.compile(r"[a-f0-9]{64}")
_REQUIREMENT = re.compile(r"([a-z0-9-]+)==([0-9][a-z0-9.]*)(?: ; (.+))? \\")
_COMPATIBLE_WHEEL = re.compile(
    r"-(?:py3|py2\.py3)-none-(?:any|win_amd64)\.whl$"
    r"|-cp313-cp313-win_amd64\.whl$"
    r"|-cp(\d{2,3})-abi3-win_amd64\.whl$"
)
_QT_WHEELS = frozenset(
    {"pyside6", "pyside6-addons", "pyside6-essentials", "pyside6-pdf", "pyside6-webengine"}
)
_ENTRY_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*")
_ENTRY_VALUE = re.compile(
    r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*):([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)", re.ASCII
)
_DOWNLOAD_HOSTS = {
    "www.python.org",
    "github.com",
    "release-assets.githubusercontent.com",
    "files.pythonhosted.org",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True)
class Pin:
    url: str
    bytes: int
    sha256: str

    def __post_init__(self) -> None:
        location = urlsplit(self.url)
        if (
            location.scheme != "https"
            or location.netloc not in _DOWNLOAD_HOSTS
            or location.query
            or location.fragment
            or type(self.bytes) is not int
            or not 0 < self.bytes <= MAX_ARCHIVE
            or not _SHA.fullmatch(self.sha256)
        ):
            raise ValueError(f"Invalid portable input pin: {self.url}")
        check_path(self.filename)

    @property
    def filename(self) -> str:
        return urlsplit(self.url).path.rsplit("/", 1)[-1]


class _Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        location = urlsplit(newurl)
        if location.scheme != "https" or location.netloc not in _DOWNLOAD_HOSTS:
            raise ValueError("Portable input redirected outside approved HTTPS hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(pin: Pin, cache: Path) -> Path:
    # Digest-keyed, atomically published and reauthenticated on every use.
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (pin.sha256 + "-" + pin.filename)
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as temporary:
            temp_path = Path(temporary.name)
        try:
            opener = urllib.request.build_opener(_Redirects())
            with opener.open(pin.url, timeout=30) as response, temp_path.open("wb") as target:
                if copy_exact(response, pin.bytes, target) != pin.sha256:
                    raise ValueError(f"SHA-256 mismatch for {pin.filename}")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise ValueError(f"Unsafe cached portable input: {pin.filename}")
    if path.stat().st_size != pin.bytes or digest_file(path) != pin.sha256:
        raise ValueError(f"Cached size or SHA-256 mismatch for {pin.filename}")
    return path


class Layout:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.paths = PathIndex()
        self.records: dict[str, dict[str, object]] = {}
        self.owners: dict[str, str] = {}

    def directory(self, path: str) -> None:
        self.paths.add(path, directory=True)
        (self.root / path).mkdir(parents=True, exist_ok=True)

    def write(self, path: str, stream: BinaryIO, size: int, owner: str) -> str:
        if path in self.records:
            previous = self.owners[path]
            qt_relative = path.removeprefix(f"{SITE}/PySide6/")
            shared_qt = (
                previous != owner
                and previous in _QT_WHEELS
                and owner in _QT_WHEELS
                and qt_relative != path
                and "/" not in qt_relative
                and (
                    qt_relative.endswith(".pyi")
                    or qt_relative
                    in {
                        "__init__.py",
                        "_config.py",
                        "_git_pyside_version.py",
                        "py.typed",
                    }
                )
            )
            if not shared_qt:
                raise ValueError(f"Portable file has multiple owners: {path}")
            digest = copy_exact(stream, size)
            if self.records[path] != {"path": path, "bytes": size, "sha256": digest}:
                raise ValueError(f"Qt wheel collision has different bytes: {path}")
            return digest

        self.paths.add(path)
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as target:
            digest = copy_exact(stream, size, target)
        self.records[path] = {"path": path, "bytes": size, "sha256": digest}
        self.owners[path] = owner
        return digest

    def generate(self, path: str, content: bytes, owner: str) -> None:
        self.write(path, io.BytesIO(content), len(content), owner)

    def copy(self, source: str, destination: str, owner: str) -> None:
        with (self.root / source).open("rb") as stream:
            self.write(destination, stream, int(self.records[source]["bytes"]), owner)

    def drop(self, path: str) -> None:
        (self.root / path).unlink()
        del self.records[path]
        del self.owners[path]
        self.paths.files.remove(path)


def _lock_pin(entry: dict) -> Pin:
    algorithm, digest = entry["hash"].split(":")
    if algorithm != "sha256":
        raise ValueError("Unsupported portable lock hash algorithm")
    return Pin(entry["url"], entry["size"], digest)


def _requirements(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if (
            not line
            or line.lstrip().startswith("#")
            or re.fullmatch(r"    --hash=sha256:[a-f0-9]{64}(?: \\)?", line)
        ):
            continue
        match = _REQUIREMENT.fullmatch(line)
        if match is None:
            raise ValueError(f"Unsupported frozen portable requirement: {line}")
        name, version, marker = match.groups()
        if marker not in (None, "sys_platform == 'win32'"):
            raise ValueError(f"Unreviewed portable requirement marker: {marker}")
        if name in result:
            raise ValueError(f"Ambiguous portable requirement: {name}")
        result[name] = version
    return result


def _locked_inputs(lock: bytes, requirements: bytes) -> dict[str, tuple[str, Pin]]:
    selected = _requirements(requirements)
    # uv export omits L-SMASH because it was installed separately from the
    # runtime manifest. Require that wheel to agree with the frozen lock too.
    packages = tomllib.loads(lock.decode())["package"]
    lsmas = [package for package in packages if package["name"] == "vapoursynth-lsmas"]
    if len(lsmas) != 1:
        raise ValueError("Expected one locked L-SMASH version")
    selected["vapoursynth-lsmas"] = lsmas[0]["version"]
    result = {}
    for name, version in selected.items():
        matches = [p for p in packages if (p["name"], p["version"]) == (name, version)]
        if len(matches) != 1 or matches[0]["source"] != {"registry": "https://pypi.org/simple"}:
            raise ValueError(f"Unapproved or ambiguous lock source: {name} {version}")
        package = matches[0]
        wheels = []
        for wheel in package.get("wheels", []):
            match = _COMPATIBLE_WHEEL.search(wheel["url"])
            if match and (match[1] is None or int(match[1]) <= 313):
                wheels.append(wheel)
        if name == "anitopy" and version == "2.1.1" and not wheels:
            result[name] = version, _lock_pin(package["sdist"])
        elif len(wheels) == 1:
            result[name] = version, _lock_pin(wheels[0])
        else:
            raise ValueError(f"Expected exactly one supported Windows wheel: {name} {version}")
    return result


def _unpack_archive(
    layout: Layout, archive_path: Path, destination: str, prefix: str, owner: str
) -> None:
    check_path(destination)
    if prefix:
        check_path(prefix.removesuffix("/"))
        if not prefix.endswith("/"):
            raise ValueError("ZIP strip prefix must end in /")
    with checked_zip(archive_path) as archive:
        for entry in archive.infolist():
            if not entry.filename.startswith(prefix):
                raise ValueError(f"ZIP member is outside its pinned strip prefix: {entry.filename}")
            relative = entry.filename[len(prefix) :].removesuffix("/")
            if entry.is_dir():
                layout.directory(f"{destination}/{relative}" if relative else destination)
            else:
                with archive.open(entry) as stream:
                    layout.write(f"{destination}/{relative}", stream, entry.file_size, owner)


def _wheel_record(archive: zipfile.ZipFile, record: str) -> dict[str, tuple[str, int]]:
    text = read_member(archive, record, 4 * 1024**2).decode("utf-8")
    rows: dict[str, tuple[str, int]] = {}
    index = PathIndex()
    self_row = False
    for row in csv.reader(io.StringIO(text, newline=""), strict=True):
        if len(row) != 3:
            raise ValueError("Invalid wheel RECORD row")
        path, hash_field, length = row
        index.add(path)
        if path == record:
            if hash_field or length:
                raise ValueError("Wheel RECORD cannot hash itself")
            self_row = True
            continue
        match = re.fullmatch(r"sha256=([A-Za-z0-9_-]{43})", hash_field)
        if match is None or not re.fullmatch(r"(?:0|[1-9][0-9]{0,9})", length):
            raise ValueError(f"Invalid wheel RECORD hash or size: {path}")
        rows[path] = (base64.urlsafe_b64decode(match[1] + "=").hex(), int(length))
    if not self_row:
        raise ValueError("Wheel RECORD lacks its own entry")
    files = {entry.filename for entry in archive.infolist() if not entry.is_dir()}
    if files != rows.keys() | {record}:
        raise ValueError("Wheel RECORD does not cover exactly the archive files")
    return rows


def _entry_wrappers(layout: Layout, entry_points: str, owner: str) -> list[str]:
    metadata = configparser.ConfigParser(interpolation=None, delimiters=("=",), strict=True)
    metadata.optionxform = str
    metadata.read_string(entry_points)
    if metadata.defaults():
        raise ValueError("Wheel entry points must not define defaults")
    paths = []
    for group, executable in (("console_scripts", "python.exe"), ("gui_scripts", "pythonw.exe")):
        if not metadata.has_section(group):
            continue
        for name, value in metadata[group].items():
            entry = _ENTRY_VALUE.fullmatch(value)
            if _ENTRY_NAME.fullmatch(name) is None or entry is None:
                raise ValueError(f"Unsupported wheel entry point: {name}")
            module, attribute = entry.groups()
            path = f"{SITE}/Scripts/{name}.cmd"
            lines = [
                "@echo off",
                "setlocal",
                f'"%~dp0..\\..\\..\\python\\{executable}" -B -c '
                f'"import sys; from importlib import import_module; '
                f"sys.exit(import_module('{module}').{attribute}())\" %*",
                "exit /b %ERRORLEVEL%",
                "",
            ]
            layout.generate(path, "\r\n".join(lines).encode("ascii"), owner)
            paths.append(path)
    return paths


def _write_record(layout: Layout, record: str, paths: list[str], owner: str) -> None:
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    for path in sorted(paths):
        if path in layout.records:
            entry = layout.records[path]
            digest = (
                base64.urlsafe_b64encode(bytes.fromhex(str(entry["sha256"]))).decode().rstrip("=")
            )
            writer.writerow((path.removeprefix(SITE + "/"), f"sha256={digest}", entry["bytes"]))
    writer.writerow((record.removeprefix(SITE + "/"), "", ""))
    layout.generate(record, text.getvalue().encode(), owner)


def _install_wheel(
    layout: Layout, path: Path, filename: str, name: str, version: str
) -> tuple[str, list[str]]:
    prefix = filename.split("-")
    if len(prefix) != 5 or normalize(prefix[0]) != name or prefix[1] != version:
        raise ValueError(f"Wheel filename does not identify its locked package: {filename}")
    dist_info = f"{prefix[0]}-{version}.dist-info"
    record = f"{dist_info}/RECORD"
    installed = []
    with checked_zip(path) as archive:
        rows = _wheel_record(archive, record)
        wheel = read_member(archive, f"{dist_info}/WHEEL", 65536).decode("utf-8").splitlines()
        if (
            wheel.count("Wheel-Version: 1.0") != 1
            or sum(line in ("Root-Is-Purelib: true", "Root-Is-Purelib: false") for line in wheel)
            != 1
        ):
            raise ValueError(f"Unsupported wheel metadata: {filename}")
        metadata = read_member(archive, f"{dist_info}/METADATA", 1024**2)
        headers = metadata.split(b"\n\n", 1)[0].decode().splitlines()
        names = [normalize(line[6:]) for line in headers if line.startswith("Name: ")]
        versions = [line[9:] for line in headers if line.startswith("Version: ")]
        if names != [name] or versions != [version]:
            raise ValueError(f"Wheel metadata does not match its pin: {filename}")
        for entry in archive.infolist():
            relative = entry.filename.removesuffix("/")
            top = relative.split("/", 1)[0]
            if (
                top.lower().endswith((".data", ".egg-info"))
                or (top.lower().endswith(".dist-info") and top != dist_info)
                or top.lower() in {"frame_compare", "scripts"}
            ):
                raise ValueError(f"Unsupported wheel member or installation scheme: {relative}")
            # A pinned Qt wheel ships build-time bytecode for a different Python.
            # Authenticate the RECORD entry but retain only its source.
            if "__pycache__" in relative.lower().split("/") or relative.lower().endswith(
                (".pyc", ".pyo")
            ):
                if name not in _QT_WHEELS:
                    raise ValueError(f"Unexpected wheel bytecode: {relative}")
                if not entry.is_dir():
                    with archive.open(entry) as stream:
                        if rows[relative] != (copy_exact(stream, entry.file_size), entry.file_size):
                            raise ValueError(f"Wheel RECORD hash or size mismatch: {relative}")
                continue
            projected = f"{SITE}/{relative}"
            if entry.is_dir():
                layout.directory(projected)
            elif relative != record:
                with archive.open(entry) as stream:
                    digest = layout.write(projected, stream, entry.file_size, name)
                if rows[relative] != (digest, entry.file_size):
                    raise ValueError(f"Wheel RECORD hash or size mismatch: {relative}")
                installed.append(projected)
        entry_points = f"{dist_info}/entry_points.txt"
        if entry_points in rows:
            installed.extend(
                _entry_wrappers(layout, read_member(archive, entry_points, 65536).decode(), name)
            )
    return f"{SITE}/{record}", installed


def _check_anitopy_tar_header(data: bytes, entry: tarfile.TarInfo, cursor: int) -> None:
    if entry.offset != cursor:
        raise ValueError("Unexpected hidden header in anitopy tar")
    first = tarfile.TarInfo.frombuf(data[cursor : cursor + 512], "ascii", "strict")
    header_offset = entry.offset_data - 512
    if first.type == tarfile.XHDTYPE:
        timestamp = data[cursor + 512 : cursor + 512 + first.size]
        if (
            header_offset != cursor + 1024
            or first.name != "././@PaxHeader"
            or not re.fullmatch(rb"[0-9]+ mtime=[0-9]+(?:\.[0-9]+)?\n", timestamp)
            or entry.pax_headers.keys() != {"mtime"}
            or any(data[cursor + 512 + first.size : header_offset])
        ):
            raise ValueError("Unsupported extended header in anitopy tar")
    elif header_offset != cursor or entry.pax_headers:
        raise ValueError("Unexpected extended header in anitopy tar")
    header = tarfile.TarInfo.frombuf(data[header_offset : header_offset + 512], "ascii", "strict")
    if (header.name, header.type, header.size) != (entry.name, entry.type, entry.size):
        raise ValueError("Ambiguous anitopy tar member")


def _install_anitopy(layout: Layout, path: Path, filename: str) -> None:
    # The one sdist in the Windows graph has no published wheel. Its static
    # package layout is explicit. Never unpack or run its build scripts.
    root = "anitopy-2.1.1"
    modules = (
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
    dist = "anitopy-2.1.1.dist-info"
    projected = {f"anitopy/{name}.py": f"anitopy/{name}.py" for name in modules}
    projected |= {"PKG-INFO": f"{dist}/METADATA", "LICENSE": f"{dist}/licenses/LICENSE"}
    ignored = {
        "MANIFEST.in",
        "README.rst",
        "setup.cfg",
        "setup.py",
        "anitopy.egg-info/PKG-INFO",
        "anitopy.egg-info/SOURCES.txt",
        "anitopy.egg-info/dependency_links.txt",
        "anitopy.egg-info/top_level.txt",
    }
    directories = {root, f"{root}/anitopy", f"{root}/anitopy.egg-info"}
    if filename != f"{root}.tar.gz":
        raise ValueError("Unexpected source archive for the anitopy projection")
    # Bound both layers before invoking tarfile. Require a single gzip
    # stream, with no concatenated data or trailing content.
    with path.open("rb") as source:
        compressed = source.read(64 * 1024 + 1)
    if len(compressed) > 64 * 1024:
        raise ValueError("Anitopy gzip exceeds compressed size limit")
    gzip_stream = zlib.decompressobj(31)
    expanded = gzip_stream.decompress(compressed, 256 * 1024 + 1)
    if len(expanded) > 256 * 1024:
        raise ValueError("Anitopy tar exceeds expanded size limit")
    if not gzip_stream.eof or gzip_stream.unused_data:
        raise ValueError("Ambiguous or truncated anitopy gzip stream")
    found: set[str] = set()
    index = PathIndex()
    installed = []
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
        cursor = 0
        for entry in archive:
            _check_anitopy_tar_header(expanded, entry, cursor)
            cursor = entry.offset_data + ((entry.size + 511) // 512) * 512
            if any(expanded[entry.offset_data + entry.size : cursor]):
                raise ValueError("Nonzero data in anitopy tar member padding")
            if entry.name in found or not (entry.isdir() or entry.type == tarfile.REGTYPE):
                raise ValueError(f"Unsafe or duplicate anitopy tar member: {entry.name}")
            found.add(entry.name)
            index.add(entry.name, directory=entry.isdir())
            if entry.isdir() and entry.name in directories and entry.size == 0:
                continue
            relative = entry.name.removeprefix(root + "/")
            if relative not in projected.keys() | ignored or entry.isdir() or entry.size > 32768:
                raise ValueError(f"Unexpected anitopy tar member: {entry.name}")
            if relative in projected:
                stream = archive.extractfile(entry)
                if stream is None:
                    raise ValueError(f"Missing anitopy member data: {entry.name}")
                with stream:
                    destination = f"{SITE}/{projected[relative]}"
                    layout.write(destination, stream, entry.size, "anitopy")
                installed.append(destination)
        if (
            cursor != archive.offset
            or len(expanded) - cursor < 1024
            or len(expanded) % 512
            or any(expanded[cursor:])
        ):
            raise ValueError("Invalid end record in anitopy tar")
    if found != directories | {f"{root}/{path}" for path in projected.keys() | ignored}:
        raise ValueError("Incomplete anitopy source archive")
    _write_record(layout, f"{SITE}/{dist}/RECORD", installed, "anitopy")


def _trim_webengine(layout: Layout) -> None:
    qt = f"{SITE}/PySide6/"
    chromium = {"icudtl.dat", "v8_context_snapshot.bin", "v8_context_snapshot.debug.bin"}
    excluded = []
    for path in layout.records:
        if path.startswith(qt):
            relative = path[len(qt) :].lower()
            if "webengine" in relative or (
                relative.split("/")[-2:-1] == ["resources"] and relative.split("/")[-1] in chromium
            ):
                excluded.append(path)
    size = sum(int(layout.records[path]["bytes"]) for path in excluded)
    if (len(excluded), size) != TRIM:
        raise ValueError(
            f"Unexpected Qt WebEngine deployment surface: files={len(excluded)} bytes={size}"
        )
    for path in excluded:
        layout.drop(path)
    print(
        f"WINDOWS_BUNDLE_PROOF qt_webengine_deployment=excluded files={len(excluded)} bytes={size}"
    )


def _python_licenses(layout: Layout) -> None:
    layout.directory("licenses/python")
    prefix = SITE + "/"
    for path in sorted(layout.records):
        if not path.startswith(prefix):
            continue
        distribution, _, leaf = path[len(prefix) :].partition("/")
        if not distribution.endswith(".dist-info"):
            continue
        if (
            leaf.startswith("licenses/")
            or "/" not in leaf
            and leaf.upper().startswith(("LICENSE", "COPYING"))
        ):
            target = f"{distribution}__{leaf}"
        else:
            continue
        layout.copy(path, f"licenses/python/{target}", "dependency-licenses")


def _unique_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    seen: set[str] = set()
    for key, value in pairs:
        if key.casefold() in seen:
            raise ValueError(f"Duplicate or case-colliding portable manifest field: {key}")
        seen.add(key.casefold())
        result[key] = value
    return result


def derive(root: Path, manifest: bytes, lock: bytes, requirements: bytes, cache: Path) -> bytes:
    layout = Layout(root)
    pinned = _locked_inputs(lock, requirements)
    artifacts = json.loads(manifest, object_pairs_hook=_unique_json_keys)["artifacts"]
    native = {}
    destinations = set()
    manifest_wheels = {}
    artifact_ids = set()
    for artifact in artifacts:
        pin = Pin(artifact["url"], artifact["bytes"], artifact["sha256"])
        install = artifact["install"]
        artifact_id = artifact["id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", artifact_id) or artifact_id in artifact_ids:
            raise ValueError(f"Invalid or duplicate portable artifact: {artifact_id}")
        artifact_ids.add(artifact_id)
        if install["type"] == "extract" and pin.filename.endswith(".zip"):
            destination = install["destination"]
            if destination not in NATIVE_DESTINATIONS - destinations:
                raise ValueError(
                    f"Unexpected or duplicate native runtime destination: {destination}"
                )
            destinations.add(destination)
            native[artifact_id] = asdict(pin)
            _unpack_archive(
                layout,
                download(pin, cache),
                install["destination"],
                install.get("strip_prefix", ""),
                artifact_id,
            )
        elif install["type"] == "python_wheel" and pin.filename.endswith(".whl"):
            name = normalize(pin.filename.split("-")[0])
            if name in manifest_wheels or name not in pinned or pin != pinned[name][1]:
                raise ValueError(f"Manifest wheel does not agree with the frozen lock: {name}")
            manifest_wheels[name] = artifact_id
        else:
            raise ValueError(f"Unsupported manifest installation for {artifact_id}")

    if destinations != NATIVE_DESTINATIONS:
        raise ValueError("Portable manifest does not pin the complete native runtime")
    python_path = "python/python313._pth"
    if not {"python/python313.zip", python_path} <= layout.records.keys():
        raise ValueError("Embedded CPython archive lacks its expected search-path files")
    layout.drop(python_path)
    layout.generate(
        python_path,
        EMBEDDED_SEARCH_PATH,
        "embedded-search-path",
    )

    records = {}
    for name, (version, pin) in sorted(pinned.items()):
        if name == "vapoursynth":
            member = f"vs/core/wheel/{pin.filename}"
            if layout.records.get(member) != {
                "path": member,
                "bytes": pin.bytes,
                "sha256": pin.sha256,
            }:
                raise ValueError("VapourSynth embedded wheel does not match the frozen lock")
            path = layout.root / member
        else:
            path = download(pin, cache)
        if name == "anitopy" and not pin.filename.endswith(".whl"):
            _install_anitopy(layout, path, pin.filename)
        else:
            records[name] = _install_wheel(layout, path, pin.filename, name, version)
    if f"{SITE}/vapoursynth/libvapoursynth.dll" not in layout.records:
        raise ValueError("VapourSynth wheel lacks the managed R81 package DLL")
    _trim_webengine(layout)
    for name, (record, installed) in records.items():
        _write_record(layout, record, installed, name)
    _python_licenses(layout)
    for source, name in (("ffmpeg/LICENSE.txt", "ffmpeg"), ("python/LICENSE.txt", "python")):
        layout.copy(source, f"licenses/{name}-LICENSE.txt", "native-licenses")

    return json_bytes(
        {
            "schema_version": 1,
            "tool_version": TOOL_VERSION,
            "policy": POLICY,
            "manifest_sha256": sha(manifest),
            "uv_lock_sha256": sha(lock),
            "tools": {
                name: digest_file(Path(__file__).with_name(name))
                for name in ("portable_runtime.py", "portable_archive.py")
            },
            "provenance": {
                "native": native,
                "packages": {
                    name: {
                        "version": version,
                        **asdict(pin),
                        "manifest_artifact": manifest_wheels.get(name),
                    }
                    for name, (version, pin) in pinned.items()
                },
            },
            "files": [layout.records[path] for path in sorted(layout.records)],
            "directories": sorted(layout.paths.directories),
        }
    )


def git_blob(repo: Path, commit: str, path: Path) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), "cat-file", "blob", f"{commit}:{path.as_posix()}"], timeout=30
    )


def export(repo: Path, output: Path | None = None) -> bytes:
    command = [*EXPORT]
    if output is not None:
        command.extend(("--output-file", str(output)))
    data = subprocess.check_output(
        command, cwd=repo, timeout=90, env=os.environ | {"UV_OFFLINE": "1", "UV_NO_CONFIG": "1"}
    )
    return data if output is None else output.read_bytes()


def _assert_catalog(candidate: bytes, repo: Path, commit: str) -> None:
    try:
        approved = git_blob(repo, commit, CATALOG)
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            "Approved commit lacks an independently derived release-runtime-files.json"
        ) from exc
    if approved != candidate:
        raise ValueError(
            "Committed release-runtime-files.json is stale or differs from authenticated inputs"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("catalog", "check-catalog", "assemble", "export"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--check-catalog", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, timeout=30).decode().strip()
    )
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Cannot determine exact source commit")
    manifest = (
        git_blob(repo, commit, MANIFEST) if args.manifest is None else args.manifest.read_bytes()
    )
    lock = git_blob(repo, commit, Path("uv.lock"))
    if args.mode == "assemble":
        root = args.output
        if root is None or not root.is_dir() or any(root.iterdir()):
            raise ValueError("Assembly needs an empty reserved output directory")
        requirement_file = root / "requirements.lock.txt"
        if args.requirements is None:
            requirements = export(repo, requirement_file)
        else:
            requirements = args.requirements.read_bytes()
            requirement_file.write_bytes(requirements)
        catalog = derive(root, manifest, lock, requirements, args.cache)
        if args.check_catalog:
            _assert_catalog(catalog, repo, commit)
        (root / "manifest.json").write_bytes(manifest)
    else:
        with tempfile.TemporaryDirectory(prefix="portable-runtime-") as temporary:
            catalog = derive(Path(temporary), manifest, lock, export(repo), args.cache)
        if args.mode == "check-catalog":
            _assert_catalog(catalog, repo, commit)
        elif args.output is not None:
            with args.output.open("xb") as output:
                output.write(catalog)
        else:
            parser.error("catalog requires --output")


if __name__ == "__main__":
    main()
