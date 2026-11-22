"""Post-pack acceptance with the exact ZIP produced by the Windows build."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

import pytest

from ._helpers import snapshot_bytes
from .test_windows_portable_install_uninstall_e2e import _get_user_path, _set_user_path

_ZIP = os.environ.get("FRAME_COMPARE_TEST_PORTABLE_ZIP")
_BUNDLE_ROOT = "frame-compare-portable-win-x64"
_DATA_DIRS = ("config", "comparison_videos", "generated")
_LEGACY_LEAVES = (
    "frame-compare-update.ps1",
    "frame-compare-update.cmd",
    "update_public_key.xml",
    "frame-compare-version.ps1",
)
_RUN = "zip-succession-sentinel"
_SHOT = "screenshots/frame.png"
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGMwyRMEAAGNALSaBQ1NAAAAAElFTkSuQmCC"
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group("windows-install-lifecycle"),
    pytest.mark.skipif(_ZIP is None, reason="Requires the post-pack portable ZIP environment"),
]

_RUN_RESULT = """\
version = 1
status = "completed"
started_at = "2026-07-14T12:00:00Z"
completed_at = "2026-07-14T12:00:05Z"
duration_seconds = 5.0
clip_count = 2
selected_frame_count = 1
warning_count = 0
warning_summaries = []
metrics_cache_status = "miss"
report_path = "report.html"
screenshot_dir = "screenshots"

[phase_timings]
render = 1.0

[slowpics]
outcome = "not_uploaded"
"""


def _cmd(env: dict[str, str], cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [env["COMSPEC"], "/d", "/c", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    return result


def _install(
    bundle: Path,
    *,
    interpreter: str,
    env: dict[str, str],
    outside: Path,
    user_data_args: tuple[str, ...] = (),
) -> str:
    if interpreter == "pwsh":
        result = _cmd(env, bundle, "install.cmd", *user_data_args)
        version_prefix = "7."
    else:
        driver = outside / "windows-powershell-install.cmd"
        driver.write_text(
            "@echo off\n"
            "setlocal\n"
            'set "ProgramFiles=%~dp0no-powershell"\n'
            'set "PATH=%SystemRoot%\\System32;%SystemRoot%\\System32\\WindowsPowerShell\\v1.0"\n'
            "where.exe pwsh.exe >nul 2>nul\n"
            "if not errorlevel 1 exit /b 91\n"
            "where.exe powershell.exe || exit /b 92\n"
            'call "%FC_TEST_INSTALL_CMD%" %*\n'
            "exit /b %ERRORLEVEL%\n",
            encoding="ascii",
        )
        result = _cmd(
            env | {"FC_TEST_INSTALL_CMD": str(bundle / "install.cmd")},
            outside,
            driver.name,
            *user_data_args,
        )
        version_prefix = "5.1."
    print(result.stdout, end="", flush=True)
    versions = re.findall(r"^Portable installer PowerShell version: (.+)$", result.stdout, re.M)
    assert len(versions) == 1 and versions[0].startswith(version_prefix), result.stdout
    return result.stdout


def _seed(bundle: Path, external_root: Path | None) -> None:
    generated_root = external_root or bundle / "generated"
    generated_setting = external_root.as_posix() if external_root else "generated"
    config = bundle / "config/config.toml"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        "[paths]\n"
        'input_dir = "comparison_videos"\n'
        'config_dir = "config"\n'
        f"generated_dir = {json.dumps(generated_setting, ensure_ascii=False)}\n"
        "\n[report]\n"
        "enable = true\n",
        encoding="utf-8",
    )
    inputs = bundle / "comparison_videos"
    inputs.mkdir(exist_ok=True)
    (inputs / "sentinel.bin").write_bytes(b"generated clip sentinel\x00")

    run = generated_root / _RUN
    screenshot = run / _SHOT
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(_PNG)
    (run / "report.html").write_text(f'<img src="{_SHOT}">\n', encoding="utf-8")
    (run / "run_result.toml").write_text(_RUN_RESULT, encoding="utf-8")


def _assert_data_owner(owner: Path, other: Path, expected: dict[str, dict[str, bytes]]) -> None:
    assert {name: snapshot_bytes(owner / name) for name in _DATA_DIRS} == expected
    assert not any(snapshot_bytes(other / name) for name in _DATA_DIRS)


def _application_tree(bundle: Path) -> dict[str, str | None]:
    tree: dict[str, str | None] = {}
    for path in (bundle / "app").rglob("*"):
        relative = path.relative_to(bundle).as_posix()
        tree[relative] = None
        if path.is_file():
            with path.open("rb") as stream:
                tree[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
    assert tree
    return tree


def _assert_active(pointer: Path, bundle: Path, expected_path: tuple[str, int]) -> None:
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    assert Path(payload["bundle_path"]) == bundle
    assert _get_user_path() == expected_path
    assert not (pointer.parent / "source-migration.pending.json").exists()


@pytest.mark.parametrize("interpreter", ["pwsh", "powershell"])
@pytest.mark.parametrize("case", ["move", "leave", "reactivate", "external"])
def test_packed_zip_succession(tmp_path: Path, interpreter: str, case: str) -> None:
    assert os.name == "nt", "Packed ZIP succession requires Windows"
    import winreg

    assert _ZIP is not None
    archive_path = Path(_ZIP)
    assert archive_path.is_file(), f"Missing packed ZIP: {archive_path}"
    pwsh = shutil.which("pwsh")
    assert pwsh, "PowerShell 7 is required for packed ZIP succession"
    powershell = Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    assert powershell.is_file(), "Windows PowerShell 5.1 is required for packed ZIP succession"

    outside = tmp_path / "outside"
    outside.mkdir()
    appdata = tmp_path / "appdata"
    env = os.environ | {"LOCALAPPDATA": str(appdata), "NO_COLOR": "1"}
    install_root = appdata / "Programs/FrameCompare"
    bin_dir = install_root / "bin"
    pointer = install_root / "state/config.json"
    fallback = pointer.with_name("config.toml")
    controlled_user_path = r"C:\FrameCompare-E2E\preserve-me"
    expected_user_path = (f"{controlled_user_path};{bin_dir}", winreg.REG_SZ)

    with TemporaryDirectory(dir=tmp_path) as workspace:
        root = Path(workspace)
        first = root / "first bundle"
        second = root / "second bundle"
        with zipfile.ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read(f"{_BUNDLE_ROOT}/manifest.json"))
            bundle_info = json.loads(archive.read(f"{_BUNDLE_ROOT}/bundle_info.json"))
            assert manifest["manifest_version"] == bundle_info["manifest_version"] == 3
            assert manifest["bundle"]["python_version"] == "3.15.2"
            sqlite_binaries = {"_sqlite3.pyd", "sqlite3.dll"}
            assert sqlite_binaries.isdisjoint(
                name.rsplit("/", 1)[-1].casefold() for name in archive.namelist()
            )
            pyside_prefix = f"{_BUNDLE_ROOT}/app/site-packages/PySide6/".casefold()
            chromium_runtime_names = {
                "icudtl.dat",
                "v8_context_snapshot.bin",
                "v8_context_snapshot.debug.bin",
            }
            webengine_files = []
            for member in archive.infolist():
                name = member.filename.casefold()
                if member.is_dir() or not name.startswith(pyside_prefix):
                    continue
                relative = PurePosixPath(name.removeprefix(pyside_prefix))
                if "webengine" in relative.as_posix() or (
                    relative.parent.name == "resources" and relative.name in chromium_runtime_names
                ):
                    webengine_files.append(member.filename)
            assert not webengine_files, f"Qt WebEngine deployment files in ZIP: {webengine_files}"
            for bundle in (first, second):
                archive.extractall(root)
                (root / _BUNDLE_ROOT).rename(bundle)
        python_version = subprocess.run(
            [str(first / "python" / "python.exe"), "--version"],
            cwd=first,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        assert python_version.stdout.strip() == "Python 3.15.2"
        first_app = _application_tree(first)
        for bundle in (first, second):
            for name in _LEGACY_LEAVES:
                assert not (bundle / name).exists()
                assert not (bundle / "shim" / name).exists()
        original_user_path = _get_user_path()
        try:
            _set_user_path((controlled_user_path, winreg.REG_SZ))
            _install(first, interpreter=interpreter, env=env, outside=outside)
            _assert_active(pointer, first, expected_user_path)
            fallback_before = fallback.read_bytes()
            external_root = tmp_path / "external-generated" if case == "external" else None
            _seed(first, external_root)
            data_before = {name: snapshot_bytes(first / name) for name in _DATA_DIRS}
            external_before = snapshot_bytes(external_root) if external_root else {}

            # Cover all four historical leaves and v0.6.1's three-file layout.
            names = _LEGACY_LEAVES[:-1] if case == "leave" else _LEGACY_LEAVES
            legacy = {name: bin_dir / name for name in names}
            unknown = bin_dir / "unknown-user-file.bin"
            unknown.write_bytes(b"keep unknown sibling")
            blocked = legacy.get(_LEGACY_LEAVES[-1]) if case in {"reactivate", "external"} else None
            for path in legacy.values():
                if path == blocked and case == "external":
                    path.mkdir()
                    (path / "nested.bin").write_bytes(b"keep nested file")
                else:
                    path.write_bytes(b"legacy installed file")

            lock = (
                blocked.open("rb")
                if blocked is not None and case == "reactivate"
                else nullcontext()
            )
            with lock:
                output = _install(
                    second,
                    interpreter=interpreter,
                    env=env,
                    outside=outside,
                    user_data_args=("-UserData", "Leave") if case == "leave" else (),
                )
                for path in legacy.values():
                    assert path.exists() == (path == blocked)
                if blocked is None:
                    assert "Could not remove legacy file" not in output
                else:
                    assert "Could not remove legacy file" in output
                    assert f"{blocked.name}:" in "".join(output.split())
                    assert "The new installation is active." in output
                    if case == "external":
                        assert (blocked / "nested.bin").read_bytes() == b"keep nested file"
                    else:
                        assert blocked.read_bytes() == b"legacy installed file"
                assert unknown.read_bytes() == b"keep unknown sibling"

            _assert_active(pointer, second, expected_user_path)

            owner, other = (first, second) if case == "leave" else (second, first)
            _assert_data_owner(owner, other, data_before)
            if case != "leave":
                assert all(
                    not (other / name).exists() for name, files in data_before.items() if files
                )
            if case == "reactivate":
                _install(first, interpreter=interpreter, env=env, outside=outside)
                _assert_active(pointer, first, expected_user_path)
                owner, other = first, second
                _assert_data_owner(owner, other, data_before)
                assert all(
                    not (other / name).exists() for name, files in data_before.items() if files
                )

            assert _application_tree(first) == first_app
            assert fallback.read_bytes() == fallback_before
            if external_root:
                assert snapshot_bytes(external_root) == external_before
            if case != "leave":
                run = (external_root or owner / "generated") / _RUN
                assert f'src="{_SHOT}"' in (run / "report.html").read_text(encoding="utf-8")
                assert (run / _SHOT).read_bytes() == _PNG
                history = _cmd(
                    env | {"PATH": f"{bin_dir};{env['PATH']}"},
                    outside,
                    "frame-compare.cmd",
                    "history",
                    "list",
                    "--json",
                )
                runs = json.loads(history.stdout)["runs"]
                assert len(runs) == 1
                assert runs[0]["name"] == _RUN
                assert runs[0]["status"] == "completed"
                assert runs[0]["report_available"] is True
        finally:
            _set_user_path(original_user_path)
