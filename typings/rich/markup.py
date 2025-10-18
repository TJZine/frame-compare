from __future__ import annotations

__all__ = ["escape"]


def escape(text: str, *, style: bool = True) -> str:
    substitutions = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
    }
    escaped = "".join(substitutions.get(char, char) for char in text)
    if style:
        return escaped

    style_chars = {"*", "_", "`", "[", "]"}
    return "".join(("\\" + char) if char in style_chars else char for char in escaped)
