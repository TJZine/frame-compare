"""E5: empty history through the real console entry point."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from tests.e2e.harness import CommandResult, Workspace


@pytest.mark.e2e
def test_cli_history_list_json_has_no_runs(
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
) -> None:
    root = workspace()
    arguments = ["history", "list", "--json", "--root", str(root.root)]
    result = run_cli(root.root, arguments)

    # History command contract.
    summary = {"exit_code": result.exit_code, "payload": json.loads(result.stdout)}
    expected = {"exit_code": 0, "payload": {"runs": []}}
    record("E5-history-empty", root, [(arguments, result)], summary, expected)
