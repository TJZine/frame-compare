from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.overrides import TonemapCliOverrides
from frame_compare.config.schema import ColorConfig, ConfigSchema, ToneCurve, TonemapPreset
from frame_compare.render.prepare import (
    prepare_clip_for_render,
    resolve_tonemap_settings,
    should_tonemap,
)
from frame_compare.utils.media_facts import PresentationState
from frame_compare.vs.errors import TonemapRequiresVapourSynthError, VapourSynthNotFoundError
from frame_compare.vs.types import HDRMetadata, SourceInfo, TonemapSettings


def test_should_tonemap_truth_table() -> None:
    hdr_source = MagicMock(spec=SourceInfo, is_hdr=True)
    sdr_source = MagicMock(spec=SourceInfo, is_hdr=False)
    enabled = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    disabled = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    assert should_tonemap(hdr_source, enabled) is True
    assert should_tonemap(hdr_source, disabled) is False
    assert should_tonemap(sdr_source, enabled) is False
    assert should_tonemap(sdr_source, disabled) is False


def test_resolve_tonemap_settings_applies_config_and_cli_overrides() -> None:
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
    cli_overrides: TonemapCliOverrides = {
        "tm_preset": TonemapPreset.REFERENCE,
        "tm_target": 400,
        "tm_curve": ToneCurve.REINHARD,
    }
    with patch("frame_compare.vs.tonemap.get_preset_settings") as get_preset:
        get_preset.return_value = TonemapSettings()
        settings = resolve_tonemap_settings(config, cli_overrides)
    get_preset.assert_called_once_with(TonemapPreset.REFERENCE)
    assert settings.target_nits == 400
    assert settings.tone_curve is ToneCurve.REINHARD
    assert settings.gamma_lift is True
    assert settings.contrast_recovery == 0.25


def test_resolve_tonemap_settings_preserves_implicit_preset_target() -> None:
    config = ConfigSchema(color=ColorConfig(preset=TonemapPreset.FILMIC))
    with patch("frame_compare.vs.tonemap.get_preset_settings") as get_preset:
        get_preset.return_value = TonemapSettings(target_nits=150)
        settings = resolve_tonemap_settings(config)
    assert settings.target_nits == 150


def test_auto_sdr_fallback_uses_canonical_classification_without_probe() -> None:
    runner = MagicMock()
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    with patch("frame_compare.vs.loader.DefaultVSLoader") as loader_cls:
        loader_cls.return_value.load.side_effect = VapourSynthNotFoundError()
        prepared = prepare_clip_for_render(
            Path("sdr_video.mkv"),
            "auto",
            config,
            ffmpeg_runner=runner,
            source_is_hdr=False,
        )
    runner.probe_hdr.assert_not_called()
    assert prepared.presentation_state is PresentationState.SDR
    assert prepared.source_is_hdr is False


def test_auto_hdr_fallback_uses_canonical_classification_without_probe() -> None:
    runner = MagicMock()
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    with patch("frame_compare.vs.loader.DefaultVSLoader") as loader_cls:
        loader_cls.return_value.load.side_effect = VapourSynthNotFoundError()
        prepared = prepare_clip_for_render(
            Path("hdr_video.mkv"),
            "auto",
            config,
            ffmpeg_runner=runner,
            source_is_hdr=True,
        )
    runner.probe_hdr.assert_not_called()
    assert prepared.presentation_state is PresentationState.HDR_TONEMAP_OFF
    assert prepared.source_is_hdr is True


def test_auto_fallback_probes_only_for_direct_calls_without_classification() -> None:
    runner = MagicMock()
    runner.probe_hdr.return_value = HDRMetadata(
        mastering_display=None,
        max_cll=None,
        max_fall=None,
        color_primaries=1,
        transfer=1,
        matrix=1,
    )
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    with patch("frame_compare.vs.loader.DefaultVSLoader") as loader_cls:
        loader_cls.return_value.load.side_effect = VapourSynthNotFoundError()
        prepared = prepare_clip_for_render(
            Path("sdr_video.mkv"), "auto", config, ffmpeg_runner=runner
        )
    runner.probe_hdr.assert_called_once_with(Path("sdr_video.mkv"))
    assert prepared.source_is_hdr is False


def test_canonical_hdr_gate_avoids_probe_for_ffmpeg() -> None:
    runner = MagicMock()
    config = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    with pytest.raises(TonemapRequiresVapourSynthError):
        prepare_clip_for_render(
            Path("hdr_video.mkv"),
            "ffmpeg",
            config,
            ffmpeg_runner=runner,
            source_is_hdr=True,
        )
    runner.probe_hdr.assert_not_called()


def test_direct_ffmpeg_tonemap_gate_probes_once_without_classification() -> None:
    runner = MagicMock()
    runner.probe_hdr.return_value = HDRMetadata(
        mastering_display=None,
        max_cll=None,
        max_fall=None,
        color_primaries=1,
        transfer=1,
        matrix=1,
    )
    config = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    prepared = prepare_clip_for_render(
        Path("sdr_video.mkv"), "ffmpeg", config, ffmpeg_runner=runner
    )
    runner.probe_hdr.assert_called_once_with(Path("sdr_video.mkv"))
    assert prepared.presentation_state is PresentationState.SDR
