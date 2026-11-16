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
            [ShortNameSource(None, "  Encode A  ", True, "Movie")],
            ["Reference"],
            ["  Encode A  "],
            id="  Encode A  ",
        ),
        pytest.param(
            [ShortNameSource(None, "\tEncode A\t", True, "Movie")],
            ["Reference"],
            ["\tEncode A\t"],
            id="\tEncode A\t",
        ),
        pytest.param(
            [ShortNameSource(None, "\xa0Encode A\xa0", True, "Movie")],
            ["Reference"],
            ["\xa0Encode A\xa0"],
            id="\xa0Encode A\xa0",
        ),
        pytest.param(
            [
                ShortNameSource(
                    identity=ReleaseIdentity(
                        content=ContentIdentity("Movie"),
                        release_group="GROUP",
                        has_terminal_release_group=True,
                    ),
                    label="  My encode  ",
                    label_is_explicit=True,
                    stem="Movie.1080p-GROUP",
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
                        content=ContentIdentity("Movie"),
                        release_group="GROUP",
                        has_terminal_release_group=True,
                    ),
                    label=" 	 ",
                    label_is_explicit=True,
                    stem="Movie.1080p-GROUP",
                )
            ],
            ["Reference"],
            ["GROUP"],
            id="test_blank_explicit_short_name_uses_available_release_identity",
        ),
        pytest.param(
            [
                ShortNameSource(identity=None, label="GROUP", label_is_explicit=True, stem="Movie"),
                ShortNameSource(
                    identity=ReleaseIdentity(
                        content=ContentIdentity("Movie"),
                        release_group="GROUP",
                        has_terminal_release_group=True,
                    ),
                    label="Automatic",
                    label_is_explicit=False,
                    stem="Movie.1080p-GROUP",
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
