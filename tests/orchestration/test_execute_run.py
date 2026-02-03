"""Unit tests for execute_run orchestration entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from frame_compare.errors import ConfigNotFoundError
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run

# Minimal valid TOML config content
MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
"""


def _create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    """Create a config file in the standard location."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(content)
    return config_file


def _create_video_files(input_dir: Path, *filenames: str) -> None:
    """Create empty video files for testing."""
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (input_dir / name).touch()


def test_execute_run_returns_success_and_records_preflight_timing(
    tmp_path: Path,
) -> None:
    """Given valid workspace → returns success and records preflight timing."""
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    request = RunRequest(root=tmp_path)

    result = asyncio.run(execute_run(request))

    assert result.success is True
    assert result.warnings == []
    assert result.duration_seconds >= 0.0
    assert "preflight" in result.phase_timings
    assert result.phase_timings["preflight"] >= 0.0


def test_execute_run_propagates_config_not_found_error(tmp_path: Path) -> None:
    """Given missing config → preflight error is raised."""
    request = RunRequest(root=tmp_path)

    with pytest.raises(ConfigNotFoundError):
        asyncio.run(execute_run(request))


def test_execute_run_creates_and_closes_http_client_when_missing(
    tmp_path: Path,
) -> None:
    """Given no injected http client → execute_run creates and closes it."""
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    request = RunRequest(root=tmp_path, quiet=True)
    deps = RunDependencies(http_client=None)

    asyncio.run(execute_run(request, deps=deps))

    assert isinstance(deps.http_client, httpx.AsyncClient)
    assert deps.http_client.is_closed is True
