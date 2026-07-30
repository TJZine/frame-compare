from __future__ import annotations

import re

from frame_compare.services.report.viewer import get_css
from tests.services.report_viewer_contracts import css_block


def test_viewer_css_preserves_accessible_input_modes() -> None:
    css = get_css()

    assert "@import" not in css
    assert re.search(r"url\s*\(\s*(['\"]?)\s*https?://", css, re.IGNORECASE) is None
    reduced_motion = css_block(css, "@media (prefers-reduced-motion: reduce)")
    assert "transition: none !important;" in reduced_motion
    assert "animation-duration: 0.01ms !important;" in reduced_motion

    coarse = css_block(css, "@media (pointer: coarse)")
    selectors = (
        "#btn-lens",
        ".rv-lens-palette-controls button",
        ".rv-lens-grip",
        "[data-lens-size]",
        "[data-lens-marker]",
        ".rv-inspector-tabs button",
        ".rv-review-field select",
        ".rv-review-transfer button",
        ".rv-review-preview button",
        ".rv-review-check",
        ".rv-review-preview label",
        "#btn-grid-prev",
        "#btn-grid-next",
        "[data-grid-retry]",
        ".rv-grid-cell",
    )
    for selector in selectors:
        target = css_block(coarse, selector)
        assert "min-width: 44px;" in target, selector
        assert "min-height: 44px;" in target, selector
