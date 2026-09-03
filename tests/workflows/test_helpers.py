from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.workflows import _helpers


def test_bash_executable_or_skip_skips_when_bash_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: None)

    with pytest.raises(pytest.skip.Exception, match="executable Bash is required"):
        _helpers.bash_executable_or_skip()


def test_bash_executable_or_skip_skips_when_bash_launcher_cannot_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: "C:/Windows/System32/bash.exe")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=["bash", "-lc", "printf frame-compare-bash-ok"],
            returncode=1,
            stdout=b"Windows Subsystem for Linux has no installed distributions.",
            stderr=b"",
        )

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    with pytest.raises(pytest.skip.Exception, match="executable Bash is required"):
        _helpers.bash_executable_or_skip()


def test_bash_executable_or_skip_returns_probed_bash_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_path = "C:/Program Files/Git/bin/bash.exe"
    captured_commands: list[list[str]] = []
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: expected_path)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command = args[0]
        assert isinstance(command, list)
        captured_commands.append(command)
        return subprocess.CompletedProcess(
            args=["bash", "-lc", "printf frame-compare-bash-ok"],
            returncode=0,
            stdout=b"frame-compare-bash-ok",
            stderr=b"",
        )

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    assert _helpers.bash_executable_or_skip() == expected_path
    assert captured_commands[0][0] == expected_path


def test_bash_executable_or_skip_falls_back_to_git_bash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wsl_bash = "C:/Windows/System32/bash.exe"
    git_path = tmp_path / "Git" / "cmd" / "git.exe"
    git_bash = tmp_path / "Git" / "bin" / "bash.exe"
    git_path.parent.mkdir(parents=True)
    git_bash.parent.mkdir(parents=True)
    git_path.touch()
    git_bash.touch()

    monkeypatch.setattr(
        _helpers.shutil,
        "which",
        lambda command: wsl_bash if command == "bash" else str(git_path),
    )

    probed: list[str] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command = args[0]
        assert isinstance(command, list)
        probed.append(command[0])
        if command[0] == wsl_bash:
            return subprocess.CompletedProcess(command, 1, b"Install a distribution.", b"")
        return subprocess.CompletedProcess(command, 0, b"frame-compare-bash-ok", b"")

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    assert _helpers.bash_executable_or_skip() == str(git_bash)
    assert probed == [wsl_bash, str(git_bash)]


def test_bash_path_or_skip_uses_cygpath_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured_commands: list[list[str]] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = args[0]
        assert isinstance(command, list)
        captured_commands.append(command)
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="/c/Users/runneradmin/AppData/Local/Temp/icd\n",
            stderr="",
        )

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    converted = _helpers.bash_path_or_skip("C:/Program Files/Git/bin/bash.exe", tmp_path / "icd")

    assert converted == "/c/Users/runneradmin/AppData/Local/Temp/icd"
    assert captured_commands[0][0] == "C:/Program Files/Git/bin/bash.exe"
    assert "cygpath -u" in captured_commands[0][2]
