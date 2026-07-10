"""Source display-label policy tests."""

from pathlib import Path
from typing import Literal

import pytest

from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.errors import SourceSelectionError
from frame_compare.orchestration.source_labels import resolve_source_labels


def _labels(
    paths: list[Path],
    *,
    mode: Literal["stem", "filename", "parsed"] = "stem",
    parser: Literal["auto", "guessit", "anitopy"] = "auto",
    overrides: dict[Path, SourceOverrideConfig] | None = None,
) -> list[str]:
    resolved = resolve_source_labels(
        ordered_paths=paths,
        overrides_by_path=overrides or {},
        label_mode=mode,
        label_parser=parser,
    )
    return [resolved[path] for path in paths]


def test_stem_and_filename_modes_preserve_order() -> None:
    paths = [Path("Reference Source.mkv"), Path("Encode Source.webm")]
    assert _labels(paths) == ["Reference Source", "Encode Source"]
    assert _labels(paths, mode="filename") == ["Reference Source.mkv", "Encode Source.webm"]


def test_parsed_mode_and_parser_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    priorities: list[str] = []

    def fake_parse(_filename: str, parser_priority: str):
        from frame_compare.services.types import ParsedMetadata

        priorities.append(parser_priority)
        return ParsedMetadata(
            title="Episode Name",
            season=1,
            episode=2,
            episode_title="Arrival",
            release_group="Group",
        )

    monkeypatch.setattr("frame_compare.orchestration.source_labels.parse_filename", fake_parse)
    assert _labels([Path("source.mkv")], mode="parsed", parser="guessit") == [
        "[Group] Episode Name S01E02 – Arrival"
    ]
    assert priorities == ["guessit"]


def test_explicit_override_wins_and_controls_are_normalized_for_derived_text() -> None:
    reference = Path("Reference\nSource.mkv")
    comparison = Path("comparison.mkv")
    assert _labels(
        [reference, comparison],
        overrides={comparison: SourceOverrideConfig(label="Custom Encode")},
    ) == ["Reference Source", "Custom Encode"]


def test_duplicate_explicit_labels_fail_with_typed_source_selection_error() -> None:
    paths = [Path("a.mkv"), Path("b.mkv")]
    overrides = {path: SourceOverrideConfig(label="Same") for path in paths}
    with pytest.raises(SourceSelectionError, match="duplicate explicit source label"):
        _labels(paths, overrides=overrides)


def test_derived_collisions_are_qualified_while_explicit_label_is_preserved() -> None:
    paths = [Path("a.mkv"), Path("b.mkv"), Path("Same.mkv")]
    overrides = {paths[0]: SourceOverrideConfig(label="Same")}
    assert _labels(paths, overrides=overrides) == ["Same", "b", "Same [Same]"]


def test_derived_collision_qualification_is_stable_by_source_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.services.types import ParsedMetadata

    monkeypatch.setattr(
        "frame_compare.orchestration.source_labels.parse_filename",
        lambda *_args, **_kwargs: ParsedMetadata(title="Same"),
    )
    paths = [Path("one.mkv"), Path("two.mkv")]
    assert _labels(paths, mode="parsed") == ["Same [one]", "Same [two]"]
