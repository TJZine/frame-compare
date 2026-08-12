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
        self.document_attributes: dict[str, str | None] | None = None
        self.stage_attributes: dict[str, str | None] | None = None
        self.mode_attributes: dict[str, dict[str, str | None]] = {}

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.document_attributes = attributes
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
    for name, label in (
        ("reference", "Movie.Title.2026.2160p.WEB-DL.Service-GROUP"),
        ("encode", "Movie.Title.2026.1080p.WEB-DL.Service-ENCODE"),
    ):
        screenshot = tmp_path / "screenshots" / name / "10.png"
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
            embed_images=False,
            auto_open=False,
        ),
        output_path=tmp_path / "report.html",
    )


def _append_screenshot_load_probe(report_path: Path) -> None:
    """Add a test-only DOM marker that proves a sibling file actually loaded."""
    html = report_path.read_text(encoding="utf-8")
    probe = """
<img id="sibling-screenshot-probe" src="screenshots/reference/10.png" alt="" hidden>
<script>
document.addEventListener('DOMContentLoaded', () => {
    const probeHud = () => {
        const frameHud = document.querySelector('.rv-stage-overlay-info');
        const label = document.getElementById('label-left');
        const rectanglesIntersect = (first, second) => !(
            first.right <= second.left
            || second.right <= first.left
            || first.bottom <= second.top
            || second.bottom <= first.top
        );
        label.textContent = ReportViewer.diffOverlayLabel(
            ReportViewer.state.data.clips[0],
            ReportViewer.state.data.clips[1]
        );
        document.documentElement.dataset.diffSourceHudVisible = String(
            window.getComputedStyle(label).display !== 'none'
            && label.textContent.includes('Base')
            && label.textContent.includes('Compare')
        );
        document.documentElement.dataset.diffHudsSeparate = String(
            !rectanglesIntersect(label.getBoundingClientRect(), frameHud.getBoundingClientRect())
        );
        const sourceHudStyle = window.getComputedStyle(label);
        const frameHudStyle = window.getComputedStyle(frameHud);
        document.documentElement.dataset.hudStylesAligned = String(
            label.getBoundingClientRect().top === frameHud.getBoundingClientRect().top
            && sourceHudStyle.borderRadius === frameHudStyle.borderRadius
        );
        ReportViewer.setOverlaysHidden(true, { save: false });
        document.documentElement.dataset.hudToggleHidesBoth = String(
            ReportViewer.dom.stage.classList.contains('rv-overlays-hidden')
            && frameHud !== null
        );
        ReportViewer.setOverlaysHidden(false, { save: false });

        ReportViewer.setMode('slider');
        const sliderLabelsSeparate = [0, 100].every(revealPercent => {
            ReportViewer.state.revealPercent = revealPercent;
            ReportViewer.updateSlider();
            ReportViewer.dom.canvas.style.setProperty('--zoom-level', '2');
            ReportViewer.dom.canvas.style.setProperty('--pan-x', '120px');
            ReportViewer.dom.canvas.style.setProperty('--pan-y', '80px');
            const leftSliderLabel = document.getElementById('label-left').getBoundingClientRect();
            const rightSliderLabel = document.getElementById('label-right').getBoundingClientRect();
            return !rectanglesIntersect(leftSliderLabel, rightSliderLabel);
        });
        document.documentElement.dataset.sliderLabelsSeparate = String(sliderLabelsSeparate);

        ReportViewer.setMode('overlay');
        const before = label.getBoundingClientRect();
        ReportViewer.dom.canvas.style.setProperty('--zoom-level', '2');
        ReportViewer.dom.canvas.style.setProperty('--pan-x', '120px');
        ReportViewer.dom.canvas.style.setProperty('--pan-y', '80px');
        const after = label.getBoundingClientRect();
        document.documentElement.dataset.sourceHudViewportStable = String(
            before.left === after.left && before.top === after.top
        );
        document.documentElement.dataset.sourceHudText = label.textContent;
        document.documentElement.dataset.sourceHudWraps = String(
            sourceHudStyle.whiteSpace === 'normal'
            && sourceHudStyle.textOverflow !== 'ellipsis'
        );
        ReportViewer.setMode('diff');
    };
    probeHud();
    const mark = () => {
        const image = document.getElementById('sibling-screenshot-probe');
        const loaded = image && image.complete && image.naturalWidth > 0;
        if (loaded || !document.documentElement.dataset.siblingScreenshotLoaded) {
            document.documentElement.dataset.siblingScreenshotLoaded = loaded ? 'true' : 'false';
        }
    };
    document.getElementById('sibling-screenshot-probe').addEventListener('load', mark);
    const interval = window.setInterval(mark, 100);
    window.setTimeout(() => window.clearInterval(interval), 5000);
});
</script>
"""
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")


@pytest.mark.integration
def test_generated_report_initializes_observable_mode_and_aria_state(tmp_path: Path) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")

    report_path = _generated_report(tmp_path)
    _append_screenshot_load_probe(report_path)
    completed = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-gpu",
            "--no-first-run",
            "--virtual-time-budget=10000",
            "--window-size=375,800",
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

    assert 'src="screenshots/reference/10.png"' in completed.stdout
    assert parser.document_attributes is not None
    assert parser.document_attributes["data-sibling-screenshot-loaded"] == "true"
    assert parser.document_attributes["data-source-hud-viewport-stable"] == "true"
    assert parser.document_attributes["data-source-hud-wraps"] == "true"
    assert parser.document_attributes["data-diff-source-hud-visible"] == "true"
    assert parser.document_attributes["data-diff-huds-separate"] == "true"
    assert parser.document_attributes["data-hud-styles-aligned"] == "true"
    assert parser.document_attributes["data-hud-toggle-hides-both"] == "true"
    assert parser.document_attributes["data-slider-labels-separate"] == "true"
    assert parser.document_attributes["data-source-hud-text"] == (
        "Movie.Title.2026.2160p.WEB-DL.Service-GROUP • 1×1 • SDR"
    )
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
