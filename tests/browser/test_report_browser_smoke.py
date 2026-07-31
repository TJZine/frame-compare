"""Real-browser smoke coverage for generated offline reports."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest

from frame_compare.config.schema import ReportConfig
from frame_compare.config.schema_enums import ViewerMode
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import ClipInfo, ReportData

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
_BROWSER_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
_MAC_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class _InitializedViewerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stage_attributes: dict[str, str | None] | None = None
        self.mode_attributes: dict[str, dict[str, str | None]] = {}

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "div" and "rv-viewer-stage" in classes:
            self.stage_attributes = attributes
        mode = attributes.get("data-mode")
        if tag == "button" and mode is not None:
            self.mode_attributes[mode] = attributes


def _browser_executable() -> str | None:
    configured = os.environ.get("REPORT_BROWSER")
    if configured:
        return configured
    for name in _BROWSER_NAMES:
        executable = shutil.which(name)
        if executable is not None:
            return executable
    if _MAC_CHROME.is_file():
        return str(_MAC_CHROME)
    return None


def _generated_report(tmp_path: Path) -> Path:
    clips: list[ClipInfo] = []
    for name, label in (("reference", "REF"), ("encode", "ENC")):
        screenshot = tmp_path / name / "10.png"
        screenshot.parent.mkdir(parents=True)
        screenshot.write_bytes(_ONE_PIXEL_PNG)
        clips.append(
            ClipInfo(
                name=name,
                label=label,
                path=tmp_path / f"{name}.mkv",
                frame_count=20,
                resolution=(1, 1),
                fps=24.0,
                hdr=False,
                screenshots=[screenshot],
            )
        )

    return generate_report(
        ReportData(clips=[replace(clip) for clip in clips], frames=[10]),
        ReportConfig(
            default_mode=ViewerMode.DIFF,
            embed_images=True,
            auto_open=False,
        ),
        output_path=tmp_path / "report.html",
    )


@pytest.mark.integration
def test_generated_report_initializes_observable_mode_and_aria_state(tmp_path: Path) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")

    report_path = _generated_report(tmp_path)
    completed = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-gpu",
            "--no-first-run",
            "--dump-dom",
            report_path.as_uri(),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)

    assert parser.stage_attributes is not None
    stage_classes = (parser.stage_attributes["class"] or "").split()
    assert "rv-mode-diff" in stage_classes
    assert "rv-mode-slider" not in stage_classes

    diff_attributes = parser.mode_attributes["diff"]
    assert "active" in (diff_attributes["class"] or "").split()
    assert diff_attributes["aria-checked"] == "true"

    slider_attributes = parser.mode_attributes["slider"]
    assert "active" not in (slider_attributes.get("class") or "").split()
    assert slider_attributes["aria-checked"] == "false"
