"""Static viewer assets (CSS, JS) for HTML report."""

from __future__ import annotations

from functools import cache
from importlib.resources import files


@cache
def get_css() -> str:
    """Load and return the CSS asset."""
    return (files("frame_compare.services.report") / "assets" / "viewer.css").read_text(
        encoding="utf-8"
    )


@cache
def get_js() -> str:
    """Load focused viewer owners before the composition asset."""
    assets = files("frame_compare.services.report") / "assets"
    pixel_inspector = (assets / "pixel_inspector.js").read_text(encoding="utf-8")
    grid_view = (assets / "grid_view.js").read_text(encoding="utf-8")
    viewer = (assets / "viewer.js").read_text(encoding="utf-8")
    return f"{pixel_inspector}\n\n{grid_view}\n\n{viewer}"
