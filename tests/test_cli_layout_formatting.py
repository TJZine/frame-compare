from pathlib import Path
from typing import Any, Dict

from rich.console import Console
from rich.progress import BarColumn

import src.cli_layout as cli_layout

from src.cli_layout import (
    CliLayoutRenderer,
    LayoutContext,
    _AnsiColorMapper,
    _ANSI_ESCAPE_RE,
    load_cli_layout,
)


def _project_root() -> Path:
    """
    Get the project's root directory.
    
    Returns:
        Path: Path object pointing to the project's root directory (two levels above this file).
    """
    return Path(__file__).resolve().parent.parent


def _sample_values(tmp_path: Path) -> Dict[str, Any]:
    """
    Constructs a nested dictionary of representative sample values for CLI layout tests.
    
    Parameters:
        tmp_path (Path): Base temporary directory used to build sample file paths referenced in the returned data.
    
    Returns:
        Dict[str, Any]: A dictionary containing test-ready sections such as `clips`, `trims`, `window`, `alignment`, `analysis`, `audio_alignment`, `render`, `tonemap`, `verify`, `overlay`, `cache`, `tmdb`, `overrides`, `warnings`, `slowpics`, and `audio_alignment_map`. The entries provide realistic example values (including file paths rooted at `tmp_path`) for use by renderer and layout tests.
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


def _make_renderer(width: int, *, no_color: bool = True) -> CliLayoutRenderer:
    """
    Create a CliLayoutRenderer configured with a Console of the given width and color settings.
    
    Parameters:
        width (int): Console width in characters used to construct the renderer's Console.
        no_color (bool): If True, disable ANSI/color output; if False, enable the standard color system.
    
    Returns:
        CliLayoutRenderer: Renderer initialized with the 'cli_layout.v1.json' layout and a Console matching the requested width and color settings.
    """
    layout_path = _project_root() / "cli_layout.v1.json"
    layout = load_cli_layout(layout_path)
    color_system = None if no_color else "standard"
    console = Console(width=width, record=True, color_system=color_system)
    return CliLayoutRenderer(layout, console, quiet=False, verbose=False, no_color=no_color)


def test_color_mapper_token_to_ansi_16(monkeypatch):
    monkeypatch.delenv("COLORTERM", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "vt100")
    mapper = _AnsiColorMapper(no_color=False)
    styled = mapper.apply("cyan.bold", "demo")
    assert styled.startswith("\x1b[1;36m")
    assert styled.endswith("\x1b[0m")


def test_color_mapper_token_to_ansi_256(monkeypatch):
    monkeypatch.setenv("COLORTERM", "truecolor")
    monkeypatch.delenv("NO_COLOR", raising=False)
    mapper = _AnsiColorMapper(no_color=False)
    styled = mapper.apply("grey.dim", "demo")
    assert "\x1b[2;38;5;240m" in styled
    assert styled.endswith("\x1b[0m")


def test_renderer_path_ellipsis_middle(tmp_path):
    renderer = _make_renderer(60)
    long_path = str(tmp_path / "very" / "deep" / "folder" / "structure" / "file.mkv")
    truncated = renderer.apply_path_ellipsis(long_path)
    assert truncated.endswith("file.mkv")
    assert "…" in truncated


def test_list_section_two_column_layout(tmp_path):
    values: Dict[str, Any] = _sample_values(tmp_path)
    flags: Dict[str, Any] = {}

    wide_renderer = _make_renderer(140)
    wide_renderer.render_section(
        next(section for section in wide_renderer.layout.sections if section["id"] == "summary"),
        values,
        flags,
    )
    wide_output = wide_renderer.console.export_text()
    assert "    •" in wide_output

    narrow_renderer = _make_renderer(90)
    narrow_renderer.render_section(
        next(section for section in narrow_renderer.layout.sections if section["id"] == "summary"),
        values,
        flags,
    )
    narrow_output = narrow_renderer.console.export_text()
    assert "    •" not in narrow_output


def test_highlight_markup_and_spans(tmp_path, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    renderer = _make_renderer(100, no_color=False)
    values = _sample_values(tmp_path)
    flags: Dict[str, Any] = {}
    context = LayoutContext(values, flags, renderer=renderer)

    token_markup = renderer._render_token("render.add_frame_info", context)
    assert token_markup == "[[bool_true]]true[[/]]"

    wrapped = f"[[value]]{token_markup}[[/]]"
    colored_output = renderer._prepare_output(wrapped)
    assert colored_output == renderer._colorize("bool_true", "true")

    padded_token = renderer._render_token("analysis.counts.motion:>5", context)
    assert padded_token.startswith(" ")
    padded_prepared = renderer._prepare_output(padded_token)
    leading_spaces = len(padded_prepared) - len(padded_prepared.lstrip(" "))
    assert leading_spaces > 0
    numeric_segment = padded_prepared[leading_spaces:]
    assert numeric_segment == renderer._colorize("accent_analyze", "4")

    renderer_no_color = _make_renderer(100)
    context_no_color = LayoutContext(values, flags, renderer=renderer_no_color)
    token_plain = renderer_no_color._render_token("render.add_frame_info", context_no_color)
    assert renderer_no_color._prepare_output(f"[[value]]{token_plain}[[/]]") == "true"


def _render_section(renderer: CliLayoutRenderer, section_id: str, values: Dict[str, Any], flags: Dict[str, Any]) -> list[str]:
    """
    Render a layout section by id and return the rendered console output as lines.
    
    Binds the provided values and flags to the renderer, renders the section identified by `section_id`, and captures the console output.
    
    Parameters:
        renderer (CliLayoutRenderer): The renderer used to render the layout section.
        section_id (str): Identifier of the section in the renderer's layout to render.
        values (Dict[str, Any]): Data values used to populate the layout tokens.
        flags (Dict[str, Any]): Feature and formatting flags that affect rendering.
    
    Returns:
        list[str]: The rendered console output split into lines, with trailing newline characters removed.
    """
    renderer.bind_context(values, flags)
    section = next(sec for sec in renderer.layout.sections if sec.get("id") == section_id)
    renderer.render_section(section, values, flags)
    return [line.rstrip("\n") for line in renderer.console.export_text().splitlines()]


def test_progress_style_toggle(tmp_path):
    values = _sample_values(tmp_path)
    renderer = _make_renderer(100, no_color=True)

    renderer.bind_context(values, {"progress_style": "fill"})
    progress_fill = renderer.create_progress("render_bar")
    try:
        assert any(isinstance(column, BarColumn) for column in progress_fill.columns)
    finally:
        progress_fill.stop()

    renderer.bind_context(values, {"progress_style": "dot"})
    progress_dot = renderer.create_progress("render_bar")
    try:
        assert any(isinstance(column, cli_layout._DotProgressColumn) for column in progress_dot.columns)
    finally:
        progress_dot.stop()


def test_group_subheading_prefix_ascii_and_unicode(tmp_path):
    values = _sample_values(tmp_path)
    shared_flags = {"tmdb_resolved": True, "upload_enabled": False}

    ascii_renderer = _make_renderer(100, no_color=True)
    ascii_flags = {**shared_flags, "verbose": False, "quiet": False, "no_color": True}
    ascii_lines = [_ANSI_ESCAPE_RE.sub("", line).strip() for line in _render_section(ascii_renderer, "render", values, ascii_flags)]
    assert any(line.startswith("> Writer") for line in ascii_lines)

    unicode_renderer = _make_renderer(100, no_color=False)
    unicode_flags = {**shared_flags, "verbose": False, "quiet": False, "no_color": False}
    unicode_lines = [_ANSI_ESCAPE_RE.sub("", line).strip() for line in _render_section(unicode_renderer, "render", values, unicode_flags)]
    assert any(line.startswith("› Writer") for line in unicode_lines)


def test_group_rule_omitted_on_narrow_terminal(tmp_path):
    values = _sample_values(tmp_path)
    renderer = _make_renderer(70, no_color=True)
    flags = {"verbose": True, "quiet": False, "no_color": True}
    lines = [_ANSI_ESCAPE_RE.sub("", line) for line in _render_section(renderer, "render", values, flags)]

    legend_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("> Legend"))
    legend_follow = next((line for line in lines[legend_idx + 1 :] if line.strip()), "")
    assert legend_follow and set(legend_follow.strip()) != {"-"}

    writer_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("> Writer"))
    writer_follow = next((line for line in lines[writer_idx + 1 :] if line.strip()), "")
    assert writer_follow and set(writer_follow.strip()) != {"-"}


def test_group_rule_matches_label_width(tmp_path):
    values = _sample_values(tmp_path)
    renderer = _make_renderer(120, no_color=True)
    flags = {"verbose": True, "quiet": False, "no_color": True}
    lines = [_ANSI_ESCAPE_RE.sub("", line) for line in _render_section(renderer, "render", values, flags)]

    writer_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("> Writer"))
    writer_rule = next((line for line in lines[writer_idx + 1 :] if line.strip()), "")
    assert writer_rule
    expected_width = len("> Writer") + 2
    assert len(writer_rule.strip()) == expected_width
