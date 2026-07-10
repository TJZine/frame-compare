"""Strict slow.pics collection-title template helpers."""

from __future__ import annotations

from collections.abc import Mapping

SLOWPICS_TITLE_TEMPLATE_FIELDS = frozenset(
    {
        "Title",
        "OriginalTitle",
        "Year",
        "TMDBId",
        "TMDBCategory",
        "OriginalLanguage",
        "Filename",
        "FileName",
        "Label",
    }
)


def validate_slowpics_title_template(template: str) -> None:
    """Reject malformed or non-allowlisted substitution syntax."""
    _substitute_slowpics_title_template(template, {})


def render_slowpics_title_template(template: str, context: Mapping[str, str]) -> str:
    """Render an allowlisted substitution-only slow.pics title template."""
    return _substitute_slowpics_title_template(template, context)


def _substitute_slowpics_title_template(
    template: str,
    context: Mapping[str, str],
) -> str:
    rendered: list[str] = []
    index = 0
    while index < len(template):
        character = template[index]
        if character != "$":
            rendered.append(character)
            index += 1
            continue

        if index + 1 >= len(template):
            raise ValueError("title_template contains an unescaped '$'")
        next_character = template[index + 1]
        if next_character == "$":
            rendered.append("$")
            index += 2
            continue
        if next_character != "{":
            raise ValueError("title_template placeholders must use ${Name} syntax")

        closing_index = template.find("}", index + 2)
        if closing_index < 0:
            raise ValueError("title_template contains an unterminated placeholder")
        identifier = template[index + 2 : closing_index]
        if identifier not in SLOWPICS_TITLE_TEMPLATE_FIELDS:
            raise ValueError(f"title_template contains unsupported placeholder {identifier!r}")
        rendered.append(context.get(identifier, ""))
        index = closing_index + 1

    return "".join(rendered)


__all__ = [
    "SLOWPICS_TITLE_TEMPLATE_FIELDS",
    "render_slowpics_title_template",
    "validate_slowpics_title_template",
]
