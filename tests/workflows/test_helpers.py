from __future__ import annotations

import subprocess

import pytest

from tests.workflows import _helpers


def test_skip_if_bash_unavailable_skips_when_bash_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: None)

    with pytest.raises(pytest.skip.Exception, match="bash is required"):
        _helpers.skip_if_bash_unavailable()


def test_skip_if_bash_unavailable_skips_when_bash_launcher_cannot_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: "bash")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["bash", "-lc", "printf frame-compare-bash-ok"],
            returncode=1,
            stdout="Windows Subsystem for Linux has no installed distributions.",
            stderr="",
        )

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    with pytest.raises(pytest.skip.Exception, match="bash is not executable"):
        _helpers.skip_if_bash_unavailable()


def test_skip_if_bash_unavailable_allows_working_bash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_helpers.shutil, "which", lambda _: "bash")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["bash", "-lc", "printf frame-compare-bash-ok"],
            returncode=0,
            stdout="frame-compare-bash-ok",
            stderr="",
        )

    monkeypatch.setattr(_helpers.subprocess, "run", fake_run)

    _helpers.skip_if_bash_unavailable()
