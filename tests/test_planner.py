from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from src.datatypes import (
    AnalysisConfig,
    AppConfig,
    AudioAlignmentConfig,
    CLIConfig,
    ColorConfig,
    DiagnosticsConfig,
    NamingConfig,
    OverridesConfig,
    PathsConfig,
    ReportConfig,
    RunnerConfig,
    RuntimeConfig,
    ScreenshotConfig,
    SlowpicsConfig,
    SourceConfig,
    TMDBConfig,
)
from src.frame_compare import planner


def _make_config(
    *,
    trim: dict[str, int] | None = None,
    trim_end: dict[str, int] | None = None,
    change_fps: dict[str, list[int] | str] | None = None,
) -> AppConfig:
    """Construct an AppConfig with focused override maps for planner tests."""

    return AppConfig(
        analysis=AnalysisConfig(
            frame_count_dark=0,
            frame_count_bright=0,
            frame_count_motion=0,
            random_frames=0,
            user_frames=[],
        ),
        screenshots=ScreenshotConfig(directory_name="screens", add_frame_info=False),
        cli=CLIConfig(),
        runner=RunnerConfig(),
        color=ColorConfig(),
        slowpics=SlowpicsConfig(auto_upload=False),
        tmdb=TMDBConfig(),
        naming=NamingConfig(always_full_filename=False, prefer_guessit=False),
        paths=PathsConfig(input_dir="media"),
        runtime=RuntimeConfig(ram_limit_mb=1024),
        overrides=OverridesConfig(
            trim=trim or {},
            trim_end=trim_end or {},
            change_fps=change_fps or {},
        ),
        source=SourceConfig(preferred="lsmas"),
        audio_alignment=AudioAlignmentConfig(enable=False),
        report=ReportConfig(enable=False),
        diagnostics=DiagnosticsConfig(),
    )


def test_build_plans_applies_trim_and_fps_overrides(tmp_path: Path) -> None:
    files = [tmp_path / "Alpha.mkv", tmp_path / "Beta - 01.mkv"]
    metadata = [{"label": "Alpha"}, {"label": "Beta"}]
    cfg = _make_config(
        trim={"0": 12, "beta - 01.mkv": 9},
        trim_end={"alpha": -24},
        change_fps={"alpha.mkv": "set", "beta - 01.mkv": [48000, 1001]},
    )

    plans = planner.build_plans(files, metadata, cfg)

    assert plans[0].trim_start == 12
    assert plans[0].has_trim_start_override
    assert plans[0].trim_end == -24
    assert plans[0].has_trim_end_override
    assert plans[0].use_as_reference

    assert plans[1].trim_start == 9
    assert plans[1].has_trim_start_override
    assert plans[1].fps_override == (48000, 1001)


def test_build_plans_rejects_unsupported_fps_override(tmp_path: Path) -> None:
    files = [tmp_path / "Clip.mkv"]
    metadata = [{"label": "Clip"}]
    invalid_change_fps = cast(
        dict[str, list[int] | str],
        {"clip.mkv": cast(list[int], {"bad": "data"})},
    )
    cfg = _make_config(change_fps=invalid_change_fps)

    with pytest.raises(ValueError):
        planner.build_plans(files, metadata, cfg)
