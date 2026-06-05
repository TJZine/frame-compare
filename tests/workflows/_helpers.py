from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workflow_helpers import read_text_or_fail as _read_text_or_fail

SCRIPT_SUBPROCESS_TIMEOUT_SECONDS = 20.0
BASH_PROBE_TIMEOUT_SECONDS = 5.0


def read_text_or_fail(path: Path) -> str:
    return _read_text_or_fail(path)


def write_bash_env(path: Path, *snippets: str) -> None:
    path.write_text("\n\n".join(snippets).strip() + "\n", encoding="utf-8")


def with_bash_env(env: dict[str, str], bash_env_path: Path) -> dict[str, str]:
    updated = os.environ.copy()
    updated.update(env)
    updated["BASH_ENV"] = str(bash_env_path)
    return updated


def bash_executable_or_skip() -> str:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash is required for Docker shell-script contract tests")
    try:
        result = subprocess.run(
            [bash_path, "-lc", "printf frame-compare-bash-ok"],
            check=False,
            capture_output=True,
            text=True,
            timeout=BASH_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"bash is not executable for Docker shell-script contract tests: {exc}")
    if result.returncode != 0 or result.stdout != "frame-compare-bash-ok":
        pytest.skip("bash is not executable for Docker shell-script contract tests")
    return bash_path
