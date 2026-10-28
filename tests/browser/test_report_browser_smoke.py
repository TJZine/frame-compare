"""Real-browser smoke coverage for generated offline reports."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import pytest
from tests.tonemap_test_support import libplacebo_tonemap

from frame_compare.config.schema import OverlayMode, ReportConfig
from frame_compare.config.schema_enums import ViewerMode
from frame_compare.render.overlay_text import format_file_size
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
    ReportClipDisplayInfo,
    ReportData,
    ReportImageInfo,
    ReportRenderingInfo,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.vs.types import TonemapSettings

# Keep the browser acceptance module on one xdist worker for bounded host load.
pytestmark = pytest.mark.xdist_group("browser")

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
_BROWSER_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
_MAC_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
_REFERENCE_LABEL = "Movie.Title.2026.2160p.WEB-DL.Service-GROUP.with-an-extremely-long-source-name-that-must-stay-on-the-left"
_COMPARISON_LABEL = "Movie.Title.2026.1080p.WEB-DL.Service-ENCODE.with-an-equally-long-source-name-that-must-stay-on-the-right"
_REFERENCE_PRIMARY = "Movie Title (2026) | 2160p | PMTP WEB-DL | DV HDR10+ | REPACK | Kitsune"
_REFERENCE_RELEASE = "2160p | PMTP WEB-DL | DV HDR10+ | REPACK | Kitsune"
_COMPARISON_PRIMARY = "Encode A"
_COMPARISON_RELEASE = "1080p | ATV WEB-DL | HDR10 | ENCODE"
_FIXTURE_SIZE_BYTES = 17 * 1024**3
_FIXTURE_SIZE_LABEL = format_file_size(_FIXTURE_SIZE_BYTES)


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


def _run_browser_dump(
    browser: str,
    report_path: Path,
    *,
    width: int,
    height: int,
    scale: float = 1.0,
) -> subprocess.CompletedProcess[str]:
    command = [
        browser,
        "--headless=new",
        # Let our subprocess timeout bound teardown, not Chrome's shorter macOS watchdog.
        "--test-type",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-gpu",
        "--no-first-run",
        "--virtual-time-budget=10000",
        f"--window-size={width},{height}",
        f"--force-device-scale-factor={scale}",
        "--dump-dom",
        report_path.as_uri(),
    ]
    with TemporaryDirectory(prefix="chrome-dump-", dir=report_path.parent) as profile:
        command.insert(1, f"--user-data-dir={profile}")
        return _run_browser_dump_command(command)


def _run_browser_dump_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    for attempt in range(2):
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        except subprocess.CalledProcessError as error:
            stderr = error.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            error.add_note(f"Chrome stderr (first 8000 characters):\n{(stderr or '')[:8000]}")
            raise
        except subprocess.TimeoutExpired:
            if attempt == 1:
                raise
    raise AssertionError("unreachable")


def test_browser_dump_retries_one_transient_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "report.html"
    report_path.write_text("<html></html>", encoding="utf-8")
    completed = subprocess.CompletedProcess(["chrome"], 0, stdout="<html></html>", stderr="")
    outcomes: list[subprocess.CompletedProcess[str] | subprocess.TimeoutExpired] = [
        subprocess.TimeoutExpired(["chrome"], 30),
        completed,
    ]

    def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        outcome = outcomes.pop(0)
        if isinstance(outcome, subprocess.TimeoutExpired):
            raise outcome
        return outcome

    monkeypatch.setattr(subprocess, "run", run)

    assert _run_browser_dump("chrome", report_path, width=375, height=240) is completed
    assert outcomes == []


def test_browser_dump_stops_after_second_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def time_out(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(["chrome"], 30)

    monkeypatch.setattr(subprocess, "run", time_out)

    with pytest.raises(subprocess.TimeoutExpired):
        _run_browser_dump("chrome", tmp_path / "report.html", width=375, height=240)
    assert calls == 2


def test_browser_dump_does_not_retry_non_timeout_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    error = subprocess.CalledProcessError(
        2, ["chrome"], stderr="profile startup failed\n" + "x" * 9000
    )

    def fail(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        raise error

    monkeypatch.setattr(subprocess, "run", fail)

    with pytest.raises(subprocess.CalledProcessError) as raised:
        _run_browser_dump("chrome", tmp_path / "report.html", width=375, height=240)
    assert calls == 1
    assert raised.value is error
    assert raised.value.returncode == 2
    assert "profile startup failed" in error.__notes__[0]
    assert len(error.__notes__[0]) < 8100


def _generated_report(
    tmp_path: Path,
    *,
    tonemapped: bool = False,
    encoded_image_paths: bool = False,
    frames: tuple[int, ...] = (10,),
) -> Path:
    clips: list[ClipInfo] = []
    geometry_by_name = {
        "reference": RenderedGeometryFacts(
            source_size=(1920, 1080),
            active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
            cropped_size=(1920, 1080),
            scaled_size=(1920, 1080),
            final_canvas_size=(1920, 1080),
            is_noop=True,
        ),
        "encode": RenderedGeometryFacts(
            source_size=(1920, 1080),
            active_picture=ActivePictureFacts(0, 276, 1920, 804, "explicit", False),
            cropped_size=(1920, 804),
            scaled_size=(1920, 804),
            final_canvas_size=(1920, 804),
            is_noop=False,
        ),
    }
    for name, label in (
        ("reference", _REFERENCE_LABEL),
        ("encode", _COMPARISON_LABEL),
    ):
        geometry = geometry_by_name[name]
        screenshot = (
            tmp_path / "screenshots # %20 Ü" / f"{name} # %20 Ü.png"
            if encoded_image_paths
            else tmp_path / "screenshots" / name / "10.png"
        )
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot.write_bytes(_ONE_PIXEL_PNG)
        clips.append(
            ClipInfo(
                name=name,
                label=label,
                path=tmp_path / f"{name}.mkv",
                frame_count=20,
                resolution=(1920, 1080),
                fps=24.0,
                size_bytes=_FIXTURE_SIZE_BYTES,
                signal=SourceSignalFacts(
                    is_hdr=tonemapped,
                    primaries=9 if tonemapped else 1,
                    transfer=16 if tonemapped else 1,
                    matrix=10,
                    color_range="limited",
                ),
                presentation_state=(
                    PresentationState.HDR_TONEMAPPED if tonemapped else PresentationState.SDR
                ),
                tonemap=libplacebo_tonemap(TonemapSettings()) if tonemapped else None,
                active_picture=geometry.active_picture,
                images=[
                    ReportImageInfo(
                        screenshot,
                        frame if name == "reference" else frame + 2,
                        RenderedFrameFacts(frame if name == "reference" else frame + 2, "B"),
                    )
                    for frame in frames
                ],
                display=ReportClipDisplayInfo(
                    primary=(_REFERENCE_PRIMARY if name == "reference" else _COMPARISON_PRIMARY),
                    release=(_REFERENCE_RELEASE if name == "reference" else _COMPARISON_RELEASE),
                    control=(_REFERENCE_RELEASE if name == "reference" else _COMPARISON_RELEASE),
                    micro="PMTP DV" if name == "reference" else "ATV HDR10",
                    filename=f"{label}.mkv",
                ),
            )
        )

    return generate_report(
        ReportData(
            clips=[replace(clip) for clip in clips],
            frames=list(frames),
            rendering=ReportRenderingInfo(
                overlay_mode=OverlayMode.DIAGNOSTIC,
                include_frame_number=True,
                geometry_by_label={
                    clip.label or clip.name: geometry_by_name[clip.name] for clip in clips
                },
            ),
        ),
        ReportConfig(
            default_mode=ViewerMode.DIFF,
            embed_images=False,
            auto_open=False,
        ),
        output_path=tmp_path / "report.html",
    )


def _append_encoded_image_load_probe(report_path: Path) -> None:
    html = report_path.read_text(encoding="utf-8")
    probe = """
<img id="encoded-screenshot-probe" src="screenshots%20%23%20%2520%20%C3%9C/reference%20%23%20%2520%20%C3%9C.png" alt="" hidden>
<script>
document.addEventListener('DOMContentLoaded', () => {
    const image = document.getElementById('encoded-screenshot-probe');
    const mark = () => {
        document.documentElement.dataset.encodedImagesLoaded = String(
            image.complete && image.naturalWidth > 0
        );
    };
    image.addEventListener('load', mark, { once: true });
    image.addEventListener('error', mark, { once: true });
    mark();
});
</script>
"""
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")


@pytest.mark.integration
def test_generated_report_loads_percent_encoded_screenshot_paths(tmp_path: Path) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")

    report_path = _generated_report(tmp_path, encoded_image_paths=True)
    _append_encoded_image_load_probe(report_path)
    completed = _run_browser_dump(browser, report_path, width=1024, height=768)
    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)

    assert "screenshots%20%23%20%2520%20%C3%9C" in completed.stdout
    assert parser.document_attributes is not None
    assert parser.document_attributes["data-encoded-images-loaded"] == "true"


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
        const rightLabel = document.getElementById('label-right');
        const stage = document.querySelector('.rv-viewer-stage');
        const stageLabels = document.querySelector('.rv-stage-labels');
        const palette = document.querySelector('.rv-viewport-palette');
        document.documentElement.dataset.selectAffordances = String(
            Array.from(document.querySelectorAll('select')).every(select => {
                const style = window.getComputedStyle(select);
                return style.backgroundImage !== 'none'
                    && parseFloat(style.paddingRight) >= 24;
            })
        );
        const rectanglesIntersect = (first, second) => !(
            first.right <= second.left
            || second.right <= first.left
            || first.bottom <= second.top
            || second.bottom <= first.top
        );
        const ariaLabelHasSizeOnce = element => {
            const accessibleName = element?.getAttribute('aria-label');
            return typeof accessibleName === 'string'
                && accessibleName.split(__FIXTURE_SIZE_LABEL__).length - 1 === 1;
        };
        const ariaLabelOmitsSize = element => {
            const accessibleName = element?.getAttribute('aria-label');
            return typeof accessibleName === 'string'
                && !accessibleName.includes(__FIXTURE_SIZE_LABEL__);
        };
        ReportViewer.setMode('slider');
        ReportViewer.setMode('diff');
        document.documentElement.dataset.diffSourceHudVisible = String(
            window.getComputedStyle(label).display !== 'none'
            && window.getComputedStyle(rightLabel).display !== 'none'
            && label.textContent.startsWith(__REFERENCE_HUD_LABEL__)
            && rightLabel.textContent.startsWith(__COMPARISON_HUD_LABEL__)
        );
        document.documentElement.dataset.diffHudsSeparate = String(
            !rectanglesIntersect(label.getBoundingClientRect(), frameHud.getBoundingClientRect())
        );
        const expectedStageHudPrefixes = {
            overlay: [__REFERENCE_HUD_LABEL__],
            slider: [
                __REFERENCE_HUD_LABEL__,
                __COMPARISON_HUD_LABEL__,
            ],
            diff: [
                __REFERENCE_HUD_LABEL__,
                __COMPARISON_HUD_LABEL__,
            ],
            blink: [
                __REFERENCE_HUD_LABEL__,
                __COMPARISON_HUD_LABEL__,
            ],
        };
        const stageHudAccessible = Object.entries(expectedStageHudPrefixes).every(
            ([mode, expectedPrefixes]) => {
                ReportViewer.setMode(mode);
                const visibleLabels = [label, rightLabel].filter(
                    item => item.textContent.length > 0
                );
                return stageLabels.getAttribute('aria-hidden') === null
                    && visibleLabels.length === expectedPrefixes.length
                    && visibleLabels.every((item, index) => (
                        item.textContent.startsWith(expectedPrefixes[index])
                        && item.textContent.split(__FIXTURE_SIZE_LABEL__).length - 1 === 1
                    ));
            }
        );
        ReportViewer.setMode('diff');
        const sourceHudStyle = window.getComputedStyle(label);
        document.documentElement.dataset.hudStylesAligned = String(
            label.getBoundingClientRect().top === rightLabel.getBoundingClientRect().top
            && sourceHudStyle.borderRadius === window.getComputedStyle(rightLabel).borderRadius
        );
        label.style.transition = 'none';
        rightLabel.style.transition = 'none';
        frameHud.style.transition = 'none';
        ReportViewer.setOverlaysHidden(true, { save: false });
        document.documentElement.dataset.hudToggleHidesBoth = String(
            ReportViewer.dom.stage.classList.contains('rv-overlays-hidden')
            && frameHud !== null
            && window.getComputedStyle(label).visibility === 'hidden'
            && window.getComputedStyle(rightLabel).visibility === 'hidden'
        );
        ReportViewer.setOverlaysHidden(false, { save: false });

        ReportViewer.setMode('slider');
        const sliderLabelsSeparate = [0, 50, 100].every(revealPercent => {
            ReportViewer.state.revealPercent = revealPercent;
            ReportViewer.viewport.updateSlider();
            ReportViewer.dom.canvas.style.setProperty('--zoom-level', '2');
            ReportViewer.dom.canvas.style.setProperty('--pan-x', '120px');
            ReportViewer.dom.canvas.style.setProperty('--pan-y', '80px');
            const leftSliderLabel = document.getElementById('label-left').getBoundingClientRect();
            const rightSliderLabel = document.getElementById('label-right').getBoundingClientRect();
            return !rectanglesIntersect(leftSliderLabel, rightSliderLabel);
        });
        document.documentElement.dataset.sliderLabelsSeparate = String(sliderLabelsSeparate);
        const stageRect = stage.getBoundingClientRect();
        const paletteRect = palette.getBoundingClientRect();
        const leftSliderLabel = document.getElementById('label-left').getBoundingClientRect();
        const rightSliderLabel = document.getElementById('label-right').getBoundingClientRect();
        const paletteInset = window.innerWidth <= 768 ? 8 : (window.innerWidth <= 992 ? 12 : 16);
        const labelInset = window.innerWidth <= 768 ? 8 : 12;
        const approximately = (first, second) => Math.abs(first - second) <= 1;
        const originalFilmstripSize = ReportViewer.state.filmstripSize;
        document.documentElement.dataset.filmstripImageSpace = String(
            [['compact', 120], ['normal', 150], ['large', 210]].every(([size, width]) => {
                ReportViewer.setFilmstripSize(size, { save: false });
                const item = document.querySelector('.rv-filmstrip-item');
                const thumb = item.querySelector('.rv-filmstrip-thumb');
                const caption = item.querySelector('.rv-filmstrip-caption');
                const cardRect = item.getBoundingClientRect();
                const thumbRect = thumb.getBoundingClientRect();
                const captionRect = caption.getBoundingClientRect();
                return approximately(cardRect.width, width)
                    && approximately(cardRect.height, cardRect.width * 10 / 16)
                    && approximately(thumbRect.width, item.clientWidth)
                    && approximately(thumbRect.height, item.clientHeight)
                    && approximately(captionRect.width, thumbRect.width)
                    && approximately(captionRect.bottom, thumbRect.bottom)
                    && captionRect.top >= thumbRect.top
                    && window.getComputedStyle(caption).position === 'absolute';
            })
        );
        ReportViewer.setFilmstripSize(originalFilmstripSize, { save: false });
        const primaryControls = document.querySelector('.rv-primary-controls');
        const frameControls = document.querySelector('.rv-frame-controls');
        const modeControls = document.querySelector('.rv-mode-controls');
        const contextZone = document.querySelector('.rv-context-zone');
        const modeGeometry = ['slider', 'overlay', 'diff', 'blink', 'grid'].map(mode => {
            ReportViewer.setMode(mode);
            const primaryRect = primaryControls.getBoundingClientRect();
            const frameRect = frameControls.getBoundingClientRect();
            const modeRect = modeControls.getBoundingClientRect();
            const contextRect = contextZone.getBoundingClientRect();
            const visibleContext = contextZone.querySelector('.rv-context-controls:not([hidden])');
            const alignment = document.getElementById('alignment-status');
            const visibleContextRect = visibleContext?.getBoundingClientRect();
            const alignmentRect = alignment.getBoundingClientRect();
            return {
                mode,
                center: modeRect.left + (modeRect.width / 2),
                primary: primaryRect.toJSON(),
                frame: frameRect.toJSON(),
                modeRect: modeRect.toJSON(),
                context: contextRect.toJSON(),
                childrenSeparate: !visibleContextRect
                    || !rectanglesIntersect(visibleContextRect, alignmentRect),
                zonesSeparate: !rectanglesIntersect(frameRect, modeRect)
                    && !rectanglesIntersect(frameRect, contextRect)
                    && !rectanglesIntersect(modeRect, contextRect),
            };
        });
        const modeCenters = modeGeometry.map(entry => entry.center);
        const firstGeometry = modeGeometry[0];
        document.documentElement.dataset.toolbarGeometry = JSON.stringify(modeGeometry);
        document.documentElement.dataset.modeCenterStable = String(
            Math.max(...modeCenters) - Math.min(...modeCenters) <= 1
        );
        document.documentElement.dataset.toolbarHeightStable = String(
            modeGeometry.every(entry => (
                approximately(entry.primary.top, firstGeometry.primary.top)
                && approximately(entry.primary.height, firstGeometry.primary.height)
            ))
        );
        document.documentElement.dataset.toolbarZonesSeparate = String(
            modeGeometry.every(entry => entry.zonesSeparate && entry.childrenSeparate)
        );
        document.documentElement.dataset.toolbarAnchors = String(
            modeGeometry.every(entry => {
                if (window.innerWidth > 1120) {
                    return approximately(entry.frame.left, entry.primary.left)
                        && approximately(entry.context.right, entry.primary.right)
                        && approximately(
                            entry.center,
                            entry.primary.left + (entry.primary.width / 2)
                        );
                }
                if (window.innerWidth > 768) {
                    return approximately(entry.frame.left, entry.primary.left)
                        && approximately(entry.modeRect.right, entry.primary.right)
                        && approximately(entry.context.left, entry.primary.left)
                        && approximately(entry.context.right, entry.primary.right);
                }
                return approximately(entry.frame.left, entry.primary.left)
                    && approximately(entry.frame.right, entry.primary.right)
                    && approximately(entry.context.left, entry.primary.left)
                    && approximately(entry.context.right, entry.primary.right);
            })
        );
        ReportViewer.setMode('slider');
        document.documentElement.dataset.paletteBottomAnchored = String(
            stageRect.height > 0
            && paletteRect.top >= stageRect.top
            && approximately(paletteRect.bottom, stageRect.bottom - paletteInset)
        );
        document.documentElement.dataset.bottomHudsSeparate = String(
            window.getComputedStyle(frameHud).display === 'none'
            || !rectanglesIntersect(paletteRect, frameHud.getBoundingClientRect())
        );
        document.documentElement.dataset.sliderLabelsTopAnchored = String(
            approximately(leftSliderLabel.top, stageRect.top + labelInset)
            && approximately(rightSliderLabel.top, stageRect.top + labelInset)
            && approximately(leftSliderLabel.left, stageRect.left + labelInset)
            && approximately(rightSliderLabel.right, stageRect.right - labelInset)
        );
        document.documentElement.dataset.sliderLabelsContained = String(
            leftSliderLabel.left >= stageRect.left
            && leftSliderLabel.right <= stageRect.left + (stageRect.width / 2)
            && rightSliderLabel.left >= stageRect.left + (stageRect.width / 2)
            && rightSliderLabel.right <= stageRect.right
        );
        document.documentElement.dataset.sliderLabelGeometry = JSON.stringify({
            stage: stageRect.toJSON(),
            left: leftSliderLabel.toJSON(),
            right: rightSliderLabel.toJSON(),
            labelInset,
        });

        stage.style.transition = 'none';
        ReportViewer.inspector.setOpen(true, { focus: false, save: false });
        ReportViewer.inspector.setTab('clips', { save: false });
        ReportViewer.updateInspectorData();
        const inspectorStageRect = stage.getBoundingClientRect();
        const inspectorPaletteRect = palette.getBoundingClientRect();
        const inspector = document.getElementById('rv-inspector');
        const activeInspectorPanel = document.querySelector('.rv-inspector-panel:not([hidden])');
        const expectedInspectorWidth = window.innerWidth <= 992
            ? Math.min(448, window.innerWidth * 0.92)
            : Math.min(Math.max(448, window.innerWidth * 0.30), 672, window.innerWidth - 32);
        const inspectorCards = Array.from(document.querySelectorAll('.rv-inspector-clip'));
        const inspectorText = inspector?.textContent || '';
        const inspectorPanelsSafe = Array.from(
            document.querySelectorAll('.rv-inspector-panel')
        ).every(panel => {
            const wasHidden = panel.hidden;
            panel.hidden = false;
            const safe = panel.scrollWidth <= panel.clientWidth;
            panel.hidden = wasHidden;
            return safe;
        });
        ReportViewer.inspector.setTab('clips', { save: false });
        ReportViewer.updateInspectorData();
        document.documentElement.dataset.inspectorWidthPolicy = String(
            approximately(inspector.getBoundingClientRect().width, expectedInspectorWidth)
            && (window.innerWidth <= 992
                ? approximately(inspectorStageRect.right, stageRect.right)
                : approximately(
                    stageRect.right - inspectorStageRect.right,
                    inspector.getBoundingClientRect().width
                ))
        );
        document.documentElement.dataset.inspectorOverflowSafe = String(
            inspector.scrollWidth <= inspector.clientWidth
            && activeInspectorPanel.scrollWidth <= activeInspectorPanel.clientWidth
            && inspectorCards.every(card => card.scrollWidth <= card.clientWidth)
            && inspectorPanelsSafe
        );
        document.documentElement.dataset.inspectorIdentityComplete = String(
            inspectorText.includes('Reference')
            && inspectorText.includes('Comparison')
            && inspectorText.includes('shown left')
            && inspectorText.includes(__REFERENCE_FILENAME__)
            && inspectorText.includes(__REFERENCE_RELEASE__)
            && inspectorText.includes('1920×1080')
            && ['2160p', 'PMTP', 'WEB-DL', 'DV HDR10+', 'REPACK', 'Kitsune']
                .every(fact => inspectorText.includes(fact))
            && inspectorCards.every(card => {
                const primary = card.querySelector('.rv-inspector-clip-primary');
                const style = window.getComputedStyle(primary);
                return style.whiteSpace !== 'nowrap' && style.textOverflow !== 'ellipsis';
            })
        );
        document.documentElement.dataset.inspectorHudAnchored = String(
            inspectorStageRect.height > 0
            && inspectorPaletteRect.top >= inspectorStageRect.top
            && approximately(inspectorPaletteRect.bottom, inspectorStageRect.bottom - paletteInset)
            && approximately(inspectorPaletteRect.right, inspectorStageRect.right - paletteInset)
        );
        ReportViewer.inspector.setOpen(false, { focus: false, save: false });
        const infoButton = document.getElementById('btn-info');
        infoButton?.focus();
        infoButton?.click();
        const infoModal = document.getElementById('info-modal');
        const infoContent = infoModal?.querySelector('.rv-modal-content');
        const infoText = infoContent?.textContent || '';
        const infoClipHeadings = Array.from(
            infoContent?.querySelectorAll('.rv-clip-meta-heading span:first-child') || []
        );
        document.documentElement.dataset.infoModalOverflowSafe = String(
            infoModal.scrollWidth <= infoModal.clientWidth
            && infoContent.scrollWidth <= infoContent.clientWidth
            && document.documentElement.scrollWidth <= document.documentElement.clientWidth
        );
        const infoCards = Array.from(infoContent?.querySelectorAll('.rv-clip-meta-item') || []);
        document.documentElement.dataset.infoModalIdentityComplete = String(
            infoText.includes(__REFERENCE_FILENAME__)
            && infoText.includes(__COMPARISON_FILENAME__)
            && infoText.includes(__REFERENCE_RELEASE__)
            && infoText.includes(__COMPARISON_RELEASE__)
            && infoCards.length === 2
            && infoCards[0].textContent.includes(__REFERENCE_FILENAME__)
            && infoCards[0].textContent.includes(__REFERENCE_RELEASE__)
            && infoCards[1].textContent.includes(__COMPARISON_FILENAME__)
            && infoCards[1].textContent.includes(__COMPARISON_RELEASE__)
            && infoClipHeadings.every(heading => {
                const style = window.getComputedStyle(heading);
                return style.whiteSpace !== 'nowrap' && style.textOverflow !== 'ellipsis';
            })
        );
        document.documentElement.dataset.infoModalWidthPolicy = String(
            approximately(
                infoContent.getBoundingClientRect().width,
                Math.min(896, window.innerWidth - 32)
            )
        );
        ReportViewer.closeInfoModal();
        document.documentElement.dataset.infoModalFocusRestored = String(
            document.activeElement === infoButton
        );
        const inspectorButton = document.getElementById('btn-inspector');
        const infoBefore = {
            label: infoButton?.getAttribute('aria-label'),
            title: infoButton?.getAttribute('title'),
            pressed: infoButton?.getAttribute('aria-pressed'),
        };
        const infoAfter = {
            label: infoButton?.getAttribute('aria-label'),
            title: infoButton?.getAttribute('title'),
            pressed: infoButton?.getAttribute('aria-pressed'),
        };
        const inspectorInitiallyClosed = inspectorButton?.getAttribute('aria-expanded') === 'false';
        inspectorButton?.focus();
        inspectorButton?.click();
        const inspectorOpened = (
            inspector?.classList.contains('open')
            && inspector?.getAttribute('aria-hidden') === 'false'
            && inspectorButton?.getAttribute('aria-expanded') === 'true'
        );
        inspectorButton?.click();
        document.documentElement.dataset.infoInspectorSemanticsStable = String(
            infoBefore.label === 'Report information'
            && infoBefore.title === 'Report information'
            && infoBefore.pressed === null
            && JSON.stringify(infoBefore) === JSON.stringify(infoAfter)
        );
        document.documentElement.dataset.visibleInspectorBehavior = String(
            inspectorButton?.getAttribute('type') === 'button'
            && inspectorButton?.getAttribute('aria-controls') === 'rv-inspector'
            && inspectorButton?.getAttribute('aria-label') === 'Open Inspector'
            && inspectorButton?.getAttribute('title') === 'Inspector (I)'
            && inspectorInitiallyClosed
            && inspectorOpened
            && inspector?.getAttribute('aria-hidden') === 'true'
            && inspectorButton?.getAttribute('aria-expanded') === 'false'
            && document.activeElement === inspectorButton
            && document.getElementById('inspector-tab-export') === null
            && document.getElementById('inspector-panel-export') === null
            && document.querySelectorAll('[data-inspector-tab]').length === 4
        );

        const filmstripAnchored = [false, true].every(collapsed => {
            ReportViewer.setFilmstripCollapsed(collapsed, { save: false });
            const currentStageRect = stage.getBoundingClientRect();
            const currentPaletteRect = palette.getBoundingClientRect();
            return currentStageRect.height > 0
                && approximately(currentPaletteRect.bottom, currentStageRect.bottom - paletteInset);
        });
        ReportViewer.setFilmstripCollapsed(false, { save: false });
        document.documentElement.dataset.filmstripHudAnchored = String(filmstripAnchored);

        ReportViewer.setPaletteOrientation('vertical', { save: false });
        const firstPaletteGroup = palette.querySelector('.rv-palette-group');
        const zoomRange = document.getElementById('zoom-range');
        document.documentElement.dataset.narrowPaletteHorizontal = String(
            window.innerWidth > 768
            || (
                window.getComputedStyle(palette).flexDirection === 'row'
                && window.getComputedStyle(firstPaletteGroup).flexDirection === 'row'
                && window.getComputedStyle(zoomRange).writingMode === 'horizontal-tb'
                && window.getComputedStyle(document.getElementById('btn-palette-orientation')).display === 'none'
            )
        );
        ReportViewer.setPaletteOrientation('horizontal', { save: false });

        ReportViewer.setMode('grid');
        const gridStageRect = stage.getBoundingClientRect();
        const gridPaletteRect = palette.getBoundingClientRect();
        const gridLabels = Array.from(document.querySelectorAll('.rv-grid-label-text'));
        const gridCells = Array.from(document.querySelectorAll('.rv-grid-cell'));
        const expectedGridLabelCount = window.matchMedia('(max-width: 768px)').matches ? 1 : 2;
        document.documentElement.dataset.gridHudAnchored = String(
            window.getComputedStyle(document.querySelector('.rv-stage-labels')).display === 'none'
            && gridLabels.length === expectedGridLabelCount
            && gridLabels.every(gridLabel => gridLabel.textContent.trim().length > 0)
            && approximately(gridPaletteRect.bottom, gridStageRect.bottom - paletteInset)
        );
        const gridHudAccessible = gridCells.every(ariaLabelHasSizeOnce);
        gridLabels.forEach(gridLabel => {
            gridLabel.closest('.rv-grid-label').style.transition = 'none';
        });
        ReportViewer.setOverlaysHidden(true, { save: false });
        const gridHudHidden = gridLabels.every(gridLabel => (
            window.getComputedStyle(gridLabel.closest('.rv-grid-label')).visibility === 'hidden'
        )) && gridCells.every(ariaLabelOmitsSize);
        ReportViewer.setOverlaysHidden(false, { save: false });
        const gridHudRestored = gridCells.every(ariaLabelHasSizeOnce);
        document.documentElement.dataset.stageHudAccessible = String(stageHudAccessible);
        document.documentElement.dataset.gridHudAccessible = String(gridHudAccessible);
        document.documentElement.dataset.gridHudHidden = String(gridHudHidden);
        document.documentElement.dataset.gridHudRestored = String(gridHudRestored);
        document.documentElement.dataset.sourceHudAccessible = String(
            stageHudAccessible && gridHudAccessible && gridHudHidden && gridHudRestored
        );

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
        ReportViewer.inspector.setOpen(true, { focus: false, save: false });
        const sourceRowsByMode = {};
        ['overlay', 'slider', 'diff', 'blink', 'grid'].forEach(mode => {
            ReportViewer.setMode(mode);
            ReportViewer.inspector.setTab('frame');
            ReportViewer.updateInspectorData();
            sourceRowsByMode[mode] = Array.from(
                document.querySelectorAll('[data-inspector-source-frames] tr')
            ).map(row => row.textContent.trim());
        });
        document.documentElement.dataset.frameSourceRows = JSON.stringify(sourceRowsByMode);
        ReportViewer.inspector.setTab('clips');
        ReportViewer.updateInspectorData();
        document.documentElement.dataset.clipsMetadata = String(
            document.querySelector('[data-inspector-clips]')?.textContent.includes('Size')
            && document.querySelector('[data-inspector-clips]')?.textContent.includes('Signal')
            && (document.querySelector('[data-inspector-clips-shared]')?.textContent ?? '').includes('All sources:')
            && !document.querySelector('[data-inspector-clips]')?.textContent.includes('Advanced tonemap')
        );
        let reviewTabUsable = false;
        try {
            ReportViewer.inspector.setTab('review', { save: false });
            const bookmark = document.querySelector('[data-review-bookmark]');
            const note = document.querySelector('[data-review-note]');
            bookmark.checked = true;
            bookmark.dispatchEvent(new Event('change', { bubbles: true }));
            note.value = 'Browser integration proof';
            note.dispatchEvent(new Event('input', { bubbles: true }));
            // dump-dom's virtual-time clock cannot establish asynchronous lock
            // completion. The CDP editor test below proves the durable save.
            reviewTabUsable = Boolean(
                ReportViewer.reviewController
                && bookmark.checked
                && note.value === 'Browser integration proof'
                && ReportViewer.reviewController.model.get(0).note === note.value
                && document.querySelector('[data-review-status]')?.textContent === 'Unsaved changes.'
            );
        } catch (error) {
            document.documentElement.dataset.reviewTabError = String(error);
        }
        document.documentElement.dataset.reviewTabUsable = String(reviewTabUsable);
        ReportViewer.inspector.setTab('clips', { save: false });
        document.documentElement.dataset.renderingDisclosure = String(
            document.querySelector('[data-rendering-tonemap-summary]')?.textContent === 'Not applied'
            && !document.querySelector('[data-rendering-details]')
        );
        document.documentElement.dataset.noHorizontalOverflow = String(
            document.documentElement.scrollWidth <= window.innerWidth
            && document.body.scrollWidth <= window.innerWidth
        );
        ReportViewer.inspector.setOpen(false, { focus: false, save: false });
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
    probe = probe.replace("__REFERENCE_FILENAME__", json.dumps(f"{_REFERENCE_LABEL}.mkv"))
    probe = probe.replace("__COMPARISON_FILENAME__", json.dumps(f"{_COMPARISON_LABEL}.mkv"))
    probe = probe.replace("__REFERENCE_PRIMARY__", json.dumps(_REFERENCE_PRIMARY))
    probe = probe.replace("__COMPARISON_PRIMARY__", json.dumps(_COMPARISON_PRIMARY))
    probe = probe.replace("__REFERENCE_RELEASE__", json.dumps(_REFERENCE_RELEASE))
    probe = probe.replace("__COMPARISON_RELEASE__", json.dumps(_COMPARISON_RELEASE))
    probe = probe.replace("__FIXTURE_SIZE_LABEL__", json.dumps(_FIXTURE_SIZE_LABEL))
    probe = probe.replace("__REFERENCE_HUD_LABEL__", json.dumps(_REFERENCE_RELEASE))
    probe = probe.replace("__COMPARISON_HUD_LABEL__", json.dumps(_COMPARISON_RELEASE))
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")


def _append_tonemap_disclosure_probe(report_path: Path) -> None:
    html = report_path.read_text(encoding="utf-8")
    probe = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    const disclosure = document.querySelector('[data-rendering-details]');
    const summary = disclosure?.querySelector('summary');
    const settings = disclosure?.querySelector('dl');
    const advancedLabels = [
        'Dynamic peak detection', 'Contrast recovery', 'Gamma lift',
        'Destination minimum', 'Knee offset', 'Smoothing period', 'Percentile',
        'Scene thresholds', 'Gamut mapping',
        'Metadata mode', 'Dolby Vision metadata use',
    ];
    document.getElementById('btn-info')?.click();
    const infoContent = document.querySelector('#info-modal .rv-modal-content');
    const infoContentStyle = infoContent ? window.getComputedStyle(infoContent) : null;
    document.documentElement.dataset.infoModalScrollable = String(
        Boolean(
            infoContent
            && infoContentStyle?.overflowY === 'auto'
            && infoContentStyle?.overscrollBehaviorY === 'contain'
            && infoContent.scrollHeight > infoContent.clientHeight
        )
    );
    document.documentElement.dataset.tonemapSummary = String(
        document.querySelector('[data-rendering-tonemap-summary]')?.textContent
        === 'BT.2390 · 100 nits'
    );
    document.documentElement.dataset.tonemapDisclosureInitial = String(
        Boolean(
            ReportViewer.isInfoModalOpen()
            && disclosure
            && summary
            && !disclosure.open
            && settings
        )
    );
    document.documentElement.dataset.tonemapAdvancedRows = String(
        Boolean(settings)
        && advancedLabels.every(label => settings.textContent.includes(label))
        && settings.textContent.includes('On')
        && settings.textContent.includes('Off')
        && settings.textContent.includes('Auto')
    );
    let enterReceived = false;
    summary?.addEventListener('keydown', event => {
        if (event.key === 'Enter') enterReceived = true;
    });
    const pressEnter = () => {
        summary?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
        // Chrome does not run default actions for synthetic keyboard events in dump-dom.
        if (summary) summary.click();
        summary?.focus();
    };
    summary?.focus();
    pressEnter();
    document.documentElement.dataset.tonemapOpenState = String(Boolean(disclosure?.open));
    document.documentElement.dataset.tonemapFocusState = String(document.activeElement === summary);
    document.documentElement.dataset.tonemapDisclosureOpened = String(
        Boolean(enterReceived && disclosure?.open && document.activeElement === summary)
    );
    pressEnter();
    document.documentElement.dataset.tonemapDisclosureClosed = String(
        Boolean(disclosure && !disclosure.open && document.activeElement === summary)
    );
});
</script>
"""
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")


@pytest.mark.integration
def test_applied_tonemap_disclosure_is_focusable_toggleable_and_scrollable(
    tmp_path: Path,
) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")
    report_path = _generated_report(tmp_path, tonemapped=True)
    _append_tonemap_disclosure_probe(report_path)
    completed = _run_browser_dump(browser, report_path, width=375, height=240)
    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)
    assert parser.document_attributes is not None
    for attribute in (
        "data-tonemap-summary",
        "data-tonemap-disclosure-initial",
        "data-tonemap-advanced-rows",
        "data-tonemap-open-state",
        "data-tonemap-focus-state",
        "data-tonemap-disclosure-opened",
        "data-tonemap-disclosure-closed",
        "data-info-modal-scrollable",
    ):
        assert parser.document_attributes[attribute] == "true", (
            attribute,
            parser.document_attributes[attribute],
            parser.document_attributes,
        )


def _append_pair_offset_mode_transition_probe(report_path: Path) -> None:
    html = report_path.read_text(encoding="utf-8")
    probe = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    const viewer = ReportViewer;
    const storageKey = viewer.viewerStorageKey();
    const results = [];
    const clickMode = mode => document.querySelector(`[data-mode="${mode}"]`).click();
    const selectRight = index => {
        const select = document.getElementById('right-select');
        select.value = String(index);
        select.dispatchEvent(new Event('change', { bubbles: true }));
    };
    const typeOffset = (x, y) => {
        for (const [axis, value] of [['x', x], ['y', y]]) {
            const input = document.getElementById(`align-${axis}`);
            input.value = String(value);
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('blur'));
        }
    };
    for (const mode of ['diff', 'blink']) {
        for (const savedOffset of [false, true]) {
            for (const sameSourceOffset of [false, true]) {
                localStorage.removeItem(storageKey);
                viewer.restorePersistedState();
                clickMode('slider');
                selectRight(1);
                if (savedOffset) typeOffset(7, 3);
                selectRight(0);
                if (sameSourceOffset) typeOffset(2, 2);
                clickMode(mode);
                const canvas = getComputedStyle(viewer.dom.canvas);
                const saved = JSON.parse(localStorage.getItem(storageKey));
                const current = viewer.viewport.currentAlignment();
                const result = {
                    mode, savedOffset, sameSourceOffset,
                    pair: viewer.viewport.currentPairAlignmentKey(),
                    current,
                    stored: saved.pairAlignments['0:1'] || null,
                    storedSameSource: saved.pairAlignments['0:0'] || null,
                    x: canvas.getPropertyValue('--align-x').trim(),
                    y: canvas.getPropertyValue('--align-y').trim(),
                    transform: getComputedStyle(document.querySelector('.rv-right')).transform,
                    status: document.getElementById('alignment-status').textContent.trim(),
                };
                viewer.restorePersistedState();
                result.restored = viewer.viewport.currentAlignment();
                results.push(result);
            }
        }
    }
    document.documentElement.dataset.pairOffsetTransitions = JSON.stringify(results);
});
</script>
"""
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")


@pytest.mark.integration
def test_pair_offsets_survive_same_source_slider_mode_repair(tmp_path: Path) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")
    report_path = _generated_report(tmp_path)
    _append_pair_offset_mode_transition_probe(report_path)
    completed = _run_browser_dump(browser, report_path, width=1024, height=768)
    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)
    assert parser.document_attributes is not None
    encoded = parser.document_attributes.get("data-pair-offset-transitions")
    assert encoded is not None, parser.document_attributes
    cases = json.loads(encoded)
    assert len(cases) == 8
    for case in cases:
        expected = {
            "alignmentPreset": "custom" if case["savedOffset"] else "none",
            "alignX": 7 if case["savedOffset"] else 0,
            "alignY": 3 if case["savedOffset"] else 0,
        }
        assert case["pair"] == "0:1", case
        assert case["current"] == expected, case
        assert case["restored"] == expected, case
        assert case["stored"] == (expected if case["savedOffset"] else None), case
        assert case["storedSameSource"] == (
            {"alignmentPreset": "custom", "alignX": 2, "alignY": 2}
            if case["sameSourceOffset"]
            else None
        ), case
        assert case["x"] == f"{expected['alignX']}px", case
        assert case["y"] == f"{expected['alignY']}px", case
        assert case["status"] == (
            "Offset: custom +7x +3y" if case["savedOffset"] else "Offset: none"
        ), case
        if case["mode"] == "diff":
            assert case["transform"] == (
                "matrix(1, 0, 0, 1, 7, 3)" if case["savedOffset"] else "matrix(1, 0, 0, 1, 0, 0)"
            ), case


def _append_width_fit_restore_probe(report_path: Path) -> None:
    """Prove the removed Fit width control, its restored-state fallback, and H.

    The floating palette exposes only actual-size and fit-height radios, but a
    returning viewer's saved `fitMode: 'width'` must still compute a real zoom
    and leave the fit radio group keyboard reachable even though neither
    visible radio is checked. The H shortcut must still toggle the renamed
    source-labels control in both directions.
    """
    html = report_path.read_text(encoding="utf-8")
    probe = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    const fitButtons = Array.from(document.querySelectorAll('[data-fit]'));
    document.documentElement.dataset.fitWidthButtonAbsent = String(
        fitButtons.length === 2
        && fitButtons.every(btn => btn.dataset.fit !== 'width')
        && Boolean(document.getElementById('btn-palette-orientation'))
    );

    localStorage.setItem(
        ReportViewer.viewerStorageKey(),
        JSON.stringify({ fitMode: 'width' }),
    );
    ReportViewer.restorePersistedState();
    ReportViewer.viewport.applyFitMode({ resetPan: true });
    ReportViewer.viewport.updateFitButtons();

    const zoomAfterRestore = ReportViewer.state.zoom;
    const checkedStates = fitButtons.map(btn => btn.getAttribute('aria-checked'));
    const tabIndexes = fitButtons.map(btn => btn.tabIndex);
    const reachableButton = fitButtons[tabIndexes.indexOf(0)];
    reachableButton?.focus();
    document.documentElement.dataset.restoredWidthFitState = String(
        ReportViewer.state.fitMode === 'width'
        && Number.isFinite(zoomAfterRestore)
        && zoomAfterRestore > 0
        && checkedStates.every(state => state === 'false')
        && tabIndexes.filter(value => value === 0).length === 1
        && document.activeElement === reachableButton
    );

    const btnOverlays = document.getElementById('btn-overlays');
    const startedHidden = ReportViewer.state.overlaysHidden;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'h', bubbles: true }));
    const firstPressHidLabels = ReportViewer.state.overlaysHidden === !startedHidden
        && btnOverlays?.getAttribute('aria-label') === 'Show source labels'
        && btnOverlays?.getAttribute('title') === 'Show source labels (H)';
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'H', bubbles: true }));
    const secondPressRestoredLabels = ReportViewer.state.overlaysHidden === startedHidden
        && btnOverlays?.getAttribute('aria-label') === 'Hide source labels'
        && btnOverlays?.getAttribute('title') === 'Hide source labels (H)';
    document.documentElement.dataset.hShortcutTogglesSourceLabels = String(
        firstPressHidLabels && secondPressRestoredLabels
    );
});
</script>
"""
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")


def _append_saved_fit_mode_init_probe(report_path: Path, fit_mode: str) -> None:
    """Seed a saved fit mode before initialization and record the fit radios after it."""
    html = report_path.read_text(encoding="utf-8")
    probe = f"""
<script>
const savedFitReportId = JSON.parse(document.getElementById('report-data').textContent).report_id;
localStorage.setItem(
    `frame-compare:report-viewer:${{savedFitReportId}}:viewport-v2`,
    JSON.stringify({{ fitMode: '{fit_mode}' }}),
);
document.addEventListener('DOMContentLoaded', () => {{
    const fitButtons = Array.from(document.querySelectorAll('[data-fit]'));
    document.documentElement.dataset.savedFitState = JSON.stringify({{
        fitMode: ReportViewer.state.fitMode,
        checked: fitButtons.map(btn => [btn.dataset.fit, btn.getAttribute('aria-checked')]),
        tabStops: fitButtons.filter(btn => btn.tabIndex === 0).length,
    }});
}});
</script>
"""
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")


@pytest.mark.integration
@pytest.mark.parametrize(
    ("fit_mode", "expected_checked"),
    [
        ("height", [["actual", "false"], ["height", "true"]]),
        ("width", [["actual", "false"], ["height", "false"]]),
    ],
)
def test_saved_fit_mode_is_reflected_by_fit_radios_on_page_load(
    tmp_path: Path, fit_mode: str, expected_checked: list[list[str]]
) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")
    report_path = _generated_report(tmp_path)
    _append_saved_fit_mode_init_probe(report_path, fit_mode)
    completed = _run_browser_dump(browser, report_path, width=1024, height=768)
    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)
    assert parser.document_attributes is not None
    saved_fit_state = parser.document_attributes["data-saved-fit-state"]
    assert saved_fit_state is not None
    state = json.loads(saved_fit_state)
    assert state == {"fitMode": fit_mode, "checked": expected_checked, "tabStops": 1}


@pytest.mark.integration
def test_report_omits_fit_width_keeps_restored_state_reachable_and_h_toggles_labels(
    tmp_path: Path,
) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")
    report_path = _generated_report(tmp_path)
    _append_width_fit_restore_probe(report_path)
    completed = _run_browser_dump(browser, report_path, width=1024, height=768)
    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)
    assert parser.document_attributes is not None
    assert parser.document_attributes["data-fit-width-button-absent"] == "true"
    assert parser.document_attributes["data-restored-width-fit-state"] == "true"
    assert parser.document_attributes["data-h-shortcut-toggles-source-labels"] == "true"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("width", "height", "scale"),
    [
        (375, 800, 1.0),
        (768, 720, 1.0),
        (900, 720, 1.0),
        (1024, 768, 1.0),
        (1366, 768, 1.0),
        (1920, 1080, 1.0),
        (3440, 1440, 1.0),
        (1920, 1080, 1.25),
        (1920, 1080, 1.5),
    ],
)
def test_generated_report_initializes_observable_mode_and_aria_state(
    tmp_path: Path,
    width: int,
    height: int,
    scale: float,
) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")

    report_path = _generated_report(tmp_path)
    _append_screenshot_load_probe(report_path)
    completed = _run_browser_dump(browser, report_path, width=width, height=height, scale=scale)

    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)

    assert 'src="screenshots/reference/10.png"' in completed.stdout
    assert parser.document_attributes is not None
    assert parser.document_attributes["data-sibling-screenshot-loaded"] == "true"
    assert parser.document_attributes["data-select-affordances"] == "true"
    assert parser.document_attributes["data-filmstrip-image-space"] == "true"
    assert parser.document_attributes["data-source-hud-viewport-stable"] == "true"
    assert parser.document_attributes["data-source-hud-wraps"] == "true"
    assert parser.document_attributes["data-diff-source-hud-visible"] == "true"
    assert parser.document_attributes["data-diff-huds-separate"] == "true"
    assert parser.document_attributes["data-hud-styles-aligned"] == "true"
    assert parser.document_attributes["data-hud-toggle-hides-both"] == "true"
    hud_accessibility = {
        name: parser.document_attributes[f"data-{name.replace('_', '-')}"]
        for name in (
            "stage_hud_accessible",
            "grid_hud_accessible",
            "grid_hud_hidden",
            "grid_hud_restored",
        )
    }
    assert parser.document_attributes["data-source-hud-accessible"] == "true", hud_accessibility
    assert parser.document_attributes["data-slider-labels-separate"] == "true"
    assert parser.document_attributes["data-palette-bottom-anchored"] == "true"
    assert parser.document_attributes["data-bottom-huds-separate"] == "true"
    assert parser.document_attributes["data-slider-labels-top-anchored"] == "true", (
        parser.document_attributes["data-slider-label-geometry"]
    )
    assert parser.document_attributes["data-slider-labels-contained"] == "true"
    assert parser.document_attributes["data-mode-center-stable"] == "true", (
        parser.document_attributes["data-toolbar-geometry"]
    )
    assert parser.document_attributes["data-toolbar-height-stable"] == "true", (
        parser.document_attributes["data-toolbar-geometry"]
    )
    assert parser.document_attributes["data-toolbar-zones-separate"] == "true", (
        parser.document_attributes["data-toolbar-geometry"]
    )
    assert parser.document_attributes["data-toolbar-anchors"] == "true", parser.document_attributes[
        "data-toolbar-geometry"
    ]
    assert parser.document_attributes["data-inspector-hud-anchored"] == "true"
    assert parser.document_attributes["data-inspector-width-policy"] == "true"
    assert parser.document_attributes["data-inspector-overflow-safe"] == "true"
    assert parser.document_attributes["data-inspector-identity-complete"] == "true"
    assert parser.document_attributes["data-info-modal-overflow-safe"] == "true"
    assert parser.document_attributes["data-info-modal-identity-complete"] == "true"
    assert parser.document_attributes["data-info-modal-width-policy"] == "true"
    assert parser.document_attributes["data-info-modal-focus-restored"] == "true"
    assert parser.document_attributes["data-info-inspector-semantics-stable"] == "true"
    assert parser.document_attributes["data-visible-inspector-behavior"] == "true"
    assert parser.document_attributes["data-filmstrip-hud-anchored"] == "true"
    assert parser.document_attributes["data-narrow-palette-horizontal"] == "true"
    assert parser.document_attributes["data-grid-hud-anchored"] == "true"
    assert parser.document_attributes["data-source-hud-text"] == (
        f"{_REFERENCE_RELEASE} · 1920×1080 · {_FIXTURE_SIZE_LABEL}"
    )
    assert parser.document_attributes["data-clips-metadata"] == "true"
    assert parser.document_attributes["data-review-tab-usable"] == "true", (
        parser.document_attributes.get("data-review-tab-error")
    )
    assert parser.document_attributes["data-rendering-disclosure"] == "true"
    assert parser.document_attributes["data-no-horizontal-overflow"] == "true"
    source_rows = json.loads(parser.document_attributes["data-frame-source-rows"] or "{}")
    assert source_rows["overlay"] == ["PMTP DVShown10 / 20B", "ATV HDR1012 / 20B"]
    assert source_rows["slider"] == [
        "PMTP DVShown left10 / 20B",
        "ATV HDR10Shown right12 / 20B",
    ]
    assert source_rows["diff"] == source_rows["slider"]
    assert source_rows["blink"] == source_rows["slider"]
    expected_grid_rows = (
        ["PMTP DVShown10 / 20B", "ATV HDR1012 / 20B"]
        if width <= 768
        else ["PMTP DVShown10 / 20B", "ATV HDR10Shown12 / 20B"]
    )
    assert source_rows["grid"] == expected_grid_rows
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


@pytest.mark.integration
def test_blink_keeps_failed_image_retry_focused_across_timer_tick(tmp_path: Path) -> None:
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable; CI preflight makes this a required proof")
    report_path = _generated_report(tmp_path)
    # A real missing sibling resource drives the viewer's image error path.
    (tmp_path / "screenshots" / "encode" / "10.png").unlink()
    html = report_path.read_text(encoding="utf-8")
    probe = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    const root = document.documentElement;
    const waitFor = (predicate, callback, remaining = 100) => {
        if (predicate()) callback();
        else if (remaining > 0) setTimeout(() => waitFor(predicate, callback, remaining - 1), 20);
        else {
            const request = ReportViewer.state.mainImageRequests.right;
            root.dataset.blinkRetryError = JSON.stringify({
                attempt: request?.attempt,
                status: request?.status,
                src: request?.image.getAttribute('src'),
                token: request?.token,
                currentToken: ReportViewer.state.imageRequestToken,
            });
        }
    };
    ReportViewer.setMode('blink');
    ReportViewer.setBlinkIntervalMs(300);
    ReportViewer.setBlinkPaused(false);
    waitFor(() => ReportViewer.state.mainImageRequests.right?.status === 'error', () => {
        const button = document.querySelector('[data-empty-state] button');
        if (!button) { root.dataset.blinkRetryError = 'Missing Retry'; return; }
        button.focus();
        const token = ReportViewer.state.imageRequestToken;
        let mutations = 0;
        const observer = new MutationObserver(records => { mutations += records.length; });
        observer.observe(ReportViewer.dom.status, { childList: true, characterData: true, subtree: true });
        waitFor(() => ReportViewer.state.imageRequestToken > token, () => {
            // Pause after a real interval tick so retry observation cannot race another tick.
            ReportViewer.setBlinkPaused(true);
            root.dataset.blinkRetryFocus = String(
                document.activeElement === button && button.isConnected
                && document.querySelector('[data-empty-state] button') === button
            );
            setTimeout(() => {
                observer.disconnect();
                root.dataset.blinkRetryQuiet = String(mutations === 0);
                button.click();
                waitFor(() => ReportViewer.state.mainImageRequests.right?.attempt === 1
                    && ReportViewer.state.mainImageRequests.right?.status === 'error', () => {
                    root.dataset.blinkRetryCurrent = 'true';
                });
            }, 0);
        });
    });
});
</script>
"""
    report_path.write_text(html.replace("</body>", f"{probe}</body>"), encoding="utf-8")
    completed = _run_browser_dump(browser, report_path, width=1024, height=768)
    parser = _InitializedViewerParser()
    parser.feed(completed.stdout)
    assert parser.document_attributes is not None
    for attribute in (
        "data-blink-retry-focus",
        "data-blink-retry-quiet",
        "data-blink-retry-current",
    ):
        assert parser.document_attributes.get(attribute) == "true", parser.document_attributes


def _run_browser_input(
    browser: str,
    report_path: Path,
    profile: Path,
    script: str,
    *,
    timeout: float = 40,
) -> subprocess.CompletedProcess[str]:
    """Own Chrome independently of Node, including helper timeout/failure cleanup."""
    from nodejs_wheel import node

    chrome = subprocess.Popen(
        [
            browser,
            "--headless=new",
            "--test-type",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-gpu",
            "--no-first-run",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
            report_path.as_uri(),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        return cast(
            subprocess.CompletedProcess[str],
            node(
                ["-e", script, report_path.as_uri(), str(profile)],
                return_completed_process=True,
                capture_output=True,
                encoding="utf-8",
                check=False,
                timeout=timeout,
            ),
        )
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=2)
        except subprocess.TimeoutExpired:
            chrome.kill()
            chrome.wait(timeout=5)


@pytest.mark.integration
def test_review_note_native_insertion_uses_unicode_scalar_limit(tmp_path: Path) -> None:
    """CDP input enters through Chrome editing, including trusted input events."""
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable")
    report_path = _generated_report(tmp_path)
    script = _viewer_input_script(r"""
        await evaluate(`(() => {
            ReportViewer.inspector.setOpen(true, { save: false });
            ReportViewer.inspector.setTab('review', { save: false });
            globalThis.note = document.querySelector('[data-review-note]');
            globalThis.trustedInputs = 0;
            note.addEventListener('input', event => { if (event.isTrusted) trustedInputs += 1; });
            note.focus();
        })()`);
        for (const prefix of ['a'.repeat(999), '😀'.repeat(999), 'a😀'.repeat(499) + 'é']) {
            // Select existing text and replace it through the browser input pipeline.
            await evaluate('note.focus(); note.select();');
            await command('Input.insertText', { text: prefix });
            assert.equal(await evaluate('note.value'), prefix);
            assert.equal(await evaluate('document.activeElement === note'), true);
            await command('Input.insertText', { text: '🚀xy' });
            const expected = prefix + '🚀';
            assert.equal(await evaluate('note.value'), expected);
            assert.equal(await evaluate("document.querySelector('[data-review-note-count]').textContent"), '1000 / 1000');
            assert.equal(await evaluate('note.selectionStart === note.value.length && note.selectionEnd === note.value.length'), true);
            const exported = JSON.parse(await evaluate('ReportViewer.reviewController.model.exportText()'));
            assert.equal(exported.reviews[0].note, expected);
            // An edit inside the note must keep its selection while below the bound.
            await evaluate('note.setSelectionRange(0, note.value.length);');
            await command('Input.insertText', { text: 'left😀right' });
            await evaluate('note.setSelectionRange(4, 6);');
            await command('Input.insertText', { text: 'é' });
            assert.equal(await evaluate('note.value'), 'leftéright');
            assert.equal(await evaluate('note.selectionStart'), 5);
            assert.equal(await evaluate('document.activeElement === note'), true);
        }
        assert.equal(await evaluate('trustedInputs'), 12);
        for (let attempt = 0; attempt < 100; attempt += 1) {
            if (!await evaluate('ReportViewer.reviewController.model.status().unsaved')) break;
            await pause();
        }
        assert.equal(await evaluate('ReportViewer.reviewController.model.status().unsaved'), false);
        assert.equal(await evaluate('JSON.parse(localStorage.getItem(ReportViewer.reviewController.model.storageKey)).reviews[0].note'), 'leftéright');
        assert.match(await evaluate("document.querySelector('[data-review-status]').textContent"), /saved in this browser/);
        console.log('Native BMP, supplementary, mixed, bounds, selection, focus and export passed');
""")
    result = _run_browser_input(browser, report_path, tmp_path / "chrome-input-profile", script)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Native BMP, supplementary, mixed" in result.stdout


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["timeout", "command"])
def test_browser_input_cleanup_survives_helper_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """A real Chrome process is reaped even when subprocess.run kills Node."""
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable")
    processes: list[subprocess.Popen[Any]] = []
    original_popen = subprocess.Popen

    def track_process(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        process = original_popen(*args, **kwargs)
        if args[0][0] == browser:
            processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", track_process)
    report_path = tmp_path / "report.html"
    report_path.write_text("<html></html>", encoding="utf-8")
    script = r"""
const fs = require('node:fs/promises');
const path = require('node:path');
const profile = process.argv[2];
(async () => {
    for (let attempt = 0; attempt < 100; attempt += 1) {
        try {
            await fs.readFile(path.join(profile, 'DevToolsActivePort'));
            console.log('Chrome ready');
            FAILURE
            return;
        } catch (error) {
            if (error.code !== 'ENOENT') throw error;
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
    throw new Error('Chrome never became ready');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    script = script.replace(
        "FAILURE",
        "setInterval(() => {}, 1000);"
        if failure == "timeout"
        else "throw new Error('CDP failed');",
    )
    if failure == "timeout":
        with pytest.raises(subprocess.TimeoutExpired) as raised:
            _run_browser_input(browser, report_path, tmp_path / "profile", script, timeout=4)
        assert "Chrome ready" in str(raised.value.output)
    else:
        result = _run_browser_input(browser, report_path, tmp_path / "profile", script)
        assert result.returncode != 0
        assert "Chrome ready" in result.stdout
        assert "CDP failed" in result.stderr
    assert len(processes) == 1
    assert processes[0].poll() is not None
    assert processes[0].wait(timeout=0) == processes[0].returncode


@pytest.mark.integration
def test_review_tabs_preserve_saved_notes_and_local_drafts(tmp_path: Path) -> None:
    """Same-file tabs serialize writes and retain conflicts through the real editor."""
    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable")
    report_path = _generated_report(tmp_path, frames=(10, 11))
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const [report, profile] = process.argv.slice(1);
const pause = () => new Promise(resolve => setTimeout(resolve, 30));
const sessions = [];
async function connect(target, waitForViewer = true) {
    const socket = new WebSocket(target.webSocketDebuggerUrl);
    let nextId = 0;
    const pending = new Map();
    await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(Error('socket timeout')), 5000);
        socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
        socket.addEventListener('error', error => { clearTimeout(timer); reject(error); }, { once: true });
    });
    socket.addEventListener('message', event => {
        const message = JSON.parse(event.data);
        const request = pending.get(message.id);
        if (!request) return;
        pending.delete(message.id);
        clearTimeout(request.timer);
        if (message.error) request.reject(Error(JSON.stringify(message.error)));
        else request.resolve(message.result);
    });
    const command = (method, params = {}) => new Promise((resolve, reject) => {
        const id = ++nextId;
        const timer = setTimeout(() => { pending.delete(id); reject(Error(method + ' timeout: ' + (params.expression || ''))); }, 5000);
        pending.set(id, { resolve, reject, timer });
        socket.send(JSON.stringify({ id, method, params }));
    });
    const evaluate = async expression => {
        const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
        assert.equal(result.exceptionDetails, undefined, JSON.stringify(result.exceptionDetails));
        return result.result.value;
    };
    const session = { command, evaluate, close: () => socket.close() };
    sessions.push(session);
    if (waitForViewer) await until(session, "typeof ReportViewer !== 'undefined' && Boolean(ReportViewer.inspector)");
    return session;
}
async function until(session, expression) {
    for (let attempt = 0; attempt < 150; attempt += 1) {
        if (await session.evaluate(expression)) return;
        await pause();
    }
    throw Error('Timed out: ' + expression + ' state: ' + await session.evaluate('JSON.stringify({status: globalThis.model?.status(), records: globalThis.model?.all(), stored: globalThis.model && localStorage.getItem(model.storageKey)})'));
}
const initialize = `
    ReportViewer.inspector.setOpen(true, { save: false });
    ReportViewer.inspector.setTab('review', { save: false });
    globalThis.model = ReportViewer.reviewController.model;
    globalThis.note = document.querySelector('[data-review-note]');
    globalThis.trustedInputs = 0;
    note.addEventListener('input', event => { if (event.isTrusted) trustedInputs += 1; });
`;
const stored = 'JSON.parse(localStorage.getItem(model.storageKey))?.reviews || []';
async function edit(session, frame, text) {
    await session.evaluate(`ReportViewer.setFrame(${frame}); note.focus(); note.select();`);
    await session.command('Input.insertText', { text });
    assert.equal(await session.evaluate('document.activeElement === note'), true);
    assert.equal(await session.evaluate('note.value'), text);
}
(async () => {
    try {
        let port;
        for (let attempt = 0; attempt < 100; attempt += 1) {
            try {
                port = (await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0];
                break;
            } catch { await pause(); }
        }
        assert.ok(port, 'Chrome did not expose a debugging port');
        const request = async (uri, method = 'GET') => (await fetch(`http://127.0.0.1:${port}${uri}`, {
            method, signal: AbortSignal.timeout(5000),
        })).json();
        const open = async (withoutLocks = false) => {
            const session = await connect(await request('/json/new?' + encodeURIComponent(withoutLocks ? 'about:blank' : report), 'PUT'), !withoutLocks);
            if (withoutLocks) {
                await session.command('Page.enable');
                await session.command('Page.addScriptToEvaluateOnNewDocument', {
                    source: "Object.defineProperty(navigator, 'locks', { value: undefined })",
                });
                await session.command('Page.navigate', { url: report });
                await until(session, "typeof ReportViewer !== 'undefined' && Boolean(ReportViewer.inspector)");
            }
            await session.evaluate(initialize);
            return session;
        };
        const a = await open();
        const b = await open();
        assert.equal(await a.evaluate("typeof navigator.locks.request"), 'function');
        await edit(a, 0, 'Saved A 😀');
        await until(a, '!model.status().unsaved');
        await edit(b, 1, 'Draft B é');
        await until(b, 'model.status().warning.includes("another tab")');
        assert.deepEqual((await b.evaluate(stored)).map(row => row.note), ['Saved A 😀']);
        assert.equal(await b.evaluate('model.get(1).note'), 'Draft B é');
        assert.match(await b.evaluate("document.querySelector('[data-review-status]').textContent"), /another tab/);
        await edit(b, 0, 'Same-frame draft');
        assert.deepEqual((await b.evaluate(stored)).map(row => row.note), ['Saved A 😀']);
        assert.equal(await b.evaluate('JSON.parse(model.exportText()).reviews[0].note'), 'Same-frame draft');
        const fresh = await open();
        assert.equal(await fresh.evaluate('model.get(0).note'), 'Saved A 😀');
        assert.equal(await fresh.evaluate('model.get(1).note'), '');

        // External deletion invalidates both Merge and Replace previews, including Apply.
        for (const mode of ['merge', 'replace']) {
            const importer = await open();
            const deleter = await open();
            await importer.evaluate(`(() => {
                const incoming = JSON.parse(model.exportText());
                incoming.reviews = [{ frame_ordinal: 1, bookmark: true, tag: null, note: 'imported', preferred_clip_id: null }];
                const transfer = new DataTransfer();
                transfer.items.add(new File([JSON.stringify(incoming)], 'review.json', { type: 'application/json' }));
                const input = document.querySelector('[data-review-import]');
                input.files = transfer.files;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            })()`);
            await until(importer, "!document.querySelector('[data-review-preview]').hidden");
            await importer.evaluate(`document.querySelector('input[name="review-import-mode"][value="${mode}"]').click()`);
            await edit(deleter, 0, '');
            await until(deleter, '!model.status().unsaved');
            await until(importer, 'model.status().warning.includes("another tab")');
            await importer.evaluate("document.querySelector('[data-review-import-apply]').click()");
            assert.deepEqual(await importer.evaluate(stored), []);
            assert.equal(await importer.evaluate('model.get(0).note'), 'Saved A 😀');
            await edit(importer, 1, 'Draft after deletion');
            assert.deepEqual(await importer.evaluate(stored), []);
            // Restore through a fresh snapshot for the next independent import mode.
            const restore = await open();
            await edit(restore, 0, 'Saved A 😀');
            await until(restore, '!model.status().unsaved');
        }

        // Hold the actual browser lock, then enqueue writes from both tabs.
        const owner = await open();
        await owner.evaluate('localStorage.removeItem(model.storageKey)');
        const left = await open();
        const right = await open();
        const hold = async () => {
            await owner.evaluate(`globalThis.lockHeld = false;
                globalThis.holding = navigator.locks.request(model.storageKey, () => new Promise(resolve => {
                    globalThis.releaseLock = resolve; globalThis.lockHeld = true;
                })); void 0;`);
            await until(owner, 'lockHeld');
        };
        await hold();
        await edit(left, 0, 'first queued');
        await edit(left, 0, 'latest queued 😀');
        await edit(right, 1, 'simultaneous draft');
        assert.equal(await left.evaluate('model.status().unsaved'), true);
        assert.equal(await right.evaluate('model.status().unsaved'), true);
        assert.deepEqual(await left.evaluate(stored), []);
        await owner.evaluate('releaseLock(); void 0;');
        for (const session of [left, right]) {
            await until(session, '!model.status().unsaved || model.status().warning.includes("another tab")');
        }
        const saved = await left.evaluate(stored);
        assert.equal(saved.length, 1);
        assert.ok(['latest queued 😀', 'simultaneous draft'].includes(saved[0].note));
        assert.equal(await left.evaluate('model.status().unsaved'), saved[0].note !== 'latest queued 😀');
        assert.equal(await right.evaluate('model.status().unsaved'), saved[0].note !== 'simultaneous draft');
        assert.equal(await right.evaluate('model.get(1).note'), 'simultaneous draft');
        assert.equal(await left.evaluate('note.selectionStart === note.value.length && document.activeElement === note'), true);

        console.log('Cross-tab conflicts, deletes, stale imports and queued writes passed');
        const memory = await open(true);
        assert.equal(await memory.evaluate('typeof navigator.locks'), 'undefined');
        const durable = await memory.evaluate('localStorage.getItem(model.storageKey)');
        await edit(memory, 1, 'exportable without locks');
        assert.equal(await memory.evaluate('model.status().memoryOnly'), true);
        assert.match(await memory.evaluate("document.querySelector('[data-review-status]').textContent"), /only for this session/);
        assert.equal(await memory.evaluate('localStorage.getItem(model.storageKey)'), durable);
        assert.equal(await memory.evaluate('JSON.parse(model.exportText()).reviews.find(row => row.frame_ordinal === 1).note'), 'exportable without locks');
        assert.equal(await left.evaluate('trustedInputs'), 2);
        assert.equal(await right.evaluate('trustedInputs'), 1);
        console.log('Real two-tab conflicts, deletions, stale Merge/Replace Apply, queued writes, drafts and missing-lock export passed');
    } finally {
        for (const session of sessions) session.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = _run_browser_input(browser, report_path, tmp_path / "chrome-tabs-profile", script)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Real two-tab conflicts" in result.stdout


def _viewer_input_script(actions: str) -> str:
    """Use the trusted-input CDP driver for loaded-viewer assertions."""
    return (
        r"""
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const [report, profile] = process.argv.slice(1);
let socket;
let nextId = 0;
const pending = new Map();
const pause = () => new Promise(resolve => setTimeout(resolve, 100));
async function command(method, params = {}) {
    const id = ++nextId;
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            pending.delete(id);
            reject(new Error(`CDP ${method} timed out`));
        }, 5000);
        pending.set(id, { resolve, reject, timer });
        socket.send(JSON.stringify({ id, method, params }));
    });
}
async function evaluate(expression) {
    const result = await command('Runtime.evaluate', { expression, returnByValue: true });
    assert.equal(result.exceptionDetails, undefined, JSON.stringify(result.exceptionDetails));
    return result.result.value;
}
(async () => {
    try {
        let port;
        for (let attempt = 0; attempt < 100; attempt += 1) {
            try {
                port = (await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0];
                break;
            } catch { await pause(); }
        }
        assert.ok(port, 'Chrome did not expose a debugging port');
        const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`, {
            signal: AbortSignal.timeout(5000),
        })).json();
        const target = targets.find(target => target.type === 'page' && target.url === report);
        assert.ok(target, 'generated report page is missing');
        socket = new WebSocket(target.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('CDP socket timed out')), 5000);
            socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
            socket.addEventListener('error', error => { clearTimeout(timer); reject(error); }, { once: true });
        });
        socket.addEventListener('message', event => {
            const message = JSON.parse(event.data);
            const request = pending.get(message.id);
            if (!request) return;
            pending.delete(message.id);
            clearTimeout(request.timer);
            if (message.error) request.reject(new Error(JSON.stringify(message.error)));
            else request.resolve(message.result);
        });
        let initialized = false;
        for (let attempt = 0; attempt < 100; attempt += 1) {
            initialized = await evaluate("typeof ReportViewer !== 'undefined' && Boolean(ReportViewer.inspector)");
            if (initialized) break;
            await pause();
        }
        assert.ok(initialized, 'viewer did not initialize');

"""
        + actions
        + r"""
    } finally {
        socket?.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    )


@pytest.mark.integration
@pytest.mark.parametrize(("source_width", "window_width"), [(1920, 1024), (3840, 640)])
def test_report_actual_pixels_fit_and_diff_lens_share_coordinates(
    tmp_path: Path, source_width: int, window_width: int
) -> None:
    from PIL import Image, ImageDraw

    browser = _browser_executable()
    if browser is None:
        pytest.skip("Chrome/Chromium is unavailable")
    report_path = _generated_report(tmp_path)
    for name, width in [("reference", source_width), ("encode", source_width // 2)]:
        image = Image.new("RGB", (width, width * 9 // 16), "black")
        ImageDraw.Draw(image).rectangle((int(width * 0.5125), 0, width, image.height), fill="white")
        image.save(tmp_path / "screenshots" / name / "10.png")
    script = _viewer_input_script(
        r"""
        await command('Emulation.setDeviceMetricsOverride', {
            width: WINDOW_WIDTH, height: 768, deviceScaleFactor: 1, mobile: false,
        });
        for (let attempt = 0; attempt < 100; attempt += 1) {
            if (await evaluate('ReportViewer.dom.leftImg.naturalWidth === SOURCE_WIDTH')) break;
            await pause();
        }
        const proof = await evaluate(`(() => {
            const viewer = ReportViewer;
            viewer.viewport.setFitMode('actual');
            const actualWidth = viewer.dom.leftImg.getBoundingClientRect().width;
            viewer.viewport.setFitMode('width');
            const fitZoom = viewer.state.zoom;
            const fitWidth = viewer.dom.leftImg.getBoundingClientRect().width;
            viewer.viewport.zoomAtPoint(320, 300, 1.1);
            const zoomed = viewer.state.zoom;
            viewer.viewport.setFitMode('actual');
            viewer.lens.setEnabled(true);
            return {actualWidth, fitZoom, fitWidth, zoomed, stageWidth: viewer.dom.stage.clientWidth};
        })()`);
        proof.cases = [];
        for (const offset of [0, 1]) {
            await evaluate(`ReportViewer.viewport.setManualAlignment(${offset}, 0)`);
            await pause();
            proof.cases.push(await evaluate(`(() => {
                ReportViewer.lens.refresh();
                const left = ReportViewer.dom.leftImg.getBoundingClientRect();
                const right = ReportViewer.dom.rightImg.getBoundingClientRect();
                const active = document.querySelector('[data-lens-image="active"]').getBoundingClientRect();
                const difference = document.querySelector('[data-lens-image="difference"]').getBoundingClientRect();
                return {
                    offset: ${offset},
                    mainSeparation: right.left + right.width * 0.5125 - left.left - left.width * 0.5125,
                    lensSeparation: difference.left + difference.width * 0.5125 - active.left - active.width * 0.5125,
                    lensWidth: active.width,
                };
            })()`));
        }
        console.log(JSON.stringify(proof));
""".replace("WINDOW_WIDTH", str(window_width)).replace("SOURCE_WIDTH", str(source_width))
    )
    completed = _run_browser_input(browser, report_path, tmp_path / "chrome-coordinates", script)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    proof = json.loads(completed.stdout)
    for case in proof["cases"]:
        assert case["mainSeparation"] == pytest.approx(case["offset"], abs=0.1), case
        assert case["lensSeparation"] == pytest.approx(case["offset"] * 4, abs=0.1), case
        assert case["lensWidth"] == source_width * 4, case
    assert proof["actualWidth"] == source_width, proof
    assert proof["fitWidth"] == pytest.approx(proof["stageWidth"], abs=1), proof
    if source_width == 3840:
        assert proof["fitZoom"] < 0.25, proof
    assert proof["zoomed"] > proof["fitZoom"], proof
