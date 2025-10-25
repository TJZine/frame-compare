import json
from pathlib import Path
from typing import Any, Dict

import pytest
from rich.console import Console

import frame_compare
import src.cli_layout as cli_layout
from src.cli_layout import CliLayoutRenderer, LayoutContext, _AnsiColorMapper, load_cli_layout


def _project_root() -> Path:
    """
    Get the project's root directory.

    Returns:
        Path: Path to the project root (the parent of this file's parent).
    """
    return Path(__file__).resolve().parent.parent


def _sample_values(tmp_path: Path) -> Dict[str, Any]:
    """
    Constructs a representative sample configuration dictionary used by CLI layout rendering tests.

    Parameters:
        tmp_path (Path): Temporary directory used to construct sample file and output paths.

    Returns:
        sample_values (Dict[str, Any]): A nested dictionary containing test-ready configuration and metadata, including:
            - clips: clip count, list of clip items and explicit ref/tgt entries.
            - trims: per-clip lead/trail frame and second values.
            - window: ignore and minimum window durations.
            - alignment: manual alignment start/end values.
            - analysis: analysis parameters and summary counts/previews.
            - audio_alignment: alignment metadata, offsets, preview paths and selected streams.
            - render: rendering options and output directory.
            - tonemap: tonemapping settings and verification threshold.
            - verify: verification thresholds, delta summary and entries.
            - overlay: overlay enablement, template and mode.
            - cache: cache file and status.
            - tmdb: media metadata (category, id, title, year, lang).
            - overrides: runtime overrides (e.g., change_fps).
            - warnings: list of warning records.
            - slowpics: slowpic-related settings and metadata.
            - audio_alignment_map: mapping structure for audio alignments (empty by default).
    """
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

    script_path = tmp_path / "vspreview_script.py"
    manual_command = frame_compare._format_vspreview_manual_command(script_path)

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
            "output_frames_full": "[0, 10, 20, …, 110, 120, 130]",
            "cache_progress_message": "Loading cached frame metrics from cache.bin…",
        },
        "audio_alignment": {
            "enabled": True,
            "use_vspreview": True,
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
        "vspreview": {
            "mode": "baseline",
            "mode_display": "baseline (0f applied to both clips)",
            "suggested_frames": 3,
            "suggested_seconds": 0.125,
            "script_path": str(script_path),
            "script_command": manual_command,
            "missing": {
                "active": False,
                "windows_install": frame_compare._VSPREVIEW_WINDOWS_INSTALL,
                "posix_install": frame_compare._VSPREVIEW_POSIX_INSTALL,
                "command": "",
                "reason": "",
            },
            "clips": {
                "ref": {"label": "Reference"},
                "tgt": {"label": "Target"},
            },
        },
        "render": {
            "writer": "vs",
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
        "emit_json_tail": False,
    }

    renderer.bind_context(sample_values, flags)
    layout_context = LayoutContext(sample_values, flags, renderer=renderer)
    assert layout_context.resolve("clips.count") == sample_values["clips"]["count"]

    rendered_check = renderer.render_template("{clips.count}", sample_values, flags)
    assert rendered_check.strip() == "2"
    highlight_markup = renderer._render_token("render.add_frame_info", layout_context)
    assert highlight_markup == "[[bool_true]]true[[/]]"
    assert renderer._prepare_output(highlight_markup) == "true"
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
        "VSPreview Information",
        "At-a-Glance",
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

    assert any("writer=vs" in line for line in lines)
    assert not any("writer=writer" in line for line in lines)
    assert any("add_frame_info=true" in line for line in lines)
    assert not any("template=" in line for line in lines)

    info_index = next(i for i, line in enumerate(lines) if "VSPreview Information" in line)
    glance_index = next(i for i, line in enumerate(lines) if "At-a-Glance" in line)
    assert info_index < glance_index

    assert any("Loading cached frame metrics from" in line for line in lines)
    canvas_line = next(line for line in lines if "Canvas single_res" in line)
    assert "crop mod" not in canvas_line

    header_idx = next(i for i, line in enumerate(lines) if "Output frames (6)" in line)
    header_line = lines[header_idx]
    assert header_line.lstrip().startswith("• Output frames (6)")

    assert header_idx + 1 < len(lines), "Expected detail line after Output frames header"
    detail_line = lines[header_idx + 1]
    header_indent = len(header_line) - len(header_line.lstrip())
    detail_indent = len(detail_line) - len(detail_line.lstrip())
    assert detail_indent == header_indent + 2
    assert "[0, 10, 20" in detail_line

    section_logs = [line for line in lines if "section[" in line and "header role" in line]
    for expected in (
        "section[discover] header role → section_discover",
        "section[prepare] header role → section_prepare",
        "section[audio_align] header role → section_prepare",
        "section[analyze] header role → section_analyze",
        "section[render] header role → section_render",
        "section[publish] header role → section_publish",
        "section[warnings] header role → section_warnings",
        "section[summary] header role → section_summary",
    ):
        assert any(expected in log for log in section_logs), expected


def test_layout_renders_vspreview_missing_panel(tmp_path: Path) -> None:
    layout_path = _project_root() / "cli_layout.v1.json"
    layout = load_cli_layout(layout_path)
    console = Console(width=100, record=True, color_system=None)
    renderer = CliLayoutRenderer(layout, console, quiet=False, verbose=False, no_color=True)

    sample_values = _sample_values(tmp_path)
    sample_values["vspreview"]["missing"]["active"] = True
    sample_values["vspreview"]["missing"]["command"] = sample_values["vspreview"]["script_command"]
    sample_values["vspreview"]["script_path"] = str(tmp_path / "vspreview_script.py")

    flags: Dict[str, Any] = {"verbose": False, "quiet": False, "no_color": True}
    renderer.bind_context(sample_values, flags)
    missing_section = next(section for section in layout.sections if section["id"] == "vspreview_missing")
    renderer.render_section(missing_section, sample_values, flags)

    output_text = console.export_text()
    assert "VSPreview dependency missing" in output_text
    assert frame_compare._VSPREVIEW_WINDOWS_INSTALL in output_text
    python_executable = frame_compare.sys.executable or "python"
    assert python_executable in output_text
    assert " -m vspreview" in output_text


def test_summary_output_frames_full_list_without_ellipsis(tmp_path: Path) -> None:
    layout_path = _project_root() / "cli_layout.v1.json"
    layout = load_cli_layout(layout_path)
    console = Console(width=160, record=True, color_system=None)
    renderer = CliLayoutRenderer(layout, console, quiet=False, verbose=False, no_color=True)

    sample_values = _sample_values(tmp_path)
    long_frames = ", ".join(str(index) for index in range(50))
    sample_values["analysis"]["output_frames_full"] = f"[{long_frames}]"
    sample_values["analysis"]["output_frame_count"] = 50
    sample_values["analysis"]["output_frames_preview"] = "0, 1, 2, 3"

    flags: Dict[str, Any] = {
        "emit_json_tail": False,
        "verbose": False,
        "quiet": False,
        "no_color": True,
    }

    renderer.bind_context(sample_values, flags)
    summary_section = next(section for section in layout.sections if section["id"] == "summary")
    renderer.render_section(summary_section, sample_values, flags)

    output_text = console.export_text()
    normalized = " ".join(line.strip() for line in output_text.splitlines() if line.strip())

    assert "• Output frames (50)" in normalized
    assert f"[{long_frames}]" in normalized

    summary_start = normalized.index("• Output frames (50)")
    summary_text = normalized[summary_start:]
    assert "…" not in summary_text


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


def test_windows_terminal_enables_256_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Windows Terminal environments are detected as 256-color capable."""

    layout_path = _project_root() / "cli_layout.v1.json"
    monkeypatch.delenv("COLORTERM", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_FORCE_256_COLOR", raising=False)
    monkeypatch.setenv("TERM_PROGRAM", "Windows_Terminal")
    monkeypatch.setattr(cli_layout.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        _AnsiColorMapper,
        "_enable_windows_vt_mode",
        staticmethod(lambda: None),
    )

    capability = _AnsiColorMapper._detect_capability()
    assert capability == "256"

    mapper = _AnsiColorMapper(no_color=False)
    layout = load_cli_layout(layout_path)
    section_token = layout.theme.colors["section_analyze"]
    accent_token = layout.theme.colors["accent_subhead"]

    section = mapper._lookup(section_token)
    accent = mapper._lookup(accent_token)

    assert mapper._capability == "256"
    assert section.startswith("\x1b[")
    assert accent.startswith("\x1b[")
    assert section != accent


def test_force_256_color_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit override should force the mapper into 256-color mode."""

    monkeypatch.setenv("FRAME_COMPARE_FORCE_256_COLOR", "yes")
    monkeypatch.delenv("COLORTERM", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.setattr(
        _AnsiColorMapper,
        "_enable_windows_vt_mode",
        staticmethod(lambda: None),
    )

    capability = _AnsiColorMapper._detect_capability()
    assert capability == "256"

    mapper = _AnsiColorMapper(no_color=False)
    assert mapper._capability == "256"
