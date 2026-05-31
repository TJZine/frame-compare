"""Direct behavior tests for the report renderer module."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html.parser import HTMLParser

import pytest

from frame_compare.services.report.payload import ReportPayload
from frame_compare.services.report.renderer import build_html
from frame_compare.services.report.viewer import get_css, get_js


@dataclass
class _ParsedOption:
    text: str
    attrs: dict[str, str | None]


@dataclass
class _ParsedSelect:
    attrs: dict[str, str | None]
    options: list[_ParsedOption] = field(default_factory=list)


class _SelectParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.selects: dict[str, _ParsedSelect] = {}
        self._current_select_id: str | None = None
        self._current_option_attrs: dict[str, str | None] | None = None
        self._current_option_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "select":
            select_id = attr_map.get("id")
            if select_id is not None:
                self.selects[select_id] = _ParsedSelect(attrs=attr_map)
                self._current_select_id = select_id
        elif tag == "option" and self._current_select_id is not None:
            self._current_option_attrs = attr_map
            self._current_option_text = []

    def handle_data(self, data: str) -> None:
        if self._current_option_attrs is not None:
            self._current_option_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self._current_option_attrs is not None:
            if self._current_select_id is not None:
                self.selects[self._current_select_id].options.append(
                    _ParsedOption(
                        text="".join(self._current_option_text),
                        attrs=self._current_option_attrs,
                    )
                )
            self._current_option_attrs = None
            self._current_option_text = []
        elif tag == "select":
            self._current_select_id = None


@pytest.fixture
def report_payload() -> ReportPayload:
    return {
        "version": "1.0",
        "report_id": "report_0123456789abcdef0123456789abcdef",
        "generated_at": "2026-05-22T12:00:00+00:00",
        "title": "Renderer Contract",
        "slowpics_url": "https://slow.pics/c/abc?x=1&y=2",
        "default_mode": "slider",
        "default_selection": {
            "left_clip_index": 0,
            "right_clip_index": 1,
        },
        "stats": {
            "frame_count": 2,
            "clip_count": 2,
        },
        "clips": [
            {
                "name": "reference",
                "label": "REF <main>",
                "frame_count": 100,
                "resolution": (1920, 1080),
                "fps": 24.0,
                "hdr": False,
            },
            {
                "name": "encode",
                "label": 'ENC "candidate"',
                "frame_count": 100,
                "resolution": (1920, 1080),
                "fps": 24.0,
                "hdr": True,
            },
        ],
        "frames": [
            {
                "number": 10,
                "label": "Frame 10",
                "detail": "Source frame 10",
                "category": "selected",
                "images": [
                    {"clip": "reference", "src": "reference/10.png"},
                    {"clip": "encode", "src": "encode/10.png"},
                ],
            },
            {
                "number": 20,
                "label": "Frame 20",
                "detail": "Source frame 20",
                "category": "scene-cut",
                "images": [
                    {"clip": "reference", "src": "reference/20.png"},
                    {"clip": "encode", "src": "encode/20.png"},
                ],
            },
        ],
    }


def _script_payload(html: str) -> ReportPayload:
    marker = '<script type="application/json" id="report-data">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    return json.loads(html[start:end])


def test_build_html_renders_only_safe_slowpics_links(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)

    assert 'href="https://slow.pics/c/abc?x=1&amp;y=2"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "View on slow.pics" in html

    unsafe_payload: ReportPayload = {**report_payload, "slowpics_url": "javascript:alert(1)"}
    unsafe_html = build_html(unsafe_payload)

    assert "javascript:alert(1)" in unsafe_html
    assert 'href="javascript:alert(1)"' not in unsafe_html
    assert "View on slow.pics" not in unsafe_html

    no_upload_payload: ReportPayload = {**report_payload, "slowpics_url": None}
    no_upload_html = build_html(no_upload_payload)

    assert "View on slow.pics" not in no_upload_html
    assert 'class="rv-link"' not in no_upload_html


def test_build_html_renders_frame_and_clip_selectors(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    parser = _SelectParser()
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
    assert parser.selects["active-select"].attrs["aria-label"] == "Overlay clip"
    active_reference = next(
        option for option in parser.selects["active-select"].options if option.text == "REF <main>"
    )
    assert "selected" in active_reference.attrs


def test_build_html_renders_mode_aware_clip_controls(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)

    assert 'data-control-scope="pair" aria-label="Comparison pair"' in html
    assert 'data-control-scope="active" aria-label="Overlay clip" hidden' in html
    assert 'id="left-select" aria-label="Left clip"' in html
    assert 'id="right-select" aria-label="Right clip"' in html
    assert 'id="active-select" aria-label="Overlay clip"' in html


def test_build_html_renders_frame_metadata_and_category_filters(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert 'data-control-scope="frame-filters" aria-label="Frame category filters"' in html
    assert 'data-category-key="__fc_all__" aria-pressed="true">All</button>' in html
    assert 'data-category-key="cat-0" data-category="selected" aria-pressed="false"' in html
    assert 'data-category-key="cat-1" data-category="scene-cut" aria-pressed="false"' in html
    assert '<span class="rv-filmstrip-label">Frame 10</span>' in html
    assert '<span class="rv-filmstrip-detail">Source frame 10</span>' in html
    assert (
        '<span class="rv-category-badge rv-filmstrip-category" '
        'data-category-key="cat-1" data-category="scene-cut">scene-cut</span>'
    ) in html
    assert 'data-category-key="cat-0" data-category="selected">selected</span></button>' in html
    assert 'value="1" data-category-key="cat-1" data-category="scene-cut">Frame 20</option>' in html


def test_build_html_renders_collapsed_progressive_metadata(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert '<section class="rv-metadata-bar" aria-label="Report metadata">' in html
    assert '<details class="rv-disclosure" data-report-metadata>' in html
    assert '<summary>Report <span class="rv-summary-value">slider</span></summary>' in html
    assert "<dt>Report ID</dt>" in html
    assert "report_0123456789abcdef0123456789abcdef" in html
    assert "<dt>Default pair</dt>" in html
    assert 'REF &lt;main&gt; vs ENC "candidate"' in html
    assert '<details class="rv-disclosure" data-clip-metadata>' in html
    assert '<li class="rv-clip-meta-item" data-clip-index="0">' in html
    assert "<dt>Resolution</dt><dd>1920x1080</dd>" in html
    assert "<dt>FPS</dt><dd>24 fps</dd>" in html
    assert "<dt>Frames</dt><dd>100</dd>" in html
    assert '<details class="rv-disclosure" data-frame-metadata>' in html
    assert '<span class="rv-summary-value" data-current-frame-summary>Frame 10</span>' in html


def test_build_html_exposes_current_frame_detail_hooks(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert "<dt>Label</dt><dd data-current-frame-label>Frame 10</dd>" in html
    assert "<dt>Detail</dt><dd data-current-frame-detail>Source frame 10</dd>" in html
    assert "<dt>Category</dt><dd data-current-frame-category>selected</dd>" in html


def test_build_html_metadata_disclosures_default_collapsed(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert '<details class="rv-disclosure" data-report-metadata open>' not in html
    assert '<details class="rv-disclosure" data-clip-metadata open>' not in html
    assert '<details class="rv-disclosure" data-frame-metadata open>' not in html


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

    assert '<div id="viewer-status" class="rv-status" role="status" aria-live="polite" hidden></div>' in html
    assert '<div class="rv-empty-state" data-empty-state hidden></div>' in html
    assert '<div class="rv-metadata-empty">No clips in payload.</div>' in html
    assert "<dd data-current-frame-label>No frame selected</dd>" in html
    assert "<dd data-current-frame-detail>No frame detail available.</dd>" in html
    assert "<dd data-current-frame-category>none</dd>" in html
    assert 'class="rv-filmstrip-item"' not in html


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

    assert 'data-category-key="__fc_all__" aria-pressed="true">All</button>' in html
    assert 'data-category-key="cat-0" data-category="__all__" aria-pressed="false"' in html
    assert 'data-category-key="cat-0" data-category="__all__">__all__</span></button>' in html
    assert 'value="0" data-category-key="cat-0" data-category="__all__">Frame 10</option>' in html
    assert (
        'class="rv-filmstrip-item" data-idx="0" data-category-key="cat-0" '
        'data-category="__all__"'
    ) in html
    assert (
        '<span class="rv-category-badge rv-filmstrip-category" '
        'data-category-key="cat-0" data-category="__all__">__all__</span>'
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

    parser = _SelectParser()
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

    assert 'role="radiogroup" aria-label="Fit mode"' in html
    assert 'data-fit="actual"' in html
    assert 'aria-label="Actual size"' in html
    assert 'data-fit="width"' in html
    assert 'aria-label="Fit width"' in html
    assert 'data-fit="height"' in html
    assert 'aria-label="Fit height"' in html
    assert 'data-fit="fill"' in html
    assert 'aria-label="Fill stage"' in html
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


def test_build_html_renders_keyboard_help_accessibility_hooks(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)

    assert (
        'id="help-modal" class="rv-modal" aria-hidden="true" role="dialog" '
        'aria-modal="true" aria-labelledby="help-modal-title" tabindex="-1"'
    ) in html
    assert 'id="help-modal-title" class="rv-modal-title">Keyboard Shortcuts</div>' in html
    assert '<div class="rv-shortcut-row"><span>Reset Viewport</span><span class="rv-key">R</span></div>' in html
    assert '<div class="rv-shortcut-row"><span>Open Help</span><span class="rv-key">?</span></div>' in html
    assert (
        '<div class="rv-shortcut-row"><span>Close Help / Exit Fullscreen</span>'
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
    assert _script_payload(html)["title"] == hazardous_title


def test_build_html_toggles_filmstrip_visibility(report_payload: ReportPayload) -> None:
    visible_html = build_html(report_payload, include_filmstrip=True)

    assert 'class="rv-filmstrip"' in visible_html
    assert 'aria-label="Frame thumbnails"' in visible_html
    assert 'aria-hidden="false"' in visible_html
    assert 'class="rv-filmstrip-item"' in visible_html
    assert 'alt="REF &lt;main&gt; - Frame 10"' in visible_html

    hidden_html = build_html(report_payload, include_filmstrip=False)

    assert 'class="rv-filmstrip rv-filmstrip--hidden"' in hidden_html
    assert 'aria-label="Frame thumbnails disabled"' in hidden_html
    assert 'aria-hidden="true"' in hidden_html
    assert 'class="rv-filmstrip-item"' not in hidden_html


def test_viewer_assets_keep_divider_slider_only_and_pointer_safe() -> None:
    css = get_css()
    js = get_js()

    assert '--font-sans: -apple-system, "BlinkMacSystemFont", "Segoe UI"' in css
    assert ".rv-viewer-stage" in css
    assert "touch-action: none;" in css
    assert "cursor: grab;" in css
    assert ".rv-viewer-stage.is-panning { cursor: grabbing; }" in css
    assert ".rv-divider {\n    display: none;" in css
    assert ".rv-mode-slider .rv-divider { display: block; }" in css
    assert ".rv-viewer-stage:fullscreen" in css
    assert "translate(var(--pan-x, 0px), var(--pan-y, 0px)) scale(var(--zoom-level, 1))" in css
    assert ".rv-right { transform: translate(var(--align-x, 0px), var(--align-y, 0px)); }" in css
    assert ".rv-overlay-label:empty { display: none; }" in css

    assert "leftLabelTxt = `${leftClip.label} (Left)`;" in js
    assert "rightLabelTxt = `${rightClip.label} (Right)`;" in js
    assert "leftLabelTxt = activeClip.label;" in js
    assert 'rightLabelTxt = "";' in js

    assert "addEventListener('pointerdown'" in js
    assert "addEventListener('pointermove'" in js
    assert "addEventListener('pointercancel'" in js
    assert "e.touches[0]" not in js
    assert "e.clientX ||" not in js
    assert "document.querySelectorAll('[data-fit]')" in js
    assert "setAttribute('aria-checked', isActive)" in js
    assert "this.state.fitMode = 'custom';" in js
    assert "if (!['actual', 'width', 'height', 'fill'].includes(mode)) return;" in js
    assert ": Math.max(fitWidthZoom, fitHeightZoom);" in js
    assert "addEventListener('load', () => this.applyFitMode())" in js
    assert "window.addEventListener('resize', () => this.applyFitMode())" in js
    assert "document.addEventListener('fullscreenchange', () => {" in js
    assert "this.updateFullscreenButton();" in js
    assert "getBoundingClientRect()" in js
    assert "rect.width / zoom" in js
    assert "sliderCanvasRect()" in js
    assert "const rect = this.sliderCanvasRect();" in js
    assert "this.dom.canvas.getBoundingClientRect()" in js
    assert "const clampedClientX = Math.max(rect.left, Math.min(rect.right, e.clientX));" in js
    assert "case 'r': case 'R': this.resetViewport(); break;" in js
    assert "requestFullscreen?.()" in js
    assert "exitFullscreen?.()" in js
    assert "aria-pressed', isFullscreen ? 'true' : 'false'" in js
    assert "alert(" not in js


def test_viewer_assets_manage_help_focus_and_escape_semantics() -> None:
    js = get_js()

    assert "helpRestoreFocus: null" in js
    assert "openHelpModal()" in js
    assert "this.state.helpRestoreFocus = activeElement" in js
    assert "closeHelpModal(options = {})" in js
    assert "this.focusElement(restoreTarget);" in js
    assert "handleModalKey(e)" in js
    assert "if (e.key === 'Escape') {" in js
    assert "e.stopPropagation();" in js
    assert "this.closeHelpModal();" in js
    assert "document.exitFullscreen?.();" in js
    assert "this.openHelpModal();" in js


def test_viewer_assets_stop_modal_escape_before_document_fullscreen_handler() -> None:
    js = get_js()
    modal_escape_guard = """handleModalKey(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            this.closeHelpModal();
            return;
        }"""

    assert modal_escape_guard in js


def test_viewer_assets_wire_report_scoped_viewport_persistence() -> None:
    js = get_js()

    assert "this.state.storageKey = this.viewportStorageKey();" in js
    assert "frame-compare:report-viewer:${reportId}:viewport" in js
    assert "this.state.data?.report_id || 'unknown-report'" in js
    assert "restorePersistedState()" in js
    assert "persistViewportState()" in js
    assert "storage.setItem(this.state.storageKey, JSON.stringify(payload))" in js
    assert "mode: this.state.mode" in js
    assert "panX: this.state.panX" in js
    assert "alignmentPreset: this.state.alignmentPreset" in js


def test_viewer_assets_wire_pan_wheel_zoom_and_alignment_hooks() -> None:
    js = get_js()

    assert "panX: 0" in js
    assert "panY: 0" in js
    assert "this.dom.stage.addEventListener('wheel'" in js
    assert "this.zoomAtPoint(e.clientX, e.clientY, e.deltaY < 0 ? 1.1 : 1 / 1.1);" in js
    assert "this.setPan(this.state.panX + dx, this.state.panY + dy, { save: false });" in js
    assert "shouldPanFromPointer" in js
    assert "this.state.mode !== 'slider'" in js
    assert "updateSliderFromPointer(e);" in js
    assert "this.dom.stage.classList.add('is-panning');" in js
    assert "this.dom.canvas.style.setProperty('--pan-x', `${this.state.panX}px`);" in js
    assert "alignmentPreset: 'none'" in js
    assert "setAlignmentPreset(preset)" in js
    assert "setManualAlignment(x, y)" in js
    assert "this.dom.rightLayer.style.setProperty('--align-x', `${this.state.alignX}px`);" in js


def test_viewer_assets_keep_overlay_and_blink_clip_semantics() -> None:
    css = get_css()
    js = get_js()

    assert ".rv-control-group[hidden] { display: none; }" in css
    assert "const selection = this.state.data.default_selection || {};" in js
    assert "this.state.leftClipIdx = left;" in js
    assert "this.state.rightClipIdx = right;" in js
    assert "this.state.activeClipIdx = left;" in js
    assert "this.dom.pairControls.hidden = isOverlay;" in js
    assert "this.dom.activeControls.hidden = !isOverlay;" in js
    assert "this.dom.leftSelect.disabled = isOverlay;" in js
    assert "this.dom.activeSelect.disabled = !isOverlay;" in js
    assert "this.dom.leftSelect.setAttribute('aria-label', 'Base clip');" in js
    assert "this.dom.rightSelect.setAttribute('aria-label', 'Compare clip');" in js
    assert "this.dom.leftSelect.setAttribute('aria-label', 'First blink clip');" in js
    assert "this.dom.rightSelect.setAttribute('aria-label', 'Second blink clip');" in js
    assert "this.state.activeClipIdx === this.state.leftClipIdx" in js
    assert "? this.state.rightClipIdx" in js
    assert ": this.state.leftClipIdx" in js
    assert "(this.state.activeClipIdx + 1) % this.state.data.clips.length" not in js
    assert "this.state.mode === 'diff' || this.state.mode === 'blink'" in js


def test_viewer_assets_wire_category_filtering_and_visible_navigation() -> None:
    css = get_css()
    js = get_js()

    assert ".rv-filter-chip.active" in css
    assert ".rv-filmstrip-item[hidden] { display: none; }" in css
    assert ".rv-filmstrip-caption" in css
    assert ".rv-category-badge" in css

    assert "const ALL_CATEGORY_FILTER_KEY = '__fc_all__';" in js
    assert "activeCategoryKey: ALL_CATEGORY_FILTER_KEY" in js
    assert "buildCategoryFilterKeys()" in js
    assert "keys.set(category, `cat-${keys.size}`);" in js
    assert "isCategoryKeyVisible(categoryKey)" in js
    assert "document.querySelectorAll('[data-frame-filter]')" in js
    assert "setFrameFilter(categoryKey)" in js
    assert "visibleFrameIndexes()" in js
    assert "nearestVisibleFrameIndex(targetIdx" in js
    assert "normalizeCurrentFrameForFilter()" in js
    assert "this.updateFrameNavigationControls();" in js
    assert "this.updateFrameOptionVisibility();" in js
    assert "this.updateFilterChips();" in js
    assert "this.scrollActiveFilmstripItem();" in js
    assert "this.setFrame(visibleIndexes[position + 1]);" in js
    assert "this.setFrame(visibleIndexes[position - 1]);" in js


def test_viewer_assets_wire_metadata_and_error_empty_state_hooks() -> None:
    css = get_css()
    js = get_js()

    assert ".rv-metadata-bar" in css
    assert ".rv-disclosure[open]" in css
    assert ".rv-status[data-tone=\"error\"]" in css
    assert ".rv-status[data-tone=\"warning\"]" in css
    assert ".rv-empty-state[hidden] { display: none; }" in css

    assert "readPayload()" in js
    assert "normalizePayload(payload)" in js
    assert "showStatus(message, tone = 'info')" in js
    assert "renderInitializationError('Failed to load report data.')" in js
    assert "renderEmptyState(this.emptyStateMessage())" in js
    assert "if (control === this.dom.btnHelp) return;" in js
    assert "hasRenderableData()" in js
    assert "updateCurrentFrameMetadata(frameData)" in js
    assert "document.querySelector('[data-current-frame-summary]')" in js
    assert "document.querySelector('[data-current-frame-detail]')" in js
    assert "Selected frame image data is unavailable." in js
    assert "Report viewer markup is incomplete." in js


def test_viewer_assets_preload_adjacent_visible_frames_and_active_clips() -> None:
    js = get_js()

    assert "preloadedSrcs: new Set()" in js
    assert "this.preloadImages();" in js
    assert "preloadFrameIndexes()" in js
    assert "if (position > 0) indexes.push(visibleIndexes[position - 1]);" in js
    assert "if (position < visibleIndexes.length - 1) indexes.push(visibleIndexes[position + 1]);" in js
    assert "preloadClipIndexes()" in js
    assert "indexes.add(this.state.activeClipIdx);" in js
    assert "indexes.add(this.state.leftClipIdx);" in js
    assert "indexes.add(this.state.rightClipIdx);" in js
    assert "const images = Array.isArray(frame.images) ? frame.images : [];" in js
    assert "const src = images[clipIdx]?.src;" in js
    assert "src.startsWith('data:')" in js
    assert "this.state.preloadedSrcs.has(src)" in js
    assert "const image = new Image();" in js
    assert "image.src = src;" in js
