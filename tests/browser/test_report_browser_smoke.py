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

import pytest

from frame_compare.config.schema import OverlayMode, ReportConfig
from frame_compare.config.schema_enums import ViewerMode
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
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

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
_BROWSER_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
_MAC_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
_REFERENCE_LABEL = "Movie.Title.2026.2160p.WEB-DL.Service-GROUP.with-an-extremely-long-source-name-that-must-stay-on-the-left"
_COMPARISON_LABEL = "Movie.Title.2026.1080p.WEB-DL.Service-ENCODE.with-an-equally-long-source-name-that-must-stay-on-the-right"


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


def _generated_report(tmp_path: Path, *, tonemapped: bool = False) -> Path:
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
        screenshot = tmp_path / "screenshots" / name / "10.png"
        screenshot.parent.mkdir(parents=True)
        screenshot.write_bytes(_ONE_PIXEL_PNG)
        clips.append(
            ClipInfo(
                name=name,
                label=label,
                path=tmp_path / f"{name}.mkv",
                frame_count=20,
                resolution=(1920, 1080),
                fps=24.0,
                size_bytes=17 * 1024**3,
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
                tonemap_settings=TonemapSettings() if tonemapped else None,
                active_picture=geometry.active_picture,
                images=[
                    ReportImageInfo(
                        screenshot,
                        10 if name == "reference" else 12,
                        RenderedFrameFacts(10 if name == "reference" else 12, "B"),
                    )
                ],
            )
        )

    return generate_report(
        ReportData(
            clips=[replace(clip) for clip in clips],
            frames=[10],
            rendering=ReportRenderingInfo(
                overlay_mode=OverlayMode.DIAGNOSTIC,
                include_frame_number=True,
                tonemap_settings=TonemapSettings() if tonemapped else None,
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
        const palette = document.querySelector('.rv-viewport-palette');
        const rectanglesIntersect = (first, second) => !(
            first.right <= second.left
            || second.right <= first.left
            || first.bottom <= second.top
            || second.bottom <= first.top
        );
        ReportViewer.setMode('slider');
        ReportViewer.setMode('diff');
        document.documentElement.dataset.diffSourceHudVisible = String(
            window.getComputedStyle(label).display !== 'none'
            && window.getComputedStyle(rightLabel).display !== 'none'
            && label.textContent.startsWith('BASE:')
            && rightLabel.textContent.startsWith('COMPARE:')
        );
        document.documentElement.dataset.diffHudsSeparate = String(
            !rectanglesIntersect(label.getBoundingClientRect(), frameHud.getBoundingClientRect())
        );
        const sourceHudStyle = window.getComputedStyle(label);
        document.documentElement.dataset.hudStylesAligned = String(
            label.getBoundingClientRect().top === rightLabel.getBoundingClientRect().top
            && sourceHudStyle.borderRadius === window.getComputedStyle(rightLabel).borderRadius
        );
        ReportViewer.setOverlaysHidden(true, { save: false });
        document.documentElement.dataset.hudToggleHidesBoth = String(
            ReportViewer.dom.stage.classList.contains('rv-overlays-hidden')
            && frameHud !== null
        );
        ReportViewer.setOverlaysHidden(false, { save: false });

        ReportViewer.setMode('slider');
        const sliderLabelsSeparate = [0, 50, 100].every(revealPercent => {
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
        const stageRect = stage.getBoundingClientRect();
        const paletteRect = palette.getBoundingClientRect();
        const leftSliderLabel = document.getElementById('label-left').getBoundingClientRect();
        const rightSliderLabel = document.getElementById('label-right').getBoundingClientRect();
        const paletteInset = window.innerWidth <= 768 ? 8 : (window.innerWidth <= 992 ? 12 : 16);
        const labelInset = window.innerWidth <= 768 ? 8 : 12;
        const approximately = (first, second) => Math.abs(first - second) <= 1;
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
        ReportViewer.setInspectorOpen(true, { focus: false, save: false });
        const inspectorStageRect = stage.getBoundingClientRect();
        const inspectorPaletteRect = palette.getBoundingClientRect();
        document.documentElement.dataset.inspectorHudAnchored = String(
            inspectorStageRect.height > 0
            && inspectorPaletteRect.top >= inspectorStageRect.top
            && approximately(inspectorPaletteRect.bottom, inspectorStageRect.bottom - paletteInset)
            && approximately(inspectorPaletteRect.right, inspectorStageRect.right - paletteInset)
        );
        ReportViewer.setInspectorOpen(false, { focus: false, save: false });
        const infoButton = document.getElementById('btn-info');
        const infoBefore = {
            label: infoButton?.getAttribute('aria-label'),
            title: infoButton?.getAttribute('title'),
            pressed: infoButton?.getAttribute('aria-pressed'),
        };
        const inspectorFocusOrigin = infoButton;
        inspectorFocusOrigin?.focus();
        ReportViewer.setInspectorOpen(true, { save: false });
        ReportViewer.setInspectorOpen(false, { save: false });
        const infoAfter = {
            label: infoButton?.getAttribute('aria-label'),
            title: infoButton?.getAttribute('title'),
            pressed: infoButton?.getAttribute('aria-pressed'),
        };
        document.documentElement.dataset.infoInspectorSemanticsStable = String(
            infoBefore.label === 'Report information'
            && infoBefore.title === 'Report Info'
            && infoBefore.pressed === null
            && JSON.stringify(infoBefore) === JSON.stringify(infoAfter)
            && document.activeElement === inspectorFocusOrigin
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
        const expectedGridLabelCount = window.matchMedia('(max-width: 768px)').matches ? 1 : 2;
        document.documentElement.dataset.gridHudAnchored = String(
            window.getComputedStyle(document.querySelector('.rv-stage-labels')).display === 'none'
            && gridLabels.length === expectedGridLabelCount
            && gridLabels.every(gridLabel => gridLabel.textContent.trim().length > 0)
            && approximately(gridPaletteRect.bottom, gridStageRect.bottom - paletteInset)
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
        const sourceRowsByMode = {};
        ['overlay', 'slider', 'diff', 'blink', 'grid'].forEach(mode => {
            ReportViewer.setMode(mode);
            ReportViewer.setInspectorTab('frame');
            ReportViewer.updateInspectorData();
            sourceRowsByMode[mode] = Array.from(
                document.querySelectorAll('[data-inspector-source-frames] .rv-inspector-source')
            ).map(row => row.textContent.trim());
        });
        document.documentElement.dataset.frameSourceRows = JSON.stringify(sourceRowsByMode);
        ReportViewer.setInspectorTab('clips');
        ReportViewer.updateInspectorData();
        document.documentElement.dataset.clipsMetadata = String(
            document.querySelector('[data-inspector-clips]')?.textContent.includes('File size')
            && document.querySelector('[data-inspector-clips]')?.textContent.includes('Signal')
            && document.querySelector('[data-inspector-clips]')?.textContent.includes('Presentation')
            && !document.querySelector('[data-inspector-clips]')?.textContent.includes('Advanced tonemap')
        );
        document.documentElement.dataset.renderingDisclosure = String(
            document.querySelector('[data-rendering-tonemap-summary]')?.textContent === 'Not applied'
            && !document.querySelector('[data-rendering-details]')
        );
        document.documentElement.dataset.noHorizontalOverflow = String(
            document.documentElement.scrollWidth <= window.innerWidth
            && document.body.scrollWidth <= window.innerWidth
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


def _append_tonemap_disclosure_probe(report_path: Path) -> None:
    html = report_path.read_text(encoding="utf-8")
    probe = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    const disclosure = document.querySelector('[data-rendering-details]');
    const summary = disclosure?.querySelector('summary');
    const settings = disclosure?.querySelector('dl');
    const advancedLabels = [
        'Dynamic peak detection', 'Contrast recovery', 'Gamma lift', 'Source peak',
        'Destination minimum', 'Knee offset', 'Smoothing period', 'Percentile',
        'Scene threshold low', 'Scene threshold high', 'Gamut mapping',
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
        === 'Reference · BT.2390 · 100 nits'
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
    completed = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-gpu",
            "--no-first-run",
            "--virtual-time-budget=10000",
            "--window-size=375,240",
            "--dump-dom",
            report_path.as_uri(),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
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


@pytest.mark.integration
@pytest.mark.parametrize(
    ("width", "height"),
    [(375, 800), (768, 720), (900, 720), (1280, 720), (1366, 768), (1920, 1080)],
)
def test_generated_report_initializes_observable_mode_and_aria_state(
    tmp_path: Path,
    width: int,
    height: int,
) -> None:
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
            f"--window-size={width},{height}",
            "--dump-dom",
            report_path.as_uri(),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
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
    assert parser.document_attributes["data-palette-bottom-anchored"] == "true"
    assert parser.document_attributes["data-bottom-huds-separate"] == "true"
    assert parser.document_attributes["data-slider-labels-top-anchored"] == "true", (
        parser.document_attributes["data-slider-label-geometry"]
    )
    assert parser.document_attributes["data-slider-labels-contained"] == "true"
    assert parser.document_attributes["data-inspector-hud-anchored"] == "true"
    assert parser.document_attributes["data-info-inspector-semantics-stable"] == "true"
    assert parser.document_attributes["data-filmstrip-hud-anchored"] == "true"
    assert parser.document_attributes["data-narrow-palette-horizontal"] == "true"
    assert parser.document_attributes["data-grid-hud-anchored"] == "true"
    assert parser.document_attributes["data-source-hud-text"] == (
        f"{_REFERENCE_LABEL} • 1920×1080 • SDR"
    )
    assert parser.document_attributes["data-clips-metadata"] == "true"
    assert parser.document_attributes["data-rendering-disclosure"] == "true"
    assert parser.document_attributes["data-no-horizontal-overflow"] == "true"
    source_rows = json.loads(parser.document_attributes["data-frame-source-rows"] or "{}")
    assert source_rows["overlay"] == [f"{_REFERENCE_LABEL} — 10 / 20 · B-frame"]
    assert source_rows["slider"] == [
        f"{_REFERENCE_LABEL} — 10 / 20 · B-frame",
        f"{_COMPARISON_LABEL} — 12 / 20 · B-frame",
    ]
    assert source_rows["diff"] == source_rows["slider"]
    assert source_rows["blink"] == source_rows["slider"]
    expected_grid_rows = source_rows["slider"][:1] if width <= 768 else source_rows["slider"]
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
