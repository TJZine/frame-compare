from __future__ import annotations

from pathlib import Path

import frame_compare.analysis.cache_io as cache_io
from frame_compare.config.loader import load_config

from .execute_run_helpers import create_config, create_video_files, write_metrics_cache


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

    fingerprint = cache_io.compute_cache_key(cache_inputs, config.analysis)
    cache_path = cache_io.find_metrics_cache_file(cache_dir, fingerprint)

    assert cache_path is not None
