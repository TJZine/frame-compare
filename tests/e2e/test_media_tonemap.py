"""M4: the PQ/BT.2020 source receives the configured tonemap and RGB export."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.e2e.harness import CommandResult, Workspace, render_summary


@pytest.mark.e2e
@pytest.mark.vs_required
def test_media_hdr_tonemap(
    media_gate: None,
    media_files: dict[str, Path],
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
) -> None:
    root = workspace(
        {
            "analysis": {"random_frame_count": 0, "user_frames": [1, 2]},
            "audio_alignment": {"enable": False},
            "sources": {"reference": "reference.mkv"},
            "screenshots": {"overlay_mode": "none", "active_rect_detection": "provided"},
            "color": {"target_nits": 200},
        }
    )
    shutil.copy2(media_files["hdr"], root.input_dir / "reference.mkv")
    shutil.copy2(media_files["sdr"], root.input_dir / "comparison.mkv")
    arguments = ["run", "--json", "--skip-metadata", "--no-upload", "--root", str(root.root)]
    result = run_cli(root.root, arguments, timeout=60)
    summary, run_dir, report = render_summary(result)
    settings = report["rendering"]["tonemap"]["settings"]
    summary["tonemap"] = (
        None
        if settings is None
        else {"preset": settings["preset"], "target_nits": settings["target_nits"]}
    )
    # Tonemap Preset And Target Resolution and Report And Overlay Metadata Contract.
    expected = {
        "success": True,
        "frame_count": 2,
        "clips_processed": 2,
        "cache_hit": False,
        "errors": [],
        "status": "completed",
        "clip_count": 2,
        "selected_frame_count": 2,
        "metrics_cache_status": "skipped",
        "frames": [
            [1, "user", [["reference", 1], ["comparison", 1]]],
            [2, "user", [["reference", 2], ["comparison", 2]]],
        ],
        "screenshots": [
            ["screenshots/1 - comparison.png", "RGB", [128, 72]],
            ["screenshots/1 - reference.png", "RGB", [64, 48]],
            ["screenshots/2 - comparison.png", "RGB", [128, 72]],
            ["screenshots/2 - reference.png", "RGB", [64, 48]],
        ],
        "tonemap": {"preset": "reference", "target_nits": 200},
    }
    record("M4-tonemap", root, [(arguments, result)], summary, expected, run_dir)
