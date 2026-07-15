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
    visually_hidden = css_block(css, ".rv-visually-hidden")

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
    assert "clip: rect(0 0 0 0) !important;" in visually_hidden
    assert "clip-path: inset(50%) !important;" in visually_hidden


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


def test_viewer_css_covers_production_lens_and_touch_controls() -> None:
    css = get_css()
    target = css_block(css, ".rv-lens-target")
    tabs = css_block(css, ".rv-inspector-tabs")
    lens = css_block(css, ".rv-lens {")
    lens_image = css_block(css, ".rv-lens-pane img")
    settings = css_block(css, ".rv-lens-settings")
    coarse = css_block(css, "@media (pointer: coarse)")
    reduced_motion = css_block(css, "@media (prefers-reduced-motion: reduce)")

    assert "width: 18px;" in target
    assert "var(--annotation)" in target
    assert "overflow-x: auto;" in tabs
    assert "display: flex;" in tabs
    assert "--lens-size: 240px;" in lens
    assert "touch-action: none;" in lens
    assert "image-rendering: pixelated;" in lens_image
    assert "mix-blend-mode: difference;" in css_block(
        css, '.rv-lens[data-render-mode="diff"] .rv-lens-image--difference'
    )
    assert "width: min(260px, calc(100vw - 24px));" in settings
    assert "overflow: auto;" in settings
    assert "overscroll-behavior: contain;" in settings
    assert '.rv-lens[data-comparison="true"] .rv-lens-pane--comparison' in css
    assert '.rv-lens[data-size="small"] #btn-lens-behavior' in css
    assert '.rv-lens[data-size="small"] .rv-lens-controls' in css
    assert "#btn-lens" in coarse
    assert ".rv-lens-controls button" in coarse
    assert "[data-lens-size]" in coarse
    assert "[data-lens-behavior]" in coarse
    assert "grid-template-columns: repeat(3, minmax(44px, 1fr));" in coarse
    assert "grid-template-columns: repeat(5, minmax(44px, 1fr));" not in coarse
    assert "#btn-lens-behavior" in coarse
    assert ".rv-inspector-tabs button" in coarse
    assert "min-width: 44px;" in coarse
    assert "min-height: 44px;" in coarse
    assert ".rv-lens" in reduced_motion
    assert ".rv-lens-target" in reduced_motion
    assert "display: none !important" not in coarse


def test_viewer_css_covers_dense_review_slate_and_accessible_states() -> None:
    css = get_css()
    assert ".rv-review-panel" in css
    assert ".rv-review-field textarea" in css
    assert '.rv-review-status[data-tone="warning"]' in css
    assert ".rv-review-preview fieldset" in css
    assert "var(--annotation)" in css_block(css, ".rv-review-frame")
    coarse = css_block(css, "@media (pointer: coarse)")
    for selector in (
        ".rv-review-field select",
        ".rv-review-transfer button",
        ".rv-review-preview button",
        ".rv-review-check",
        ".rv-review-preview label",
    ):
        assert selector in coarse
    assert coarse.count("min-height: 44px;") >= 3


def test_viewer_css_covers_deterministic_grid_and_mobile_cells() -> None:
    css = get_css()
    two = css_block(css, '.rv-grid[data-layout="two"] .rv-grid-cells')
    three_wide = css_block(css, '.rv-grid[data-layout="three-wide"] .rv-grid-cells')
    three_wrap = css_block(
        css,
        '.rv-grid[data-layout="three-wrap"] .rv-grid-cells,\n.rv-grid[data-layout="four"] .rv-grid-cells',
    )
    mobile = css_block(
        css,
        '.rv-grid[data-layout="single"] .rv-grid-cells,\n.rv-grid[data-layout="mobile"] .rv-grid-cells',
    )
    image = css_block(css, ".rv-grid-image")
    coarse = css_block(css, "@media (pointer: coarse)")

    assert "repeat(2, minmax(0, 1fr))" in two
    assert "repeat(3, minmax(0, 1fr))" in three_wide
    assert "repeat(2, minmax(0, 1fr))" in three_wrap
    assert "grid-template-columns: minmax(0, 1fr);" in mobile
    assert "object-fit: contain;" in image
    assert "var(--grid-pan-x, 0px)" in image
    assert "scale(var(--grid-zoom-level, 1))" in image
    assert "text-overflow: ellipsis;" in css_block(css, ".rv-grid-label-text")
    assert "border-color: var(--accent);" in css_block(css, '.rv-grid-cell[data-reference="true"]')
    assert "var(--annotation)" in css_block(css, '.rv-grid-cell[data-active="true"]')
    assert "overflow: hidden;" in css_block(css, ".rv-grid")
    assert "#btn-grid-prev" in coarse
    assert "[data-grid-retry]" in coarse
    assert "min-width: 44px;" in coarse
