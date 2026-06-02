"""Tests for configured source selector resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.config.schema_models import SourceOverrideConfig, SourcesConfig
from frame_compare.orchestration.errors import DuplicateSourceStemError, SourceSelectionError
from frame_compare.orchestration.source_selection import (
    reference_cache_domain_token,
    resolve_source_selection,
)


def _paths(input_dir: Path, *names: str) -> list[Path]:
    return [input_dir / name for name in names]


def test_source_selection_without_reference_preserves_discovered_order(tmp_path: Path) -> None:
    input_dir = tmp_path / "comparison_videos"
    paths = _paths(input_dir, "00-reference.mkv", "01-encode.mkv")

    selection = resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=paths,
        config=SourcesConfig(),
    )

    assert selection.ordered_paths == paths
    assert selection.overrides_by_path == {}


@pytest.mark.parametrize(
    "selector",
    ["nested/00-reference.mkv", "nested\\00-reference.mkv", "00-reference.mkv", "00-reference"],
)
def test_source_selection_matches_reference_by_path_filename_and_stem(
    tmp_path: Path,
    selector: str,
) -> None:
    input_dir = tmp_path / "comparison_videos"
    reference = input_dir / "nested" / "00-reference.mkv"
    paths = _paths(input_dir, "01-encode.mkv") + [reference]

    selection = resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=paths,
        config=SourcesConfig(reference=selector),
    )

    assert selection.ordered_paths == [reference, input_dir / "01-encode.mkv"]


@pytest.mark.parametrize(
    "selector",
    [
        "",
        "/absolute.mkv",
        "C:\\absolute.mkv",
        "C:clip.mkv",
        "D:",
        "\\\\server\\share\\clip.mkv",
        ".",
        "a/../b.mkv",
    ],
)
def test_source_selection_rejects_invalid_selector_forms(
    tmp_path: Path,
    selector: str,
) -> None:
    input_dir = tmp_path / "comparison_videos"
    paths = _paths(input_dir, "00-reference.mkv")

    with pytest.raises(SourceSelectionError):
        resolve_source_selection(
            input_dir=input_dir,
            discovered_paths=paths,
            config=SourcesConfig(reference=selector),
        )


def test_source_selection_rejects_missing_reference_selector(tmp_path: Path) -> None:
    input_dir = tmp_path / "comparison_videos"
    paths = _paths(input_dir, "00-reference.mkv")

    with pytest.raises(SourceSelectionError) as exc_info:
        resolve_source_selection(
            input_dir=input_dir,
            discovered_paths=paths,
            config=SourcesConfig(reference="missing"),
        )

    assert exc_info.value.context.details["reason"] == "no matching source"


def test_source_selection_rejects_duplicate_stems_before_matching(tmp_path: Path) -> None:
    input_dir = tmp_path / "comparison_videos"
    paths = _paths(input_dir, "nested/source.mkv", "source.mp4")

    with pytest.raises(DuplicateSourceStemError) as exc_info:
        resolve_source_selection(
            input_dir=input_dir,
            discovered_paths=paths,
            config=SourcesConfig(reference="source"),
        )

    assert exc_info.value.context.details["stem"] == "source"


def test_source_selection_resolves_overrides_by_selector(tmp_path: Path) -> None:
    input_dir = tmp_path / "comparison_videos"
    reference, encode = _paths(input_dir, "00-reference.mkv", "01-encode.mkv")
    override = SourceOverrideConfig(
        trim_start_frames=12,
        trim_end_frames=2,
        effective_fps="24000/1001",
    )

    selection = resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=[reference, encode],
        config=SourcesConfig(overrides={"01-encode": override}),
    )

    assert selection.overrides_by_path == {encode: override}
    assert reference_cache_domain_token(selection.overrides_by_path.get(reference)) is None
    assert reference_cache_domain_token(selection.overrides_by_path[encode]) == (
        "trim_start=12|trim_end=2|effective_fps=24000/1001"
    )


def test_reference_cache_domain_token_preserves_integral_num_den_effective_fps() -> None:
    token = reference_cache_domain_token(SourceOverrideConfig(effective_fps="24/1"))

    assert token == "trim_start=0|trim_end=0|effective_fps=24/1"


def test_source_selection_rejects_duplicate_override_selectors_for_same_source(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "comparison_videos"
    reference, encode = _paths(input_dir, "00-reference.mkv", "01-encode.mkv")

    with pytest.raises(SourceSelectionError) as exc_info:
        resolve_source_selection(
            input_dir=input_dir,
            discovered_paths=[reference, encode],
            config=SourcesConfig(
                overrides={
                    "01-encode": SourceOverrideConfig(trim_start_frames=1),
                    "01-encode.mkv": SourceOverrideConfig(trim_start_frames=2),
                }
            ),
        )

    assert "duplicates override selector" in exc_info.value.context.details["reason"]
