from __future__ import annotations

import subprocess

import pytest

from tests.workflows import _helpers


def test_bash_executable_or_skip_skips_when_bash_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: None)

    with pytest.raises(pytest.skip.Exception, match="bash is required"):
        _helpers.bash_executable_or_skip()


def test_bash_executable_or_skip_skips_when_bash_launcher_cannot_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: "C:/Windows/System32/bash.exe")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["bash", "-lc", "printf frame-compare-bash-ok"],
            returncode=1,
            stdout="Windows Subsystem for Linux has no installed distributions.",
            stderr="",
        )

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    with pytest.raises(pytest.skip.Exception, match="bash is not executable"):
        _helpers.bash_executable_or_skip()


def test_bash_executable_or_skip_returns_probed_bash_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_path = "C:/Program Files/Git/bin/bash.exe"
    captured_commands: list[list[str]] = []
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: expected_path)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = args[0]
        assert isinstance(command, list)
        captured_commands.append(command)
        return subprocess.CompletedProcess(
            args=["bash", "-lc", "printf frame-compare-bash-ok"],
            returncode=0,
            stdout="frame-compare-bash-ok",
            stderr="",
        )

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    assert _helpers.bash_executable_or_skip() == expected_path
    assert captured_commands[0][0] == expected_path
