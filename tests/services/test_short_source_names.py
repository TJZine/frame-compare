"""Regression coverage for explicit terminal short-name preservation."""

import pytest

from frame_compare.services.release_identity import (
    ContentIdentity,
    ReleaseIdentity,
    ShortNameSource,
    short_source_names,
)


@pytest.mark.parametrize("label", ["  Encode A  ", "\tEncode A\t", "\u00a0Encode A\u00a0"])
def test_explicit_short_name_preserves_nonblank_label(label: str) -> None:
    source = ShortNameSource(identity=None, label=label, label_is_explicit=True)

    assert short_source_names([source], roles=["Reference"]) == [label]


def test_explicit_short_name_is_not_replaced_by_release_group() -> None:
    identity = ReleaseIdentity(content=ContentIdentity("Movie"), release_group="GROUP")
    source = ShortNameSource(identity=identity, label="  My encode  ", label_is_explicit=True)

    assert short_source_names([source], roles=["Reference"]) == ["  My encode  "]


def test_blank_explicit_short_name_uses_available_release_identity() -> None:
    identity = ReleaseIdentity(content=ContentIdentity("Movie"), release_group="GROUP")
    source = ShortNameSource(identity=identity, label=" \t ", label_is_explicit=True)

    assert short_source_names([source], roles=["Reference"]) == ["GROUP"]


def test_derived_short_name_collision_does_not_rewrite_explicit_label() -> None:
    identity = ReleaseIdentity(content=ContentIdentity("Movie"), release_group="GROUP")
    sources = [
        ShortNameSource(identity=None, label="GROUP", label_is_explicit=True),
        ShortNameSource(identity=identity, label="Automatic", label_is_explicit=False),
    ]

    assert short_source_names(sources, roles=["Reference", "Comparison"]) == [
        "GROUP",
        "Comparison | GROUP",
    ]
