"""Shared validation primitives for user-visible configuration text."""

from __future__ import annotations

import unicodedata


def is_control_character(character: str) -> bool:
    """Return whether one Unicode character has the control category."""
    return unicodedata.category(character) == "Cc"


def reject_control_characters(value: str, *, field_name: str) -> None:
    """Reject Unicode control characters from user-visible configuration text."""
    if any(is_control_character(character) for character in value):
        raise ValueError(f"{field_name} must not contain control characters")


__all__ = ["is_control_character", "reject_control_characters"]
