"""Cache-mode tests for orchestration preparation."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from frame_compare.orchestration import preparation
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.vs.types import SourceInfo
from tests.orchestration.preparation_test_support import (
    ALIGNMENT_CONFIG,
    METRIC_CONFIG,
)
from tests.orchestration.preparation_test_support import (
    create_config as _create_config,
)
from tests.orchestration.preparation_test_support import (
    create_video_files as _create_video_files,
)

if TYPE_CHECKING:
    import vapoursynth as vs
import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.config.errors import ConfigValidationError
from frame_compare.orchestration.active_rect import metric_cache_request_for_clip
from frame_compare.orchestration.execution_types import PrepState
from frame_compare.vspreview.overrides import MANUAL_OVERRIDES_FILE
from tests.orchestration.execute_run_helpers import (
    analysis_selection_domain_for_cache_inputs,
    metric_cache_request_for_cache_inputs,
    write_metrics_cache,
    write_probe_cache_for_inputs,
)


class FakeVSLoader:
    def __init__(self, *, fps_by_name: dict[str, Fraction] | None = None) -> None:
        self.loaded: list[Path] = []
        self._fps_by_name = fps_by_name or {}

    def load(self, path: Path) -> SourceInfo:
        self.loaded.append(path)
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=self._fps_by_name.get(path.name, Fraction(24000, 1001)),
            format=cast(Any, object()),
            frame_props={
                "_Transfer": 16,
                "DolbyVisionRPU": b"opaque-rpu",
                "Ignored": {"not": "toml-safe"},
            },
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> vs.Core:
        raise AssertionError("Preparation probing should not request the VS core directly")


def _prepared_metric_cache_fingerprint(source_paths: list[Path], *, prep: PrepState) -> str:
    """Build the exact metric-cache identity for a prepared analysis source."""
    return cache_io.compute_cache_key(
        source_paths,
        prep.config.analysis,
        selection_domain=prep.analysis_selection_domain,
        metric_request=metric_cache_request_for_clip(
            prep.analysis_clip,
            selection_window=prep.selection_window,
            fallback_detection_mode=prep.config.screenshots.active_rect_detection.value,
        ),
    )


def test_execute_prep_rejects_mutually_exclusive_cache_flags(tmp_path: Path) -> None:
    request = RunRequest(root=tmp_path, no_cache=True, from_cache_only=True)

    with pytest.raises(MetricsCalculationError, match="mutually exclusive"):
        asyncio.run(preparation.execute_prep(request, RunDependencies()))


def test_execute_prep_no_cache_removes_only_matching_shared_metrics_cache(tmp_path: Path) -> None:
    _create_config(tmp_path, content=METRIC_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    preflight = preparation.prepare_preflight(root=tmp_path)
    source_path = input_dir / "source.mkv"
    prep_for_domain = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )
    fingerprint = _prepared_metric_cache_fingerprint(
        [source_path],
        prep=prep_for_domain,
    )
    metrics_dir = tmp_path / "generated" / "cache" / "analysis"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / cache_io.metrics_cache_filename([source_path], fingerprint)
    metrics_path.write_text("{}", encoding="utf-8")
    other_metrics_path = metrics_dir / "other__other.compframes"
    other_metrics_path.write_text("{}", encoding="utf-8")
    manual_overrides_path = tmp_path / "generated" / MANUAL_OVERRIDES_FILE
    manual_overrides_path.parent.mkdir(parents=True, exist_ok=True)
    manual_overrides_path.write_text('version = "1"\n', encoding="utf-8")
    alignment_cache_path = preflight.workspace.shared_alignment_cache_dir / "shared_prev_offset"
    alignment_cache_path.parent.mkdir(parents=True, exist_ok=True)
    alignment_cache_path.write_text("preserve me\n", encoding="utf-8")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path, no_cache=True),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.clips[0].label == "source"
    assert not metrics_path.exists()
    assert other_metrics_path.exists()
    assert manual_overrides_path.exists()
    assert alignment_cache_path.exists()


def test_execute_prep_no_cache_uses_analysis_active_rect_fingerprint(tmp_path: Path) -> None:
    config_content = (
        METRIC_CONFIG
        + """
[sources.overrides."source.mkv"]
active_rect = { x = 10, y = 20, width = 300, height = 200 }
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    source_path = _create_video_files(input_dir, "source.mkv")[0]
    prep_for_domain = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )
    rect_fingerprint = _prepared_metric_cache_fingerprint(
        [source_path],
        prep=prep_for_domain,
    )
    full_frame_fingerprint = cache_io.compute_cache_key(
        [source_path],
        prep_for_domain.config.analysis,
        selection_domain=prep_for_domain.analysis_selection_domain,
    )
    metrics_dir = tmp_path / "generated" / "cache" / "analysis"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    rect_cache_path = metrics_dir / cache_io.metrics_cache_filename([source_path], rect_fingerprint)
    full_frame_cache_path = metrics_dir / cache_io.metrics_cache_filename(
        [source_path],
        full_frame_fingerprint,
    )
    rect_cache_path.write_text("{}", encoding="utf-8")
    full_frame_cache_path.write_text("{}", encoding="utf-8")

    asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path, no_cache=True),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert not rect_cache_path.exists()
    assert full_frame_cache_path.exists()


def test_execute_prep_no_cache_removes_only_selected_reference_metrics_cache(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nreference = "b-reference.mkv"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a-default.mkv", "b-reference.mkv")

    config = preparation.prepare_preflight(root=tmp_path).config
    default_order = [input_dir / "a-default.mkv", input_dir / "b-reference.mkv"]
    selected_order = [input_dir / "b-reference.mkv", input_dir / "a-default.mkv"]
    prep_for_domain = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )
    metrics_dir = tmp_path / "generated" / "cache" / "analysis"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    default_fingerprint = cache_io.compute_cache_key(default_order, config.analysis)
    selected_fingerprint = _prepared_metric_cache_fingerprint(
        selected_order,
        prep=prep_for_domain,
    )
    default_cache_path = metrics_dir / cache_io.metrics_cache_filename(
        default_order, default_fingerprint
    )
    selected_cache_path = metrics_dir / cache_io.metrics_cache_filename(
        selected_order, selected_fingerprint
    )
    default_cache_path.write_text("{}", encoding="utf-8")
    selected_cache_path.write_text("{}", encoding="utf-8")

    asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path, no_cache=True),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert default_cache_path.exists()
    assert not selected_cache_path.exists()


def test_execute_prep_from_cache_only_does_not_require_cached_alignment_offsets(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=ALIGNMENT_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a_source.mkv", "b_comp.mkv")

    request = RunRequest(root=tmp_path, from_cache_only=True, skip_analysis=True)

    prep = asyncio.run(
        preparation.execute_prep(request, RunDependencies(vs_loader=cast(Any, FakeVSLoader())))
    )

    assert [clip.label for clip in prep.clips] == ["a_source", "b_comp"]


def test_execute_prep_from_cache_only_validates_metrics_cache_when_analysis_runs(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=METRIC_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    source_path = _create_video_files(input_dir, "source.mkv")[0]
    config = preparation.prepare_preflight(root=tmp_path).config
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)

    request = RunRequest(root=tmp_path, from_cache_only=True, skip_analysis=False)

    with pytest.raises(MetricsCalculationError, match="Cached metrics missing"):
        asyncio.run(
            preparation.execute_prep(request, RunDependencies(vs_loader=cast(Any, FakeVSLoader())))
        )


def test_execute_prep_cache_only_rejects_metadata_mismatch_before_run_folder_reservation(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    source_path = _create_video_files(input_dir, "source.mkv")[0]
    preflight = preparation.prepare_preflight(root=tmp_path)
    config = preflight.config
    generated_dir = preflight.workspace.generated_dir
    cache_dir = generated_dir / "cache" / "analysis"
    write_metrics_cache(cache_dir, source_path=source_path, config=config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_request=metric_cache_request_for_cache_inputs([source_path], config),
    )
    cache_path = cache_io.find_metrics_cache_file(cache_dir, fingerprint)
    assert cache_path is not None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["metadata"]["active_rect_source"] = "explicit"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    directories_before = {path for path in generated_dir.iterdir() if path.is_dir()}

    with pytest.raises(MetricsCalculationError, match="mismatched_inputs"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path, from_cache_only=True),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )

    directories_after = {path for path in generated_dir.iterdir() if path.is_dir()}
    assert directories_after == directories_before


def test_execute_prep_rejects_skip_analysis_with_metric_frame_selection(tmp_path: Path) -> None:
    _create_config(tmp_path, content=METRIC_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    with pytest.raises(ConfigValidationError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path, skip_analysis=True),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )

    assert exc_info.value.context.message == "Metric-based frame selection requires analysis"
    assert exc_info.value.validation_errors[0]["loc"] == ["analysis", "dark_frame_count"]


def test_execute_prep_from_cache_only_misses_when_selected_reference_differs(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nreference = "b-reference.mkv"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a-default.mkv", "b-reference.mkv")
    config = preparation.prepare_preflight(root=tmp_path).config
    default_order = [input_dir / "a-default.mkv", input_dir / "b-reference.mkv"]
    fingerprint = cache_io.compute_cache_key(default_order, config.analysis)
    metrics_dir = tmp_path / "generated" / "cache" / "analysis"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / cache_io.metrics_cache_filename(default_order, fingerprint)).write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(MetricsCalculationError, match="Cached clip probe data is required"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path, from_cache_only=True),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )


def test_execute_prep_from_cache_only_misses_when_reference_effective_fps_differs(
    tmp_path: Path,
) -> None:
    config_content = (
        METRIC_CONFIG
        + """
[sources.overrides."a-default.mkv"]
effective_fps = "24000/1001"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a-default.mkv", "b-encode.mkv")
    config = preparation.prepare_preflight(root=tmp_path).config
    input_order = [input_dir / "a-default.mkv", input_dir / "b-encode.mkv"]
    source_fps_fingerprint = cache_io.compute_cache_key(input_order, config.analysis)
    metrics_dir = tmp_path / "generated" / "cache" / "analysis"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / cache_io.metrics_cache_filename(input_order, source_fps_fingerprint)).write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(MetricsCalculationError, match="Cached clip probe data is required"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path, from_cache_only=True),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )


def test_execute_prep_shared_analysis_cache_stays_outside_run_folder(
    tmp_path: Path,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "custom_generated"
config_dir = "config"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path, skip_analysis=True),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.workspace.run_dir is not None
    assert prep.workspace.generated_dir == prep.workspace.run_dir / "generated"
    assert prep.workspace.cache_dir == tmp_path / "custom_generated" / "cache" / "analysis"
    assert (
        prep.workspace.shared_alignment_cache_dir
        == tmp_path / "custom_generated" / "cache" / "alignment"
    )


def test_execute_prep_preserves_explicit_reference_effective_fps_cache_domain_when_equal_to_source(
    tmp_path: Path,
) -> None:
    config_content = (
        METRIC_CONFIG
        + """
[sources.overrides."00-reference.mkv"]
effective_fps = "24/1"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24, 1),
            "01-encode.mkv": Fraction(24, 1),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.analysis_selection_domain is not None
    selection_domain = json.loads(prep.analysis_selection_domain)
    assert selection_domain["reference_path"] == (input_dir / "00-reference.mkv").as_posix()
    assert selection_domain["clips"][0]["effective_fps"] == {"numerator": 24, "denominator": 1}
    assert selection_domain["selection_window"] == {
        "start_frame": 0,
        "end_frame_exclusive": 100,
    }
    assert prep.clips[0].source_fps == Fraction(24, 1)
    assert prep.clips[0].effective_fps == Fraction(24, 1)
