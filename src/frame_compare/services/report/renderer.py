"""HTML rendering for comparison reports."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from frame_compare.services.report.category_display import (
    humanize_category,
    label_repeats_category,
)
from frame_compare.services.report.payload import REPORT_VERSION
from frame_compare.services.report.viewer import get_css, get_js

ALL_CATEGORY_FILTER_KEY = "__fc_all__"
_REVIEW_NOTE_MAX_LENGTH = 1000

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


def _frame_category_text(frame: ReportFramePayload) -> str:
    return humanize_category(frame["category"]) or frame["category"]


def _frame_label_repeats_category(frame: ReportFramePayload) -> bool:
    return label_repeats_category(frame["label"], frame["category"])


def _frame_filmstrip_label(frame: ReportFramePayload) -> str:
    category_text = _frame_category_text(frame)
    if _frame_label_repeats_category(frame):
        return frame["label"]
    return f"{frame['label']} • {category_text}"


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
        f"{_esc_text(humanize_category(category) or category)} ({counts[category]})"
        "</span></button>"
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
                <button class="rv-filmstrip-item" data-idx="{_esc_attr(i)}" data-category-key="{_esc_attr(category_filter_keys[frame["category"]])}" data-category="{_esc_attr(frame["category"])}" aria-label="{_esc_attr(_frame_filmstrip_label(frame))}">
                    <span class="rv-filmstrip-thumb">
                        <img src="{_esc_attr(frame["images"][0]["src"] if frame["images"] else "")}" loading="lazy" alt="{_esc_attr(first_clip_label)} - Frame {_esc_attr(frame["number"])}">
                        <span class="rv-filmstrip-accent" data-category-key="{_esc_attr(category_filter_keys[frame["category"]])}" data-category="{_esc_attr(frame["category"])}"></span>
                    </span>
                    <span class="rv-filmstrip-caption">
                        <span class="rv-filmstrip-label">{_esc_text(_frame_filmstrip_label(frame))}</span>
                        <span class="rv-filmstrip-compact-label">Frame {_esc_text(frame["number"])}</span>
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


def _render_bottom_panel(
    category_filter_controls: str, filmstrip: str, *, include_filmstrip: bool
) -> str:
    disabled_attr = " disabled" if not include_filmstrip else ""
    aria_expanded = "true" if include_filmstrip else "false"
    expanded_label = "Hide timeline" if include_filmstrip else "Filmstrip disabled"
    aria_label = "Collapse timeline controls" if include_filmstrip else "Filmstrip disabled"
    title = "Toggle timeline (F)" if include_filmstrip else "Filmstrip disabled"
    return f"""<section class="rv-bottom-panel" data-filmstrip-enabled="{str(include_filmstrip).lower()}" aria-label="Frame timeline">
    <div class="rv-bottom-panel-bar">
        <div class="rv-filter-group" data-control-scope="frame-filters" aria-label="Frame category filters">
            {category_filter_controls}
        </div>
        <div class="rv-filmstrip-controls">
            <div class="rv-filmstrip-size-control" role="radiogroup" aria-label="Filmstrip size">
                <button type="button" data-filmstrip-size="compact" role="radio" aria-checked="false"{disabled_attr}>Compact</button>
                <button type="button" data-filmstrip-size="normal" class="active" role="radio" aria-checked="true"{disabled_attr}>Normal</button>
                <button type="button" data-filmstrip-size="large" role="radio" aria-checked="false"{disabled_attr}>Large</button>
            </div>
            <button id="btn-filmstrip-toggle" type="button" aria-expanded="{aria_expanded}" aria-label="{aria_label}" title="{title}"{disabled_attr}>{expanded_label}</button>
        </div>
    </div>
    {filmstrip}
</section>"""


def _render_resolution(resolution: tuple[int, int]) -> str:
    return f"{resolution[0]}x{resolution[1]}"


def _render_fps(fps: float) -> str:
    return f"{fps:g} fps"


def _clip_label_for_index(clips: list[ReportClipPayload], index: int) -> str:
    if 0 <= index < len(clips):
        return clips[index]["label"]
    return f"Clip {index + 1}"


def _render_info_modal(
    data: ReportPayload,
    *,
    left_clip_index: int,
    right_clip_index: int,
) -> str:
    clips = data["clips"]
    stats = data["stats"]
    title = data["title"]
    report_id = data["report_id"]
    generated_at = data["generated_at"]
    default_mode = data["default_mode"]
    default_mode_label = "Single" if default_mode == "overlay" else default_mode

    default_pair = (
        f"{_esc_text(_clip_label_for_index(clips, left_clip_index))} "
        f"vs {_esc_text(_clip_label_for_index(clips, right_clip_index))}"
    )

    slowpics_url = data["slowpics_url"]
    safe_slowpics_href = _safe_http_href(slowpics_url)
    slowpics_row = ""
    if safe_slowpics_href:
        slowpics_row = f'<div><dt>slow.pics</dt><dd><a href="{safe_slowpics_href}" target="_blank" rel="noopener noreferrer" class="rv-link">{_esc_text(slowpics_url)}</a></dd></div>'
    elif slowpics_url:
        slowpics_row = f"<div><dt>slow.pics</dt><dd>{_esc_text(slowpics_url)}</dd></div>"
    else:
        slowpics_row = "<div><dt>slow.pics</dt><dd>Not uploaded</dd></div>"

    clip_items: list[str] = []
    for i, clip in enumerate(clips):
        hdr_tag = "HDR" if clip["hdr"] else "SDR"
        clip_items.append(
            f'<li class="rv-clip-meta-item" data-clip-index="{_esc_attr(i)}">'
            f'<div class="rv-clip-meta-heading">'
            f"<span>{_esc_text(clip['label'])}</span>"
            f"<span>{hdr_tag}</span>"
            f"</div>"
            f'<dl class="rv-metadata-list">'
            f"<div><dt>Name</dt><dd>{_esc_text(clip['name'])}</dd></div>"
            f"<div><dt>Resolution</dt><dd>{_render_resolution(clip['resolution'])}</dd></div>"
            f"<div><dt>FPS</dt><dd>{_render_fps(clip['fps'])}</dd></div>"
            f"<div><dt>Frames</dt><dd>{clip['frame_count']}</dd></div>"
            f"</dl>"
            f"</li>"
        )
    clip_list_html = (
        f'<ol class="rv-clip-meta-list">{"".join(clip_items)}</ol>'
        if clip_items
        else '<div class="rv-metadata-empty">No clips in payload.</div>'
    )

    return f"""    <div id="info-modal" class="rv-modal" aria-hidden="true" role="dialog" aria-modal="true" aria-labelledby="info-modal-title" tabindex="-1">
        <div class="rv-modal-content rv-modal-content--wide">
            <div id="info-modal-title" class="rv-modal-title">Report Information</div>
            <div class="rv-info-grid">
                <div class="rv-info-section">
                    <h3>General</h3>
                    <dl class="rv-metadata-list">
                        <div><dt>Title</dt><dd>{_esc_text(title)}</dd></div>
                        <div><dt>Report ID</dt><dd>{_esc_text(report_id)}</dd></div>
                        <div><dt>Generated</dt><dd>{_esc_text(generated_at)}</dd></div>
                        <div><dt>Frames</dt><dd>{stats["frame_count"]}</dd></div>
                        <div><dt>Clips</dt><dd>{stats["clip_count"]}</dd></div>
                        <div><dt>Default Mode</dt><dd>{_esc_text(default_mode_label)}</dd></div>
                        <div><dt>Default Pair</dt><dd>{default_pair}</dd></div>
                        {slowpics_row}
                    </dl>
                </div>
                <div class="rv-info-section">
                    <h3>Clips</h3>
                    {clip_list_html}
                </div>
            </div>
            <div class="rv-modal-actions rv-modal-actions--spacious">
                <button id="btn-close-info">Close</button>
            </div>
        </div>
    </div>"""


def _render_header(
    title: str,
    generated_at: str,
    frame_count: int,
    clip_count: int,
    slowpics_link: str,
) -> str:
    info_button = '<button id="btn-info" class="rv-header-info-btn" aria-label="Report information" title="Report Info"><span class="rv-btn-icon">ℹ</span></button>'
    help_button = '<button id="btn-help" class="rv-header-help-btn" aria-label="Keyboard shortcuts" title="Help (?)"><span class="rv-btn-icon">?</span></button>'
    slowpics_block = f"{slowpics_link} • " if slowpics_link else ""
    return f"""        <header class="rv-header">
            <div>
                <div class="rv-title">{_esc_text(title)}</div>
                <div class="rv-meta">Generated {_esc_text(generated_at)} • {frame_count} frames • {clip_count} clips</div>
            </div>
            <div class="rv-header-right">
                {slowpics_block}{info_button} {help_button}
            </div>
        </header>"""


def _render_controls(
    frame_options: str,
    left_clip_options: str,
    right_clip_options: str,
    active_clip_options: str,
) -> str:
    return f"""    <div class="rv-controls" role="toolbar" aria-label="Viewer controls">
        <div class="rv-primary-controls" aria-label="Primary viewer controls">
        <div class="rv-control-group rv-frame-controls">
            <button id="btn-prev" aria-label="Previous frame">←</button>
            <select id="frame-select" aria-label="Select frame">
                {frame_options}
            </select>
            <button id="btn-next" aria-label="Next frame">→</button>
            <span id="active-filter-badge" class="rv-active-filter-badge" hidden></span>
        </div>

        <div class="rv-control-group" role="radiogroup" aria-label="View mode">
            <button data-mode="slider" class="active" role="radio" aria-checked="true" aria-label="Slider mode" title="Slider (S)">Slider</button>
            <button data-mode="overlay" role="radio" aria-checked="false" aria-label="Single clip view" title="Single clip view (O)">Single</button>
            <button data-mode="diff" role="radio" aria-checked="false" aria-label="Difference mode" title="Difference (D)">Diff</button>
            <button data-mode="blink" role="radio" aria-checked="false" aria-label="Blink mode" title="Blink (B)">Blink</button>
            <button data-mode="grid" role="radio" aria-checked="false" aria-label="Grid mode" title="Grid comparison">Grid</button>
        </div>

        <div class="rv-control-group rv-inspect-control">
            <button id="btn-inspect" type="button" aria-label="Open pixel inspector" title="Inspect pixels (M)">Inspect</button>
        </div>

        <div class="rv-control-group rv-grid-controls" data-control-scope="grid" aria-label="Grid clips" hidden>
            <button id="btn-grid-prev" type="button" aria-label="Previous grid clips">←</button>
            <span class="rv-grid-position" data-grid-position aria-live="off"></span>
            <button id="btn-grid-next" type="button" aria-label="Next grid clips">→</button>
        </div>

        <div class="rv-control-group" data-control-scope="pair" aria-label="Comparison pair">
            <span class="rv-clip-prefix left">L:</span>
            <select id="left-select" aria-label="Left clip">
                {left_clip_options}
            </select>
            <button id="btn-swap-clips" class="rv-swap-button" aria-label="Swap comparison clips" title="Swap clips (X)">⇄</button>
            <span class="rv-clip-vs">vs</span>
            <span class="rv-clip-prefix right">R:</span>
            <select id="right-select" aria-label="Right clip">
                {right_clip_options}
            </select>
        </div>

        <div class="rv-control-group" data-control-scope="active" aria-label="Single clip" hidden>
            <span class="rv-clip-prefix active">Clip:</span>
            <select id="active-select" aria-label="Single clip">
                {active_clip_options}
            </select>
        </div>
        <div id="alignment-status" class="rv-alignment-status" role="status" aria-live="polite">Aligned: none</div>
        </div>
    </div>"""


def _render_viewport_palette() -> str:
    return """        <div class="rv-viewport-palette" role="toolbar" aria-label="Viewport controls" data-orientation="horizontal">
        <div class="rv-palette-group">
            <button id="btn-palette-orientation" aria-label="Toggle palette orientation" title="Toggle palette orientation">↔</button>
        </div>

        <div class="rv-palette-group rv-palette-group--zoom">
            <button id="btn-zoom-out" aria-label="Zoom out">-</button>
            <input type="range" id="zoom-range" min="0.25" max="4.0" step="0.1" value="1.0" aria-label="Zoom level" aria-valuemin="0.25" aria-valuemax="4.0" aria-valuenow="1.0">
            <button id="btn-zoom-in" aria-label="Zoom in">+</button>
            <button id="btn-zoom-reset" aria-label="Reset zoom">R</button>
            <span id="zoom-val" class="rv-zoom-value">100%</span>
        </div>

        <div class="rv-palette-group" role="radiogroup" aria-label="Fit mode">
            <button data-fit="actual" class="active" role="radio" aria-checked="true" aria-label="Actual size" title="Actual size (1:1)">1:1</button>
            <button data-fit="width" role="radio" aria-checked="false" aria-label="Fit width" title="Fit width (↔)">↔</button>
            <button data-fit="height" role="radio" aria-checked="false" aria-label="Fit height" title="Fit height (↕)">↕</button>
        </div>

        <div class="rv-palette-group rv-alignment-group">
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

        <div class="rv-palette-group">
            <button id="btn-fullscreen" aria-label="Enter fullscreen" aria-pressed="false" title="Enter fullscreen"><span class="rv-fullscreen-icon" aria-hidden="true">⛶</span></button>
        </div>

        <div class="rv-palette-group">
            <button id="btn-overlays" class="active" aria-label="Hide HUD" aria-pressed="true" title="Hide HUD (H)">HUD</button>
        </div>

        <div class="rv-palette-group rv-blink-controls" data-control-scope="blink" hidden>
            <button id="btn-blink-pause" aria-label="Pause blink" aria-pressed="false" title="Pause blink (Space)">Pause</button>
            <select id="blink-speed" aria-label="Blink speed">
                <option value="300">0.3s</option>
                <option value="700" selected>0.7s</option>
                <option value="1200">1.2s</option>
            </select>
            <span id="blink-status" class="rv-blink-status" role="status" aria-live="polite"></span>
        </div>
    </div>"""


def _render_stage() -> str:
    return f"""    <div class="rv-viewer-stage rv-mode-slider" role="region" aria-label="Comparison viewer">
        <div class="rv-empty-state" data-empty-state hidden></div>
        <div class="rv-canvas" role="img" aria-label="Comparison image canvas">
            <img src="data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA=" alt="" class="rv-sizer" aria-hidden="true">
            <div class="rv-layer rv-left">
                <img src="" alt="" class="rv-image">
            </div>
            <div class="rv-layer rv-right">
                <img src="" alt="" class="rv-image">
            </div>
            <div class="rv-divider"><div class="rv-divider-handle"></div></div>
            <div class="rv-stage-labels" aria-hidden="true">
                <div id="label-left" class="rv-overlay-label"></div>
                <div id="label-right" class="rv-overlay-label right"></div>
            </div>
        </div>
        <button id="rv-inspection-point" class="rv-inspection-point" type="button" aria-label="Inspection point unavailable" aria-pressed="false" tabindex="-1" hidden>
            <span aria-hidden="true"></span>
        </button>
        <section id="rv-grid" class="rv-grid" aria-label="Grid comparison" hidden>
            <div class="rv-grid-frame-error" data-grid-frame-error hidden></div>
            <div class="rv-grid-cells" data-grid-cells></div>
        </section>
        <aside id="rv-pixel-lens" class="rv-pixel-lens" aria-label="Pixel lens" data-magnification="4" hidden>
            <img src="" alt="">
        </aside>
        <div class="rv-stage-overlay-info">
            <span class="rv-info-label" data-current-frame-label></span>
            <span class="rv-info-divider" data-current-frame-category-divider>•</span>
            <span class="rv-info-category" data-current-frame-category></span>
        </div>
{_render_viewport_palette()}
    </div>"""


def _render_inspector() -> str:
    return f"""    <aside id="rv-inspector" class="rv-inspector" aria-hidden="true" aria-labelledby="rv-inspector-title" inert>
        <div class="rv-inspector-header">
            <div id="rv-inspector-title" class="rv-inspector-title">Inspector</div>
            <button id="btn-inspector-close" type="button" aria-label="Close inspector" title="Close inspector (I)" tabindex="-1">Close</button>
        </div>
        <div class="rv-inspector-tabs" role="tablist" aria-label="Inspector tabs">
            <button id="inspector-tab-pixel" type="button" role="tab" data-inspector-tab="pixel" aria-selected="false" aria-controls="inspector-panel-pixel" tabindex="-1">Pixel</button>
            <button id="inspector-tab-frame" type="button" role="tab" data-inspector-tab="frame" aria-selected="true" aria-controls="inspector-panel-frame" tabindex="-1">Frame</button>
            <button id="inspector-tab-clips" type="button" role="tab" data-inspector-tab="clips" aria-selected="false" aria-controls="inspector-panel-clips" tabindex="-1">Clips</button>
            <button id="inspector-tab-align" type="button" role="tab" data-inspector-tab="align" aria-selected="false" aria-controls="inspector-panel-align" tabindex="-1">Align</button>
            <button id="inspector-tab-review" type="button" role="tab" data-inspector-tab="review" aria-selected="false" aria-controls="inspector-panel-review" tabindex="-1">Review</button>
            <button id="inspector-tab-export" type="button" role="tab" data-inspector-tab="export" aria-selected="false" aria-controls="inspector-panel-export" tabindex="-1">Export</button>
        </div>
        <section id="inspector-panel-pixel" class="rv-inspector-panel rv-pixel-panel" role="tabpanel" aria-labelledby="inspector-tab-pixel" tabindex="-1" hidden>
            <div class="rv-pixel-toolbar">
                <button id="pixel-lens-toggle" type="button" aria-pressed="false" tabindex="-1">Lens off</button>
                <div class="rv-pixel-magnification" role="radiogroup" aria-label="Lens magnification">
                    <button type="button" role="radio" data-pixel-magnification="2" aria-checked="false" aria-label="Magnification 2×" tabindex="-1">2×</button>
                    <button type="button" role="radio" data-pixel-magnification="4" aria-checked="true" aria-label="Magnification 4×" tabindex="-1">4×</button>
                    <button type="button" role="radio" data-pixel-magnification="8" aria-checked="false" aria-label="Magnification 8×" tabindex="-1">8×</button>
                </div>
            </div>
            <p class="rv-pixel-anchor" data-pixel-anchor>Anchor: not selected</p>
            <ol class="rv-pixel-rows" data-pixel-rows></ol>
            <p class="rv-pixel-legend">Decoded display sample · 8-bit sRGB</p>
            <p class="rv-inspector-note">Coordinates are zero-based with origin at top-left.</p>
            <p class="rv-inspector-note">Normalized cross-size mapping; not scene registration.</p>
        </section>
        <section id="inspector-panel-frame" class="rv-inspector-panel" role="tabpanel" aria-labelledby="inspector-tab-frame" tabindex="-1">
            <dl class="rv-inspector-list">
                <div><dt>Label</dt><dd data-inspector-frame-label></dd></div>
                <div><dt>Number</dt><dd data-inspector-frame-number></dd></div>
                <div><dt>Category</dt><dd data-inspector-frame-category></dd></div>
                <div><dt>Detail</dt><dd data-inspector-frame-detail></dd></div>
                <div><dt>Shown</dt><dd data-inspector-frame-position></dd></div>
            </dl>
        </section>
        <section id="inspector-panel-clips" class="rv-inspector-panel" role="tabpanel" aria-labelledby="inspector-tab-clips" tabindex="-1" hidden>
            <ol class="rv-inspector-clip-list" data-inspector-clips></ol>
        </section>
        <section id="inspector-panel-align" class="rv-inspector-panel" role="tabpanel" aria-labelledby="inspector-tab-align" tabindex="-1" hidden>
            <dl class="rv-inspector-list">
                <div><dt>Pair</dt><dd data-inspector-align-pair></dd></div>
                <div><dt>Preset</dt><dd data-inspector-align-preset></dd></div>
                <div><dt>X</dt><dd data-inspector-align-x></dd></div>
                <div><dt>Y</dt><dd data-inspector-align-y></dd></div>
            </dl>
            <div class="rv-inspector-actions">
                <button id="btn-inspector-reset-current-align" type="button" tabindex="-1">Reset current pair</button>
                <button id="btn-inspector-reset-all-align" type="button" tabindex="-1">Reset all pairs</button>
            </div>
            <p class="rv-inspector-note">Offsets are scoped to the selected pair.</p>
        </section>
        <section id="inspector-panel-review" class="rv-inspector-panel rv-review-panel" role="tabpanel" aria-labelledby="inspector-tab-review" tabindex="-1" hidden>
            <p class="rv-review-frame" data-review-frame>Frame 1</p>
            <label class="rv-review-check"><input type="checkbox" data-review-bookmark tabindex="-1"> Bookmark this frame</label>
            <label class="rv-review-field">Tag
                <select data-review-tag tabindex="-1">
                    <option value="">No tag</option><option value="artifact">Artifact</option><option value="detail">Detail</option><option value="motion">Motion</option><option value="color">Color</option><option value="other">Other</option>
                </select>
            </label>
            <label class="rv-review-field">Note <span data-review-note-count>0 / {_REVIEW_NOTE_MAX_LENGTH}</span>
                <textarea data-review-note rows="5" maxlength="{_REVIEW_NOTE_MAX_LENGTH}" tabindex="-1"></textarea>
            </label>
            <label class="rv-review-field">Preferred clip
                <select data-review-preferred tabindex="-1"></select>
            </label>
            <p class="rv-review-status" data-review-status></p>
            <div class="rv-inspector-actions rv-review-transfer">
                <button type="button" data-review-export tabindex="-1">Export review JSON</button>
                <button type="button" data-review-import-trigger tabindex="-1">Import review JSON</button>
                <input type="file" data-review-import accept=".json,application/json" hidden tabindex="-1">
            </div>
            <div class="rv-review-preview" data-review-preview hidden>
                <p data-review-preview-counts></p>
                <fieldset><legend>Apply mode</legend>
                    <label><input type="radio" name="review-import-mode" value="merge" checked> Merge</label>
                    <label><input type="radio" name="review-import-mode" value="replace"> Replace</label>
                </fieldset>
                <fieldset><legend>Conflicts</legend>
                    <label><input type="radio" name="review-import-conflict" value="keep-local" checked> Keep local</label>
                    <label><input type="radio" name="review-import-conflict" value="use-imported"> Use imported</label>
                </fieldset>
                <div class="rv-inspector-actions">
                    <button type="button" data-review-import-apply>Apply import</button>
                    <button type="button" data-review-import-cancel>Cancel</button>
                </div>
            </div>
        </section>
        <section id="inspector-panel-export" class="rv-inspector-panel" role="tabpanel" aria-labelledby="inspector-tab-export" tabindex="-1" hidden>
            <dl class="rv-inspector-list">
                <div><dt>Title</dt><dd data-inspector-export-title></dd></div>
                <div><dt>Report ID</dt><dd data-inspector-export-id></dd></div>
                <div><dt>Generated</dt><dd data-inspector-export-generated></dd></div>
                <div><dt>slow.pics</dt><dd data-inspector-export-slowpics></dd></div>
                <div><dt>Summary</dt><dd data-inspector-export-summary></dd></div>
            </dl>
        </section>
    </aside>"""


def _render_help_modal() -> str:
    return """    <div id="help-modal" class="rv-modal" aria-hidden="true" role="dialog" aria-modal="true" aria-labelledby="help-modal-title" tabindex="-1">
        <div class="rv-modal-content">
            <div id="help-modal-title" class="rv-modal-title">Viewer Shortcuts</div>
            <div class="rv-shortcuts-grid">
                <div class="rv-shortcut-row"><span>Previous Frame</span><span class="rv-key">←</span></div>
                <div class="rv-shortcut-row"><span>Next Frame</span><span class="rv-key">→</span></div>
                <div class="rv-shortcut-row"><span>First / Last Frame</span><span class="rv-key">Home / End</span></div>
                <div class="rv-shortcut-row"><span>Cycle Clip</span><span class="rv-key">↑ / ↓</span></div>
                <div class="rv-shortcut-row"><span>Direct Clip Select</span><span class="rv-key">1 - 9</span></div>
                <div class="rv-shortcut-row"><span>Swap Clips</span><span class="rv-key">X</span></div>
                <div class="rv-shortcut-row"><span>Modes (Slider/Single/Diff/Blink)</span><span class="rv-key">S / O / D / B</span></div>
                <div class="rv-shortcut-row"><span>Toggle HUD</span><span class="rv-key">H</span></div>
                <div class="rv-shortcut-row"><span>Toggle Filmstrip</span><span class="rv-key">F</span></div>
                <div class="rv-shortcut-row"><span>Toggle Inspector</span><span class="rv-key">I</span></div>
                <div class="rv-shortcut-row"><span>Inspect Pixels</span><span class="rv-key">M</span></div>
                <div class="rv-shortcut-row"><span>Blink Pause / Speed</span><span class="rv-key">Space / [ / ]</span></div>
                <div class="rv-shortcut-row"><span>Zoom In / Out</span><span class="rv-key">+ / -</span></div>
                <div class="rv-shortcut-row"><span>Reset Viewport</span><span class="rv-key">R / Double-click</span></div>
                <div class="rv-shortcut-row"><span>Open Help</span><span class="rv-key">?</span></div>
                <div class="rv-shortcut-row"><span>Close Panel / Exit Fullscreen</span><span class="rv-key">Esc</span></div>
            </div>
            <div class="rv-modal-subtitle">Viewport Fit Modes</div>
            <div class="rv-legend-grid">
                <div class="rv-legend-row"><span class="rv-key">1:1</span><span>Actual size</span></div>
                <div class="rv-legend-row"><span class="rv-key">↔</span><span>Fit width</span></div>
                <div class="rv-legend-row"><span class="rv-key">↕</span><span>Fit height</span></div>
            </div>
            <div class="rv-modal-actions">
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
    bottom_panel = _render_bottom_panel(
        category_filter_controls,
        filmstrip,
        include_filmstrip=include_filmstrip,
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
        left_clip_options,
        right_clip_options,
        active_clip_options,
    )
    stage_html = _render_stage()
    inspector_html = _render_inspector()
    modal_html = _render_help_modal()
    info_modal_html = _render_info_modal(
        data,
        left_clip_index=left_clip_index,
        right_clip_index=right_clip_index,
    )
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
<div id="pixel-inspector-live" class="rv-visually-hidden" role="status" aria-live="polite" aria-atomic="true"></div>
{controls_html}
{stage_html}
{inspector_html}
{modal_html}
{info_modal_html}
{bottom_panel}
{footer_html}
</body>
</html>"""
