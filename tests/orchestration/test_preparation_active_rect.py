"""Active-rectangle resolution tests for orchestration preparation."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pytest

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.orchestration import preparation
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.orchestration.errors import (
    SourceSelectionError,
)
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.vs.types import SourceInfo
from tests.orchestration.execute_run_helpers import write_probe_cache_for_inputs
from tests.orchestration.preparation_test_support import (
    AUTO_METRIC_CONFIG,
    AUTO_MINIMAL_CONFIG,
    METRIC_CONFIG,
    MINIMAL_CONFIG,
)
from tests.orchestration.preparation_test_support import (
    create_config as _create_config,
)
from tests.orchestration.preparation_test_support import (
    create_video_files as _create_video_files,
)

if TYPE_CHECKING:
    import vapoursynth as vs


class FakeVSLoader:
    def __init__(
        self,
        *,
        fps_by_name: dict[str, Fraction] | None = None,
        dimensions_by_name: dict[str, tuple[int, int]] | None = None,
        frame_props_by_name: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.loaded: list[Path] = []
        self._fps_by_name = fps_by_name or {}
        self._dimensions_by_name = dimensions_by_name or {}
        self._frame_props_by_name = frame_props_by_name or {}

    def load(self, path: Path) -> SourceInfo:
        self.loaded.append(path)
        width, height = self._dimensions_by_name.get(path.name, (1920, 1080))
        return SourceInfo(
            clip=cast(Any, object()),
            width=width,
            height=height,
            num_frames=100,
            fps=self._fps_by_name.get(path.name, Fraction(24000, 1001)),
            format=cast(Any, object()),
            frame_props=self._frame_props_by_name.get(
                path.name,
                {
                    "_Transfer": 16,
                    "DolbyVisionRPU": b"opaque-rpu",
                    "Ignored": {"not": "toml-safe"},
                },
            ),
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> vs.Core:
        raise AssertionError("Preparation probing should not request the VS core directly")


def _letterbox_luma_frame(
    *,
    width: int = 100,
    height: int = 80,
    top: int = 10,
    bottom: int = 10,
) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
    frame = np.full((height, width), 0.065, dtype=np.float32)
    content_y = np.linspace(0.20, 0.80, height - top - bottom, dtype=np.float32)[:, None]
    content_x = np.linspace(0.0, 0.20, width, dtype=np.float32)[None, :]
    frame[top : height - bottom, :] = content_y + content_x
    return frame


def test_execute_prep_resolves_dimension_active_rects_during_preparation(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG.replace(
        "[screenshots]\nuse_ffmpeg = true",
        '[screenshots]\nuse_ffmpeg = true\nactive_rect_detection = "dimension"',
    )
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")
    loader = FakeVSLoader(
        dimensions_by_name={
            "00-reference.mkv": (1920, 1080),
            "01-encode.mkv": (1440, 1080),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.clips[0].active_rect == ClipActiveRect(
        240,
        0,
        1440,
        1080,
        "dimension-derived",
        "dimension",
    )
    assert prep.clips[1].active_rect == ClipActiveRect(
        0,
        0,
        1440,
        1080,
        "dimension-derived",
        "dimension",
    )


def test_execute_prep_resolves_metadata_active_rect_from_preserved_probe_props(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")
    loader = FakeVSLoader(
        frame_props_by_name={
            "00-reference.mkv": {
                "DolbyVision_L5_Left": 100,
                "DolbyVision_L5_Right": 120,
                "DolbyVision_L5_Top": 40,
                "DolbyVision_L5_Bottom": 60,
            }
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.clips[0].active_rect == ClipActiveRect(
        100,
        40,
        1700,
        980,
        "metadata",
        "aspect_ratio",
    )


def test_execute_prep_selection_domain_includes_resolved_active_rect_identity(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path, content=METRIC_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv", "02-encode.mkv")
    loader = FakeVSLoader(
        dimensions_by_name={
            "00-reference.mkv": (3840, 2160),
            "01-encode.mkv": (1920, 800),
            "02-encode.mkv": (1920, 800),
        }
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    selection_domain = json.loads(prep.analysis_selection_domain)
    assert selection_domain["active_rect_policy"] == {
        "detection_mode": "aspect_ratio",
        "algorithm_id": "active_rect_resolution_v2",
    }
    assert selection_domain["clips"][0]["active_rect"] == {
        "x": 0,
        "y": 280,
        "width": 3840,
        "height": 1600,
        "source": "aspect-ratio-derived",
        "detection_mode": "aspect_ratio",
        "algorithm_id": "active_rect_resolution_v2",
    }


def test_execute_prep_auto_content_refinement_updates_selection_domain_after_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_config(tmp_path, content=AUTO_METRIC_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")
    loader = FakeVSLoader(
        dimensions_by_name={
            "00-reference.mkv": (100, 80),
            "01-encode.mkv": (100, 80),
        }
    )
    sampled_indices: dict[str, tuple[int, ...]] = {}

    class FakeContentSampler:
        def __init__(self, _loader: object) -> None:
            pass

        def sample_luma_frames(
            self,
            clip: object,
            source_frame_indices: object,
        ) -> list[np.ndarray[tuple[int, int], np.dtype[np.float32]]]:
            clip_state = cast(Any, clip)
            indices = tuple(cast(Any, source_frame_indices))
            sampled_indices[clip_state.path.name] = indices
            return [_letterbox_luma_frame() for _index in indices]

    monkeypatch.setattr(preparation, "VSActiveRectFrameSampler", FakeContentSampler)

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert sampled_indices["00-reference.mkv"]
    assert len(sampled_indices["00-reference.mkv"]) == 16
    assert prep.clips[0].active_rect == ClipActiveRect(
        0,
        10,
        100,
        60,
        "content-derived",
        "auto",
    )
    selection_domain = json.loads(prep.analysis_selection_domain)
    assert selection_domain["active_rect_policy"] == {
        "detection_mode": "auto",
        "algorithm_id": "active_rect_resolution_v2",
    }
    assert selection_domain["clips"][0]["active_rect"] == {
        "x": 0,
        "y": 10,
        "width": 100,
        "height": 60,
        "source": "content-derived",
        "detection_mode": "auto",
        "algorithm_id": "active_rect_resolution_v2",
    }


def test_execute_prep_auto_propagates_supported_content_ratio_to_unresolved_clip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_config(tmp_path, content=AUTO_METRIC_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv", "02-full-frame.mkv")
    loader = FakeVSLoader(
        dimensions_by_name={
            "00-reference.mkv": (100, 80),
            "01-encode.mkv": (100, 80),
            "02-full-frame.mkv": (100, 80),
        }
    )

    class PartiallyDetectedContentSampler:
        def __init__(self, _loader: object) -> None:
            pass

        def sample_luma_frames(
            self,
            clip: object,
            source_frame_indices: object,
        ) -> list[np.ndarray[tuple[int, int], np.dtype[np.float32]]]:
            clip_state = cast(Any, clip)
            indices = tuple(cast(Any, source_frame_indices))
            if clip_state.path.name == "02-full-frame.mkv":
                return [np.full((80, 100), 0.5, dtype=np.float32) for _index in indices]
            return [_letterbox_luma_frame() for _index in indices]

    monkeypatch.setattr(
        preparation,
        "VSActiveRectFrameSampler",
        PartiallyDetectedContentSampler,
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert [clip.active_rect for clip in prep.clips] == [
        ClipActiveRect(0, 10, 100, 60, "content-derived", "auto"),
        ClipActiveRect(0, 10, 100, 60, "content-derived", "auto"),
        ClipActiveRect(0, 10, 100, 60, "aspect-ratio-derived", "auto"),
    ]
    selection_domain = json.loads(prep.analysis_selection_domain)
    assert selection_domain["clips"][2]["active_rect"] == {
        "x": 0,
        "y": 10,
        "width": 100,
        "height": 60,
        "source": "aspect-ratio-derived",
        "detection_mode": "auto",
        "algorithm_id": "active_rect_resolution_v2",
    }


def test_execute_prep_auto_sampling_failure_warns_and_leaves_full_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_config(tmp_path, content=AUTO_MINIMAL_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")
    loader = FakeVSLoader(dimensions_by_name={"00-reference.mkv": (100, 80)})

    class FailingContentSampler:
        def __init__(self, _loader: object) -> None:
            pass

        def sample_luma_frames(self, _clip: object, _source_frame_indices: object) -> object:
            raise RuntimeError("sample boom")

    monkeypatch.setattr(preparation, "VSActiveRectFrameSampler", FailingContentSampler)

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.clips[0].active_rect == ClipActiveRect(0, 0, 100, 80, "full-frame", "auto")
    assert any(
        "active-rect auto detection failed" in warning for warning in prep.preflight_warnings
    )


def test_execute_prep_from_cache_only_auto_sampling_failure_fails_before_cache_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_config(tmp_path, content=AUTO_METRIC_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    source_path = _create_video_files(input_dir, "source.mkv")[0]
    config = preparation.prepare_preflight(root=tmp_path).config
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)

    class FailingContentSampler:
        def __init__(self, _loader: object) -> None:
            pass

        def sample_luma_frames(self, _clip: object, _source_frame_indices: object) -> object:
            raise RuntimeError("sample boom")

    monkeypatch.setattr(preparation, "VSActiveRectFrameSampler", FailingContentSampler)

    with pytest.raises(MetricsCalculationError, match="active-rect auto detection failed"):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path, from_cache_only=True),
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
