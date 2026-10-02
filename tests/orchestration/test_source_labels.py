"""Source display-label policy tests."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot, ClipState
from frame_compare.orchestration.selection_domain import build_analysis_selection_domain_token
from frame_compare.orchestration.source_labels import (
    resolve_source_label_details,
)
from frame_compare.services.release_identity import ContentIdentity, ReleaseIdentity


def test_stem_and_filename_modes_preserve_order() -> None:
    paths = [Path("Reference Source.mkv"), Path("Encode Source.webm")]
    stem_details = resolve_source_label_details(
        ordered_paths=paths, overrides_by_path={}, label_mode="stem", label_parser="auto"
    )
    assert [stem_details[path].value for path in paths] == ["Reference Source", "Encode Source"]
    filename_details = resolve_source_label_details(
        ordered_paths=paths, overrides_by_path={}, label_mode="filename", label_parser="auto"
    )
    assert [filename_details[path].value for path in paths] == [
        "Reference Source.mkv",
        "Encode Source.webm",
    ]


def test_parsed_mode_and_parser_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    priorities: list[str] = []

    def fake_parse(_filename: str, parser_priority: str, *, alternate_policy: str):
        from frame_compare.services.types import ParsedMetadata

        priorities.append(f"{parser_priority}:{alternate_policy}")
        return ParsedMetadata(
            title="Episode Name",
            season=1,
            episode=2,
            episode_title="Arrival",
            release_group="Group",
        )

    monkeypatch.setattr("frame_compare.orchestration.source_labels.parse_filename", fake_parse)
    path = Path("source.mkv")
    details = resolve_source_label_details(
        ordered_paths=[path], overrides_by_path={}, label_mode="parsed", label_parser="guessit"
    )
    assert [details[path].value] == ["[Group] Episode Name S01E02 – Arrival"]
    assert priorities == ["guessit:fallback"]


def test_explicit_override_wins_and_controls_are_normalized_for_derived_text() -> None:
    reference = Path("Reference\nSource.mkv")
    comparison = Path("comparison.mkv")
    details = resolve_source_label_details(
        ordered_paths=[reference, comparison],
        overrides_by_path={comparison: SourceOverrideConfig(label="Custom Encode")},
        label_mode="stem",
        label_parser="auto",
    )
    assert [details[path].value for path in [reference, comparison]] == [
        "Reference Source",
        "Custom Encode",
    ]
    assert not details[reference].explicit
    assert details[comparison].explicit


def test_derived_collisions_are_qualified_while_explicit_label_is_preserved() -> None:
    paths = [Path("a.mkv"), Path("b.mkv"), Path("Same.mkv")]
    overrides = {paths[0]: SourceOverrideConfig(label="Same")}
    details = resolve_source_label_details(
        ordered_paths=paths, overrides_by_path=overrides, label_mode="stem", label_parser="auto"
    )
    assert [details[path].value for path in paths] == ["Same", "b", "Same [Same]"]


def test_derived_collision_qualification_is_stable_by_source_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.services.types import ParsedMetadata

    monkeypatch.setattr(
        "frame_compare.orchestration.source_labels.parse_filename",
        lambda *_args, **_kwargs: ParsedMetadata(title="Same"),
    )
    paths = [Path("one.mkv"), Path("two.mkv")]
    details = resolve_source_label_details(
        ordered_paths=paths, overrides_by_path={}, label_mode="parsed", label_parser="auto"
    )
    assert [details[path].value for path in paths] == ["Same [one]", "Same [two]"]


def test_display_labels_do_not_change_analysis_cache_identity() -> None:
    path = Path("source.mkv")
    probe = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path=path, size_bytes=1024, mtime_ns=1234),
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    clip = ClipState(
        path=path,
        label="source",
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
    )
    relabeled = replace(clip, label="Custom Source")
    presentation_enriched = replace(
        clip,
        release_identity=ReleaseIdentity(ContentIdentity("Source"), resolution="1080p"),
        label_is_explicit=True,
    )
    config = ConfigSchema()
    window = SelectionWindow(start_frame=0, end_frame_exclusive=100)

    original_identity = build_analysis_selection_domain_token(
        clips=[clip],
        analysis_clip=clip,
        config=config,
        selection_window=window,
    )
    relabeled_identity = build_analysis_selection_domain_token(
        clips=[relabeled],
        analysis_clip=relabeled,
        config=config,
        selection_window=window,
    )
    enriched_identity = build_analysis_selection_domain_token(
        clips=[presentation_enriched],
        analysis_clip=presentation_enriched,
        config=config,
        selection_window=window,
    )

    assert relabeled_identity == original_identity
    assert enriched_identity == original_identity
