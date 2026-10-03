"""Regression coverage for explicit terminal short-name preservation."""

import pytest

from frame_compare.services.release_identity import (
    ContentIdentity,
    ReleaseIdentity,
    ShortNameSource,
    short_source_names,
)


@pytest.mark.parametrize(
    ("sources", "roles", "expected"),
    [
        pytest.param(
            [ShortNameSource(None, "  Encode A  ", True)],
            ["Reference"],
            ["  Encode A  "],
            id="  Encode A  ",
        ),
        pytest.param(
            [ShortNameSource(None, "\tEncode A\t", True)],
            ["Reference"],
            ["\tEncode A\t"],
            id="\tEncode A\t",
        ),
        pytest.param(
            [ShortNameSource(None, "\xa0Encode A\xa0", True)],
            ["Reference"],
            ["\xa0Encode A\xa0"],
            id="\xa0Encode A\xa0",
        ),
        pytest.param(
            [
                ShortNameSource(
                    identity=ReleaseIdentity(
                        content=ContentIdentity("Movie"), release_group="GROUP"
                    ),
                    label="  My encode  ",
                    label_is_explicit=True,
                )
            ],
            ["Reference"],
            ["  My encode  "],
            id="test_explicit_short_name_is_not_replaced_by_release_group",
        ),
        pytest.param(
            [
                ShortNameSource(
                    identity=ReleaseIdentity(
                        content=ContentIdentity("Movie"), release_group="GROUP"
                    ),
                    label=" 	 ",
                    label_is_explicit=True,
                )
            ],
            ["Reference"],
            ["GROUP"],
            id="test_blank_explicit_short_name_uses_available_release_identity",
        ),
        pytest.param(
            [
                ShortNameSource(identity=None, label="GROUP", label_is_explicit=True),
                ShortNameSource(
                    identity=ReleaseIdentity(
                        content=ContentIdentity("Movie"), release_group="GROUP"
                    ),
                    label="Automatic",
                    label_is_explicit=False,
                ),
            ],
            ["Reference", "Comparison"],
            [
                "GROUP",
                "Comparison | GROUP",
            ],
            id="test_derived_short_name_collision_does_not_rewrite_explicit_label",
        ),
    ],
)
def test_explicit_short_names(
    sources: list[ShortNameSource], roles: list[str], expected: list[str]
) -> None:
    assert short_source_names(sources, roles=roles) == expected
