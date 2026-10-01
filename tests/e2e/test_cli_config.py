"""E4: config and preset persistence through the real console entry point."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from .conftest import CommandResult, Workspace, _write_artifact


def _run(
    run_cli: Callable[..., CommandResult],
    root: Workspace,
    arguments: list[str],
) -> CommandResult:
    return run_cli(root.root, [*arguments, "--root", str(root.root)])


@pytest.mark.e2e
def test_cli_config_and_preset_persistence(
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    artifact_root: Path,
) -> None:
    root = workspace()
    (root.input_dir / "reference.mkv").touch()
    (root.input_dir / "comparison.mkv").touch()

    write_arguments = [
        "run",
        "--write-config",
        "--frames",
        "3,7",
        "--random-frame-count",
        "2",
        "--dark-frame-count",
        "1",
        "--seed",
        "99",
        "--skip-metadata",
        "--no-upload",
    ]
    write_result = _run(run_cli, root, write_arguments)
    before_result = _run(
        run_cli,
        root,
        ["run", "--dry-run", "--json", "--skip-metadata", "--no-upload"],
    )
    before_selection = json.loads(before_result.stdout)["selection"]
    save_result = _run(run_cli, root, ["preset", "save", "p1"])
    list_result = _run(run_cli, root, ["preset", "list"])
    change_result = _run(
        run_cli,
        root,
        [
            "run",
            "--write-config",
            "--frames",
            "5",
            "--random-frame-count",
            "1",
            "--dark-frame-count",
            "0",
            "--seed",
            "7",
            "--skip-metadata",
            "--no-upload",
        ],
    )
    apply_result = _run(run_cli, root, ["preset", "apply", "p1"])
    after_result = _run(
        run_cli,
        root,
        ["run", "--dry-run", "--json", "--skip-metadata", "--no-upload"],
    )
    after_selection = json.loads(after_result.stdout)["selection"]

    # Persistence rules and preset command contract.
    summary = {
        "exit_codes": {
            "write_config": write_result.exit_code,
            "dry_run_before": before_result.exit_code,
            "preset_save": save_result.exit_code,
            "preset_list": list_result.exit_code,
            "change_config": change_result.exit_code,
            "preset_apply": apply_result.exit_code,
            "dry_run_after": after_result.exit_code,
        },
        "selection_after_step_2": before_selection,
        "selection_after_step_5": after_selection,
        "preset_list": [line for line in list_result.stdout.splitlines() if line],
    }
    expected = {
        "exit_codes": {
            "write_config": 0,
            "dry_run_before": 0,
            "preset_save": 0,
            "preset_list": 0,
            "change_config": 0,
            "preset_apply": 0,
            "dry_run_after": 0,
        },
        "selection_after_step_2": {
            "analysis_metrics_required": True,
            "analysis_performance_mode": "quality",
            "bright_frame_count": 0,
            "dark_frame_count": 1,
            "motion_frame_count": 0,
            "random_frame_count": 2,
            "random_seed": 99,
            "requested_user_frames": [3, 7],
            "strategy": ["user", "random", "dark"],
        },
        "selection_after_step_5": {
            "analysis_metrics_required": True,
            "analysis_performance_mode": "quality",
            "bright_frame_count": 0,
            "dark_frame_count": 1,
            "motion_frame_count": 0,
            "random_frame_count": 2,
            "random_seed": 99,
            "requested_user_frames": [3, 7],
            "strategy": ["user", "random", "dark"],
        },
        "preset_list": ["p1"],
    }
    _write_artifact(
        artifact_root, "E4-config-persistence", [*write_arguments], root.root, after_result, summary
    )
    assert summary == expected
