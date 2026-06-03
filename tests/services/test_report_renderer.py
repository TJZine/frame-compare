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


@dataclass
class _ParsedClipMetadata:
    label: str = ""
    dynamic_range: str = ""
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class _ParsedInfoModal:
    attrs: dict[str, str | None]
    section_headings: list[str] = field(default_factory=list)
    general: dict[str, str] = field(default_factory=dict)
    links: dict[str, str] = field(default_factory=dict)
    clips: list[_ParsedClipMetadata] = field(default_factory=list)


@dataclass
class _ParsedElement:
    tag: str
    attrs: dict[str, str | None]
    children: list[_ParsedElement] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        parts = [*self.text_parts]
        parts.extend(child.text for child in self.children)
        return _normalize_text(parts)

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())


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


class _StartTagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.by_id: dict[str, tuple[str, dict[str, str | None]]] = {}
        self.tags_with_style: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        element_id = attr_map.get("id")
        if element_id is not None:
            self.by_id[element_id] = (tag, attr_map)
        if "style" in attr_map:
            self.tags_with_style.append((tag, attr_map))


class _ElementTreeParser(HTMLParser):
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__()
        self.root = _ParsedElement("document", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = _ParsedElement(tag, dict(attrs))
        self._stack[-1].children.append(element)
        if tag not in self._VOID_TAGS:
            self._stack.append(element)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].text_parts.append(data)


class _InfoModalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.modal: _ParsedInfoModal | None = None
        self._in_info_modal = False
        self._info_div_depth = 0
        self._capture_kind: str | None = None
        self._capture_text: list[str] = []
        self._current_term: str | None = None
        self._current_clip: _ParsedClipMetadata | None = None
        self._in_clip_heading = False
        self._clip_heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if not self._in_info_modal and tag == "div" and attr_map.get("id") == "info-modal":
            self._in_info_modal = True
            self._info_div_depth = 1
            self.modal = _ParsedInfoModal(attrs=attr_map)
            return
        if not self._in_info_modal:
            return

        classes = set((attr_map.get("class") or "").split())
        if tag == "div":
            self._info_div_depth += 1
            if "rv-clip-meta-heading" in classes:
                self._in_clip_heading = True
                self._clip_heading_parts = []
        elif tag == "li" and "rv-clip-meta-item" in classes:
            self._current_clip = _ParsedClipMetadata()
        elif tag == "h3":
            self._start_capture("section")
        elif tag == "dt":
            self._start_capture("term")
        elif tag == "dd":
            self._start_capture("definition")
        elif tag == "span" and self._in_clip_heading:
            self._start_capture("clip-heading")
        elif tag == "a" and self._capture_kind == "definition" and self._current_term is not None:
            href = attr_map.get("href")
            if href is not None and self.modal is not None:
                self.modal.links[self._current_term] = href

    def handle_data(self, data: str) -> None:
        if self._capture_kind is not None:
            self._capture_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_info_modal:
            return

        if tag == "h3" and self._capture_kind == "section":
            if self.modal is not None:
                self.modal.section_headings.append(_normalize_text(self._capture_text))
            self._stop_capture()
        elif tag == "dt" and self._capture_kind == "term":
            self._current_term = _normalize_text(self._capture_text)
            self._stop_capture()
        elif tag == "dd" and self._capture_kind == "definition":
            definition = _normalize_text(self._capture_text)
            self._store_definition(definition)
            self._current_term = None
            self._stop_capture()
        elif tag == "span" and self._capture_kind == "clip-heading":
            self._clip_heading_parts.append(_normalize_text(self._capture_text))
            self._stop_capture()
        elif tag == "li" and self._current_clip is not None:
            if self.modal is not None:
                self.modal.clips.append(self._current_clip)
            self._current_clip = None
        elif tag == "div":
            if self._in_clip_heading:
                self._in_clip_heading = False
                if self._current_clip is not None:
                    if self._clip_heading_parts:
                        self._current_clip.label = self._clip_heading_parts[0]
                    if len(self._clip_heading_parts) > 1:
                        self._current_clip.dynamic_range = self._clip_heading_parts[1]
            self._info_div_depth -= 1
            if self._info_div_depth == 0:
                self._in_info_modal = False

    def _start_capture(self, kind: str) -> None:
        self._capture_kind = kind
        self._capture_text = []

    def _stop_capture(self) -> None:
        self._capture_kind = None
        self._capture_text = []

    def _store_definition(self, definition: str) -> None:
        if self._current_term is None or self.modal is None:
            return
        if self._current_clip is not None:
            self._current_clip.fields[self._current_term] = definition
            return
        self.modal.general[self._current_term] = definition


def _normalize_text(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


def _parse_start_tags(html: str) -> _StartTagParser:
    parser = _StartTagParser()
    parser.feed(html)
    return parser


def _parse_info_modal(html: str) -> _ParsedInfoModal:
    parser = _InfoModalParser()
    parser.feed(html)
    assert parser.modal is not None
    return parser.modal


def _parse_elements(html: str) -> _ParsedElement:
    parser = _ElementTreeParser()
    parser.feed(html)
    return parser.root


def _find_first(
    element: _ParsedElement,
    *,
    tag: str | None = None,
    element_id: str | None = None,
    class_name: str | None = None,
) -> _ParsedElement | None:
    tag_matches = tag is None or element.tag == tag
    id_matches = element_id is None or element.attrs.get("id") == element_id
    class_matches = class_name is None or class_name in element.classes
    if tag_matches and id_matches and class_matches:
        return element
    for child in element.children:
        match = _find_first(child, tag=tag, element_id=element_id, class_name=class_name)
        if match is not None:
            return match
    return None


def _require_first(
    element: _ParsedElement,
    *,
    tag: str | None = None,
    element_id: str | None = None,
    class_name: str | None = None,
) -> _ParsedElement:
    match = _find_first(element, tag=tag, element_id=element_id, class_name=class_name)
    assert match is not None
    return match


def _find_children(
    element: _ParsedElement,
    *,
    tag: str | None = None,
    class_name: str | None = None,
) -> list[_ParsedElement]:
    return [
        child
        for child in element.children
        if (tag is None or child.tag == tag) and (class_name is None or class_name in child.classes)
    ]


def _css_block(css: str, selector: str) -> str:
    selector_start = css.index(selector)
    block_start = css.index("{", selector_start)
    depth = 0
    for idx in range(block_start, len(css)):
        char = css[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return css[block_start + 1 : idx]
    raise AssertionError(f"Unterminated CSS block for selector: {selector}")


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
    info_modal = _parse_info_modal(html)

    assert 'href="https://slow.pics/c/abc?x=1&amp;y=2"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "View on slow.pics" in html
    assert info_modal.links["slow.pics"] == "https://slow.pics/c/abc?x=1&y=2"
    assert info_modal.general["slow.pics"] == "https://slow.pics/c/abc?x=1&y=2"

    unsafe_payload: ReportPayload = {**report_payload, "slowpics_url": "javascript:alert(1)"}
    unsafe_html = build_html(unsafe_payload)
    unsafe_info_modal = _parse_info_modal(unsafe_html)

    assert "javascript:alert(1)" in unsafe_html
    assert 'href="javascript:alert(1)"' not in unsafe_html
    assert "View on slow.pics" not in unsafe_html
    assert "slow.pics" not in unsafe_info_modal.links
    assert unsafe_info_modal.general["slow.pics"] == "javascript:alert(1)"

    no_upload_payload: ReportPayload = {**report_payload, "slowpics_url": None}
    no_upload_html = build_html(no_upload_payload)
    no_upload_info_modal = _parse_info_modal(no_upload_html)

    assert "View on slow.pics" not in no_upload_html
    assert 'class="rv-link"' not in no_upload_html
    assert no_upload_info_modal.general["slow.pics"] == "Not uploaded"


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

    parser = _SelectParser()
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
    assert "Source frame 10</span>" not in html
    assert (
        '<span class="rv-filmstrip-accent" '
        'data-category-key="cat-1" data-category="scene-cut"></span>'
    ) in html
    assert 'value="1" data-category-key="cat-1" data-category="scene-cut">Frame 20</option>' in html


def test_build_html_renders_header_metadata(
    report_payload: ReportPayload,
) -> None:
    html = build_html(report_payload)
    tags = _parse_start_tags(html)
    info_modal = _parse_info_modal(html)

    assert "Generated 2026-05-22T12:00:00+00:00 • 2 frames • 2 clips" in html
    assert tags.by_id["btn-help"][1]["class"] == "rv-header-help-btn"
    assert tags.by_id["btn-info"][1]["class"] == "rv-header-info-btn"
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
    info_modal = _parse_info_modal(html)

    assert _script_payload(html)["default_mode"] == "overlay"
    assert info_modal.general["Default Mode"] == "Single"


def test_build_html_avoids_inline_styles(report_payload: ReportPayload) -> None:
    html = build_html(report_payload)
    tags = _parse_start_tags(html)

    assert tags.tags_with_style == []


def test_build_html_exposes_current_frame_metadata_hooks(
    report_payload: ReportPayload,
) -> None:
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
    document = _parse_elements(html)
    palette = _require_first(document, tag="div", class_name="rv-viewport-palette")

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
    assert 'id="btn-focus-mode" aria-label="Enter focus mode" aria-pressed="false"' in html
    assert 'id="btn-overlays"' in html
    assert 'aria-label="Hide HUD"' in html
    assert ">HUD</button>" in html
    assert 'class="rv-palette-group rv-blink-controls" data-control-scope="blink" hidden' in html
    assert 'id="btn-blink-pause" aria-label="Pause blink" aria-pressed="false"' in html
    assert '<option value="300">0.3s</option>' in html
    assert '<option value="700" selected>0.7s</option>' in html
    assert '<option value="1200">1.2s</option>' in html
    assert 'id="blink-status" class="rv-blink-status" role="status" aria-live="polite"' in html

    active_filter_badge = _require_first(document, tag="span", element_id="active-filter-badge")
    assert "rv-active-filter-badge" in active_filter_badge.classes
    assert "hidden" in active_filter_badge.attrs

    orientation_button = _require_first(palette, tag="button", element_id="btn-palette-orientation")
    assert orientation_button.attrs["aria-label"] == "Toggle palette orientation"
    assert orientation_button.text == "↔"

    fit_buttons = {
        child.attrs.get("data-fit"): child
        for group in _find_children(palette, tag="div", class_name="rv-palette-group")
        for child in group.children
        if child.tag == "button" and "data-fit" in child.attrs
    }
    assert fit_buttons["actual"].text == "1:1"
    assert fit_buttons["actual"].attrs["title"] == "Actual size (1:1)"
    assert fit_buttons["width"].text == "↔"
    assert fit_buttons["width"].attrs["title"] == "Fit width (↔)"
    assert fit_buttons["height"].text == "↕"
    assert fit_buttons["height"].attrs["title"] == "Fit height (↕)"
    assert fit_buttons["fill"].text == "⛶"
    assert fit_buttons["fill"].attrs["title"] == "Fill stage (⛶)"
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
        assert f'data-inspector-tab="{tab}"' in html
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
    assert "data-focus-frame" in html
    assert "data-focus-mode" in html
    assert "data-focus-pair" in html


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
    assert (
        '<div class="rv-shortcut-row"><span>Toggle Focus</span><span class="rv-key">Z</span></div>'
        in html
    )
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
        '<div class="rv-shortcut-row"><span>Close Panel / Exit Focus / Exit Fullscreen</span>'
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
    visible_document = _parse_elements(visible_html)
    visible_panel = _require_first(visible_document, tag="section", class_name="rv-bottom-panel")
    visible_panel_bar = _require_first(visible_panel, tag="div", class_name="rv-bottom-panel-bar")
    visible_filter_group = _require_first(
        visible_panel_bar, tag="div", class_name="rv-filter-group"
    )
    visible_filmstrip_controls = _require_first(
        visible_panel_bar, tag="div", class_name="rv-filmstrip-controls"
    )
    visible_toggle = _require_first(
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
        for size_control in _find_children(
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
    hidden_document = _parse_elements(hidden_html)
    hidden_panel = _require_first(hidden_document, tag="section", class_name="rv-bottom-panel")
    hidden_toggle = _require_first(hidden_panel, tag="button", element_id="btn-filmstrip-toggle")

    assert hidden_panel.attrs["data-filmstrip-enabled"] == "false"
    assert hidden_panel.attrs["aria-label"] == "Frame timeline"
    assert hidden_toggle.attrs["type"] == "button"
    assert hidden_toggle.attrs["aria-expanded"] == "true"
    assert hidden_toggle.attrs["aria-label"] == "Filmstrip disabled"
    assert hidden_toggle.attrs["title"] == "Filmstrip disabled"
    assert "disabled" in hidden_toggle.attrs
    assert hidden_toggle.text == "Filmstrip disabled"
    assert 'class="rv-filmstrip rv-filmstrip--hidden"' in hidden_html
    assert 'aria-label="Frame thumbnails disabled"' in hidden_html
    assert 'aria-hidden="true"' in hidden_html
    assert 'class="rv-filmstrip-item"' not in hidden_html


def test_viewer_assets_keep_divider_slider_only_and_pointer_safe() -> None:
    css = get_css()
    js = get_js()

    assert "color-scheme: dark;" in css
    assert '--font-sans: "Inter", "SF Pro Text", "Segoe UI Variable Text"' in css
    assert ".rv-viewer-stage" in css
    assert "touch-action: none;" in css
    assert "cursor: grab;" in css
    assert "cursor: grabbing;" in _css_block(css, ".rv-viewer-stage.is-panning")
    assert "display: none;" in _css_block(css, ".rv-divider")
    assert "display: block;" in _css_block(css, ".rv-mode-slider .rv-divider")
    assert ".rv-viewer-stage:fullscreen" in css
    assert "translate(var(--pan-x, 0px), var(--pan-y, 0px)) scale(var(--zoom-level, 1))" in css
    alignment_transform_block = _css_block(
        css, ".rv-right,\n.rv-mode-overlay .rv-left.rv-layer--aligned-active"
    )
    assert (
        "transform: translate(var(--align-x, 0px), var(--align-y, 0px));"
        in alignment_transform_block
    )
    assert ".rv-overlay-label:empty { display: none; }" in css
    assert "select option," in css
    assert 'background-image: url("data:image/svg+xml,' in css
    assert "position: absolute;" in _css_block(css, ".rv-stage-labels")
    assert "display: none;" in _css_block(css, ".rv-mode-diff .rv-stage-labels")
    assert "top: 12px;" in _css_block(css, ".rv-overlay-label")
    assert "color: var(--text-primary);" in _css_block(css, ".rv-overlay-label")
    assert "backdrop-filter:" not in _css_block(css, ".rv-overlay-label")
    assert "top: 12px;" in _css_block(css, ".rv-stage-overlay-info")
    assert "right: 12px;" in _css_block(css, ".rv-stage-overlay-info")
    assert "left: 50%;" not in _css_block(css, ".rv-stage-overlay-info")
    assert "transform: translateX(-50%);" not in _css_block(css, ".rv-stage-overlay-info")
    assert "left: var(--label-left-x, 50%);" in _css_block(css, ".rv-mode-slider #label-left")
    assert "left: var(--label-right-x, 50%);" in _css_block(css, ".rv-mode-slider #label-right")
    assert "position: absolute;" in _css_block(css, ".rv-filmstrip-caption")
    assert "text-shadow:" in _css_block(css, ".rv-filmstrip-label")

    assert "imageLoadPromises: new Map()," in js
    assert "void this.ensureImageReady(src);" in js
    assert "Promise.all([" in js
    assert "this.ensureImageReady(imageState.leftSrc)" in js
    assert "this.ensureImageReady(imageState.rightSrc)" in js
    assert "window.requestAnimationFrame(() => commit());" in js
    assert "preloadedSrcs" not in js
    assert "leftLabelTxt = `${leftClip.label} (Left)`;" in js
    assert "rightLabelTxt = `${rightClip.label} (Right)`;" in js
    assert "const blinkLabels = this.blinkStageLabels(leftClip.label, rightClip.label);" in js
    assert "leftLabelTxt = blinkLabels.left;" in js
    assert "rightLabelTxt = blinkLabels.right;" in js
    assert "blinkStageLabels(leftClipLabel, rightClipLabel)" in js
    assert "leftLabelTxt = activeClip.label;" in js
    assert 'rightLabelTxt = "";' in js
    assert "this.dom.stage.className = `rv-viewer-stage rv-mode-${mode}`;" not in js
    assert "this.dom.stage.classList.remove(" in js
    assert "this.dom.stage.classList.add(`rv-mode-${mode}`);" in js
    assert "updateSmartStageLabels()" in js
    assert "untransformedCanvasWidth()" in js
    assert "smartLabelPositions(canvasWidth, leftLabelWidth, rightLabelWidth)" in js
    assert "return rectWidth / this.clampZoom(this.state.zoom);" in js
    assert "this.dom.canvas.style.setProperty('--label-left-x', `${positions.leftX}px`);" in js
    assert "this.dom.canvas.style.setProperty('--label-right-x', `${positions.rightX}px`);" in js

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


def test_viewer_assets_group_event_binding_by_interaction_area() -> None:
    js = get_js()
    expected_binding_methods = [
        "bindModeEvents",
        "bindFrameNavigationEvents",
        "bindClipSelectionEvents",
        "bindViewportEvents",
        "bindAlignmentEvents",
        "bindHelpEvents",
        "bindInspectorEvents",
        "bindBlinkEvents",
        "bindFilmstripEvents",
        "bindKeyboardEvents",
    ]

    for method_name in expected_binding_methods:
        assert f"\n    {method_name}() {{" in js
        assert f"this.{method_name}();" in js

    assert "bindInteractionEvents()" in js
    assert "this.bindHelpEvents();" in js
    assert "this.bindInteractionEvents();" in js
    assert js.index("this.bindHelpEvents();") < js.index("if (!this.hasRenderableData())")
    assert js.index("if (!this.hasRenderableData())") < js.index("this.bindInteractionEvents();")
    assert "renderEmptyState(this.emptyStateMessage());\n                return;" in js


def test_viewer_assets_manage_help_focus_and_escape_semantics() -> None:
    js = get_js()

    assert "helpRestoreFocus: null" in js
    assert "infoRestoreFocus: null" in js
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
    assert "openInfoModal()" in js
    assert "handleInfoModalKey(e)" in js
    assert "this.state.infoRestoreFocus = activeElement" in js
    assert "this.closeInfoModal();" in js


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


def test_viewer_assets_close_alignment_popover_before_global_escape_and_shortcuts() -> None:
    js = get_js()

    assert "isAlignmentPopoverOpen()" in js
    assert "setAlignmentPopoverOpen(isOpen, options = {})" in js
    assert "this.closeAlignmentPopover({ restoreFocus: false });" in js
    assert "e.stopPropagation();" in js
    assert "if (this.isAlignmentPopoverOpen()) {" in js
    assert "this.closeAlignmentPopover();" in js
    assert "if (this.isAlignmentPopoverOpen()) return;" in js


def test_viewer_assets_wire_report_scoped_viewport_persistence() -> None:
    js = get_js()
    persistence_block = js[
        js.index("persistViewportState() {") : js.index("\n    localStorage() {")
    ]

    assert "this.state.storageKey = this.viewportStorageKey();" in js
    assert "frame-compare:report-viewer:${reportId}:viewport" in js
    assert "this.state.data?.report_id || 'unknown-report'" in js
    assert "restorePersistedState()" in js
    assert "persistViewportState()" in js
    assert "storage.setItem(this.state.storageKey, JSON.stringify(payload))" in js
    assert "mode: this.state.mode" in js
    assert "panX: this.state.panX" in js
    assert "overlaysHidden: this.state.overlaysHidden" in js
    assert "inspectorOpen: this.state.inspectorOpen" in persistence_block
    assert "inspectorTab: this.state.inspectorTab" in persistence_block
    assert "blinkIntervalMs: this.state.blinkIntervalMs" in persistence_block
    assert "blinkPaused" not in persistence_block
    assert "focusMode" not in persistence_block
    assert "pairAlignments: this.state.pairAlignments" in persistence_block
    assert "alignmentPreset: this.state.alignmentPreset" not in persistence_block
    assert "alignX: this.state.alignX" not in persistence_block


def test_viewer_assets_wire_pan_wheel_zoom_and_alignment_hooks() -> None:
    js = get_js()

    assert "panX: 0" in js
    assert "panY: 0" in js
    assert "this.dom.stage.addEventListener('wheel'" in js
    assert "this.dom.stage.addEventListener('dblclick'" in js
    assert "if (this.state.mode === 'overlay' || this.state.mode === 'diff') return;" in js
    assert "this.zoomAtPoint(e.clientX, e.clientY, e.deltaY < 0 ? 1.1 : 1 / 1.1);" in js
    assert "this.setPan(this.state.panX + dx, this.state.panY + dy, { save: false });" in js
    assert "shouldPanFromPointer" in js
    assert "this.state.mode !== 'slider'" in js
    assert "updateSliderFromPointer(e);" in js
    assert "pointerPositions: new Map()" in js
    assert "capturedPointerIds: new Set()" in js
    assert "pinchStartDistance: 0" in js
    assert "trackedTouchPointers()" in js
    assert "Math.hypot(dx, dy)" in js
    assert "startPinchFromTrackedPointers()" in js
    assert "updatePinchFromTrackedPointers()" in js
    assert "finishPinchInteraction()" in js
    assert "this.dom.stage.classList.add('is-panning');" in js
    assert "this.dom.canvas.style.setProperty('--pan-x', `${this.state.panX}px`);" in js
    assert "alignmentPreset: 'none'" in js
    assert "rawAlignX: null" in js
    assert "rawAlignY: null" in js
    assert "setAlignmentPreset(preset)" in js
    assert "setManualAlignment(x, y)" in js
    assert "setRawAlignmentInput('x', e.target.value);" in js
    assert "setRawAlignmentInput('y', e.target.value);" in js
    assert "this.setManualAlignment(parseFloat(e.target.value), this.state.alignY);" not in js
    assert "this.setManualAlignment(this.state.alignX, parseFloat(e.target.value));" not in js
    assert "commitRawAlignmentInput('x')" in js
    assert "commitRawAlignmentInput('y')" in js
    assert "this.dom.alignX.value = this.state.rawAlignX ?? this.state.alignX;" in js
    assert "this.dom.alignY.value = this.state.rawAlignY ?? this.state.alignY;" in js
    assert "this.dom.canvas.style.setProperty('--align-x', `${this.state.alignX}px`);" in js
    assert "this.dom.canvas.style.setProperty('--align-y', `${this.state.alignY}px`);" in js


def test_viewer_assets_keep_overlay_and_blink_clip_semantics() -> None:
    css = get_css()
    js = get_js()

    assert "display: none;" in _css_block(css, ".rv-control-group[hidden]")
    assert "const selection = this.state.data.default_selection || {};" in js
    assert "this.state.leftClipIdx = left;" in js
    assert "this.state.rightClipIdx = right;" in js
    assert "this.state.activeClipIdx = left;" in js
    assert "this.dom.pairControls.hidden = isOverlay;" in js
    assert "this.dom.activeControls.hidden = !isOverlay;" in js
    assert "this.dom.leftSelect.disabled = isOverlay;" in js
    assert "this.dom.btnSwapClips.disabled = isOverlay || this.clipCount() <= 1;" in js
    assert "this.dom.activeSelect.disabled = !isOverlay;" in js
    assert "this.dom.leftSelect.setAttribute('aria-label', 'Base clip');" in js
    assert "this.dom.rightSelect.setAttribute('aria-label', 'Compare clip');" in js
    assert "this.dom.leftSelect.setAttribute('aria-label', 'First blink clip');" in js
    assert "this.dom.rightSelect.setAttribute('aria-label', 'Second blink clip');" in js
    assert "this.state.activeClipIdx === this.state.leftClipIdx" in js
    assert "? this.state.rightClipIdx" in js
    assert ": this.state.leftClipIdx" in js
    assert (
        "this.state.mode === 'slider' || this.state.mode === 'diff' || this.state.mode === 'blink'"
        in js
    )
    assert "isBlink && this.state.activeClipIdx === this.state.rightClipIdx" in js
    assert "(this.state.activeClipIdx + 1) % this.state.data.clips.length" not in js
    assert "this.state.mode === 'diff' || this.state.mode === 'blink'" in js


def test_viewer_assets_wire_category_filtering_and_visible_navigation() -> None:
    css = get_css()
    js = get_js()

    assert ".rv-filter-chip.active" in css
    assert ".rv-filter-chip::before" in css
    assert "--category-accent: var(--accent);" in css
    assert "display: none;" in _css_block(css, ".rv-filmstrip-item[hidden]")
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

    assert ".rv-stage-overlay-info" in css
    assert ".rv-viewer-stage.rv-overlays-hidden .rv-overlay-label" in css
    assert ".rv-viewer-stage.rv-overlays-hidden .rv-focus-hud" in css
    assert ".rv-align-popover" in css
    assert '.rv-status[data-tone="error"]' in css
    assert '.rv-status[data-tone="warning"]' in css
    assert "display: none;" in _css_block(css, ".rv-empty-state[hidden]")
    assert ".rv-modal-content--wide" in css
    assert ".rv-modal-actions" in css
    assert ".rv-zoom-value" in css

    assert "readPayload()" in js
    assert "normalizePayload(payload)" in js
    assert "showStatus(message, tone = 'info')" in js
    assert "renderInitializationError('Failed to load report data.')" in js
    assert "renderEmptyState(this.emptyStateMessage())" in js
    assert "if (control === this.dom.btnHelp) return;" in js
    assert "hasRenderableData()" in js
    assert "updateCurrentFrameMetadata(frameData)" in js
    assert "this.updateCurrentFrameMetadata(null);" in js
    assert "document.querySelector('[data-current-frame-detail]')" not in js
    assert "normalizedDisplayToken(value)" in js
    assert "this.dom.currentFrameCategoryDivider.hidden = !showCategory;" in js
    assert "Selected frame image data is unavailable." in js
    assert "Report viewer markup is incomplete." in js


def test_viewer_assets_toggle_overlays_and_keep_split_pairs_distinct() -> None:
    js = get_js()

    assert "setOverlaysHidden(hidden, options = {})" in js
    assert "updateOverlayVisibility()" in js
    assert "this.dom.btnOverlays.addEventListener('click'" in js
    assert "case 'h': case 'H': this.setOverlaysHidden(!this.state.overlaysHidden); break;" in js
    assert "case 'x': case 'X': this.swapPairClips(); break;" in js
    assert "ensureDistinctPairSelection(mode = this.state.mode)" in js
    assert "nextDistinctClipIndex(startIdx, excludedIdx, direction = 1)" in js
    assert "this.state.rightClipIdx = this.nextDistinctClipIndex(" in js


def test_viewer_assets_wire_bottom_panel_and_filmstrip_state() -> None:
    css = get_css()
    js = get_js()

    assert ".rv-bottom-panel" in css
    assert ".rv-bottom-panel--collapsed .rv-filmstrip" in css
    assert "display: none;" in _css_block(css, ".rv-bottom-panel--collapsed .rv-filmstrip")
    assert "display: none;" in _css_block(css, ".rv-bottom-panel--collapsed .rv-filter-group")
    assert "aspect-ratio: 16 / 10;" in _css_block(css, ".rv-filmstrip-item")
    assert "object-fit: contain;" in _css_block(css, ".rv-filmstrip-item img")
    assert "width: 120px;" in _css_block(css, ".rv-filmstrip-size-compact .rv-filmstrip-item")
    assert "width: 150px;" in _css_block(css, ".rv-filmstrip-size-normal .rv-filmstrip-item")
    assert "width: 210px;" in _css_block(css, ".rv-filmstrip-size-large .rv-filmstrip-item")
    assert "display: none;" in _css_block(css, ".rv-filmstrip-size-compact .rv-filmstrip-caption")
    assert "linear-gradient" in _css_block(css, ".rv-filmstrip-caption")
    assert "Show timeline" in js
    assert "Hide timeline" in js
    assert "timeline controls" in js
    assert "Toggle timeline (F)" in js


def test_viewer_assets_wire_inspector_blink_and_focus_state() -> None:
    css = get_css()
    vertical_palette_css = _css_block(css, '.rv-viewport-palette[data-orientation="vertical"]')
    tablet_css = _css_block(css, "@media (max-width: 992px)")
    mobile_css = _css_block(css, "@media (max-width: 768px)")
    reduced_motion_css = _css_block(css, "@media (prefers-reduced-motion: reduce)")

    assert ".rv-inspector" in css
    assert ".rv-inspector.open" in css
    assert "body.rv-inspector-open .rv-viewer-stage" in css
    assert "body.rv-focus-mode .rv-header" in css
    assert "body.rv-focus-mode .rv-focus-hud" in css
    assert ".rv-blink-status" in css
    assert "flex-direction: column;" in vertical_palette_css
    assert "flex-wrap: nowrap;" in vertical_palette_css
    assert "overflow-y: auto;" in vertical_palette_css
    for block in (tablet_css, mobile_css):
        assert ".rv-viewport-palette" in block
        assert ".rv-bottom-panel-bar" in block
        assert "body.rv-inspector-open .rv-viewer-stage" in block
        assert ".rv-inspector" in block
        assert ".rv-focus-hud" in block
    assert "margin-right: 0;" in tablet_css
    assert "width: min(360px, 92vw);" in tablet_css
    assert "transition: none !important;" in reduced_motion_css
    assert "animation-duration: 0.01ms !important;" in reduced_motion_css


def test_viewer_assets_preload_adjacent_visible_frames_and_active_clips() -> None:
    js = get_js()

    assert "imageLoadPromises: new Map()" in js
    assert "this.preloadImages();" in js
    assert "preloadFrameIndexes()" in js
    assert "if (position > 0) indexes.push(visibleIndexes[position - 1]);" in js
    assert (
        "if (position < visibleIndexes.length - 1) indexes.push(visibleIndexes[position + 1]);"
        in js
    )
    assert "preloadClipIndexes()" in js
    assert "indexes.add(this.state.activeClipIdx);" in js
    assert "indexes.add(this.state.leftClipIdx);" in js
    assert "indexes.add(this.state.rightClipIdx);" in js
    assert "const images = Array.isArray(frame.images) ? frame.images : [];" in js
    assert "const src = images[clipIdx]?.src;" in js
    assert "src.startsWith('data:')" in js
    assert "this.state.imageLoadPromises.get(src)" in js
    assert "const image = new Image();" in js
    assert "image.src = src;" in js
    assert "image.decode().catch(() => undefined).finally(finish);" in js
