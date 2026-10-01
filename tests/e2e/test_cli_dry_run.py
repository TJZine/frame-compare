"""E3: dry-run planning through the real console entry point."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from .conftest import CommandResult, Workspace, _write_artifact


def _workspace_listing(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


@pytest.mark.e2e
def test_cli_dry_run_is_side_effect_free(
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    artifact_root: Path,
) -> None:
    root = workspace(
        {
            "analysis": {
                "random_frame_count": 2,
                "dark_frame_count": 1,
                "bright_frame_count": 1,
                "random_seed": 7,
            },
            "slowpics": {"auto_upload": False},
            "tmdb": {"enabled": False},
            "report": {"auto_open": False},
        }
    )
    (root.input_dir / "reference.mkv").touch()
    (root.input_dir / "comparison.mkv").touch()
    before = _workspace_listing(root.root)
    arguments = [
        "run",
        "--root",
        str(root.root),
        "--json",
        "--dry-run",
        "--skip-metadata",
        "--no-upload",
    ]
    result = run_cli(root.root, arguments)
    payload: dict[str, Any] = json.loads(result.stdout)
    after = _workspace_listing(root.root)

    # Run output modes contract: successful dry-run JSON.
    summary = {
        "top_level_keys": sorted(payload),
        "reference_resolved_filename": payload["reference"]["resolved_filename"],
        "input_source_filenames": payload["input"]["source_filenames"],
        "selection": payload["selection"],
        "workspace_before": before,
        "workspace_after": after,
    }
    expected = {
        "top_level_keys": [
            "checks_not_performed",
            "dry_run",
            "input",
            "outputs",
            "publishing",
            "reference",
            "runtime_facts",
            "selection",
        ],
        "reference_resolved_filename": "comparison.mkv",
        "input_source_filenames": ["comparison.mkv", "reference.mkv"],
        "selection": {
            "analysis_metrics_required": True,
            "analysis_performance_mode": "quality",
            "bright_frame_count": 1,
            "dark_frame_count": 1,
            "motion_frame_count": 0,
            "random_frame_count": 2,
            "random_seed": 7,
            "requested_user_frames": [],
            "strategy": ["random", "dark", "bright"],
        },
        "workspace_before": before,
        "workspace_after": before,
    }
    _write_artifact(artifact_root, "E3-dry-run", arguments, root.root, result, summary)
    assert result.exit_code == 0
    assert summary == expected
