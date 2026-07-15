"""Markup and payload contract tests for the report renderer module."""

from __future__ import annotations

import html as html_module
import re

from frame_compare.services.report.payload import ReportPayload
from frame_compare.services.report.renderer import build_html
from frame_compare.services.report.viewer import get_css, get_js
from tests.services.report_viewer_contracts import (
    SelectParser,
    find_all,
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
    document = parse_elements(html)
    tags = parse_start_tags(html)

    pair_controls = require_first(
        document, tag="div", attr_name="data-control-scope", attr_value="pair"
    )
    active_controls = require_first(
        document, tag="div", attr_name="data-control-scope", attr_value="active"
    )
    assert pair_controls.attrs["aria-label"] == "Comparison pair"
    assert active_controls.attrs["aria-label"] == "Single clip"
    assert "hidden" in active_controls.attrs
    assert tags.by_id["left-select"][1]["aria-label"] == "Left clip"
    assert tags.by_id["right-select"][1]["aria-label"] == "Right clip"
    assert tags.by_id["active-select"][1]["aria-label"] == "Single clip"
    assert tags.by_id["btn-swap-clips"][0] == "button"
    assert 'data-mode="overlay" role="radio"' in html


def test_build_html_exposes_viewer_only_grid_controls_and_empty_mount(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)
    document = parse_elements(html)
    tags = parse_start_tags(html)

    grid_button = require_first(document, tag="button", attr_name="data-mode", attr_value="grid")
    grid_controls = require_first(
        document, tag="div", attr_name="data-control-scope", attr_value="grid"
    )
    grid = require_first(document, tag="section", element_id="rv-grid")
    cells = require_first(grid, tag="div", attr_name="data-grid-cells")

    assert grid_button.attrs["aria-label"] == "Grid mode"
    assert grid_controls.attrs["aria-label"] == "Grid clips"
    assert "hidden" in grid_controls.attrs
    assert tags.by_id["btn-grid-prev"][1]["aria-label"] == "Previous grid clips"
    assert tags.by_id["btn-grid-next"][1]["aria-label"] == "Next grid clips"
    assert grid.attrs["aria-label"] == "Grid comparison"
    assert "hidden" in grid.attrs
    assert cells.children == []
    assert script_payload(html)["default_mode"] == "slider"
    assert html.count('id="pixel-inspector-live"') == 1


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

    assert "text-overflow: ellipsis;" in css
    assert "flex-wrap: wrap;" in css
    assert ".rv-mode-slider #label-left" in css
    assert ".rv-mode-slider #label-right" in css


def test_build_html_renders_frame_metadata_and_category_filters(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)
    document = parse_elements(html)
    parser = SelectParser()
    parser.feed(html)

    filters = require_first(
        document, tag="div", attr_name="data-control-scope", attr_value="frame-filters"
    )
    assert filters.attrs["aria-label"] == "Frame category filters"
    all_filter = require_first(
        filters, tag="button", attr_name="data-category-key", attr_value="__fc_all__"
    )
    assert all_filter.attrs["aria-pressed"] == "true"
    selected_filter = require_first(
        filters, tag="button", attr_name="data-category", attr_value="selected"
    )
    scene_cut_filter = require_first(
        filters, tag="button", attr_name="data-category", attr_value="scene-cut"
    )
    assert selected_filter.attrs["aria-pressed"] == "false"
    assert scene_cut_filter.attrs["aria-pressed"] == "false"
    assert parser.selects["frame-select"].options[1].attrs["data-category"] == "scene-cut"
    assert "Source frame 10</span>" not in html
    assert find_all(
        document,
        tag="span",
        class_name="rv-filmstrip-accent",
        attr_name="data-category",
        attr_value="scene-cut",
    )


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
    document = parse_elements(html)
    stage = require_first(document, tag="div", class_name="rv-viewer-stage")
    canvas = require_first(stage, tag="div", class_name="rv-canvas")
    stage_labels = require_first(stage, tag="div", class_name="rv-stage-labels")

    assert stage.attrs["role"] == "region"
    assert stage.attrs["aria-label"] == "Comparison viewer"
    assert canvas.attrs["role"] == "img"
    assert canvas.attrs["aria-label"] == "Comparison image canvas"
    assert stage_labels.attrs["aria-hidden"] == "true"
    require_first(stage_labels, tag="div", element_id="label-left")
    require_first(stage_labels, tag="div", element_id="label-right")
    for layer_class in ("rv-left", "rv-right"):
        layer = require_first(canvas, tag="div", class_name=layer_class)
        assert not find_all(layer, element_id="label-left")
        assert not find_all(layer, element_id="label-right")


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

    document = parse_elements(html)
    assert require_first(document, tag="span", class_name="rv-filmstrip-label").text == "Motion"
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
    document = parse_elements(html)
    parser = SelectParser()
    parser.feed(html)

    all_filter = require_first(
        document, tag="button", attr_name="data-category-key", attr_value="__fc_all__"
    )
    assert all_filter.attrs["aria-pressed"] == "true"
    reserved_filter = require_first(
        document, tag="button", attr_name="data-category", attr_value="__all__"
    )
    assert reserved_filter.attrs["data-category-key"] != "__all__"
    reserved_option = parser.selects["frame-select"].options[0]
    assert reserved_option.attrs["data-category"] == "__all__"
    assert reserved_option.attrs["data-category-key"] != "__all__"
    assert find_all(
        document,
        tag="button",
        class_name="rv-filmstrip-item",
        attr_name="data-category",
        attr_value="__all__",
    )
    assert find_all(
        document,
        tag="span",
        class_name="rv-filmstrip-accent",
        attr_name="data-category",
        attr_value="__all__",
    )
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
    stage = require_first(document, tag="div", class_name="rv-viewer-stage")
    controls = require_first(document, tag="div", class_name="rv-controls")
    palette = require_first(document, tag="div", class_name="rv-viewport-palette")

    assert palette.attrs["role"] == "toolbar"
    assert palette.attrs["aria-label"] == "Viewport controls"
    assert palette.attrs["data-orientation"] == "horizontal"
    assert controls.attrs["role"] == "toolbar"
    assert stage.attrs["aria-label"] == "Comparison viewer"

    alignment_status = require_first(document, tag="div", element_id="alignment-status")
    assert "rv-alignment-status" in alignment_status.classes
    assert alignment_status.text
    fit_group = require_first(palette, tag="div", attr_name="role", attr_value="radiogroup")
    assert fit_group.attrs["aria-label"] == "Fit mode"
    fit_buttons = {
        child.attrs.get("data-fit"): child
        for group in find_children(palette, tag="div", class_name="rv-palette-group")
        for child in group.children
        if child.tag == "button" and "data-fit" in child.attrs
    }
    assert set(fit_buttons) == {"actual", "width", "height"}
    assert fit_buttons["actual"].attrs["aria-label"] == "Actual size"
    assert fit_buttons["width"].attrs["aria-label"] == "Fit width"
    assert fit_buttons["height"].attrs["aria-label"] == "Fit height"

    tags = parse_start_tags(html)
    assert tags.by_id["alignment-preset"][1]["aria-label"] == "Alignment preset"
    assert tags.by_id["align-x"][1]["aria-label"] == "Manual horizontal alignment offset"
    assert tags.by_id["align-y"][1]["aria-label"] == "Manual vertical alignment offset"
    fullscreen_button = require_first(palette, tag="button", element_id="btn-fullscreen")
    assert fullscreen_button.attrs["aria-label"] == "Enter fullscreen"
    assert fullscreen_button.attrs["aria-pressed"] == "false"
    assert 'id="btn-focus-mode"' not in html
    overlays_button = require_first(palette, tag="button", element_id="btn-overlays")
    assert overlays_button.attrs["aria-label"] == "Hide HUD"
    blink_controls = require_first(
        palette, tag="div", attr_name="data-control-scope", attr_value="blink"
    )
    assert "hidden" in blink_controls.attrs
    blink_pause = require_first(blink_controls, tag="button", element_id="btn-blink-pause")
    assert blink_pause.attrs["aria-label"] == "Pause blink"
    assert blink_pause.attrs["aria-pressed"] == "false"
    blink_status = require_first(blink_controls, tag="span", element_id="blink-status")
    assert blink_status.attrs["role"] == "status"
    assert blink_status.attrs["aria-live"] == "polite"

    active_filter_badge = require_first(document, tag="span", element_id="active-filter-badge")
    assert "rv-active-filter-badge" in active_filter_badge.classes
    assert "hidden" in active_filter_badge.attrs

    orientation_button = require_first(palette, tag="button", element_id="btn-palette-orientation")
    assert orientation_button.attrs["aria-label"] == "Toggle palette orientation"


def test_build_html_renders_inspector_drawer(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    document = parse_elements(html)

    inspector = require_first(document, tag="aside", element_id="rv-inspector")
    assert "rv-inspector" in inspector.classes
    assert inspector.attrs["aria-hidden"] == "true"
    assert inspector.attrs["aria-labelledby"] == "rv-inspector-title"
    assert "inert" in inspector.attrs
    tablist = require_first(inspector, tag="div", attr_name="role", attr_value="tablist")
    assert tablist.attrs["aria-label"] == "Inspector tabs"
    tab_names = [
        child.attrs.get("data-inspector-tab") for child in tablist.children if child.tag == "button"
    ]
    assert tab_names == ["pixel", "frame", "clips", "align", "review", "export"]
    for tab in ("pixel", "frame", "clips", "align", "review", "export"):
        tab_button = require_first(
            tablist, tag="button", attr_name="data-inspector-tab", attr_value=tab
        )
        assert tab_button.attrs["tabindex"] == "-1"
        panel = require_first(inspector, element_id=f"inspector-panel-{tab}")
        assert panel.attrs["tabindex"] == "-1"

    assert "data-inspector-frame-label" in html
    assert "data-inspector-frame-position" in html
    assert "data-inspector-clips" in html
    assert "data-inspector-align-pair" in html
    pixel_panel = require_first(inspector, element_id="inspector-panel-pixel")
    assert "hidden" in pixel_panel.attrs
    assert "Decoded display sample · 8-bit sRGB" in pixel_panel.text
    assert "Normalized cross-size mapping; not scene registration." in pixel_panel.text
    lens_toggle = require_first(pixel_panel, tag="button", element_id="pixel-lens-toggle")
    assert lens_toggle.attrs["aria-pressed"] == "false"
    magnification = find_all(
        pixel_panel,
        tag="button",
        attr_name="data-pixel-magnification",
    )
    assert [button.attrs["data-pixel-magnification"] for button in magnification] == [
        "2",
        "4",
        "8",
    ]
    assert [button.attrs["aria-label"] for button in magnification] == [
        "Magnification 2×",
        "Magnification 4×",
        "Magnification 8×",
    ]
    live = require_first(document, tag="div", element_id="pixel-inspector-live")
    assert live.attrs["role"] == "status"
    assert live.attrs["aria-live"] == "polite"
    assert find_all(pixel_panel, tag="div", element_id="pixel-inspector-live") == []
    for button_id in (
        "btn-inspector-close",
        "btn-inspector-reset-current-align",
        "btn-inspector-reset-all-align",
    ):
        button = require_first(inspector, tag="button", element_id=button_id)
        assert button.attrs["tabindex"] == "-1"
    assert "data-inspector-export-summary" in html
    review_panel = require_first(inspector, element_id="inspector-panel-review")
    review_note = require_first(review_panel, tag="textarea", attr_name="data-review-note")
    review_note_count = require_first(review_panel, tag="span", attr_name="data-review-note-count")
    assert review_note.attrs["maxlength"] == "2000"
    assert review_note_count.text == "0 / 1000"
    assert require_first(review_panel, tag="input", attr_name="data-review-bookmark")
    assert require_first(review_panel, tag="select", attr_name="data-review-tag")
    assert require_first(review_panel, tag="select", attr_name="data-review-preferred")
    assert require_first(review_panel, tag="input", attr_name="data-review-import")
    review_status = require_first(review_panel, attr_name="data-review-status")
    assert "role" not in review_status.attrs
    assert "aria-live" not in review_status.attrs
    assert html.count('id="pixel-inspector-live"') == 1
    assert "data-focus-frame" not in html
    assert "data-focus-mode" not in html
    assert "data-focus-pair" not in html


def test_build_html_renders_pixel_inspection_stage_controls(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)
    document = parse_elements(html)
    controls = require_first(document, tag="div", class_name="rv-controls")
    inspect_button = require_first(controls, tag="button", element_id="btn-inspect")
    assert inspect_button.attrs["aria-label"] == "Open pixel inspector"
    assert inspect_button.attrs["title"] == "Inspect pixels (M)"

    stage = require_first(document, tag="div", class_name="rv-viewer-stage")
    roi = require_first(stage, tag="button", element_id="rv-inspection-point")
    assert roi.attrs["aria-label"] == "Inspection point unavailable"
    assert roi.attrs["aria-pressed"] == "false"
    assert roi.attrs["tabindex"] == "-1"
    assert "hidden" in roi.attrs

    lens = require_first(stage, tag="aside", element_id="rv-pixel-lens")
    assert lens.attrs["aria-label"] == "Pixel lens"
    assert lens.attrs["data-magnification"] == "4"
    assert len(find_all(lens, tag="img")) == 1
    assert not find_all(stage, tag="canvas")


def test_build_html_renders_keyboard_help_accessibility_hooks(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)
    document = parse_elements(html)

    modal = require_first(document, tag="div", element_id="help-modal")
    assert "rv-modal" in modal.classes
    assert modal.attrs["aria-hidden"] == "true"
    assert modal.attrs["role"] == "dialog"
    assert modal.attrs["aria-modal"] == "true"
    assert modal.attrs["aria-labelledby"] == "help-modal-title"
    assert modal.attrs["tabindex"] == "-1"
    shortcut_rows = find_all(modal, tag="div", class_name="rv-shortcut-row")
    assert len(shortcut_rows) >= 6
    assert "Toggle Focus" not in modal.text


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
    visible_filmstrip = require_first(visible_document, tag="nav", class_name="rv-filmstrip")
    assert visible_filmstrip.attrs["aria-label"] == "Frame thumbnails"
    assert visible_filmstrip.attrs["aria-hidden"] == "false"
    assert find_all(visible_filmstrip, tag="button", class_name="rv-filmstrip-item")

    hidden_html = build_html(report_payload, include_filmstrip=False)
    hidden_document = parse_elements(hidden_html)
    hidden_panel = require_first(hidden_document, tag="section", class_name="rv-bottom-panel")
    hidden_toggle = require_first(hidden_panel, tag="button", element_id="btn-filmstrip-toggle")

    assert hidden_panel.attrs["data-filmstrip-enabled"] == "false"
    assert hidden_panel.attrs["aria-label"] == "Frame timeline"
    assert hidden_toggle.attrs["type"] == "button"
    assert hidden_toggle.attrs["aria-expanded"] == "false"
    assert hidden_toggle.attrs["aria-label"] == "Filmstrip disabled"
    assert "disabled" in hidden_toggle.attrs
    hidden_filmstrip = require_first(hidden_document, tag="nav", class_name="rv-filmstrip")
    assert "rv-filmstrip--hidden" in hidden_filmstrip.classes
    assert hidden_filmstrip.attrs["aria-label"] == "Frame thumbnails disabled"
    assert hidden_filmstrip.attrs["aria-hidden"] == "true"
    assert not find_all(hidden_filmstrip, tag="button", class_name="rv-filmstrip-item")


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
