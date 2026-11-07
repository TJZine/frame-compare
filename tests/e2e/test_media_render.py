"""M1/M2: both real screenshot paths preserve metric selection and provenance."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.e2e.harness import CommandResult, Workspace, render_summary


@pytest.mark.e2e
@pytest.mark.vs_required
@pytest.mark.parametrize("use_ffmpeg", [False, True], ids=["M1-vapoursynth", "M2-ffmpeg"])
def test_media_render(
    media_gate: None,
    media_files: dict[str, Path],
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
    use_ffmpeg: bool,
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
            "screenshots": {
                "use_ffmpeg": use_ffmpeg,
                "overlay_mode": "none",
                "active_rect_detection": "provided",
            },
        }
    )
    for name in ("reference.mkv", "comparison.mkv"):
        shutil.copy2(media_files["sdr"], root.input_dir / name)
    arguments = [
        "run",
        "--json",
        "--skip-metadata",
        "--no-upload",
        "--root",
        str(root.root),
    ]
    result = run_cli(root.root, arguments, timeout=60)
    summary, run_dir, _ = render_summary(result)
    # Run output, cache semantics, report provenance and screenshot surface.
    expected = {
        "success": True,
        "frame_count": 2,
        "clips_processed": 2,
        "cache_hit": False,
        "errors": [],
        "status": "completed",
        "clip_count": 2,
        "selected_frame_count": 2,
        "metrics_cache_status": "miss",
        "frames": [
            [0, "quantile_dark", [["reference", 0], ["comparison", 0]]],
            [11, "quantile_bright", [["reference", 11], ["comparison", 11]]],
        ],
        "screenshots": [
            ["screenshots/0 - comparison.png", "RGB", [128, 72]],
            ["screenshots/0 - reference.png", "RGB", [128, 72]],
            ["screenshots/11 - comparison.png", "RGB", [128, 72]],
            ["screenshots/11 - reference.png", "RGB", [128, 72]],
        ],
    }
    record(
        "M2-ffmpeg" if use_ffmpeg else "M1-vapoursynth",
        root,
        [(arguments, result)],
        summary,
        expected,
        run_dir,
    )


@pytest.mark.e2e
@pytest.mark.vs_required
def test_metric_only_selection_failure_stops_before_render(
    media_gate: None,
    media_files: dict[str, Path],
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
) -> None:
    root = workspace(
        {
            "analysis": {
                "user_frames": [],
                "random_frame_count": 0,
                "dark_frame_count": 3,
                "performance_mode": "performance",
            },
            "audio_alignment": {"enable": False},
            "sources": {"reference": "reference.mkv"},
            "screenshots": {"use_ffmpeg": True, "active_rect_detection": "provided"},
        }
    )
    reference = root.input_dir / "reference.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(media_files["sdr"]),
            "-frames:v",
            "8",
            "-c:v",
            "copy",
            str(reference),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    shutil.copy2(reference, root.input_dir / "comparison.mkv")
    arguments = ["run", "--json", "--skip-metadata", "--no-upload", "--root", str(root.root)]
    result = run_cli(root.root, arguments, timeout=60)
    payload = json.loads(result.stdout)
    error = payload.get("error", {})
    render_started = False
    for line in result.stderr.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(event, dict)
            and event.get("event") == "phase_started"
            and event.get("phase") == "render"
        ):
            render_started = True
            break
    summary = {
        "exit_code": result.exit_code,
        "success": payload["success"],
        "error_code": error.get("code"),
        "selection_failure": error.get("details"),
        "render_started": render_started,
        "rendered": bool(list(root.generated_dir.rglob("*.png"))),
        "report": bool(list(root.generated_dir.rglob("report.html"))),
    }
    record(
        "metric-only-selection-failure",
        root,
        [(arguments, result)],
        summary,
        {
            "exit_code": 5,
            "success": False,
            "error_code": "FC-4012",
            "selection_failure": {"reason": "insufficient_candidates", "requested": 3, "found": 2},
            "render_started": False,
            "rendered": False,
            "report": False,
        },
    )
