import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cli_layout import CliLayoutRenderer, LayoutContext, load_cli_layout


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _sample_values(tmp_path: Path) -> Dict[str, Any]:
    sample_clips = [
        {
            "label": "Reference",
            "width": 1920,
            "height": 1080,
            "fps": 23.976,
            "frames": 240,
            "duration": 10.0,
            "duration_tc": "00:00:10.0",
            "path": str(tmp_path / "ref.mkv"),
        },
        {
            "label": "Target",
            "width": 1920,
            "height": 1080,
            "fps": 23.976,
            "frames": 240,
            "duration": 10.0,
            "duration_tc": "00:00:10.0",
            "path": str(tmp_path / "tgt.mkv"),
        },
    ]

    return {
        "clips": {
            "count": len(sample_clips),
            "items": sample_clips,
            "ref": sample_clips[0],
            "tgt": sample_clips[1],
        },
        "trims": {
            "ref": {"lead_f": 5, "trail_f": 0, "lead_s": 0.21, "trail_s": 0.0},
            "tgt": {"lead_f": 3, "trail_f": 2, "lead_s": 0.12, "trail_s": 0.08},
        },
        "window": {
            "ignore_lead_seconds": 0.5,
            "ignore_trail_seconds": 0.5,
            "min_window_seconds": 5.0,
        },
        "alignment": {
            "manual_start_s": 0.0,
            "manual_end_s": None,
        },
        "analysis": {
            "step": 2,
            "downscale_height": 540,
            "motion_method": "edge",
            "motion_scenecut_quantile": 0.2,
            "motion_diff_radius": 2,
            "counts": {
                "dark": 4,
                "bright": 4,
                "motion": 4,
                "random": 0,
                "user": 0,
            },
            "screen_separation_sec": 1.0,
            "random_seed": 1234,
            "kept": 6,
            "scanned": 12,
            "output_frame_count": 6,
            "output_frames_preview": "0, 10, 20, …, 110, 120, 130",
        },
        "audio_alignment": {
            "enabled": True,
            "offsets_sec": 0.123,
            "offsets_frames": 3,
            "corr": 0.95,
            "threshold": 0.5,
            "offsets_filename": str(tmp_path / "align.toml"),
            "preview_paths": [str(tmp_path / "a.wav"), str(tmp_path / "b.wav")],
            "confirmed": "auto",
            "reference_stream": "Reference->ac3/en/5.1",
            "target_stream": "Target->aac/en/5.1",
        },
        "render": {
            "writer": "VS",
            "out_dir": str(tmp_path / "out"),
            "add_frame_info": True,
            "single_res": 0,
            "upscale": True,
            "mod_crop": 2,
            "letterbox_pillarbox_aware": True,
            "pad_to_canvas": "off",
            "center_pad": False,
            "letterbox_px_tolerance": 4,
            "compression": 3,
        },
        "tonemap": {
            "preset": "reference",
            "tone_curve": "bt.2390",
            "dynamic_peak_detection": True,
            "target_nits": 100.0,
            "verify_luma_threshold": 0.1,
        },
        "verify": {
            "count": 1,
            "threshold": 0.1,
            "delta": {
                "max": 0.05,
                "average": 0.02,
                "frame": 12,
                "file": str(tmp_path / "ref.mkv"),
                "auto_selected": True,
            },
            "entries": [],
        },
        "overlay": {
            "enabled": True,
            "template": "Overlay {frame}",
            "mode": "minimal",
        },
        "cache": {
            "file": "cache.bin",
            "status": "reused",
        },
        "tmdb": {
            "category": "movie",
            "id": "100",
            "title": "Sample Title",
            "year": "2024",
            "lang": "en",
        },
        "overrides": {
            "change_fps": "none",
        },
        "warnings": [
            {
                "warning.type": "general",
                "warning.count": 1,
                "warning.labels": "demo warning",
            }
        ],
        "slowpics": {
            "enabled": False,
            "title": {"inputs": {"resolved_base": None, "collection_name": None, "collection_suffix": ""}, "final": None},
            "url": None,
            "shortcut_path": None,
            "deleted_screens_dir": False,
            "is_public": True,
            "is_hentai": False,
            "remove_after_days": 0,
        },
        "audio_alignment_map": {},
    }


def test_layout_renderer_sample_output(tmp_path, monkeypatch):
    """
    Exercise CliLayoutRenderer with synthetic sample values and assert that rendering, token evaluation, and console output meet expected structure and content.
    
    Performs these checks:
    - Binds sample values and flags to the renderer and verifies simple template resolution.
    - Renders and validates token highlighting, conditional token splitting, and conditional rendering that includes TMDB identifiers.
    - Renders every layout section without error.
    - Prints a JSON snippet to the console and verifies exported text contains required section markers (Frame Compare, DISCOVER, PREPARE, ANALYZE, RENDER, PUBLISH, WARNINGS, SUMMARY).
    - Verifies presence and formatting of the Legend divider, that the Writer block precedes the Canvas block with a blank line between, and that box-drawing characters ("┌", "└") appear.
    - Ensures no output line exceeds the console width and that the printed JSON is syntactically valid.
    """
    layout_path = _project_root() / "cli_layout.v1.json"
    layout = load_cli_layout(layout_path)
    console = Console(width=100, record=True, color_system=None)
    renderer = CliLayoutRenderer(
        layout,
        console,
        quiet=False,
        verbose=True,
        no_color=True,
    )

    sample_values = _sample_values(tmp_path)
    flags: Dict[str, Any] = {
        "tmdb_resolved": True,
        "upload_enabled": False,
        "verbose": True,
        "quiet": False,
        "no_color": True,
    }

    renderer.bind_context(sample_values, flags)
    layout_context = LayoutContext(sample_values, flags, renderer=renderer)
    assert layout_context.resolve("clips.count") == sample_values["clips"]["count"]

    rendered_check = renderer.render_template("{clips.count}", sample_values, flags)
    assert rendered_check.strip() == "2"
    highlight_markup = renderer._render_token("render.add_frame_info", layout_context)
    assert highlight_markup == "[[bool_true]]True[[/]]"
    assert renderer._prepare_output(highlight_markup) == "True"
    token = "tmdb_resolved?`TMDB: ${tmdb.category}/${tmdb.id}`:''"
    context_obj = LayoutContext(sample_values, flags, renderer=renderer)
    assert renderer._find_conditional_split(token) is not None
    rendered_token = renderer._render_token(token, context_obj)
    assert "movie/100" in rendered_token
    tmdb_line = renderer.render_template(f"{{{token}}}", sample_values, flags)
    remainder = "`TMDB: ${tmdb.category}/${tmdb.id}`:''"
    split_index = renderer._find_matching_colon(remainder)
    assert split_index is not None
    assert "movie/100" in tmdb_line

    for section in layout.sections:
        renderer.render_section(section, sample_values, flags)

    sample_json = {
        "analysis": sample_values["analysis"],
        "render": sample_values["render"],
    }
    console.print(json.dumps(sample_json))

    output_text = console.export_text()
    lines = [line.rstrip("\n") for line in output_text.splitlines()]

    required_markers = [
        "Frame Compare",
        "[DISCOVER]",
        "[PREPARE]",
        "[PREPARE · Audio]",
        "[ANALYZE]",
        "[RENDER]",
        "[PUBLISH]",
        "[WARNINGS]",
        "[SUMMARY]",
    ]
    for marker in required_markers:
        assert any(marker in line for line in lines), marker

    assert any(line.strip().startswith("> Legend") for line in lines)
    legend_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("> Legend"))
    assert legend_idx + 1 < len(lines)
    assert set(lines[legend_idx + 1].strip()) <= {"-"}, "Legend divider missing"

    writer_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("> Writer"))
    canvas_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("> Canvas"))
    assert writer_idx < canvas_idx
    assert any(lines[i] == "" for i in range(writer_idx, canvas_idx)), "Expected blank line between Writer and Canvas blocks"

    assert any(line.startswith("┌") for line in lines)
    assert any(line.startswith("└") for line in lines)

    width = console.width or 100
    for line in lines:
        assert len(line) <= width

    assert any(line.strip().startswith("{") for line in lines)
    json.loads(json.dumps(sample_json))


def test_layout_expression_rejects_dunder_access(tmp_path):
    layout_path = _project_root() / "cli_layout.v1.json"
    layout = load_cli_layout(layout_path)
    console = Console(width=100, record=True, color_system=None)
    renderer = CliLayoutRenderer(layout, console, quiet=False, verbose=False, no_color=True)
    sample_values = _sample_values(tmp_path)
    flags: Dict[str, Any] = {"verbose": False, "quiet": False, "no_color": True}
    renderer.bind_context(sample_values, flags)
    context = LayoutContext(sample_values, flags, renderer=renderer)

    assert context.resolve("clips.ref.__class__") is None

    assert renderer._evaluate_expression("clips.ref.__class__", context) is None
    assert not renderer._evaluate_condition("clips.ref.__class__", context)

    assert renderer._evaluate_expression("tonemap.verify_luma_threshold * 0.9", context) == pytest.approx(
        0.09
    )

    assert renderer._evaluate_expression("__import__('os')", context) is None