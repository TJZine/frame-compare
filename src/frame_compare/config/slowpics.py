"""Strict slow.pics collection-title template helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict, overload

from frame_compare.config.text_validation import reject_control_characters


class SlowpicsTitleTemplateContext(TypedDict):
    """Complete allowlisted substitution context for one slow.pics title."""

    Title: str
    OriginalTitle: str
    Year: str
    TMDBId: str
    TMDBCategory: str
    OriginalLanguage: str
    Filename: str
    FileName: str
    Label: str


SLOWPICS_TITLE_TEMPLATE_FIELDS = frozenset(SlowpicsTitleTemplateContext.__required_keys__)


def validate_slowpics_title_template(template: str) -> None:
    """Reject malformed or non-allowlisted substitution syntax."""
    _substitute_slowpics_title_template(template, {})


@overload
def render_slowpics_title_template(
    template: str,
    context: SlowpicsTitleTemplateContext,
) -> str: ...


@overload
def render_slowpics_title_template(template: str, context: Mapping[str, str]) -> str: ...


def render_slowpics_title_template(template: str, context: Mapping[str, object]) -> str:
    """Render an allowlisted substitution-only slow.pics title template."""
    return _substitute_slowpics_title_template(template, context)


def _substitute_slowpics_title_template(
    template: str,
    context: Mapping[str, object],
) -> str:
    reject_control_characters(template, field_name="title_template")
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
            raise ValueError("title_template contains an unsupported placeholder")
        replacement = context.get(identifier, "")
        if not isinstance(replacement, str):
            raise ValueError(f"title_template context value {identifier} must be a string")
        reject_control_characters(
            replacement,
            field_name=f"title_template context value {identifier}",
        )
        rendered.append(replacement)
        index = closing_index + 1

    return "".join(rendered)


__all__ = [
    "SLOWPICS_TITLE_TEMPLATE_FIELDS",
    "SlowpicsTitleTemplateContext",
    "render_slowpics_title_template",
    "validate_slowpics_title_template",
]
