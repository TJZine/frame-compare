"""Shared helpers for report viewer renderer contract tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html.parser import HTMLParser

import pytest

from frame_compare.services.report.payload import ReportPayload


@dataclass
class ParsedOption:
    text: str
    attrs: dict[str, str | None]


@dataclass
class ParsedSelect:
    attrs: dict[str, str | None]
    options: list[ParsedOption] = field(default_factory=list)


@dataclass
class ParsedClipMetadata:
    label: str = ""
    dynamic_range: str = ""
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedInfoModal:
    attrs: dict[str, str | None]
    section_headings: list[str] = field(default_factory=list)
    general: dict[str, str] = field(default_factory=dict)
    links: dict[str, str] = field(default_factory=dict)
    clips: list[ParsedClipMetadata] = field(default_factory=list)


@dataclass
class ParsedElement:
    tag: str
    attrs: dict[str, str | None]
    children: list[ParsedElement] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        parts = [*self.text_parts]
        parts.extend(child.text for child in self.children)
        return normalize_text(parts)

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())


class SelectParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.selects: dict[str, ParsedSelect] = {}
        self._current_select_id: str | None = None
        self._current_option_attrs: dict[str, str | None] | None = None
        self._current_option_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "select":
            select_id = attr_map.get("id")
            if select_id is not None:
                self.selects[select_id] = ParsedSelect(attrs=attr_map)
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
                    ParsedOption(
                        text="".join(self._current_option_text),
                        attrs=self._current_option_attrs,
                    )
                )
            self._current_option_attrs = None
            self._current_option_text = []
        elif tag == "select":
            self._current_select_id = None


class StartTagParser(HTMLParser):
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


class ElementTreeParser(HTMLParser):
    void_tags = {
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
        self.root = ParsedElement("document", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = ParsedElement(tag, dict(attrs))
        self._stack[-1].children.append(element)
        if tag not in self.void_tags:
            self._stack.append(element)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].text_parts.append(data)


class InfoModalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.modal: ParsedInfoModal | None = None
        self._in_info_modal = False
        self._info_div_depth = 0
        self._capture_kind: str | None = None
        self._capture_text: list[str] = []
        self._current_term: str | None = None
        self._current_clip: ParsedClipMetadata | None = None
        self._in_clip_heading = False
        self._clip_heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if not self._in_info_modal and tag == "div" and attr_map.get("id") == "info-modal":
            self._in_info_modal = True
            self._info_div_depth = 1
            self.modal = ParsedInfoModal(attrs=attr_map)
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
            self._current_clip = ParsedClipMetadata()
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
                self.modal.section_headings.append(normalize_text(self._capture_text))
            self._stop_capture()
        elif tag == "dt" and self._capture_kind == "term":
            self._current_term = normalize_text(self._capture_text)
            self._stop_capture()
        elif tag == "dd" and self._capture_kind == "definition":
            definition = normalize_text(self._capture_text)
            self._store_definition(definition)
            self._current_term = None
            self._stop_capture()
        elif tag == "span" and self._capture_kind == "clip-heading":
            self._clip_heading_parts.append(normalize_text(self._capture_text))
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


def normalize_text(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


def parse_start_tags(html: str) -> StartTagParser:
    parser = StartTagParser()
    parser.feed(html)
    return parser


def parse_info_modal(html: str) -> ParsedInfoModal:
    parser = InfoModalParser()
    parser.feed(html)
    assert parser.modal is not None
    return parser.modal


def parse_elements(html: str) -> ParsedElement:
    parser = ElementTreeParser()
    parser.feed(html)
    return parser.root


def find_first(
    element: ParsedElement,
    *,
    tag: str | None = None,
    element_id: str | None = None,
    class_name: str | None = None,
    attr_name: str | None = None,
    attr_value: str | None = None,
) -> ParsedElement | None:
    tag_matches = tag is None or element.tag == tag
    id_matches = element_id is None or element.attrs.get("id") == element_id
    class_matches = class_name is None or class_name in element.classes
    attr_matches = attr_name is None or (
        attr_name in element.attrs
        and (attr_value is None or element.attrs[attr_name] == attr_value)
    )
    if tag_matches and id_matches and class_matches and attr_matches:
        return element
    for child in element.children:
        match = find_first(
            child,
            tag=tag,
            element_id=element_id,
            class_name=class_name,
            attr_name=attr_name,
            attr_value=attr_value,
        )
        if match is not None:
            return match
    return None


def require_first(
    element: ParsedElement,
    *,
    tag: str | None = None,
    element_id: str | None = None,
    class_name: str | None = None,
    attr_name: str | None = None,
    attr_value: str | None = None,
) -> ParsedElement:
    match = find_first(
        element,
        tag=tag,
        element_id=element_id,
        class_name=class_name,
        attr_name=attr_name,
        attr_value=attr_value,
    )
    assert match is not None
    return match


def find_children(
    element: ParsedElement,
    *,
    tag: str | None = None,
    class_name: str | None = None,
) -> list[ParsedElement]:
    return [
        child
        for child in element.children
        if (tag is None or child.tag == tag) and (class_name is None or class_name in child.classes)
    ]


def find_all(
    element: ParsedElement,
    *,
    tag: str | None = None,
    element_id: str | None = None,
    class_name: str | None = None,
    attr_name: str | None = None,
    attr_value: str | None = None,
) -> list[ParsedElement]:
    matches: list[ParsedElement] = []
    tag_matches = tag is None or element.tag == tag
    id_matches = element_id is None or element.attrs.get("id") == element_id
    class_matches = class_name is None or class_name in element.classes
    attr_matches = attr_name is None or (
        attr_name in element.attrs
        and (attr_value is None or element.attrs[attr_name] == attr_value)
    )
    if tag_matches and id_matches and class_matches and attr_matches:
        matches.append(element)
    for child in element.children:
        matches.extend(
            find_all(
                child,
                tag=tag,
                element_id=element_id,
                class_name=class_name,
                attr_name=attr_name,
                attr_value=attr_value,
            )
        )
    return matches


def parse_definition_pairs(element: ParsedElement) -> dict[str, str]:
    terms = find_all(element, tag="dt")
    definitions = find_all(element, tag="dd")
    assert len(terms) == len(definitions)
    return {term.text: definition.text for term, definition in zip(terms, definitions, strict=True)}


def css_block(css: str, selector: str) -> str:
    selector_start = css.index(selector)
    return brace_block(css, css.index("{", selector_start))


def brace_block(source: str, opening_brace_index: int) -> str:
    depth = 0
    for index in range(opening_brace_index, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace_index + 1 : index]
    raise AssertionError("Unterminated block")


def script_payload(html: str) -> ReportPayload:
    marker = '<script type="application/json" id="report-data">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    return json.loads(html[start:end])


@pytest.fixture
def report_payload() -> ReportPayload:
    return {
        "version": "1.1",
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
                "size_bytes": 1048576,
                "signal": {
                    "is_hdr": False,
                    "primaries": 1,
                    "transfer": 1,
                    "matrix": 1,
                    "range": "limited",
                    "dolby_vision_rpu": False,
                    "hdr_static": None,
                },
                "presentation": {"state": "sdr", "tone_curve": None, "target_nits": None},
                "active_picture": None,
            },
            {
                "name": "encode",
                "label": 'ENC "candidate"',
                "frame_count": 100,
                "resolution": (1920, 1080),
                "fps": 24.0,
                "size_bytes": 2147483648,
                "signal": {
                    "is_hdr": True,
                    "primaries": 9,
                    "transfer": 16,
                    "matrix": 10,
                    "range": "limited",
                    "dolby_vision_rpu": False,
                    "hdr_static": None,
                },
                "presentation": {
                    "state": "hdr_tonemap_off",
                    "tone_curve": None,
                    "target_nits": None,
                },
                "active_picture": None,
            },
        ],
        "frames": [
            {
                "number": 10,
                "label": "Frame 10",
                "detail": "Selected comparison frame",
                "category": "selected",
                "images": [
                    {
                        "clip": "reference",
                        "src": "reference/10.png",
                        "source_frame": 10,
                        "picture_type": "I",
                        "dolby_vision_rpu": True,
                    },
                    {
                        "clip": "encode",
                        "src": "encode/10.png",
                        "source_frame": 10,
                        "picture_type": "P",
                        "dolby_vision_rpu": False,
                    },
                ],
            },
            {
                "number": 20,
                "label": "Frame 20",
                "detail": "Selected comparison frame",
                "category": "scene-cut",
                "images": [
                    {
                        "clip": "reference",
                        "src": "reference/20.png",
                        "source_frame": 20,
                        "picture_type": "B",
                        "dolby_vision_rpu": False,
                    },
                    {
                        "clip": "encode",
                        "src": "encode/20.png",
                        "source_frame": 20,
                        "picture_type": "B",
                        "dolby_vision_rpu": None,
                    },
                ],
            },
        ],
        "rendering": {
            "overlay_mode": "diagnostic",
            "include_frame_number": True,
            "tonemap": {"applied": False, "settings": None},
            "geometry_by_label": {},
        },
    }
