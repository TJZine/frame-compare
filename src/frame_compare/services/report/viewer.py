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
    """Load and return the JS asset."""
    return (files("frame_compare.services.report") / "assets" / "viewer.js").read_text(
        encoding="utf-8"
    )
