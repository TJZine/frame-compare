from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_SUBPROCESS_TIMEOUT_SECONDS = 20.0
BASH_PROBE_TIMEOUT_SECONDS = 5.0


def write_bash_env(path: Path, *snippets: str) -> None:
    path.write_text("\n\n".join(snippets).strip() + "\n", encoding="utf-8")


def with_bash_env(env: dict[str, str], bash_env_path: Path) -> dict[str, str]:
    updated = os.environ.copy()
    updated.update(env)
    updated["BASH_ENV"] = str(bash_env_path)
    return updated


def bash_executable_or_skip() -> str:
    candidates = [shutil.which("bash")]
    git_path = shutil.which("git")
    if git_path is not None:
        executable_suffix = Path(git_path).suffix
        git_bash = Path(git_path).parent.parent / "bin" / f"bash{executable_suffix}"
        if git_bash.is_file():
            candidates.append(str(git_bash))

    for bash_path in dict.fromkeys(candidate for candidate in candidates if candidate):
        try:
            result = subprocess.run(
                [bash_path, "-lc", "printf frame-compare-bash-ok"],
                check=False,
                capture_output=True,
                timeout=BASH_PROBE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout == b"frame-compare-bash-ok":
            return bash_path

    pytest.skip("an executable Bash is required for shell-script contract tests")


def bash_path_or_skip(bash: str, path: Path) -> str:
    try:
        result = subprocess.run(
            [
                bash,
                "-lc",
                'if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else printf "%s" "$1"; fi',
                "_",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=BASH_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"bash path conversion failed for Docker shell-script contract tests: {exc}")
    if result.returncode != 0 or not result.stdout:
        pytest.skip("bash path conversion failed for Docker shell-script contract tests")
    return result.stdout.rstrip("\n")
