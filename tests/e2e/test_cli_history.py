"""E5: empty history through the real console entry point."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
import tomli_w

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


@pytest.mark.e2e
def test_cli_history_list_json_isolates_oversized_record(
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
) -> None:
    root = workspace()
    valid = root.generated_dir / "Valid"
    broken = root.generated_dir / "Broken"
    valid.mkdir()
    broken.mkdir()
    payload = {
        "version": 1,
        "status": "completed",
        "started_at": "2026-07-14T12:00:00Z",
        "completed_at": "2026-07-14T12:00:05Z",
        "duration_seconds": 5.0,
        "clip_count": 0,
        "selected_frame_count": 0,
        "warning_count": 0,
        "warning_summaries": [],
        "metrics_cache_status": "skipped",
        "phase_timings": {},
        "slowpics": {"outcome": "not_uploaded"},
    }
    (valid / "run_result.toml").write_text(tomli_w.dumps(payload), encoding="utf-8")
    broken_payload = {**payload, "duration_seconds": 10**400}
    (broken / "run_result.toml").write_text(tomli_w.dumps(broken_payload), encoding="utf-8")

    arguments = ["history", "list", "--json", "--root", str(root.root)]
    result = run_cli(root.root, arguments)

    assert result.exit_code == 0, result.stderr
    listed = json.loads(result.stdout)["runs"]
    summary = {
        "exit_code": result.exit_code,
        "runs": sorted([[entry["name"], entry["status"]] for entry in listed]),
        "warning_on_stderr": "Broken" in result.stderr
        and "unreadable or unsupported" in result.stderr,
    }
    expected = {
        "exit_code": 0,
        "runs": [["Broken", "unavailable"], ["Valid", "completed"]],
        "warning_on_stderr": True,
    }
    record("E5-history-oversized", root, [(arguments, result)], summary, expected)
