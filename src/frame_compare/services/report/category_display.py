"""Shared category display helpers for report labels and filters."""

from __future__ import annotations

_CATEGORY_LABELS = {
    "quantile_bright": "Bright",
    "quantile_dark": "Dark",
    "scene-cut": "Scene Cuts",
    "scene_cut": "Scene Cuts",
    "selected": "Selected",
}


def humanize_category(category: str | None) -> str | None:
    """Map technical report categories into readable display labels."""
    if category is None:
        return None
    if category in _CATEGORY_LABELS:
        return _CATEGORY_LABELS[category]
    return category.replace("_", " ").replace("-", " ").title()


def normalized_display_token(value: str | None) -> str | None:
    """Normalize category and label text for display-equivalence checks."""
    if value is None:
        return None
    normalized = " ".join(value.replace("_", " ").replace("-", " ").split()).casefold()
    return normalized or None


def label_repeats_category(label: str | None, category: str | None) -> bool:
    """Return whether a label repeats the human-readable category text."""
    label_token = normalized_display_token(label)
    return label_token is not None and label_token == normalized_display_token(
        humanize_category(category)
    )
