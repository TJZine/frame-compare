"""Canonical slow.pics identifier and comparison URL grammar."""

import re

SLOWPICS_BASE_URL = "https://slow.pics"
_COMPARISON_PREFIX = f"{SLOWPICS_BASE_URL}/c/"
_MAX_IDENTIFIER_LENGTH = 128
_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]+")


def is_slowpics_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= _MAX_IDENTIFIER_LENGTH
        and _IDENTIFIER.fullmatch(value) is not None
    )


def comparison_url(key: str) -> str:
    if not is_slowpics_identifier(key):
        raise ValueError("Invalid slow.pics comparison key")
    return f"{_COMPARISON_PREFIX}{key}"


def require_comparison_url(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > len(_COMPARISON_PREFIX) + _MAX_IDENTIFIER_LENGTH
        or not value.startswith(_COMPARISON_PREFIX)
        or not is_slowpics_identifier(value[len(_COMPARISON_PREFIX) :])
    ):
        raise ValueError("slowpics.url must be a canonical https://slow.pics/c/ URL")
    return value
