"""Shared validation primitives for user-visible configuration text."""

from __future__ import annotations

import re
import unicodedata

_BIDI_FORMATTING_CONTROLS = re.compile(r"[\u202A-\u202E\u2066-\u2069]")


def is_control_character(character: str) -> bool:
    """Return whether one Unicode character has the control category."""
    return unicodedata.category(character) == "Cc"


def reject_control_characters(value: str, *, field_name: str) -> None:
    """Reject Unicode control characters from user-visible configuration text."""
    if any(is_control_character(character) for character in value):
        raise ValueError(f"{field_name} must not contain control characters")


def reject_label_controls(value: str, *, field_name: str) -> None:
    """Reject control characters and bidirectional formatting in authored labels."""
    reject_control_characters(value, field_name=field_name)
    if _BIDI_FORMATTING_CONTROLS.search(value):
        raise ValueError(f"{field_name} must not contain bidirectional formatting controls")


def show_bidi_formatting_controls(value: str) -> str:
    """Make bidirectional formatting controls visible in a presentation string."""
    return _BIDI_FORMATTING_CONTROLS.sub(lambda match: f"[U+{ord(match[0]):04X}]", value)


__all__ = [
    "is_control_character",
    "reject_control_characters",
    "reject_label_controls",
    "show_bidi_formatting_controls",
]
