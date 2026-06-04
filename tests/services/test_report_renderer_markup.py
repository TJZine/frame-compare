"""Markup and payload contract tests for the report renderer module."""

from __future__ import annotations

import html as html_module
import re

from frame_compare.services.report.payload import ReportPayload
from frame_compare.services.report.renderer import build_html
from frame_compare.services.report.viewer import get_css, get_js
from tests.services.report_viewer_contracts import (
    SelectParser,
    find_children,
    parse_elements,
    parse_info_modal,
    parse_start_tags,
    report_payload,
    require_first,
    script_payload,
)

__all__ = ["report_payload"]


def test_build_html_renders_only_safe_slowpics_links(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    info_modal = parse_info_modal(html)

    assert 'href="https://slow.pics/c/abc?x=1&amp;y=2"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "View on slow.pics" in html
    assert info_modal.links["slow.pics"] == "https://slow.pics/c/abc?x=1&y=2"
    assert info_modal.general["slow.pics"] == "https://slow.pics/c/abc?x=1&y=2"

    unsafe_payload: ReportPayload = {**report_payload, "slowpics_url": "javascript:alert(1)"}
    unsafe_html = build_html(unsafe_payload)
    unsafe_info_modal = parse_info_modal(unsafe_html)

    assert "javascript:alert(1)" in unsafe_html
    assert 'href="javascript:alert(1)"' not in unsafe_html
    assert "View on slow.pics" not in unsafe_html
    assert "slow.pics" not in unsafe_info_modal.links
    assert unsafe_info_modal.general["slow.pics"] == "javascript:alert(1)"

    no_upload_payload: ReportPayload = {**report_payload, "slowpics_url": None}
    no_upload_html = build_html(no_upload_payload)
    no_upload_info_modal = parse_info_modal(no_upload_html)

    assert "View on slow.pics" not in no_upload_html
    assert 'class="rv-link"' not in no_upload_html
    assert no_upload_info_modal.general["slow.pics"] == "Not uploaded"


def test_build_html_renders_frame_and_clip_selectors(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    parser = SelectParser()
    parser.feed(html)

    assert parser.selects["frame-select"].attrs["aria-label"] == "Select frame"
    assert [option.text for option in parser.selects["frame-select"].options] == [
        "Frame 10",
        "Frame 20",
    ]
    assert parser.selects["left-select"].attrs["aria-label"] == "Left clip"
    reference = next(
        option for option in parser.selects["left-select"].options if option.text == "REF <main>"
    )
    assert "selected" in reference.attrs
    assert parser.selects["right-select"].attrs["aria-label"] == "Right clip"
    candidate = next(
        option
        for option in parser.selects["right-select"].options
        if option.text == 'ENC "candidate"'
    )
    assert "selected" in candidate.attrs
    assert parser.selects["active-select"].attrs["aria-label"] == "Single clip"
    active_reference = next(
        option for option in parser.selects["active-select"].options if option.text == "REF <main>"
    )
    assert "selected" in active_reference.attrs


def test_build_html_renders_mode_aware_clip_controls(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)

    assert 'data-control-scope="pair" aria-label="Comparison pair"' in html
    assert 'data-control-scope="active" aria-label="Single clip" hidden' in html
    assert 'id="left-select" aria-label="Left clip"' in html
    assert 'id="btn-swap-clips" class="rv-swap-button"' in html
    assert 'id="right-select" aria-label="Right clip"' in html
    assert 'id="active-select" aria-label="Single clip"' in html
    assert 'data-mode="overlay" role="radio"' in html
    assert 'aria-label="Single clip view" title="Single clip view (O)">Single</button>' in html
    assert 'title="Overlay (O)"' not in html
    assert ">Overlay</button>" not in html


def test_build_html_keeps_ten_plus_long_label_clips_reachable_and_mobile_safe(
    report_payload: ReportPayload,
) -> None:
    long_label = "Reference candidate with a very long release label and source annotation "
    clips = [
        {
            **report_payload["clips"][0],
            "name": f"clip-{idx + 1}",
            "label": f"{long_label}{idx + 1:02d}",
        }
        for idx in range(12)
    ]
    frames = [
        {
            **report_payload["frames"][0],
            "images": [{"clip": clip["name"], "src": f"{clip['name']}/10.png"} for clip in clips],
        }
    ]
    payload: ReportPayload = {
        **report_payload,
        "stats": {"frame_count": 1, "clip_count": 12},
        "clips": clips,
        "frames": frames,
    }

    parser = SelectParser()
    parser.feed(build_html(payload))
    css = get_css()

    for select_id in ("left-select", "right-select", "active-select"):
        options = parser.selects[select_id].options
        assert len(options) == 12
        assert options[9].attrs["value"] == "9"
        assert options[11].attrs["value"] == "11"
        assert options[11].text.endswith("12")

    assert "max-width: min(22rem, 100%);" in css
    assert "text-overflow: ellipsis;" in css
    assert "flex-wrap: wrap;" in css
    assert "flex: 1 1 12rem;" in css
    assert ".rv-mode-slider #label-left" in css
    assert ".rv-mode-slider #label-right" in css


def test_build_html_renders_frame_metadata_and_category_filters(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert 'data-control-scope="frame-filters" aria-label="Frame category filters"' in html
    assert 'data-category-key="__fc_all__" aria-pressed="true">All (2)</button>' in html
    assert 'data-category-key="cat-0" data-category="selected" aria-pressed="false"' in html
    assert 'data-category-key="cat-1" data-category="scene-cut" aria-pressed="false"' in html
    assert '<span class="rv-filmstrip-label">Frame 10 • Selected</span>' in html
    assert '<span class="rv-filmstrip-compact-label">Frame 10</span>' in html
    assert "Source frame 10</span>" not in html
    assert (
        '<span class="rv-filmstrip-accent" '
        'data-category-key="cat-1" data-category="scene-cut"></span>'
    ) in html
    assert 'value="1" data-category-key="cat-1" data-category="scene-cut">Frame 20</option>' in html


def test_build_html_renders_header_metadata(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    tags = parse_start_tags(html)
    info_modal = parse_info_modal(html)
    elements = parse_elements(html)
    help_button = require_first(elements, tag="button", element_id="btn-help")
    info_button = require_first(elements, tag="button", element_id="btn-info")
    help_icon = require_first(help_button, tag="span", class_name="rv-btn-icon")
    info_icon = require_first(info_button, tag="span", class_name="rv-btn-icon")

    assert "Generated 2026-05-22T12:00:00+00:00 • 2 frames • 2 clips" in html
    assert tags.by_id["btn-help"][1]["class"] == "rv-header-help-btn"
    assert tags.by_id["btn-info"][1]["class"] == "rv-header-info-btn"
    assert tags.by_id["btn-info"][1]["title"] == "Report Info"
    assert help_icon.text == "?"
    assert info_icon.text == "ℹ"
    assert info_modal.attrs["class"] == "rv-modal"
    assert info_modal.attrs["aria-hidden"] == "true"
    assert info_modal.attrs["role"] == "dialog"
    assert info_modal.section_headings == ["General", "Clips"]
    assert info_modal.general == {
        "Title": "Renderer Contract",
        "Report ID": "report_0123456789abcdef0123456789abcdef",
        "Generated": "2026-05-22T12:00:00+00:00",
        "Frames": "2",
        "Clips": "2",
        "Default Mode": "slider",
        "Default Pair": 'REF <main> vs ENC "candidate"',
        "slow.pics": "https://slow.pics/c/abc?x=1&y=2",
    }
    assert [(clip.label, clip.dynamic_range, clip.fields) for clip in info_modal.clips] == [
        (
            "REF <main>",
            "SDR",
            {
                "Name": "reference",
                "Resolution": "1920x1080",
                "FPS": "24 fps",
                "Frames": "100",
            },
        ),
        (
            'ENC "candidate"',
            "HDR",
            {
                "Name": "encode",
                "Resolution": "1920x1080",
                "FPS": "24 fps",
                "Frames": "100",
            },
        ),
    ]


def test_build_html_displays_overlay_default_mode_as_single(
    report_payload: ReportPayload,
) -> None:
    payload: ReportPayload = {**report_payload, "default_mode": "overlay"}
    html = build_html(payload)
    info_modal = parse_info_modal(html)

    assert script_payload(html)["default_mode"] == "overlay"
    assert info_modal.general["Default Mode"] == "Single"


def test_build_html_avoids_inline_styles(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    tags = parse_start_tags(html)

    assert tags.tags_with_style == []


def test_build_html_exposes_current_frame_metadata_hooks(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)

    assert "data-current-frame-label" in html
    assert "data-current-frame-category-divider" in html
    assert "data-current-frame-category" in html


def test_build_html_positions_stage_labels_outside_image_layers(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert (
        '<div class="rv-viewer-stage rv-mode-slider" role="region" aria-label="Comparison viewer">'
        in html
    )
    assert '<div class="rv-canvas" role="img" aria-label="Comparison image canvas">' in html

    left_layer_start = html.index('<div class="rv-layer rv-left">')
    stage_labels_start = html.index('<div class="rv-stage-labels" aria-hidden="true">')
    left_layer_markup = html[left_layer_start:stage_labels_start]

    assert stage_labels_start > left_layer_start
    assert 'id="label-left"' not in left_layer_markup
    assert 'id="label-right"' not in left_layer_markup


def test_build_html_renders_empty_viewer_hooks_for_empty_payload(
    report_payload: ReportPayload,
) -> None:
    payload: ReportPayload = {
        **report_payload,
        "stats": {"frame_count": 0, "clip_count": 0},
        "clips": [],
        "frames": [],
    }

    html = build_html(payload)

    assert (
        '<div id="viewer-status" class="rv-status" role="status" aria-live="polite" hidden></div>'
        in html
    )
    assert '<div class="rv-empty-state" data-empty-state hidden></div>' in html
    assert 'class="rv-filmstrip-item"' not in html


def test_build_html_avoids_duplicate_category_labels_when_label_matches_category(
    report_payload: ReportPayload,
) -> None:
    payload: ReportPayload = {
        **report_payload,
        "frames": [
            {
                "number": 10,
                "label": "Motion",
                "detail": "Source frame 10",
                "category": "motion",
                "images": report_payload["frames"][0]["images"],
            },
        ],
        "stats": {"frame_count": 1, "clip_count": 2},
    }

    html = build_html(payload)

    assert '<span class="rv-filmstrip-label">Motion</span>' in html
    assert "Motion • Motion" not in html


def test_build_html_uses_internal_category_keys_for_reserved_category_text(
    report_payload: ReportPayload,
) -> None:
    payload: ReportPayload = {
        **report_payload,
        "frames": [
            {
                **report_payload["frames"][0],
                "category": "__all__",
            },
            report_payload["frames"][1],
        ],
    }

    html = build_html(payload)

    assert 'data-category-key="__fc_all__" aria-pressed="true">All (2)</button>' in html
    assert 'data-category-key="cat-0" data-category="__all__" aria-pressed="false"' in html
    assert 'value="0" data-category-key="cat-0" data-category="__all__">Frame 10</option>' in html
    assert (
        'class="rv-filmstrip-item" data-idx="0" data-category-key="cat-0" data-category="__all__"'
    ) in html
    assert (
        '<span class="rv-filmstrip-accent" '
        'data-category-key="cat-0" data-category="__all__"></span>'
    ) in html
    assert 'data-category-key="__all__"' not in html


def test_build_html_uses_payload_default_selection_for_clip_controls(
    report_payload: ReportPayload,
) -> None:
    payload: ReportPayload = {
        **report_payload,
        "default_selection": {
            "left_clip_index": 1,
            "right_clip_index": 0,
        },
    }

    parser = SelectParser()
    parser.feed(build_html(payload))

    left_selected = [
        option.text
        for option in parser.selects["left-select"].options
        if "selected" in option.attrs
    ]
    right_selected = [
        option.text
        for option in parser.selects["right-select"].options
        if "selected" in option.attrs
    ]
    active_selected = [
        option.text
        for option in parser.selects["active-select"].options
        if "selected" in option.attrs
    ]

    assert left_selected == ['ENC "candidate"']
    assert right_selected == ["REF <main>"]
    assert active_selected == ['ENC "candidate"']


def test_build_html_renders_viewport_audit_controls(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    document = parse_elements(html)
    palette = require_first(document, tag="div", class_name="rv-viewport-palette")

    assert palette.attrs["role"] == "toolbar"
    assert palette.attrs["aria-label"] == "Viewport controls"
    assert palette.attrs["data-orientation"] == "horizontal"
    stage_start = html.index('<div class="rv-viewer-stage rv-mode-slider"')
    palette_start = html.index('class="rv-viewport-palette"')
    controls_start = html.index('<div class="rv-controls"')
    assert palette_start > stage_start
    assert controls_start < palette_start
    assert 'id="alignment-status" class="rv-alignment-status"' in html
    assert "Aligned: none" in html
    assert 'role="radiogroup" aria-label="Fit mode"' in html
    assert 'data-fit="actual"' in html
    assert 'aria-label="Actual size"' in html
    assert 'data-fit="width"' in html
    assert 'aria-label="Fit width"' in html
    assert 'data-fit="height"' in html
    assert 'aria-label="Fit height"' in html
    assert 'data-fit="fill"' not in html
    assert 'aria-label="Fill stage"' not in html
    assert 'id="alignment-preset" aria-label="Alignment preset"' in html
    assert '<option value="left-1">Left 1px</option>' in html
    assert '<option value="custom">Custom</option>' in html
    assert 'id="align-x"' in html
    assert 'aria-label="Manual horizontal alignment offset"' in html
    assert 'id="align-y"' in html
    assert 'aria-label="Manual vertical alignment offset"' in html
    assert 'id="btn-fullscreen"' in html
    assert 'aria-label="Enter fullscreen"' in html
    assert 'aria-pressed="false"' in html
    assert (
        'id="btn-fullscreen" aria-label="Enter fullscreen" aria-pressed="false" '
        'title="Enter fullscreen"><span class="rv-fullscreen-icon" aria-hidden="true">⛶</span></button>'
    ) in html
    assert 'id="btn-focus-mode"' not in html
    assert 'id="btn-overlays"' in html
    assert 'aria-label="Hide HUD"' in html
    assert ">HUD</button>" in html
    assert 'class="rv-palette-group rv-blink-controls" data-control-scope="blink" hidden' in html
    assert 'id="btn-blink-pause" aria-label="Pause blink" aria-pressed="false"' in html
    assert '<option value="300">0.3s</option>' in html
    assert '<option value="700" selected>0.7s</option>' in html
    assert '<option value="1200">1.2s</option>' in html
    assert 'id="blink-status" class="rv-blink-status" role="status" aria-live="polite"' in html

    active_filter_badge = require_first(document, tag="span", element_id="active-filter-badge")
    assert "rv-active-filter-badge" in active_filter_badge.classes
    assert "hidden" in active_filter_badge.attrs

    orientation_button = require_first(palette, tag="button", element_id="btn-palette-orientation")
    assert orientation_button.attrs["aria-label"] == "Toggle palette orientation"
    assert orientation_button.text == "↔"

    fit_buttons = {
        child.attrs.get("data-fit"): child
        for group in find_children(palette, tag="div", class_name="rv-palette-group")
        for child in group.children
        if child.tag == "button" and "data-fit" in child.attrs
    }
    assert fit_buttons["actual"].text == "1:1"
    assert fit_buttons["actual"].attrs["title"] == "Actual size (1:1)"
    assert fit_buttons["width"].text == "↔"
    assert fit_buttons["width"].attrs["title"] == "Fit width (↔)"
    assert fit_buttons["height"].text == "↕"
    assert fit_buttons["height"].attrs["title"] == "Fit height (↕)"
    assert "fill" not in fit_buttons
    assert '<div class="rv-modal-subtitle">Viewport Fit Modes</div>' in html


def test_build_html_renders_inspector_drawer(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)

    assert (
        'id="rv-inspector" class="rv-inspector" aria-hidden="true" '
        'aria-labelledby="rv-inspector-title" inert'
    ) in html
    assert 'role="tablist" aria-label="Inspector tabs"' in html
    for tab in ("frame", "clips", "align", "export"):
        assert f'data-inspector-tab="{tab}"' in html
        assert f'id="inspector-panel-{tab}"' in html
        tab_start = html.index(f'data-inspector-tab="{tab}"')
        tab_end = html.index("</button>", tab_start)
        assert 'tabindex="-1"' in html[tab_start:tab_end]

    assert "data-inspector-frame-label" in html
    assert "data-inspector-frame-position" in html
    assert "data-inspector-clips" in html
    assert "data-inspector-align-pair" in html
    assert 'id="btn-inspector-reset-current-align"' in html
    assert 'id="btn-inspector-reset-all-align"' in html
    for button_id in (
        "btn-inspector-close",
        "btn-inspector-reset-current-align",
        "btn-inspector-reset-all-align",
    ):
        button_start = html.index(f'id="{button_id}"')
        button_end = html.index("</button>", button_start)
        assert 'tabindex="-1"' in html[button_start:button_end]
    assert "Offsets are scoped to the selected pair." in html
    assert "data-inspector-export-summary" in html
    assert "data-focus-frame" not in html
    assert "data-focus-mode" not in html
    assert "data-focus-pair" not in html


def test_build_html_renders_keyboard_help_accessibility_hooks(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert (
        'id="help-modal" class="rv-modal" aria-hidden="true" role="dialog" '
        'aria-modal="true" aria-labelledby="help-modal-title" tabindex="-1"'
    ) in html
    assert 'id="help-modal-title" class="rv-modal-title">Viewer Shortcuts</div>' in html
    assert (
        '<div class="rv-shortcut-row"><span>Swap Clips</span><span class="rv-key">X</span></div>'
        in html
    )
    assert (
        '<div class="rv-shortcut-row"><span>Toggle HUD</span><span class="rv-key">H</span></div>'
        in html
    )
    assert (
        '<div class="rv-shortcut-row"><span>Toggle Inspector</span><span class="rv-key">I</span></div>'
        in html
    )
    assert (
        '<div class="rv-shortcut-row"><span>Blink Pause / Speed</span><span class="rv-key">Space / [ / ]</span></div>'
        in html
    )
    assert "Toggle Focus" not in html
    assert "Modes (Slider/Single/Diff/Blink)" in html
    assert (
        '<div class="rv-shortcut-row"><span>Reset Viewport</span><span class="rv-key">R / Double-click</span></div>'
        in html
    )
    assert (
        '<div class="rv-shortcut-row"><span>Open Help</span><span class="rv-key">?</span></div>'
        in html
    )
    assert (
        '<div class="rv-shortcut-row"><span>Close Panel / Exit Fullscreen</span>'
        '<span class="rv-key">Esc</span></div>'
    ) in html


def test_build_html_embeds_json_without_raw_script_terminators(
    report_payload: ReportPayload,
) -> None:
    hazardous_title = '</script><script>alert("x")</script>&'
    hazardous_payload: ReportPayload = {**report_payload, "title": hazardous_title}

    html = build_html(hazardous_payload)
    marker = '<script type="application/json" id="report-data">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    json_text = html[start:end]

    assert hazardous_title not in html
    assert "&lt;/script&gt;&lt;script&gt;alert" in html
    assert "</script>" not in json_text
    assert "<script>" not in json_text
    assert "\\u003c/script\\u003e" in json_text
    assert "\\u0026" in json_text
    assert script_payload(html)["title"] == hazardous_title


def test_build_html_toggles_filmstrip_visibility(report_payload: ReportPayload) -> None:
    visible_html = build_html(report_payload, include_filmstrip=True)
    visible_document = parse_elements(visible_html)
    visible_panel = require_first(visible_document, tag="section", class_name="rv-bottom-panel")
    visible_panel_bar = require_first(visible_panel, tag="div", class_name="rv-bottom-panel-bar")
    visible_filter_group = require_first(visible_panel_bar, tag="div", class_name="rv-filter-group")
    visible_filmstrip_controls = require_first(
        visible_panel_bar, tag="div", class_name="rv-filmstrip-controls"
    )
    visible_toggle = require_first(
        visible_filmstrip_controls, tag="button", element_id="btn-filmstrip-toggle"
    )

    assert visible_panel.attrs["data-filmstrip-enabled"] == "true"
    assert visible_panel.attrs["aria-label"] == "Frame timeline"
    assert visible_filter_group.attrs["data-control-scope"] == "frame-filters"
    assert visible_filter_group.attrs["aria-label"] == "Frame category filters"
    assert visible_toggle.attrs["type"] == "button"
    assert visible_toggle.attrs["aria-expanded"] == "true"
    assert visible_toggle.attrs["aria-label"] == "Collapse timeline controls"
    assert visible_toggle.attrs["title"] == "Toggle timeline (F)"
    assert visible_toggle.text == "Hide timeline"

    size_buttons = {
        child.attrs.get("data-filmstrip-size"): child
        for size_control in find_children(
            visible_filmstrip_controls, tag="div", class_name="rv-filmstrip-size-control"
        )
        for child in size_control.children
        if child.tag == "button"
    }
    assert size_buttons["compact"].attrs["role"] == "radio"
    assert size_buttons["compact"].attrs["aria-checked"] == "false"
    assert size_buttons["normal"].attrs["role"] == "radio"
    assert size_buttons["normal"].attrs["aria-checked"] == "true"
    assert "active" in size_buttons["normal"].classes
    assert size_buttons["large"].attrs["role"] == "radio"
    assert size_buttons["large"].attrs["aria-checked"] == "false"
    assert 'class="rv-filmstrip"' in visible_html
    assert 'aria-label="Frame thumbnails"' in visible_html
    assert 'aria-hidden="false"' in visible_html
    assert 'class="rv-filmstrip-item"' in visible_html
    assert 'alt="REF &lt;main&gt; - Frame 10"' in visible_html

    hidden_html = build_html(report_payload, include_filmstrip=False)
    hidden_document = parse_elements(hidden_html)
    hidden_panel = require_first(hidden_document, tag="section", class_name="rv-bottom-panel")
    hidden_toggle = require_first(hidden_panel, tag="button", element_id="btn-filmstrip-toggle")

    assert hidden_panel.attrs["data-filmstrip-enabled"] == "false"
    assert hidden_panel.attrs["aria-label"] == "Frame timeline"
    assert hidden_toggle.attrs["type"] == "button"
    assert hidden_toggle.attrs["aria-expanded"] == "false"
    assert hidden_toggle.attrs["aria-label"] == "Filmstrip disabled"
    assert hidden_toggle.attrs["title"] == "Filmstrip disabled"
    assert "disabled" in hidden_toggle.attrs
    assert hidden_toggle.text == "Filmstrip disabled"
    assert 'class="rv-filmstrip rv-filmstrip--hidden"' in hidden_html
    assert 'aria-label="Frame thumbnails disabled"' in hidden_html
    assert 'aria-hidden="true"' in hidden_html
    assert 'class="rv-filmstrip-item"' not in hidden_html


def test_report_viewer_assets_and_markup_stay_offline(report_payload: ReportPayload) -> None:
    js = get_js()
    js_urls = re.findall(r'https?://[^\s\'"<>]+', js)
    for url in js_urls:
        if not url.startswith(("http://www.w3.org/", "https://www.w3.org/")):
            raise AssertionError(f"Found forbidden external URL in JS: {url}")

    rendered_html = build_html(report_payload)
    html_urls = re.findall(r'https?://[^\s\'"<>]+', rendered_html)
    allowed_html_urls = {
        "http://www.w3.org/2000/svg",
        "https://www.w3.org/2000/svg",
    }
    if report_payload["slowpics_url"] is not None:
        allowed_html_urls.add(report_payload["slowpics_url"])
        allowed_html_urls.add(html_module.escape(report_payload["slowpics_url"], quote=True))
        allowed_html_urls.add(report_payload["slowpics_url"].replace("&", "\\u0026"))
    for url in html_urls:
        if url not in allowed_html_urls:
            raise AssertionError(f"Found forbidden external URL in HTML: {url}")
