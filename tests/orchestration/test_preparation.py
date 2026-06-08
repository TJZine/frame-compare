"""Direct tests for orchestration preparation behavior."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.config.errors import ConfigValidationError
from frame_compare.orchestration import preparation
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.orchestration.errors import (
    DuplicateSourceStemError,
    MixedSourceFpsError,
    SourceSelectionError,
)
from frame_compare.orchestration.probing.probe_cache import load_clip_probe_cache
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.vs.types import SourceInfo
from frame_compare.vspreview.overrides import MANUAL_OVERRIDES_FILE
from tests.orchestration.execute_run_helpers import write_probe_cache_for_inputs

if TYPE_CHECKING:
    import vapoursynth as vs

MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""

METRIC_CONFIG = (
    MINIMAL_CONFIG
    + """
[analysis]
random_frame_count = 0
dark_frame_count = 1
"""
)


ALIGNMENT_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = true

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def _create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def _create_video_files(input_dir: Path, *filenames: str) -> list[Path]:
    input_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename in filenames:
        path = input_dir / filename
        path.write_bytes(b"video")
        paths.append(path)
    return paths


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


class FakeBenchmarkClip:
    def __init__(self, *, num_frames: int, delay: float, clock: list[float]) -> None:
        self.num_frames = num_frames
        self.delay = delay
        self.clock = clock

    def get_frame(self, _frame: int) -> object:
        self.clock[0] += self.delay
        return object()


class FakeBenchmarkVSLoader(FakeVSLoader):
    def __init__(
        self,
        *,
        delays_by_name: dict[str, float],
        clock: list[float],
        frames_by_name: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        self._delays_by_name = delays_by_name
        self._clock = clock
        self._frames_by_name = frames_by_name or {}

    def load(self, path: Path) -> SourceInfo:
        self.loaded.append(path)
        num_frames = self._frames_by_name.get(path.name, 100)
        return SourceInfo(
            clip=cast(
                Any,
                FakeBenchmarkClip(
                    num_frames=num_frames,
                    delay=self._delays_by_name[path.name],
                    clock=self._clock,
                ),
            ),
            width=1920,
            height=1080,
            num_frames=num_frames,
            fps=Fraction(24000, 1001),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=False,
            hdr_metadata=None,
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
    config = preflight.config
    source_path = input_dir / "source.mkv"
    prep_for_domain = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=prep_for_domain.analysis_selection_domain,
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

    assert prep.clips[0].label == "Reference"
    assert not metrics_path.exists()
    assert other_metrics_path.exists()
    assert manual_overrides_path.exists()
    assert alignment_cache_path.exists()


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
    selected_fingerprint = cache_io.compute_cache_key(
        selected_order,
        config.analysis,
        selection_domain=prep_for_domain.analysis_selection_domain,
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

    assert [clip.label for clip in prep.clips] == ["Reference", "Encode 1"]


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
screenshots_dir = "screenshots"
generated_dir = "custom_generated"
config_dir = "config"
use_run_folders = true

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


def test_execute_prep_probes_uncached_clips_and_persists_probe_snapshot(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    source, encode = _create_video_files(input_dir, "source.mkv", "encode.mkv")
    loader = FakeVSLoader()

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert set(loader.loaded) == {source, encode}
    assert [clip.label for clip in prep.clips] == ["Reference", "Encode 1"]
    assert [clip.probe.width for clip in prep.clips] == [1920, 1920]
    assert prep.clips[0].probe.tonemap_prop_keys == ("DolbyVisionRPU", "_Transfer")
    assert prep.clips[0].probe.preserved_frame_props == {
        "DolbyVisionRPU": 1,
        "_Transfer": 16,
    }

    probe_cache = load_clip_probe_cache(tmp_path / "generated" / "clip_probe.toml")
    assert len(probe_cache) == 2
    assert {snapshot.fingerprint.path for snapshot in probe_cache.values()} == {source, encode}


def test_execute_prep_preserves_deterministic_four_clip_order_and_labels(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(
        input_dir,
        "03-delta.mkv",
        "01-bravo.mkv",
        "04-charlie.ts",
        "00-alpha.mp4",
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in prep.clips] == [
        input_dir / "00-alpha.mp4",
        input_dir / "01-bravo.mkv",
        input_dir / "03-delta.mkv",
        input_dir / "04-charlie.ts",
    ]
    assert [clip.label for clip in prep.clips] == [
        "Reference",
        "Encode 1",
        "Encode 2",
        "Encode 3",
    ]


def test_execute_prep_explicit_reference_moves_selected_source_to_front(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nreference = "03-delta.mkv"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(
        input_dir,
        "00-alpha.mp4",
        "01-bravo.mkv",
        "03-delta.mkv",
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in prep.clips] == [
        input_dir / "03-delta.mkv",
        input_dir / "00-alpha.mp4",
        input_dir / "01-bravo.mkv",
    ]
    assert [clip.label for clip in prep.clips] == ["Reference", "Encode 1", "Encode 2"]


def test_execute_prep_reference_auto_behaves_like_omitted_reference(tmp_path: Path) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nreference = "auto"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-alpha.mp4", "01-bravo.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in prep.clips] == [
        input_dir / "00-alpha.mp4",
        input_dir / "01-bravo.mkv",
    ]


def test_execute_prep_analysis_source_reference_selects_selected_reference(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nreference = "01-reference.mkv"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-default.mkv", "01-reference.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.analysis_clip is prep.clips[0]
    assert prep.analysis_clip.path == input_dir / "01-reference.mkv"


def test_execute_prep_analysis_source_selector_does_not_reorder_clips(tmp_path: Path) -> None:
    config_content = (
        METRIC_CONFIG
        + """
[sources]
analysis_source = "02-analysis.mkv"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv", "02-analysis.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path.name for clip in prep.clips] == [
        "00-reference.mkv",
        "01-encode.mkv",
        "02-analysis.mkv",
    ]
    assert prep.analysis_clip is not None
    assert prep.analysis_clip.path.name == "02-analysis.mkv"


def test_execute_prep_analysis_selection_domain_differs_by_analysis_source(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-analysis.mkv")
    _create_config(tmp_path, content=METRIC_CONFIG)
    reference_prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    _create_config(
        tmp_path,
        content=METRIC_CONFIG + '\n[sources]\nanalysis_source = "01-analysis.mkv"\n',
    )
    configured_prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert [clip.path for clip in reference_prep.clips] == [
        clip.path for clip in configured_prep.clips
    ]
    assert reference_prep.analysis_selection_domain != configured_prep.analysis_selection_domain
    assert (
        json.loads(reference_prep.analysis_selection_domain)["analysis_source_path"]
        == (input_dir / "00-reference.mkv").as_posix()
    )
    assert (
        json.loads(configured_prep.analysis_selection_domain)["analysis_source_path"]
        == (input_dir / "01-analysis.mkv").as_posix()
    )


def test_execute_prep_invalid_analysis_source_selector_fails_when_metrics_required(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "missing"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")

    with pytest.raises(SourceSelectionError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )

    assert exc_info.value.context.details["role"] == "sources.analysis_source"


def test_execute_prep_invalid_analysis_source_selector_is_ignored_when_analysis_skipped(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nanalysis_source = "missing"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.analysis_clip is None
    assert prep.analysis_selection_domain == ""


def test_execute_prep_applies_source_trim_and_active_rect_overrides(tmp_path: Path) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."01-encode.mkv"]
trim_start_frames = 12
trim_end_frames = 5
active_rect = { x = 240, y = 0, width = 1440, height = 1080 }
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.clips[0].trim.trim_start_frames == 0
    assert prep.clips[1].trim.trim_start_frames == 12
    assert prep.clips[1].trim.trim_end_frame_inclusive == 94
    assert prep.clips[1].active_rect == ClipActiveRect(
        x=240,
        y=0,
        width=1440,
        height=1080,
    )


def test_execute_prep_applies_effective_fps_overrides_without_changing_source_fps(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."01-encode.mkv"]
effective_fps = "24000/1001"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-encode.mkv": Fraction(30000, 1001),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.clips[0].source_fps == Fraction(24000, 1001)
    assert prep.clips[0].effective_fps == Fraction(24000, 1001)
    assert prep.clips[1].source_fps == Fraction(30000, 1001)
    assert prep.clips[1].effective_fps == Fraction(24000, 1001)


def test_execute_prep_match_fps_assumes_reference_for_unoverridden_comparisons(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources]
reference = "00-reference.mkv"
match_fps = "assume_reference"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(
        input_dir,
        "00-reference.mkv",
        "01-source-24.mkv",
        "02-source-ntsc-ish.mkv",
    )
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-source-24.mkv": Fraction(24, 1),
            "02-source-ntsc-ish.mkv": Fraction(13978, 583),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert [clip.source_fps for clip in prep.clips] == [
        Fraction(24000, 1001),
        Fraction(24, 1),
        Fraction(13978, 583),
    ]
    assert [clip.effective_fps for clip in prep.clips] == [
        Fraction(24000, 1001),
        Fraction(24000, 1001),
        Fraction(24000, 1001),
    ]


def test_execute_prep_match_fps_uses_selected_reference_before_matching(
    tmp_path: Path,
) -> None:
    config_content = (
        METRIC_CONFIG
        + """
[sources]
reference = "02-reference-ntsc.mkv"
match_fps = "assume_reference"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-default-24.mkv", "02-reference-ntsc.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-default-24.mkv": Fraction(24, 1),
            "02-reference-ntsc.mkv": Fraction(30000, 1001),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert [clip.path for clip in prep.clips] == [
        input_dir / "02-reference-ntsc.mkv",
        input_dir / "00-default-24.mkv",
    ]
    assert [clip.source_fps for clip in prep.clips] == [
        Fraction(30000, 1001),
        Fraction(24, 1),
    ]
    assert [clip.effective_fps for clip in prep.clips] == [
        Fraction(30000, 1001),
        Fraction(30000, 1001),
    ]
    selection_domain = json.loads(prep.analysis_selection_domain)
    assert selection_domain["reference_path"] == (input_dir / "02-reference-ntsc.mkv").as_posix()
    assert [clip["effective_fps"] for clip in selection_domain["clips"]] == [
        {"numerator": 30000, "denominator": 1001},
        {"numerator": 30000, "denominator": 1001},
    ]


def test_execute_prep_match_fps_preserves_explicit_comparison_effective_fps(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources]
match_fps = "assume_reference"

[sources.overrides."01-source-25.mkv"]
effective_fps = "25/1"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-source-25.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-source-25.mkv": Fraction(25, 1),
        }
    )

    with pytest.raises(MixedSourceFpsError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert exc_info.value.context.details["comparison_fps"] == "25"


def test_execute_prep_match_fps_majority_matches_outlier_and_preserves_source_fps(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nmatch_fps = "majority"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-majority.mkv", "02-outlier.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-majority.mkv": Fraction(24000, 1001),
            "02-outlier.mkv": Fraction(24, 1),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert [clip.source_fps for clip in prep.clips] == [
        Fraction(24000, 1001),
        Fraction(24000, 1001),
        Fraction(24, 1),
    ]
    assert [clip.effective_fps for clip in prep.clips] == [Fraction(24000, 1001)] * 3
    assert "FPS target: 24000/1001 (majority)" in prep.load_source_diagnostics
    assert not prep.preflight_warnings


def test_execute_prep_match_fps_majority_falls_back_to_reference_without_majority(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nmatch_fps = "majority"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-a.mkv", "02-b.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-a.mkv": Fraction(24, 1),
            "02-b.mkv": Fraction(25, 1),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert [clip.effective_fps for clip in prep.clips] == [Fraction(24000, 1001)] * 3
    assert "FPS target: 24000/1001 (reference fallback; no FPS majority)" in (
        prep.load_source_diagnostics
    )
    assert any(
        "reference fallback; no FPS majority" in warning for warning in prep.preflight_warnings
    )


def test_execute_prep_match_fps_majority_noop_has_no_diagnostic_noise(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nmatch_fps = "majority"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.load_source_diagnostics == []
    assert prep.preflight_warnings == []


def test_execute_prep_match_fps_majority_can_change_reference_outlier(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nmatch_fps = "majority"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference-outlier.mkv", "01-majority.mkv", "02-majority.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference-outlier.mkv": Fraction(24, 1),
            "01-majority.mkv": Fraction(24000, 1001),
            "02-majority.mkv": Fraction(24000, 1001),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.clips[0].source_fps == Fraction(24, 1)
    assert prep.clips[0].effective_fps == Fraction(24000, 1001)


def test_execute_prep_match_fps_majority_preserves_explicit_override_and_can_still_fail(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources]
match_fps = "majority"

[sources.overrides."02-explicit.mkv"]
effective_fps = "25/1"
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-majority.mkv", "02-explicit.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "00-reference.mkv": Fraction(24000, 1001),
            "01-majority.mkv": Fraction(24000, 1001),
            "02-explicit.mkv": Fraction(24, 1),
        }
    )

    with pytest.raises(MixedSourceFpsError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert exc_info.value.context.details["comparison_fps"] == "25"


def test_execute_prep_analysis_source_fastest_selects_lowest_timing_and_ties_by_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-fast.mkv", "02-tie.mkv")
    clock = [0.0]
    monkeypatch.setattr(
        "frame_compare.orchestration.analysis_source.perf_counter", lambda: clock[0]
    )
    loader = FakeBenchmarkVSLoader(
        delays_by_name={
            "00-reference.mkv": 2.0,
            "01-fast.mkv": 1.0,
            "02-tie.mkv": 1.0,
        },
        clock=clock,
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.analysis_clip is not None
    assert prep.analysis_clip.path.name == "01-fast.mkv"


def test_execute_prep_analysis_source_fastest_compares_per_sample_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-short-slow.mkv", "01-long-fast.mkv")
    clock = [0.0]
    monkeypatch.setattr(
        "frame_compare.orchestration.analysis_source.perf_counter", lambda: clock[0]
    )
    loader = FakeBenchmarkVSLoader(
        delays_by_name={
            "00-short-slow.mkv": 1.5,
            "01-long-fast.mkv": 1.0,
        },
        frames_by_name={
            "00-short-slow.mkv": 10,
            "01-long-fast.mkv": 100,
        },
        clock=clock,
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.analysis_clip is not None
    assert prep.analysis_clip.path.name == "01-long-fast.mkv"


def test_execute_prep_analysis_source_fastest_cache_only_rejects_before_probe(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")
    loader = FakeVSLoader()

    with pytest.raises(preparation.FastestAnalysisSourceCacheOnlyError):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path, from_cache_only=True),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert loader.loaded == []


def test_execute_prep_analysis_source_fastest_skipped_analysis_does_not_benchmark(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")
    loader = FakeVSLoader()

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.analysis_clip is None
    assert loader.loaded == [input_dir / "00-reference.mkv", input_dir / "01-encode.mkv"]


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


def test_execute_prep_reference_source_trims_constrain_effective_frame_domain(
    tmp_path: Path,
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."00-reference.mkv"]
trim_start_frames = 10
trim_end_frames = 5
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.clips[0].trim.trim_start_frames == 10
    assert prep.clips[0].trim.trim_end_frame_inclusive == 94
    assert prep.clips[0].effective_num_frames() == 85


def test_execute_prep_rejects_source_trims_that_remove_every_frame(tmp_path: Path) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."01-encode.mkv"]
trim_start_frames = 100
trim_end_frames = 0
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    with pytest.raises(SourceSelectionError, match="source trims remove every frame"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )


def test_execute_prep_rejects_out_of_bounds_explicit_active_rect(tmp_path: Path) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """
[sources.overrides."01-encode.mkv"]
active_rect = { x = 1800, y = 0, width = 400, height = 1080 }
"""
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")

    with pytest.raises(SourceSelectionError, match="active_rect is outside source dimensions"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
            )
        )


def test_execute_prep_rejects_duplicate_source_stems_before_probe(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv", "source.mp4")
    loader = FakeVSLoader()

    with pytest.raises(DuplicateSourceStemError):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert loader.loaded == []


def test_execute_prep_reuses_probe_cache_without_vs_loader(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    first = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )
    second = asyncio.run(preparation.execute_prep(RunRequest(root=tmp_path), RunDependencies()))

    assert second.clips[0].label == "Reference"
    assert second.clips[0].probe == first.clips[0].probe


def test_execute_prep_rejects_mixed_source_fps_before_downstream_work(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a_reference.mkv", "b_comparison.mkv")
    loader = FakeVSLoader(
        fps_by_name={
            "a_reference.mkv": Fraction(24000, 1001),
            "b_comparison.mkv": Fraction(30000, 1001),
        }
    )

    with pytest.raises(MixedSourceFpsError) as exc_info:
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    error = exc_info.value
    assert error.code == "FC-3011"
    assert "Mixed source FPS is not supported" in error.context.message
    assert error.context.details == {
        "reference_path": str(input_dir / "a_reference.mkv"),
        "reference_fps": "24000/1001",
        "comparison_label": "Encode 1",
        "comparison_path": str(input_dir / "b_comparison.mkv"),
        "comparison_fps": "30000/1001",
    }
    assert loader.loaded == [input_dir / "a_reference.mkv", input_dir / "b_comparison.mkv"]
