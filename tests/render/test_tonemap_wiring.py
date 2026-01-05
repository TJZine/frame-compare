"""Integration tests for tonemap gating scenarios (Phase 6.5).

SSOT: render-module.md §1.4, §7.2

These tests use mocked module boundaries (no real VS/FFmpeg required by default).
All tests that need real VS/FFmpeg MUST be marked with @pytest.mark.vs_required or @pytest.mark.integration.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.errors import SourceLoadError, VapourSynthNotFoundError
from frame_compare.render.orchestrator import (
    render_screenshots,
    resolve_tonemap_settings,
    should_tonemap,
)
from frame_compare.vs.types import SourceInfo, TonemapSettings

# ─── Helper Truth Table Tests ──────────────────────────────────────────────────


def test_should_tonemap_truth_table() -> None:
    """Verify should_tonemap logic for all (is_hdr, enable_tonemap) combinations."""
    # Create mock source_info objects
    hdr_source = MagicMock(spec=SourceInfo)
    hdr_source.is_hdr = True

    sdr_source = MagicMock(spec=SourceInfo)
    sdr_source.is_hdr = False

    enable_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    disable_config = ConfigSchema(color=ColorConfig(enable_tonemap=False))

    # Truth table:
    # is_hdr=True,  enable_tonemap=True  → True
    assert should_tonemap(hdr_source, enable_config) is True

    # is_hdr=True,  enable_tonemap=False → False
    assert should_tonemap(hdr_source, disable_config) is False

    # is_hdr=False, enable_tonemap=True  → False
    assert should_tonemap(sdr_source, enable_config) is False

    # is_hdr=False, enable_tonemap=False → False
    assert should_tonemap(sdr_source, disable_config) is False


def test_resolve_tonemap_settings_applies_config_overrides() -> None:
    """Verify resolve_tonemap_settings uses config values correctly."""
    config = ConfigSchema(
        color=ColorConfig(
            enable_tonemap=True,
            preset="filmic",
            target_nits=250,
            tone_curve="spline",
        )
    )

    with patch("frame_compare.vs.tonemap.get_preset_settings") as mock_get_preset:
        # Return a base settings object
        mock_get_preset.return_value = TonemapSettings(
            enabled=True,
            preset="filmic",
            tone_curve="bt2390",  # Will be overridden
            target_nits=203,  # Will be overridden
        )

        settings = resolve_tonemap_settings(config)

        # Verify preset was requested
        mock_get_preset.assert_called_once_with("filmic")

        # Verify config overrides were applied
        assert settings.target_nits == 250
        assert settings.tone_curve == "spline"


# ─── Probe Failure Determinism Tests ───────────────────────────────────────────


@pytest.mark.integration
def test_probe_failure_disallows_fallback_when_tonemap_enabled(tmp_path: Path) -> None:
    """Verify probe failures propagate when tonemap is enabled (no FFmpeg fallback).

    Scenario: VS load fails, config.color.enable_tonemap=True, renderer="auto".
    Setup: patch probe_is_hdr_ffprobe to raise SourceLoadError (FC-4015).
    Assert: render_screenshots(...) propagates the probe exception.
    """
    clips = [Path("hdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    with (
        patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls,
        patch(
            "frame_compare.render.orchestrator.probe_is_hdr_ffprobe",
            side_effect=SourceLoadError(Path("hdr_video.mkv"), "ffprobe failed"),
        ),
    ):
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()

        # Should propagate probe exception, NOT raise VapourSynthNotFoundError
        with pytest.raises(SourceLoadError, match="ffprobe failed"):
            render_screenshots(clips, frames, tmp_path, enable_tonemap_config, renderer="auto")


# ─── HDR Tonemap Gating Integration Tests ──────────────────────────────────────


@pytest.mark.integration
def test_hdr_enable_tonemap_requires_vs_when_renderer_auto(tmp_path: Path) -> None:
    """HDR + enable_tonemap=True + VS missing → raises original VS failure."""
    clips = [Path("hdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    with (
        patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls,
        patch("frame_compare.render.orchestrator.probe_is_hdr_ffprobe", return_value=True),
    ):
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()

        # Should re-raise VS failure (not fall back to FFmpeg)
        with pytest.raises(VapourSynthNotFoundError):
            render_screenshots(clips, frames, tmp_path, enable_tonemap_config, renderer="auto")


@pytest.mark.integration
def test_hdr_enable_tonemap_requires_vs_when_renderer_ffmpeg(tmp_path: Path) -> None:
    """HDR + enable_tonemap=True + renderer=ffmpeg → raises VapourSynthNotFoundError."""
    clips = [Path("hdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    with (
        patch("frame_compare.render.orchestrator.probe_is_hdr_ffprobe", return_value=True),
        pytest.raises(VapourSynthNotFoundError),
    ):
        # Should raise VS not found (tonemap required, no FFmpeg path for HDR)
        render_screenshots(clips, frames, tmp_path, enable_tonemap_config, renderer="ffmpeg")


@pytest.mark.integration
def test_hdr_disable_tonemap_allows_ffmpeg_when_vs_missing(tmp_path: Path) -> None:
    """HDR + enable_tonemap=False + VS missing → fallback to FFmpeg allowed."""
    clips = [Path("hdr_video.mkv")]
    frames = [0]
    disable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=False))

    with (
        patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls,
        patch("frame_compare.render.orchestrator.render_batch") as mock_batch,
    ):
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()
        mock_batch.return_value = [tmp_path / "out.png"]

        # Should NOT raise — fallback allowed because tonemap is disabled
        results = render_screenshots(
            clips, frames, tmp_path, disable_tonemap_config, renderer="auto"
        )

        assert "hdr_video" in results


@pytest.mark.integration
def test_sdr_allows_ffmpeg_fallback_when_vs_missing(tmp_path: Path) -> None:
    """SDR source + VS missing → fallback to FFmpeg allowed regardless of tonemap setting."""
    clips = [Path("sdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    with (
        patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls,
        patch("frame_compare.render.orchestrator.probe_is_hdr_ffprobe", return_value=False),
        patch("frame_compare.render.orchestrator.render_batch") as mock_batch,
    ):
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()
        mock_batch.return_value = [tmp_path / "out.png"]

        # Should NOT raise — SDR content can use FFmpeg
        results = render_screenshots(
            clips, frames, tmp_path, enable_tonemap_config, renderer="auto"
        )

        assert "sdr_video" in results
