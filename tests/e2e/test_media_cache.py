"""M3: cache reuse, explicit bypass, corruption refusal and persisted history."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.e2e.harness import ArtifactStep, CommandResult, Workspace, render_summary


@pytest.mark.e2e
@pytest.mark.vs_required
def test_media_cache_lifecycle(
    media_gate: None,
    media_files: dict[str, Path],
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
) -> None:
    root = workspace(
        {
            "analysis": {
                "random_frame_count": 0,
                "dark_frame_count": 1,
                "bright_frame_count": 1,
                "min_window_seconds": 0,
            },
            "audio_alignment": {"enable": False},
            "sources": {"reference": "reference.mkv"},
            "screenshots": {"overlay_mode": "none", "active_rect_detection": "provided"},
        }
    )
    for name in ("reference.mkv", "comparison.mkv"):
        shutil.copy2(media_files["sdr"], root.input_dir / name)
    base_arguments = ["run", "--json", "--skip-metadata", "--no-upload", "--root", str(root.root)]
    steps: list[ArtifactStep] = []
    runs = []
    run_dir = None
    for flags in ([], [], ["--from-cache-only"], ["--no-cache"]):
        arguments = [*base_arguments, *flags]
        result = run_cli(root.root, arguments, timeout=60)
        steps.append((arguments, result))
        rendered, run_dir, report = render_summary(result)
        runs.append(
            {
                "exit_code": result.exit_code,
                "metrics_cache_status": rendered["metrics_cache_status"],
                "frames": [frame["number"] for frame in report["frames"]],
            }
        )
    cache_files = list((root.generated_dir / "cache" / "analysis").glob("*.compframes"))
    assert len(cache_files) == 1
    # Preserve the header/version and truncate the compressed metrics payload.
    cache_file = cache_files[0]
    content = cache_file.read_bytes()
    cache_file.write_bytes(content[: len(content) // 2])
    before = sorted(
        path.name for path in root.generated_dir.iterdir() if path.is_dir() and path.name != "cache"
    )
    arguments = [*base_arguments, "--from-cache-only"]
    corrupted = run_cli(root.root, arguments, timeout=60)
    steps.append((arguments, corrupted))
    error = json.loads(corrupted.stdout)["error"]
    after = sorted(
        path.name for path in root.generated_dir.iterdir() if path.is_dir() and path.name != "cache"
    )
    arguments = ["history", "list", "--json", "--root", str(root.root)]
    history = run_cli(root.root, arguments, timeout=30)
    steps.append((arguments, history))
    assert history.exit_code == 0, history.stderr
    summary = {
        "runs": runs,
        "corrupted": {
            "exit_code": corrupted.exit_code,
            "error_code": error["code"],
            "error_name": error["name"],
            "no_new_run_folder": before == after,
        },
        "history": sorted(
            [entry["name"], entry["status"], entry["report_available"]]
            for entry in json.loads(history.stdout)["runs"]
        ),
    }
    # Cache Mode Semantics and History Command Contract.
    expected = {
        "runs": [
            {"exit_code": 0, "metrics_cache_status": "miss", "frames": [0, 11]},
            {"exit_code": 0, "metrics_cache_status": "hit", "frames": [0, 11]},
            {"exit_code": 0, "metrics_cache_status": "hit", "frames": [0, 11]},
            {"exit_code": 0, "metrics_cache_status": "miss", "frames": [0, 11]},
        ],
        "corrupted": {
            "exit_code": 5,
            "error_code": "FC-4006",
            "error_name": "CACHE_CORRUPTION",
            "no_new_run_folder": True,
        },
        "history": [
            ["reference + comparison", "completed", True],
            ["reference + comparison_2", "completed", True],
            ["reference + comparison_3", "completed", True],
            ["reference + comparison_4", "completed", True],
        ],
    }
    record("M3-cache", root, steps, summary, expected, run_dir)
