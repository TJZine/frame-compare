"""HTML rendering for comparison reports."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from frame_compare.services.report.payload import REPORT_VERSION
from frame_compare.services.report.viewer import get_css, get_js

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


def _render_frame_options(frames: list[ReportFramePayload]) -> str:
    return "".join(
        f'<option value="{_esc_attr(i)}">Frame {_esc_text(frame["number"])}</option>'
        for i, frame in enumerate(frames)
    )


def _render_clip_options(clips: list[ReportClipPayload], *, selected_index: int | None) -> str:
    if selected_index is None:
        return "".join(
            f'<option value="{_esc_attr(i)}">{_esc_text(clip["label"])}</option>'
            for i, clip in enumerate(clips)
        )
    return "".join(
        f'<option value="{_esc_attr(i)}" {"selected" if i == selected_index else ""}>'
        f"{_esc_text(clip['label'])}</option>"
        for i, clip in enumerate(clips)
    )


def _render_slowpics_link(slowpics_url: str | None) -> str:
    """Render the slow.pics link when the URL is safe to expose as href."""
    safe_href = _safe_http_href(slowpics_url)
    if not safe_href:
        return ""
    return (
        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer" '
        'class="rv-link">View on slow.pics ↗</a>'
    )


def _render_filmstrip(
    frames: list[ReportFramePayload],
    clips: list[ReportClipPayload],
    *,
    include_filmstrip: bool,
) -> str:
    items = (
        "".join(
            f"""
                <button class="rv-filmstrip-item" data-idx="{_esc_attr(i)}" aria-label="Frame {_esc_attr(frame["number"])}">
                    <img src="{_esc_attr(frame["images"][0]["src"])}" loading="lazy" alt="{_esc_attr(clips[0]["label"])} - Frame {_esc_attr(frame["number"])}">
                    <span class="rv-filmstrip-label">{_esc_text(frame["number"])}</span>
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
    return f"""        <header class="rv-header">
            <div>
                <div class="rv-title">{_esc_text(title)}</div>
                <div class="rv-meta">Generated {_esc_text(generated_at)} • {frame_count} frames • {clip_count} clips</div>
            </div>
            <div>
                {slowpics_link}
            </div>
        </header>"""


def _render_controls(
    frame_options: str,
    left_clip_options: str,
    right_clip_options: str,
) -> str:
    return f"""    <div class="rv-controls" role="toolbar" aria-label="Viewer controls">
        <div class="rv-control-group">
                <button id="btn-prev" aria-label="Previous frame">←</button>
                <select id="frame-select" aria-label="Select frame">
                    {frame_options}
                </select>
                <button id="btn-next" aria-label="Next frame">→</button>
            </div>

            <div class="rv-control-group">
                <select id="left-select" aria-label="Left clip">
                    {left_clip_options}
                </select>
                <select id="right-select" aria-label="Right clip">
                    {right_clip_options}
                </select>
            </div>

        <div class="rv-control-group" role="radiogroup" aria-label="View mode">
            <button data-mode="slider" class="active" role="radio" aria-checked="true" aria-label="Slider mode" title="Slider (S)">⊟</button>
            <button data-mode="overlay" role="radio" aria-checked="false" aria-label="Overlay mode" title="Overlay (O)">◐</button>
            <button data-mode="diff" role="radio" aria-checked="false" aria-label="Difference mode" title="Difference (D)">◑</button>
            <button data-mode="blink" role="radio" aria-checked="false" aria-label="Blink mode" title="Blink (B)">◫</button>
        </div>

        <div class="rv-control-group">
            <button id="btn-zoom-out" aria-label="Zoom out">-</button>
            <input type="range" id="zoom-range" min="0.25" max="2.0" step="0.1" value="1.0" aria-label="Zoom level" aria-valuemin="0.25" aria-valuemax="2.0" aria-valuenow="1.0">
            <button id="btn-zoom-in" aria-label="Zoom in">+</button>
            <button id="btn-zoom-reset" aria-label="Reset zoom">R</button>
            <span id="zoom-val" style="font-size: var(--text-xs); width: 3ch">100%</span>
        </div>

        <div class="rv-control-group">
             <button id="btn-help" aria-label="Keyboard shortcuts" title="Help (?)">?</button>
        </div>
    </div>"""


def _render_stage() -> str:
    return """    <div class="rv-viewer-stage rv-mode-slider" role="img" aria-label="Comparison viewer">
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
            <div class="rv-divider"></div>
        </div>
    </div>"""


def _render_help_modal() -> str:
    return """    <div id="help-modal" class="rv-modal" aria-hidden="true" role="dialog" aria-label="Keyboard Shortcuts">
        <div class="rv-modal-content">
            <div class="rv-modal-title">Keyboard Shortcuts</div>
            <div class="rv-shortcuts-grid">
                <div class="rv-shortcut-row"><span>Previous Frame</span><span class="rv-key">←</span></div>
                <div class="rv-shortcut-row"><span>Next Frame</span><span class="rv-key">→</span></div>
                <div class="rv-shortcut-row"><span>First / Last Frame</span><span class="rv-key">Home / End</span></div>
                <div class="rv-shortcut-row"><span>Cycle Clip</span><span class="rv-key">↑ / ↓</span></div>
                <div class="rv-shortcut-row"><span>Direct Clip Select</span><span class="rv-key">1 - 9</span></div>
                <div class="rv-shortcut-row"><span>Modes (Slider/Overlay/Diff/Blink)</span><span class="rv-key">S / O / D / B</span></div>
                <div class="rv-shortcut-row"><span>Zoom In / Out</span><span class="rv-key">+ / -</span></div>
                <div class="rv-shortcut-row"><span>Reset Zoom</span><span class="rv-key">R</span></div>
                <div class="rv-shortcut-row"><span>Close Help</span><span class="rv-key">Esc</span></div>
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
    frame_options = _render_frame_options(frames)
    left_clip_options = _render_clip_options(clips, selected_index=None)
    right_clip_options = _render_clip_options(clips, selected_index=1)
    filmstrip = _render_filmstrip(frames, clips, include_filmstrip=include_filmstrip)

    header_html = _render_header(
        title=title,
        generated_at=generated_at,
        frame_count=stats["frame_count"],
        clip_count=stats["clip_count"],
        slowpics_link=slowpics_link,
    )
    controls_html = _render_controls(frame_options, left_clip_options, right_clip_options)
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
{controls_html}
{stage_html}
{modal_html}
{filmstrip}
{footer_html}
</body>
</html>"""
