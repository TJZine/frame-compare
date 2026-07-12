"""Passive live probes for the slow.pics browser upload protocol.

These tests intentionally avoid image uploads and comparison creation. They are
skipped by default because they use the live slow.pics site.
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
import pytest

pytestmark = pytest.mark.network

_LIVE_SLOWPICS_ENABLED = os.environ.get("FRAME_COMPARE_LIVE_SLOWPICS") == "1"


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attrs_by_name = dict(attrs)
        src = attrs_by_name.get("src")
        if src:
            self.scripts.append(src)


def _same_origin_scripts(page_url: httpx.URL, html: str) -> list[str]:
    parser = _ScriptParser()
    parser.feed(html)
    page_url_text = str(page_url)
    return [
        urljoin(page_url_text, src)
        for src in parser.scripts
        if urlparse(urljoin(page_url_text, src)).netloc == "slow.pics"
    ]


def _literal_field_names(script: str) -> set[str]:
    return set(re.findall(r"\bappend\(\s*['\"]([^'\"]+)['\"]", script))


def _append_call_windows(script: str, *, width: int = 300) -> list[str]:
    return [
        script[match.start() : match.start() + width]
        for match in re.finditer(r"\bappend\(", script)
    ]


def _assert_dynamic_field_evidence(
    script: str,
    field_name: str,
    required_fragments: tuple[str, ...],
) -> None:
    if any(
        all(fragment in window for fragment in required_fragments)
        for window in _append_call_windows(script)
    ):
        return

    pytest.fail(f"Expected FormData.append evidence for dynamic field {field_name!r}")


def _assert_script_regex(script: str, pattern: str, description: str) -> None:
    if re.search(pattern, script):
        return

    pytest.fail(f"Expected upload script evidence for {description}")


_JS_IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"


def _matching_brace_index(script: str, open_brace_index: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False

    for index in range(open_brace_index, len(script)):
        char = script[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"', "`"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index

    return None


def _named_function_bodies(script: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    for match in re.finditer(rf"\bfunction\s+({_JS_IDENTIFIER})\s*\([^)]*\)\s*\{{", script):
        body_start = match.end()
        body_end = _matching_brace_index(script, body_start - 1)
        if body_end is not None:
            bodies.append((match.group(1), script[body_start:body_end]))
    return bodies


def _function_names_touching_cookie(script: str, *, writes: bool) -> set[str]:
    cookie_pattern = r"document\s*\.\s*cookie\s*=" if writes else r"document\s*\.\s*cookie(?!\s*=)"
    return {
        name for name, body in _named_function_bodies(script) if re.search(cookie_pattern, body)
    }


def _calls_browser_id_cookie_function(script: str, function_names: set[str]) -> bool:
    return any(
        re.search(rf"\b{re.escape(function_name)}\(\s*['\"]BROWSER-ID['\"]", script)
        for function_name in function_names
    )


def _browser_id_near_cookie_expression(script: str, *, writes: bool) -> bool:
    cookie_pattern = r"document\s*\.\s*cookie\s*=" if writes else r"document\s*\.\s*cookie(?!\s*=)"
    browser_id_pattern = r"['\"]BROWSER-ID['\"]"
    return (
        re.search(
            rf"(?:{cookie_pattern}.{{0,500}}{browser_id_pattern})|"
            rf"(?:{browser_id_pattern}.{{0,500}}{cookie_pattern})",
            script,
        )
        is not None
    )


def _assert_browser_id_cookie_behavior(script: str) -> None:
    cookie_readers = _function_names_touching_cookie(script, writes=False)
    if not (
        _calls_browser_id_cookie_function(script, cookie_readers)
        or _browser_id_near_cookie_expression(script, writes=False)
    ):
        pytest.fail("Expected BROWSER-ID to be read from document.cookie")

    cookie_writers = _function_names_touching_cookie(script, writes=True)
    if not (
        _calls_browser_id_cookie_function(script, cookie_writers)
        or _browser_id_near_cookie_expression(script, writes=True)
    ):
        pytest.fail("Expected BROWSER-ID to be written through document.cookie")


@pytest.mark.skipif(
    not _LIVE_SLOWPICS_ENABLED,
    reason="Set FRAME_COMPARE_LIVE_SLOWPICS=1 to run passive slow.pics probes",
)
def test_slowpics_comparison_page_exposes_passive_upload_protocol() -> None:
    with httpx.Client(
        base_url="https://slow.pics",
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": "frame-compare-passive-slowpics-probe/1.0"},
    ) as client:
        page = client.get("/comparison")
        page.raise_for_status()

        assert page.url == httpx.URL("https://slow.pics/comparison")
        assert "XSRF-TOKEN" in client.cookies

        script_urls = _same_origin_scripts(page.url, page.text)
        upload_script_url = next(
            (script_url for script_url in script_urls if "/js/upload-comparison-" in script_url),
            None,
        )
        if upload_script_url is None:
            pytest.fail(
                f"Upload script not found for {page.url}; same-origin scripts={script_urls!r}"
            )
        upload_script = client.get(upload_script_url)
        upload_script.raise_for_status()

    script_text = upload_script.text
    literal_fields = _literal_field_names(script_text)

    assert "/upload/comparison" in script_text
    assert "/upload/image/" in script_text
    assert "XSRF-TOKEN" in script_text
    _assert_browser_id_cookie_behavior(script_text)
    _assert_script_regex(
        script_text,
        r"['\"]?credentials['\"]?\s*:\s*['\"]same-origin['\"]",
        'fetch credentials set to "same-origin"',
    )
    _assert_script_regex(
        script_text,
        r"['\"]X-XSRF-TOKEN['\"]\s*:",
        "X-XSRF-TOKEN upload header",
    )
    _assert_script_regex(
        script_text,
        r"['\"]Access-Control-Allow-Origin['\"]\s*:\s*['\"]\*['\"]",
        "Access-Control-Allow-Origin upload header",
    )
    _assert_script_regex(
        script_text,
        r"localStorage\s*\.\s*getItem\(\s*['\"]browserId['\"]\s*\)",
        "browserId localStorage read",
    )
    _assert_script_regex(
        script_text,
        r"localStorage\s*\.\s*setItem\(\s*['\"]browserId['\"]",
        "browserId localStorage write",
    )

    assert {
        "collectionName",
        "browserId",
        "optimizeImages",
        "desiredFileType",
        "hentai",
        "public",
        "visibility",
        "removeAfter",
        "tmdbId",
        "collectionUuid",
        "imageUuid",
        "file",
    } <= literal_fields

    _assert_dynamic_field_evidence(
        script_text,
        "comparisons[].name",
        ("comparisons[", "].name"),
    )
    _assert_dynamic_field_evidence(
        script_text,
        "comparisons[].images[].name",
        ("comparisons[", "].images[", "].name"),
    )
    _assert_dynamic_field_evidence(
        script_text,
        "comparisons[].images[].sortOrder",
        ("comparisons[", "].images[", "].sortOrder"),
    )
    _assert_dynamic_field_evidence(
        script_text,
        "tags[]",
        ("tags[", "]"),
    )
