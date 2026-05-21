"""Integration tests for tonemap gating scenarios (Phase 6.5).

SSOT: render-module.md §1.4, §7.2

These tests use mocked module boundaries (no real VS/FFmpeg required by default).
All tests that need real VS/FFmpeg MUST be marked with @pytest.mark.vs_required or @pytest.mark.integration.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.overrides import TonemapCliOverrides
from frame_compare.config.schema import ColorConfig, ConfigSchema, ToneCurve, TonemapPreset
from frame_compare.errors import (
    SourceLoadError,
    TonemapRequiresVapourSynthError,
    VapourSynthNotFoundError,
)
from frame_compare.render.orchestrator import render_screenshots
from frame_compare.render.prepare import (
    resolve_tonemap_settings,
    should_tonemap,
)
from frame_compare.render.types import ScreenshotRenderOptions
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
            preset=TonemapPreset.FILMIC,
            target_nits=250,
            tone_curve=ToneCurve.SPLINE,
            gamma_lift=True,
            contrast_recovery=0.25,
        )
    )

    with patch("frame_compare.vs.tonemap.get_preset_settings") as mock_get_preset:
        # Return a base settings object
        mock_get_preset.return_value = TonemapSettings(
            enabled=True,
            preset=TonemapPreset.FILMIC,
            tone_curve=ToneCurve.BT2390,  # Will be overridden
            target_nits=203,  # Will be overridden
        )

        settings = resolve_tonemap_settings(config)

        # Verify preset was requested
        mock_get_preset.assert_called_once_with(TonemapPreset.FILMIC)

        # Verify config overrides were applied
        assert settings.target_nits == 250
        assert settings.tone_curve == ToneCurve.SPLINE
        assert settings.gamma_lift is True
        assert settings.contrast_recovery == 0.25


def test_resolve_tonemap_settings_applies_cli_overrides() -> None:
    """Verify resolve_tonemap_settings applies CLI overrides with highest priority."""
    config = ConfigSchema(
        color=ColorConfig(
            enable_tonemap=True,
            preset=TonemapPreset.FILMIC,
            target_nits=250,
            tone_curve=ToneCurve.SPLINE,
        )
    )

    cli_overrides: TonemapCliOverrides = {
        "tm_preset": TonemapPreset.REFERENCE,
        "tm_target": 400,
        "tm_curve": ToneCurve.REINHARD,
    }

    with patch("frame_compare.vs.tonemap.get_preset_settings") as mock_get_preset:
        mock_get_preset.return_value = TonemapSettings(
            enabled=True,
            preset=TonemapPreset.REFERENCE,
            tone_curve=ToneCurve.BT2390,
            target_nits=203,
        )

        settings = resolve_tonemap_settings(config, cli_overrides)

        # Verify preset requested was reference, not filmic
        mock_get_preset.assert_called_once_with(TonemapPreset.REFERENCE)

        # Verify CLI overrides overrode both the preset default and the config values
        assert settings.target_nits == 400
        assert settings.tone_curve == ToneCurve.REINHARD


# ─── Probe Failure Determinism Tests ───────────────────────────────────────────


@pytest.mark.integration
def test_probe_failure_disallows_fallback_when_tonemap_enabled(tmp_path: Path) -> None:
    """Verify probe failures propagate when tonemap is enabled (no FFmpeg fallback).

    Scenario: VS load fails, config.color.enable_tonemap=True, renderer="auto".
    Setup: mock ffmpeg_runner to raise SourceLoadError (FC-4015).
    Assert: render_screenshots(...) propagates the probe exception.
    """
    clips = [Path("hdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    mock_runner = MagicMock()
    mock_runner.probe_hdr.side_effect = SourceLoadError(Path("hdr_video.mkv"), "ffprobe failed")

    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()

        # Should propagate probe exception, NOT raise VapourSynthNotFoundError
        with pytest.raises(SourceLoadError, match="ffprobe failed"):
            render_screenshots(
                clips,
                frames,
                tmp_path,
                enable_tonemap_config,
                ScreenshotRenderOptions(renderer="auto", ffmpeg_runner=mock_runner),
            )


# ─── HDR Tonemap Gating Integration Tests ──────────────────────────────────────


@pytest.mark.integration
def test_hdr_enable_tonemap_requires_vs_when_renderer_auto(tmp_path: Path) -> None:
    """HDR + enable_tonemap=True + VS missing → raises TonemapRequiresVapourSynthError from original VS failure."""
    clips = [Path("hdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    from frame_compare.vs.types import HDRMetadata

    mock_runner = MagicMock()
    mock_runner.probe_hdr.return_value = HDRMetadata(
        mastering_display=None,
        max_cll=None,
        max_fall=None,
        color_primaries=9,
        transfer=16,
        matrix=9,
    )

    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()

        # Should raise TonemapRequiresVapourSynthError with the original VS failure as cause
        with pytest.raises(TonemapRequiresVapourSynthError) as exc_info:
            render_screenshots(
                clips,
                frames,
                tmp_path,
                enable_tonemap_config,
                ScreenshotRenderOptions(renderer="auto", ffmpeg_runner=mock_runner),
            )
        assert isinstance(exc_info.value.__cause__, VapourSynthNotFoundError)


@pytest.mark.integration
def test_hdr_enable_tonemap_requires_vs_when_renderer_ffmpeg(tmp_path: Path) -> None:
    """HDR + enable_tonemap=True + renderer=ffmpeg → raises dedicated tonemap gating error."""
    clips = [Path("hdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    from frame_compare.vs.types import HDRMetadata

    mock_runner = MagicMock()
    mock_runner.probe_hdr.return_value = HDRMetadata(
        mastering_display=None,
        max_cll=None,
        max_fall=None,
        color_primaries=9,
        transfer=16,
        matrix=9,
    )

    with pytest.raises(TonemapRequiresVapourSynthError):
        # Should raise explicit tonemap-gating error (no FFmpeg path for HDR+tonemap).
        render_screenshots(
            clips,
            frames,
            tmp_path,
            enable_tonemap_config,
            ScreenshotRenderOptions(renderer="ffmpeg", ffmpeg_runner=mock_runner),
        )


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
            clips,
            frames,
            tmp_path,
            disable_tonemap_config,
            ScreenshotRenderOptions(renderer="auto"),
        )

        assert "hdr_video" in results


@pytest.mark.integration
def test_sdr_allows_ffmpeg_fallback_when_vs_missing(tmp_path: Path) -> None:
    """SDR source + VS missing → fallback to FFmpeg allowed regardless of tonemap setting."""
    clips = [Path("sdr_video.mkv")]
    frames = [0]
    enable_tonemap_config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

    from frame_compare.vs.types import HDRMetadata

    mock_runner = MagicMock()
    mock_runner.probe_hdr.return_value = HDRMetadata(
        mastering_display=None,
        max_cll=None,
        max_fall=None,
        color_primaries=1,
        transfer=1,
        matrix=1,
    )

    with (
        patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls,
        patch("frame_compare.render.orchestrator.render_batch") as mock_batch,
    ):
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()
        mock_batch.return_value = [tmp_path / "out.png"]

        # Should NOT raise — SDR content can use FFmpeg
        results = render_screenshots(
            clips,
            frames,
            tmp_path,
            enable_tonemap_config,
            ScreenshotRenderOptions(renderer="auto", ffmpeg_runner=mock_runner),
        )

        assert "sdr_video" in results
        mock_batch.assert_called_once()
        called_args, _ = mock_batch.call_args
        requests_passed = called_args[0]
        assert len(requests_passed) == 1
        assert requests_passed[0].clip == Path("sdr_video.mkv")
