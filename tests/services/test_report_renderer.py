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
        "generated_at": "2026-05-22T12:00:00+00:00",
        "title": "Renderer Contract",
        "slowpics_url": "https://slow.pics/c/abc?x=1&y=2",
        "default_mode": "slider",
        "stats": {
            "frame_count": 2,
            "clip_count": 2,
        },
        "clips": [
            {
                "name": "reference",
                "label": "REF <main>",
                "resolution": (1920, 1080),
                "fps": 24.0,
                "hdr": False,
            },
            {
                "name": "encode",
                "label": 'ENC "candidate"',
                "resolution": (1920, 1080),
                "fps": 24.0,
                "hdr": True,
            },
        ],
        "frames": [
            {
                "number": 10,
                "images": [
                    {"clip": "reference", "src": "reference/10.png"},
                    {"clip": "encode", "src": "encode/10.png"},
                ],
            },
            {
                "number": 20,
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
    assert any(option.text == "REF <main>" for option in parser.selects["left-select"].options)
    assert parser.selects["right-select"].attrs["aria-label"] == "Right clip"
    candidate = next(
        option
        for option in parser.selects["right-select"].options
        if option.text == 'ENC "candidate"'
    )
    assert "selected" in candidate.attrs


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
    assert ".rv-divider {\n    display: none;" in css
    assert ".rv-mode-slider .rv-divider { display: block; }" in css

    assert "addEventListener('pointerdown'" in js
    assert "addEventListener('pointermove'" in js
    assert "addEventListener('pointercancel'" in js
    assert "e.touches[0]" not in js
    assert "e.clientX ||" not in js
