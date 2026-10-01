"""E1: version and help through the installed console entry point."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from .conftest import CommandResult, Workspace, _write_artifact


@pytest.mark.e2e
def test_cli_version_command(
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    artifact_root: Path,
    pyproject_version: str,
) -> None:
    root = workspace()
    arguments = ["version"]
    result = run_cli(root.root, arguments)

    # Version command contract.
    summary = {"exit_code": result.exit_code, "stdout": result.stdout}
    expected = {"exit_code": 0, "stdout": f"frame-compare {pyproject_version}\n"}
    _write_artifact(artifact_root, "E1-version", arguments, root.root, result, summary)
    assert summary == expected


@pytest.mark.e2e
def test_cli_no_args_shows_usage_and_commands(
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    artifact_root: Path,
) -> None:
    root = workspace()
    arguments: list[str] = []
    result = run_cli(root.root, arguments)
    command_names = sorted(
        re.findall(r"│\s+([a-z][a-z-]*)\s{2,}", result.stdout, flags=re.MULTILINE)
    )

    # Command surface contract.
    summary = {
        "exit_code": result.exit_code,
        "usage_present": "Usage:" in result.stdout,
        "commands": command_names,
    }
    expected = {
        "exit_code": 0,
        "usage_present": True,
        "commands": ["doctor", "history", "preset", "run", "version", "wizard"],
    }
    _write_artifact(artifact_root, "E1-help", arguments, root.root, result, summary)
    assert summary == expected
