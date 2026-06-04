from __future__ import annotations

import json
from pathlib import Path

import frame_compare.analysis.cache_io as cache_io
from frame_compare.config.loader import load_config

from .execute_run_helpers import (
    analysis_selection_domain_for_cache_inputs,
    create_config,
    create_video_files,
    write_metrics_cache,
)


def test_write_metrics_cache_uses_cache_inputs_stats_when_video_paths_are_provided(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_source.mkv", "b_comp.mkv")
    config = load_config(tmp_path / "config" / "config.toml")
    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    cache_inputs = [input_dir / "a_source.mkv", input_dir / "b_comp.mkv"]

    write_metrics_cache(
        cache_dir,
        source_path=input_dir / "missing-reference.mkv",
        config=config,
        video_paths=cache_inputs,
    )

    fingerprint = cache_io.compute_cache_key(
        cache_inputs,
        config.analysis,
        selection_domain=analysis_selection_domain_for_cache_inputs(cache_inputs, config),
    )
    cache_path = cache_io.find_metrics_cache_file(cache_dir, fingerprint)

    assert cache_path is not None


def test_analysis_selection_domain_for_cache_inputs_applies_source_overrides(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[sources]
reference = "b_comp.mkv"

[sources.overrides."a_source.mkv"]
trim_start_frames = 12
trim_end_frames = 5
effective_fps = "24000/1001"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_source.mkv", "b_comp.mkv")
    config = load_config(tmp_path / "config" / "config.toml")

    selection_domain = json.loads(
        analysis_selection_domain_for_cache_inputs(
            [input_dir / "a_source.mkv", input_dir / "b_comp.mkv"],
            config,
        )
    )

    assert selection_domain["reference_path"] == (input_dir / "b_comp.mkv").as_posix()
    assert [clip["path"] for clip in selection_domain["clips"]] == [
        (input_dir / "b_comp.mkv").as_posix(),
        (input_dir / "a_source.mkv").as_posix(),
    ]
    assert selection_domain["clips"][1]["trim_start_frames"] == 12
    assert selection_domain["clips"][1]["trim_end_frame_inclusive"] == 94
    assert selection_domain["clips"][1]["effective_fps"] == {
        "numerator": 24000,
        "denominator": 1001,
    }


def test_write_metrics_cache_uses_selected_reference_order_for_fingerprint(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[sources]
reference = "b_comp.mkv"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_source.mkv", "b_comp.mkv")
    config = load_config(tmp_path / "config" / "config.toml")
    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    discovered_paths = [input_dir / "a_source.mkv", input_dir / "b_comp.mkv"]

    write_metrics_cache(
        cache_dir,
        source_path=discovered_paths[0],
        config=config,
        video_paths=discovered_paths,
    )

    selection_domain = analysis_selection_domain_for_cache_inputs(discovered_paths, config)
    fingerprint = cache_io.compute_cache_key(
        [input_dir / "b_comp.mkv", input_dir / "a_source.mkv"],
        config.analysis,
        selection_domain=selection_domain,
    )

    cache_path = cache_io.find_metrics_cache_file(cache_dir, fingerprint)
    assert cache_path is not None
