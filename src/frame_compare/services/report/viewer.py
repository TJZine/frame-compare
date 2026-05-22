"""Static viewer assets (CSS, JS) for HTML report."""

from __future__ import annotations

from importlib.resources import files

CSS = (files("frame_compare.services.report") / "assets" / "viewer.css").read_text(encoding="utf-8")
JS = (files("frame_compare.services.report") / "assets" / "viewer.js").read_text(encoding="utf-8")
