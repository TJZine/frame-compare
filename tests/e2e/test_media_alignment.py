"""M5/M6: computed alignment either applies a verified delay or leaves frames alone."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

from tests.e2e.harness import CommandResult, Workspace, decode_frame_number, render_summary


@pytest.mark.e2e
@pytest.mark.vs_required
@pytest.mark.parametrize("comparison", ["delayed", "unrelated"], ids=["M5-applied", "M6-refused"])
def test_media_audio_alignment(
    media_gate: None,
    media_files: dict[str, Path],
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
    comparison: str,
) -> None:
    root = workspace(
        {
            "analysis": {"random_frame_count": 0, "user_frames": [16, 40, 72]},
            "sources": {"reference": "reference.mkv"},
            "screenshots": {"overlay_mode": "none", "active_rect_detection": "provided"},
            "audio_alignment": {"max_offset_seconds": 1},
        }
    )
    shutil.copy2(media_files["numbered"], root.input_dir / "reference.mkv")
    shutil.copy2(media_files[comparison], root.input_dir / "comparison.mkv")
    arguments = ["run", "--json", "--skip-metadata", "--no-upload", "--root", str(root.root)]
    result = run_cli(root.root, arguments, timeout=90)
    rendered, run_dir, report = render_summary(result)
    summary: dict[str, Any] = {
        "exit_code": result.exit_code,
        "status": rendered["status"],
        "source_frame_deltas": [
            frame["images"][1]["source_frame"] - frame["images"][0]["source_frame"]
            for frame in report["frames"]
        ],
    }
    # Config-Only Audio Alignment Surface: only trusted audio/video applies trims.
    if comparison == "delayed":
        summary["pattern_ids"] = [
            [decode_frame_number(run_dir / unquote(image["src"])) for image in frame["images"]]
            for frame in report["frames"]
        ]
        expected = {
            "exit_code": 0,
            "status": "completed",
            "source_frame_deltas": [4, 4, 4],
            "pattern_ids": [[16, 16], [40, 40], [72, 72]],
        }
        scenario = "M5-alignment-applied"
    else:
        events = []
        for line in result.stderr.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("event") == "audio_alignment_requires_review":
                events.append(event)
        assert len(events) == 1, result.stderr
        summary["reason"] = events[0]["reason"]
        summary["decision_state"] = events[0]["decision_state"]
        expected = {
            "exit_code": 0,
            "status": "completed_with_warnings",
            "source_frame_deltas": [0, 0, 0],
            "reason": "no_single_offset",
            "decision_state": "provisional",
        }
        scenario = "M6-alignment-refused"
    record(scenario, root, [(arguments, result)], summary, expected, run_dir)
