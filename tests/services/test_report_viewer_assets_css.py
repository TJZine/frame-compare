"""CSS asset contracts for the report viewer."""

from __future__ import annotations

import re

from frame_compare.services.report.viewer import get_css
from tests.services.report_viewer_contracts import css_block


def test_viewer_css_keeps_stage_pointer_and_label_contracts() -> None:
    css = get_css()
    alignment_transform_block = css_block(
        css, ".rv-right,\n.rv-mode-overlay .rv-left.rv-layer--aligned-active"
    )

    assert "color-scheme: dark;" in css
    assert ".rv-viewer-stage" in css
    assert "touch-action: none;" in css
    assert "cursor: grab;" in css
    assert "cursor: grabbing;" in css_block(css, ".rv-viewer-stage.is-panning")
    assert "display: none;" in css_block(css, ".rv-divider")
    assert "display: block;" in css_block(css, ".rv-mode-slider .rv-divider")
    assert ".rv-viewer-stage:fullscreen" in css
    assert "translate(var(--pan-x, 0px), var(--pan-y, 0px)) scale(var(--zoom-level, 1))" in css
    assert (
        "transform: translate(var(--align-x, 0px), var(--align-y, 0px));"
        in alignment_transform_block
    )
    assert ".rv-overlay-label:empty { display: none; }" in css
    assert "select option," in css
    assert "position: absolute;" in css_block(css, ".rv-stage-labels")
    assert "display: none;" in css_block(css, ".rv-mode-diff .rv-stage-labels")
    assert "left: var(--label-left-x, 50%);" in css_block(css, ".rv-mode-slider #label-left")
    assert "left: var(--label-right-x, 50%);" in css_block(css, ".rv-mode-slider #label-right")
    assert "position: absolute;" in css_block(css, ".rv-filmstrip-caption")


def test_viewer_css_keeps_hidden_state_and_empty_stage_regressions() -> None:
    css = get_css()

    assert "display: none;" in css_block(css, ".rv-control-group[hidden]")
    assert "display: none;" in css_block(css, ".rv-filmstrip-item[hidden]")
    assert "display: none !important;" in css_block(css, "[hidden]")
    assert "display: none;" in css_block(css, ".rv-empty-state[hidden]")
    assert ".rv-viewer-stage.rv-overlays-hidden .rv-overlay-label" in css
    assert ".rv-align-popover" in css
    assert '.rv-status[data-tone="error"]' in css
    assert '.rv-status[data-tone="warning"]' in css
    assert ".rv-modal-content--wide" in css
    assert ".rv-modal-actions" in css
    assert ".rv-zoom-value" in css


def test_viewer_css_covers_timeline_layout_contracts() -> None:
    css = get_css()

    assert ".rv-bottom-panel" in css
    assert ".rv-bottom-panel--collapsed .rv-filmstrip" in css
    assert "display: none;" in css_block(css, ".rv-bottom-panel--collapsed .rv-filmstrip")
    assert "justify-content: flex-end;" in css_block(
        css, ".rv-bottom-panel--collapsed .rv-bottom-panel-bar"
    )
    assert "margin-left: auto;" in css_block(
        css, ".rv-bottom-panel--collapsed .rv-filmstrip-controls"
    )
    assert "display: none;" in css_block(css, ".rv-bottom-panel--collapsed .rv-filter-group")
    assert "display: none;" in css_block(
        css, ".rv-bottom-panel--collapsed .rv-filmstrip-size-control"
    )
    assert "aspect-ratio: 16 / 10;" in css_block(css, ".rv-filmstrip-item")
    assert "object-fit: contain;" in css_block(css, ".rv-filmstrip-item img")
    assert "display: none;" not in css_block(
        css, ".rv-filmstrip-size-compact .rv-filmstrip-caption"
    )
    assert "display: none;" in css_block(css, ".rv-filmstrip-compact-label")
    assert "display: none;" in css_block(css, ".rv-filmstrip-size-compact .rv-filmstrip-label")
    assert "display: block;" in css_block(
        css, ".rv-filmstrip-size-compact .rv-filmstrip-compact-label"
    )


def test_viewer_css_keeps_mobile_palette_and_reduced_motion_contracts() -> None:
    css = get_css()
    vertical_palette_css = css_block(css, '.rv-viewport-palette[data-orientation="vertical"]')
    tablet_css = css_block(css, "@media (max-width: 992px)")
    mobile_css = css_block(css, "@media (max-width: 768px)")
    reduced_motion_css = css_block(css, "@media (prefers-reduced-motion: reduce)")

    assert ".rv-inspector" in css
    assert ".rv-inspector.open" in css
    assert "body.rv-inspector-open .rv-viewer-stage" in css
    assert ".rv-blink-status" in css
    assert "flex-direction: column;" in vertical_palette_css
    assert "flex-wrap: nowrap;" in vertical_palette_css
    assert "overflow-y: auto;" in vertical_palette_css
    for block in (tablet_css, mobile_css):
        assert ".rv-viewport-palette" in block
        assert ".rv-bottom-panel-bar" in block
        assert "body.rv-inspector-open .rv-viewer-stage" in block
        assert ".rv-inspector" in block
    assert "margin-right: 0;" in tablet_css
    assert "width: min(360px, 92vw);" in tablet_css
    assert "flex-direction: row !important;" in mobile_css
    assert "flex-wrap: wrap !important;" in mobile_css
    assert "#btn-palette-orientation" in mobile_css
    assert "display: none !important;" in mobile_css
    assert "transition: none !important;" in reduced_motion_css
    assert "animation-duration: 0.01ms !important;" in reduced_motion_css


def test_viewer_css_stays_offline_and_preserves_tokenized_regressions() -> None:
    css = get_css()

    urls = re.findall(r'url\([\'"]?([^\'")]+)[\'"]?\)', css)
    for url in urls:
        if url.startswith(("http://", "https://")):
            assert url.startswith(("http://www.w3.org/", "https://www.w3.org/"))

    assert "@import" not in css
    empty_palette_block = css_block(css, ".rv-viewer-stage--empty .rv-viewport-palette")
    assert "pointer-events: none" in empty_palette_block
    webkit_vertical_track = css_block(
        css,
        '.rv-viewport-palette[data-orientation="vertical"] #zoom-range::-webkit-slider-runnable-track',
    )
    moz_vertical_track = css_block(
        css,
        '.rv-viewport-palette[data-orientation="vertical"] #zoom-range::-moz-range-track',
    )
    assert "margin" not in webkit_vertical_track
    assert "margin" not in moz_vertical_track


def test_viewer_css_covers_pixel_inspector_roi_lens_and_tabs() -> None:
    css = get_css()
    roi = css_block(css, ".rv-inspection-point")
    tabs = css_block(css, ".rv-inspector-tabs")
    lens_image = css_block(css, ".rv-pixel-lens img")
    grid = css_block(css, '.rv-pixel-lens[data-magnification="8"]::after')
    coarse = css_block(css, "@media (pointer: coarse)")
    reduced_motion = css_block(css, "@media (prefers-reduced-motion: reduce)")

    assert "width: 44px;" in roi
    assert "height: 44px;" in roi
    assert "touch-action: none;" in roi
    assert "overflow-x: auto;" in tabs
    assert "display: flex;" in tabs
    assert '.rv-pixel-lens[data-magnification="2"]' in css
    assert '.rv-pixel-lens[data-magnification="4"]' in css
    assert '.rv-pixel-lens[data-magnification="8"]' in css
    assert "image-rendering: pixelated;" in lens_image
    assert "repeating-linear-gradient" in grid
    assert "background-position: 4px 4px;" in grid
    assert ".rv-pixel-lens" in coarse
    assert "display: none !important;" in coarse
    assert "#btn-inspect" in coarse
    assert "#pixel-lens-toggle" in coarse
    assert "[data-pixel-magnification]" in coarse
    assert ".rv-inspector-tabs button" in coarse
    assert "min-width: 44px;" in coarse
    assert "min-height: 44px;" in coarse
    assert ".rv-pixel-lens" in reduced_motion
    assert ".rv-inspection-point" in reduced_motion
