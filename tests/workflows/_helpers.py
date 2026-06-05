from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from tests.workflow_helpers import read_text_or_fail as _read_text_or_fail

SCRIPT_SUBPROCESS_TIMEOUT_SECONDS = 20.0


def read_text_or_fail(path: Path) -> str:
    return _read_text_or_fail(path)


def write_bash_env(path: Path, *snippets: str) -> None:
    path.write_text("\n\n".join(snippets).strip() + "\n", encoding="utf-8")


def with_bash_env(env: dict[str, str], bash_env_path: Path) -> dict[str, str]:
    updated = os.environ.copy()
    updated.update(env)
    updated["BASH_ENV"] = str(bash_env_path)
    return updated


def skip_if_bash_unavailable() -> None:
    if shutil.which("bash") is None:
        pytest.skip("bash is required for Docker shell-script contract tests")
