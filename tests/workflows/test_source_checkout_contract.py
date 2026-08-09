"""Tests for the bounded source checkout build helper."""

from __future__ import annotations

import ast
import re
from pathlib import Path


def test_source_checkout_bounds_every_git_boundary(repo_root: Path) -> None:
    script = (repo_root / "tools/checkout_source_commit.sh").read_text(encoding="utf-8")

    assert "readonly GIT_COMMAND_TIMEOUT_SECONDS=300" in script
    assert "readonly GIT_COMMAND_KILL_AFTER_SECONDS=10" in script
    assert (
        '    --kill-after="${GIT_COMMAND_KILL_AFTER_SECONDS}s" \\\n'
        '    "${GIT_COMMAND_TIMEOUT_SECONDS}s" \\\n'
        '    "$@"'
    ) in script

    for description in (
        "git init",
        "git remote add",
        "git fetch",
        "git checkout",
        "git rev-parse",
    ):
        assert re.search(rf'run_bounded "{re.escape(description)}" git(?: |$)', script)

    assert 'run_bounded "source-tree digest" python - "$destination"' in script

    shell_source = script.split("actual_tree_sha256=$(run_bounded", 1)[0]
    assert not re.search(r"^\s*git(?:\s|-C)", shell_source, re.MULTILINE)

    python_source = script.split("python - \"$destination\" <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    module = ast.parse(python_source)
    check_output_calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "check_output"
    ]
    assert len(check_output_calls) == 1
    timeout_keywords = [
        keyword for keyword in check_output_calls[0].keywords if keyword.arg == "timeout"
    ]
    assert len(timeout_keywords) == 1
    assert isinstance(timeout_keywords[0].value, ast.Name)
    assert timeout_keywords[0].value.id == "GIT_SUBPROCESS_TIMEOUT_SECONDS"
    assert 'git_output(["git", "-C", str(root), "ls-tree"' in python_source
    assert 'git_output(\n            ["git", "-C", str(root), "cat-file"' in python_source
