"""Derive Windows portable runtime files from exact, authenticated inputs.

Invoke with the host interpreter's -I -S options. This tool treats all downloaded
packages as data, including their entry-point definitions and Python sources.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
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
)

OWNER = Path("tools/windows_portable")
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
_DOWNLOAD_HOSTS = {
    "www.python.org",
    "github.com",
    "release-assets.githubusercontent.com",
    "files.pythonhosted.org",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
        self.records: dict[str, tuple[int, str]] = {}

    def directory(self, path: str) -> None:
        self.paths.add(path, directory=True)
        (self.root / path).mkdir(parents=True, exist_ok=True)

    def write(self, path: str, stream: BinaryIO, size: int) -> None:
        self.paths.add(path)
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as target:
            digest = copy_exact(stream, size, target)
        self.records[path] = (size, digest)

    def generate(self, path: str, content: bytes) -> None:
        self.write(path, io.BytesIO(content), len(content))


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


def _unpack_archive(layout: Layout, archive_path: Path, destination: str, prefix: str) -> None:
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
                    layout.write(f"{destination}/{relative}", stream, entry.file_size)


def record_bytes(files: dict[str, bytes], record: str) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    for path, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        writer.writerow((path, f"sha256={digest}", len(data)))
    writer.writerow((record, "", ""))
    return text.getvalue().encode()


def _convert_anitopy(source: Path, wheelhouse: Path) -> Path:
    # anitopy 2.1.1 ships only an sdist. Read an explicit allowlist from the
    # authenticated tarball and synthesize wheel metadata without a backend.
    package = "anitopy-2.1.1"
    dist = f"{package}.dist-info"
    projected = {
        f"anitopy/{module}.py": f"anitopy/{module}.py"
        for module in (
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
    projected.update({"PKG-INFO": f"{dist}/METADATA", "LICENSE": f"{dist}/licenses/LICENSE"})
    with source.open("rb") as stream:
        compressed = stream.read(64 * 1024 + 1)
    if len(compressed) > 64 * 1024:
        raise ValueError("Oversized compressed anitopy source archive")
    gzip_stream = zlib.decompressobj(31)
    expanded = gzip_stream.decompress(compressed, 256 * 1024 + 1)
    if len(expanded) > 256 * 1024 or not gzip_stream.eof or gzip_stream.unused_data:
        raise ValueError("Invalid or oversized anitopy source archive")

    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
        for member in archive:
            if member.type not in (tarfile.DIRTYPE, tarfile.REGTYPE, tarfile.AREGTYPE):
                raise ValueError(f"Unsafe anitopy source member: {member.name}")
            if not member.name.startswith(f"{package}/"):
                continue
            target = projected.get(member.name.removeprefix(f"{package}/"))
            if target is None:
                continue
            if member.isdir() or not 0 <= member.size <= 32768 or target in files:
                raise ValueError(f"Unsafe or duplicate anitopy source member: {member.name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"Missing anitopy source data: {member.name}")
            with stream:
                files[target] = stream.read()
    if files.keys() != set(projected.values()):
        raise ValueError("Incomplete anitopy source archive")
    files[f"{dist}/WHEEL"] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    record = f"{dist}/RECORD"
    files[record] = record_bytes(files, record)
    wheel = wheelhouse / f"{package}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "x") as archive:
        for path, data in sorted(files.items()):
            archive.writestr(zipfile.ZipInfo(path), data)
    return wheel


def _stage_wheel(source: Path, pin: Pin, wheelhouse: Path) -> None:
    # Keep archive/path safety checks at the extraction boundary. uv handles
    # wheel metadata, RECORD, and the actual installation.
    with checked_zip(source) as archive:
        for entry in archive.infolist():
            top = entry.filename.split("/", 1)[0].lower()
            if top.endswith(".data") or top in {"bin", "scripts", "frame_compare"}:
                raise ValueError(f"Unsupported portable wheel path: {entry.filename}")
    shutil.copyfile(source, wheelhouse / pin.filename)


def _install_runtime_wheels(
    layout: Layout, pinned: dict[str, tuple[str, Pin]], cache: Path
) -> None:
    with tempfile.TemporaryDirectory(prefix="fc-wheels-") as temporary:
        work = Path(temporary)
        wheelhouse = work / "wheels"
        wheelhouse.mkdir()
        requirements = []
        for name, (version, pin) in sorted(pinned.items()):
            if name == "vapoursynth":
                member = f"vs/core/wheel/{pin.filename}"
                if layout.records.get(member) != (pin.bytes, pin.sha256):
                    raise ValueError("VapourSynth embedded wheel does not match the frozen lock")
                source = layout.root / member
            else:
                source = download(pin, cache)
            if name == "anitopy" and pin.filename == "anitopy-2.1.1.tar.gz":
                digest = digest_file(_convert_anitopy(source, wheelhouse))
            else:
                _stage_wheel(source, pin, wheelhouse)
                digest = pin.sha256
            requirements.append(f"{name}=={version} --hash=sha256:{digest}\n")

        exact = work / "requirements.txt"
        exact.write_text("".join(requirements), encoding="ascii")
        # Resolve these exact names from the wheelhouse rather than direct file
        # requirements, which would embed absolute paths in direct_url.json.
        # Ignore ambient uv options such as extra find-links or bytecode compilation.
        subprocess.run(
            [
                "uv",
                "--no-config",
                "--offline",
                "--no-cache",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-build",
                "--no-python-downloads",
                "--require-hashes",
                "--link-mode",
                "copy",
                "--python",
                sys.executable,
                "--python-platform",
                "x86_64-pc-windows-msvc",
                "--target",
                str((layout.root / SITE).resolve()),
                "--find-links",
                str(wheelhouse),
                "--requirements",
                str(exact),
            ],
            cwd=work,
            env={
                key: value for key, value in os.environ.items() if not key.upper().startswith("UV_")
            },
            timeout=300,
            check=True,
        )


def _trim_webengine(site: Path) -> list[Path]:
    qt = site / "PySide6"
    chromium = {"icudtl.dat", "v8_context_snapshot.bin", "v8_context_snapshot.debug.bin"}
    excluded = [
        path
        for path in qt.rglob("*")
        if path.is_file()
        and (
            "webengine" in path.relative_to(qt).as_posix().lower()
            or (path.parent.name.lower() == "resources" and path.name.lower() in chromium)
        )
    ]
    size = sum(path.stat().st_size for path in excluded)
    if (len(excluded), size) != TRIM:
        raise ValueError(
            f"Unexpected Qt WebEngine deployment surface: files={len(excluded)} bytes={size}"
        )
    print(
        f"WINDOWS_BUNDLE_PROOF qt_webengine_deployment=excluded files={len(excluded)} bytes={size}"
    )
    return excluded


def _trim_site_packages(site: Path) -> None:
    # uv's dependency entry-point launchers refer to the build interpreter.
    # Frame Compare ships its own relocatable launchers at the bundle root.
    # The Qt wheels also contain bytecode for a different Python version.
    # uv's local cache metadata records the staged wheel's filesystem timestamp.
    (site / ".lock").unlink(missing_ok=True)
    script_dirs = [site / name for name in ("Scripts", "bin") if (site / name).is_dir()]
    removed = [
        *[path for directory in script_dirs for path in directory.rglob("*") if path.is_file()],
        *site.rglob("*.pyc"),
        *site.rglob("*.pyo"),
        *site.glob("*.dist-info/uv_cache.json"),
    ]
    for path in removed:
        path.unlink()
    for directory in [*script_dirs, *site.rglob("__pycache__")]:
        shutil.rmtree(directory)
    excluded = _trim_webengine(site)
    for path in excluded:
        path.unlink()

    removed_names = {path.relative_to(site).as_posix() for path in removed + excluded}
    for record in site.glob("*.dist-info/RECORD"):
        with record.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream))
        kept = [row for row in rows if row[0].replace("\\", "/") not in removed_names]
        if kept != rows:
            with record.open("w", encoding="utf-8", newline="") as stream:
                csv.writer(stream, lineterminator="\n").writerows(kept)


def _python_licenses(root: Path) -> None:
    target = root / "licenses/python"
    target.mkdir(parents=True)
    for distribution in (root / SITE).glob("*.dist-info"):
        notices = [path for path in (distribution / "licenses").rglob("*") if path.is_file()]
        notices += [
            path
            for path in distribution.iterdir()
            if path.is_file() and path.name.upper().startswith(("LICENSE", "COPYING"))
        ]
        for source in notices:
            destination = (
                target / f"{distribution.name}__{source.relative_to(distribution).as_posix()}"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)


def _unique_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    seen: set[str] = set()
    for key, value in pairs:
        if key.casefold() in seen:
            raise ValueError(f"Duplicate or case-colliding portable manifest field: {key}")
        seen.add(key.casefold())
        result[key] = value
    return result


def assemble(root: Path, manifest: bytes, lock: bytes, requirements: bytes, cache: Path) -> None:
    layout = Layout(root)
    pinned = _locked_inputs(lock, requirements)
    artifacts = json.loads(manifest, object_pairs_hook=_unique_json_keys)["artifacts"]
    destinations = set()
    manifest_wheels = set()
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
            _unpack_archive(
                layout,
                download(pin, cache),
                install["destination"],
                install.get("strip_prefix", ""),
            )
        elif install["type"] == "python_wheel" and pin.filename.endswith(".whl"):
            name = normalize(pin.filename.split("-")[0])
            if name in manifest_wheels or name not in pinned or pin != pinned[name][1]:
                raise ValueError(f"Manifest wheel does not agree with the frozen lock: {name}")
            manifest_wheels.add(name)
        else:
            raise ValueError(f"Unsupported manifest installation for {artifact_id}")

    if destinations != NATIVE_DESTINATIONS:
        raise ValueError("Portable manifest does not pin the complete native runtime")
    python_path = "python/python313._pth"
    if not {"python/python313.zip", python_path} <= layout.records.keys():
        raise ValueError("Embedded CPython archive lacks its expected search-path files")
    (root / python_path).write_bytes(EMBEDDED_SEARCH_PATH)

    _install_runtime_wheels(layout, pinned, cache)
    site = root / SITE
    if not (site / "vapoursynth/libvapoursynth.dll").is_file():
        raise ValueError("VapourSynth wheel lacks the managed R81 package DLL")
    _trim_site_packages(site)
    _python_licenses(root)
    for source, name in (("ffmpeg/LICENSE.txt", "ffmpeg"), ("python/LICENSE.txt", "python")):
        shutil.copyfile(root / source, root / f"licenses/{name}-LICENSE.txt")


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("assemble", "export", "anitopy-wheel"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--requirements", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, timeout=30).decode().strip()
    )
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Cannot determine exact source commit")
    if args.mode == "export":
        if args.output is None:
            parser.error("export requires --output")
        export(repo, args.output)
        return

    lock = git_blob(repo, commit, Path("uv.lock"))
    if args.mode == "anitopy-wheel":
        if args.cache is None or args.output is None:
            parser.error("anitopy-wheel requires --cache and --output")
        (package,) = (
            package
            for package in tomllib.loads(lock.decode())["package"]
            if package["name"] == "anitopy" and package["version"] == "2.1.1"
        )
        pin = _lock_pin(package["sdist"])
        if pin.filename != "anitopy-2.1.1.tar.gz":
            raise ValueError("Unexpected anitopy source archive")
        args.output.mkdir(parents=True)
        _convert_anitopy(download(pin, args.cache), args.output)
        return

    manifest = (
        git_blob(repo, commit, MANIFEST) if args.manifest is None else args.manifest.read_bytes()
    )
    root = args.output
    if args.cache is None or root is None or not root.is_dir() or any(root.iterdir()):
        parser.error("assembly needs a cache and an empty reserved output directory")
    requirement_file = root / "requirements.lock.txt"
    if args.requirements is None:
        requirements = export(repo, requirement_file)
    else:
        requirements = args.requirements.read_bytes()
        requirement_file.write_bytes(requirements)
    assemble(root, manifest, lock, requirements, args.cache)
    (root / "manifest.json").write_bytes(manifest)


if __name__ == "__main__":
    main()
