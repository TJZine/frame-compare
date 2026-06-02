"""HTML rendering for comparison reports."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from frame_compare.services.report.payload import REPORT_VERSION
from frame_compare.services.report.viewer import get_css, get_js

ALL_CATEGORY_FILTER_KEY = "__fc_all__"

if TYPE_CHECKING:
    from frame_compare.services.report.payload import (
        ReportClipPayload,
        ReportFramePayload,
        ReportPayload,
    )


def _esc_text(value: object) -> str:
    """Escape dynamic text for safe HTML interpolation."""
    return html.escape(str(value), quote=False)


def _esc_attr(value: object) -> str:
    """Escape dynamic values for safe HTML attribute interpolation."""
    return html.escape(str(value), quote=True)


def _safe_http_href(url: str | None) -> str | None:
    """Return an escaped http(s) URL suitable for href, else None."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    return _esc_attr(url)


def _json_for_script_tag(data: ReportPayload) -> str:
    """Serialize JSON safely for embedding inside a <script> tag.

    Escapes characters that can terminate the script tag or trigger HTML parsing.
    """
    raw = json.dumps(data)
    # Prevent </script> and other HTML parsing hazards inside the script element.
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _render_frame_options(
    frames: list[ReportFramePayload],
    category_filter_keys: dict[str, str],
) -> str:
    return "".join(
        f'<option value="{_esc_attr(i)}" '
        f'data-category-key="{_esc_attr(category_filter_keys[frame["category"]])}" '
        f'data-category="{_esc_attr(frame["category"])}">'
        f"{_esc_text(frame['label'])}</option>"
        for i, frame in enumerate(frames)
    )


def _render_clip_options(clips: list[ReportClipPayload], *, selected_index: int | None) -> str:
    if selected_index is None:
        return "".join(
            f'<option value="{_esc_attr(i)}">{_esc_text(clip["label"])}</option>'
            for i, clip in enumerate(clips)
        )
    options: list[str] = []
    for i, clip in enumerate(clips):
        selected_attr = " selected" if i == selected_index else ""
        options.append(
            f'<option value="{_esc_attr(i)}"{selected_attr}>{_esc_text(clip["label"])}</option>'
        )
    return "".join(options)


def _clip_index_or_default(value: object, *, clip_count: int, fallback: int) -> int:
    if isinstance(value, int) and 0 <= value < clip_count:
        return value
    if 0 <= fallback < clip_count:
        return fallback
    return 0


def _render_slowpics_link(slowpics_url: str | None) -> str:
    """Render the slow.pics link when the URL is safe to expose as href."""
    safe_href = _safe_http_href(slowpics_url)
    if not safe_href:
        return ""
    return (
        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer" '
        'class="rv-link">View on slow.pics ↗</a>'
    )


def _humanize_category(cat: str) -> str:
    """Map dynamic technical categories into readable names."""
    mapping = {
        "quantile_bright": "Bright",
        "quantile_dark": "Dark",
        "scene-cut": "Scene Cuts",
        "scene_cut": "Scene Cuts",
        "selected": "Selected",
    }
    if cat in mapping:
        return mapping[cat]
    return cat.replace("_", " ").replace("-", " ").title()



def _frame_categories(frames: list[ReportFramePayload]) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for frame in frames:
        category = frame["category"]
        if category in seen:
            continue
        categories.append(category)
        seen.add(category)
    return categories


def _category_filter_keys(frames: list[ReportFramePayload]) -> dict[str, str]:
    return {category: f"cat-{index}" for index, category in enumerate(_frame_categories(frames))}


def _render_category_filters(
    frames: list[ReportFramePayload],
    category_filter_keys: dict[str, str],
) -> str:
    categories = _frame_categories(frames)
    counts: dict[str, int] = {}
    for frame in frames:
        cat = frame["category"]
        counts[cat] = counts.get(cat, 0) + 1

    category_buttons = "".join(
        f'<button class="rv-filter-chip" type="button" data-frame-filter '
        f'data-category-key="{_esc_attr(category_filter_keys[category])}" '
        f'data-category="{_esc_attr(category)}" aria-pressed="false">'
        f'<span class="rv-category-badge" '
        f'data-category-key="{_esc_attr(category_filter_keys[category])}" '
        f'data-category="{_esc_attr(category)}">'
        f"{_esc_text(_humanize_category(category))} ({counts[category]})</span></button>"
        for category in categories
    )
    return (
        '<button class="rv-filter-chip active" type="button" data-frame-filter '
        f'data-category-key="{_esc_attr(ALL_CATEGORY_FILTER_KEY)}" '
        f'aria-pressed="true">All ({len(frames)})</button>'
        f"{category_buttons}"
    )


def _render_filmstrip(
    frames: list[ReportFramePayload],
    clips: list[ReportClipPayload],
    *,
    include_filmstrip: bool,
    category_filter_keys: dict[str, str],
) -> str:
    first_clip_label = clips[0]["label"] if clips else "Clip"
    items = (
        "".join(
            f"""
                <button class="rv-filmstrip-item" data-idx="{_esc_attr(i)}" data-category-key="{_esc_attr(category_filter_keys[frame["category"]])}" data-category="{_esc_attr(frame["category"])}" aria-label="{_esc_attr(frame["label"])}: {_esc_attr(frame["detail"])}">
                    <span class="rv-filmstrip-thumb">
                        <img src="{_esc_attr(frame["images"][0]["src"] if frame["images"] else "")}" loading="lazy" alt="{_esc_attr(first_clip_label)} - Frame {_esc_attr(frame["number"])}">
                        <span class="rv-filmstrip-accent" data-category-key="{_esc_attr(category_filter_keys[frame["category"]])}" data-category="{_esc_attr(frame["category"])}"></span>
                    </span>
                    <span class="rv-filmstrip-caption">
                        <span class="rv-filmstrip-label">{_esc_text(frame["label"])} • {_esc_text(_humanize_category(frame["category"]))}</span>
                        <span class="rv-filmstrip-detail">{_esc_text(frame["detail"])}</span>
                    </span>
                </button>
                """
            for i, frame in enumerate(frames)
        )
        if include_filmstrip
        else ""
    )
    classes = "rv-filmstrip" if include_filmstrip else "rv-filmstrip rv-filmstrip--hidden"
    aria_hidden = "false" if include_filmstrip else "true"
    aria_label = "Frame thumbnails" if include_filmstrip else "Frame thumbnails disabled"
    return f"""
        <nav class="{classes}" role="navigation" aria-label="{aria_label}" aria-hidden="{aria_hidden}">
            {items}
        </nav>
        """


def _render_header(
    title: str,
    generated_at: str,
    frame_count: int,
    clip_count: int,
    slowpics_link: str,
) -> str:
    help_button = '<button id="btn-help" class="rv-header-help-btn" aria-label="Keyboard shortcuts" title="Help (?)">?</button>'
    slowpics_block = f"{slowpics_link} • " if slowpics_link else ""
    return f"""        <header class="rv-header">
            <div>
                <div class="rv-title">{_esc_text(title)}</div>
                <div class="rv-meta">Generated {_esc_text(generated_at)} • {frame_count} frames • {clip_count} clips</div>
            </div>
            <div class="rv-header-right">
                {slowpics_block}{help_button}
            </div>
        </header>"""


def _render_controls(
    frame_options: str,
    category_filter_controls: str,
    left_clip_options: str,
    right_clip_options: str,
    active_clip_options: str,
) -> str:
    return f"""    <div class="rv-controls" role="toolbar" aria-label="Viewer controls">
        <div class="rv-control-group">
            <button id="btn-prev" aria-label="Previous frame">←</button>
            <select id="frame-select" aria-label="Select frame">
                {frame_options}
            </select>
            <button id="btn-next" aria-label="Next frame">→</button>
        </div>

        <div class="rv-control-group" role="radiogroup" aria-label="View mode">
            <button data-mode="slider" class="active" role="radio" aria-checked="true" aria-label="Slider mode" title="Slider (S)">Slider</button>
            <button data-mode="overlay" role="radio" aria-checked="false" aria-label="Overlay mode" title="Overlay (O)">Overlay</button>
            <button data-mode="diff" role="radio" aria-checked="false" aria-label="Difference mode" title="Difference (D)">Diff</button>
            <button data-mode="blink" role="radio" aria-checked="false" aria-label="Blink mode" title="Blink (B)">Blink</button>
        </div>

        <div class="rv-control-group" data-control-scope="pair" aria-label="Comparison pair">
            <span class="rv-clip-prefix left">L:</span>
            <select id="left-select" aria-label="Left clip">
                {left_clip_options}
            </select>
            <span class="rv-clip-vs">vs</span>
            <span class="rv-clip-prefix right">R:</span>
            <select id="right-select" aria-label="Right clip">
                {right_clip_options}
            </select>
        </div>

        <div class="rv-control-group" data-control-scope="active" aria-label="Overlay clip" hidden>
            <span class="rv-clip-prefix active">Clip:</span>
            <select id="active-select" aria-label="Overlay clip">
                {active_clip_options}
            </select>
        </div>

        <div class="rv-control-group">
            <button id="btn-zoom-out" aria-label="Zoom out">-</button>
            <input type="range" id="zoom-range" min="0.25" max="4.0" step="0.1" value="1.0" aria-label="Zoom level" aria-valuemin="0.25" aria-valuemax="4.0" aria-valuenow="1.0">
            <button id="btn-zoom-in" aria-label="Zoom in">+</button>
            <button id="btn-zoom-reset" aria-label="Reset zoom">R</button>
            <span id="zoom-val" style="width: 4ch">100%</span>
        </div>

        <div class="rv-control-group" role="radiogroup" aria-label="Fit mode">
            <button data-fit="actual" class="active" role="radio" aria-checked="true" aria-label="Actual size" title="Actual size">Actual</button>
            <button data-fit="width" role="radio" aria-checked="false" aria-label="Fit width" title="Fit width">Fit width</button>
            <button data-fit="height" role="radio" aria-checked="false" aria-label="Fit height" title="Fit height">Fit height</button>
            <button data-fit="fill" role="radio" aria-checked="false" aria-label="Fill stage" title="Fill stage">Fill</button>
        </div>

        <div class="rv-control-group rv-alignment-group">
            <button id="btn-align-toggle" aria-label="Alignment settings" title="Alignment Settings (⚙)" aria-expanded="false" aria-haspopup="true">⚙</button>
            <div id="align-popover" class="rv-align-popover" aria-hidden="true" hidden>
                <div class="rv-popover-row">
                    <label for="alignment-preset">Preset</label>
                    <select id="alignment-preset" aria-label="Alignment preset">
                        <option value="none">No offset</option>
                        <option value="left-1">Left 1px</option>
                        <option value="right-1">Right 1px</option>
                        <option value="up-1">Up 1px</option>
                        <option value="down-1">Down 1px</option>
                        <option value="custom">Custom</option>
                    </select>
                </div>
                <div class="rv-popover-row">
                    <label for="align-x">X</label>
                    <input id="align-x" class="rv-number-input" type="number" value="0" step="1" aria-label="Manual horizontal alignment offset">
                    <label for="align-y">Y</label>
                    <input id="align-y" class="rv-number-input" type="number" value="0" step="1" aria-label="Manual vertical alignment offset">
                </div>
                <div class="rv-popover-row">
                    <button id="btn-alignment-reset" aria-label="Reset alignment" title="Reset alignment">Reset</button>
                </div>
            </div>
        </div>

        <div class="rv-control-group">
            <button id="btn-fullscreen" aria-label="Enter fullscreen" aria-pressed="false" title="Fullscreen">Fullscreen</button>
        </div>
    </div>"""


def _render_stage() -> str:
    return """    <div class="rv-viewer-stage rv-mode-slider" role="img" aria-label="Comparison viewer">
        <div class="rv-empty-state" data-empty-state hidden></div>
        <div class="rv-canvas">
            <img src="data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA=" alt="" class="rv-sizer" aria-hidden="true">
            <div class="rv-layer rv-left">
                <img src="" alt="" class="rv-image">
                <div id="label-left" class="rv-overlay-label"></div>
            </div>
            <div class="rv-layer rv-right">
                <img src="" alt="" class="rv-image">
                <div id="label-right" class="rv-overlay-label right"></div>
            </div>
            <div class="rv-divider"><div class="rv-divider-handle"></div></div>
        </div>
        <div class="rv-stage-overlay-info">
            <span class="rv-info-label" data-current-frame-label></span>
            <span class="rv-info-divider">•</span>
            <span class="rv-info-detail" data-current-frame-detail></span>
            <span class="rv-info-divider">•</span>
            <span class="rv-info-category" data-current-frame-category></span>
        </div>
    </div>"""


def _render_help_modal() -> str:
    return """    <div id="help-modal" class="rv-modal" aria-hidden="true" role="dialog" aria-modal="true" aria-labelledby="help-modal-title" tabindex="-1">
        <div class="rv-modal-content">
            <div id="help-modal-title" class="rv-modal-title">Keyboard Shortcuts</div>
            <div class="rv-shortcuts-grid">
                <div class="rv-shortcut-row"><span>Previous Frame</span><span class="rv-key">←</span></div>
                <div class="rv-shortcut-row"><span>Next Frame</span><span class="rv-key">→</span></div>
                <div class="rv-shortcut-row"><span>First / Last Frame</span><span class="rv-key">Home / End</span></div>
                <div class="rv-shortcut-row"><span>Cycle Clip</span><span class="rv-key">↑ / ↓</span></div>
                <div class="rv-shortcut-row"><span>Direct Clip Select</span><span class="rv-key">1 - 9</span></div>
                <div class="rv-shortcut-row"><span>Modes (Slider/Overlay/Diff/Blink)</span><span class="rv-key">S / O / D / B</span></div>
                <div class="rv-shortcut-row"><span>Zoom In / Out</span><span class="rv-key">+ / -</span></div>
                <div class="rv-shortcut-row"><span>Reset Viewport</span><span class="rv-key">R</span></div>
                <div class="rv-shortcut-row"><span>Open Help</span><span class="rv-key">?</span></div>
                <div class="rv-shortcut-row"><span>Close Help / Exit Fullscreen</span><span class="rv-key">Esc</span></div>
            </div>
            <div style="margin-top: 1rem; text-align: right;">
                <button id="btn-close-help">Close</button>
            </div>
        </div>
    </div>"""


def _render_footer(json_str: str) -> str:
    return f"""    <footer class="rv-footer">
        <div>Frame Compare v{REPORT_VERSION}</div>
        <div>Use arrow keys to navigate • S/O/D/B to change mode</div>
    </footer>

    <script type="application/json" id="report-data">{json_str}</script>
    <script>{get_js()}</script>"""


def build_html(data: ReportPayload, include_filmstrip: bool = True) -> str:
    """Construct the full HTML string."""
    json_str = _json_for_script_tag(data)

    title = data["title"]
    generated_at = data["generated_at"]
    stats = data["stats"]
    slowpics_url = data["slowpics_url"]
    frames = data["frames"]
    clips = data["clips"]
    slowpics_link = _render_slowpics_link(slowpics_url)
    category_filter_keys = _category_filter_keys(frames)
    frame_options = _render_frame_options(frames, category_filter_keys)
    category_filter_controls = _render_category_filters(frames, category_filter_keys)
    default_selection = data["default_selection"]
    left_selection = default_selection.get("left_clip_index")
    right_selection = default_selection.get("right_clip_index")
    left_clip_index = _clip_index_or_default(
        left_selection,
        clip_count=len(clips),
        fallback=0,
    )
    right_clip_index = _clip_index_or_default(
        right_selection,
        clip_count=len(clips),
        fallback=1 if len(clips) > 1 else left_clip_index,
    )
    left_clip_options = _render_clip_options(clips, selected_index=left_clip_index)
    right_clip_options = _render_clip_options(clips, selected_index=right_clip_index)
    active_clip_options = _render_clip_options(clips, selected_index=left_clip_index)
    filmstrip = _render_filmstrip(
        frames,
        clips,
        include_filmstrip=include_filmstrip,
        category_filter_keys=category_filter_keys,
    )

    header_html = _render_header(
        title=title,
        generated_at=generated_at,
        frame_count=stats["frame_count"],
        clip_count=stats["clip_count"],
        slowpics_link=slowpics_link,
    )
    controls_html = _render_controls(
        frame_options,
        category_filter_controls,
        left_clip_options,
        right_clip_options,
        active_clip_options,
    )
    stage_html = _render_stage()
    modal_html = _render_help_modal()
    footer_html = _render_footer(json_str)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc_text(title)} - Frame Compare Report</title>
    <style>{get_css()}</style>
</head>
<body>
{header_html}
<div id="viewer-status" class="rv-status" role="status" aria-live="polite" hidden></div>
{controls_html}
{stage_html}
{modal_html}
<div class="rv-category-filters-container">
    <div class="rv-filter-group" data-control-scope="frame-filters" aria-label="Frame category filters">
        {category_filter_controls}
    </div>
</div>
{filmstrip}
{footer_html}
</body>
</html>"""
