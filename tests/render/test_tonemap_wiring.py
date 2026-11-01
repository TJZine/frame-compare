from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.loader import get_default_config
from frame_compare.config.overrides import CLIConfigOverrides, apply_cli_overrides
from frame_compare.config.schema import ColorConfig, ConfigSchema, ToneCurve, TonemapPreset
from frame_compare.config.schema_enums import TonemapSpeed
from frame_compare.render.prepare import (
    prepare_clip_for_render,
    resolve_tonemap_settings,
)
from frame_compare.utils.media_facts import PresentationState
from frame_compare.vs.errors import TonemapRequiresVapourSynthError, VapourSynthNotFoundError
from frame_compare.vs.types import HDRMetadata, TonemapSettings


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


@pytest.mark.parametrize(
    "color, overrides, preset_settings, expected, expected_preset",
    [
        pytest.param(
            ColorConfig(
                enable_tonemap=True,
                preset=TonemapPreset.SPLINE,
                tonemap_speed=TonemapSpeed.FAST,
                target_nits=250,
                tone_curve=ToneCurve.SPLINE,
                gamma_lift=True,
                contrast_recovery=0.25,
            ),
            CLIConfigOverrides(
                tm_preset=TonemapPreset.REFERENCE, tm_target_nits=400, tm_curve=ToneCurve.REINHARD
            ),
            TonemapSettings(),
            {
                "target_nits": 400,
                "tonemap_speed": TonemapSpeed.FAST,
                "tone_curve": ToneCurve.REINHARD,
                "gamma_lift": True,
                "contrast_recovery": 0.25,
            },
            TonemapPreset.REFERENCE,
            id="config_cli_overrides",
        ),
        pytest.param(
            ColorConfig(preset=TonemapPreset.SPLINE),
            None,
            TonemapSettings(target_nits=150),
            {"target_nits": 150},
            None,
            id="implicit_target",
        ),
    ],
)
def test_resolve_tonemap_settings_cases(
    color: ColorConfig,
    overrides: CLIConfigOverrides | None,
    preset_settings: TonemapSettings,
    expected: dict[str, object],
    expected_preset: TonemapPreset | None,
) -> None:
    with patch(
        "frame_compare.vs.tonemap.get_preset_settings", return_value=preset_settings
    ) as get_preset:
        config = ConfigSchema(color=color)
        if overrides:
            config = apply_cli_overrides(config, overrides)
        settings = resolve_tonemap_settings(config)
    if expected_preset is not None:
        get_preset.assert_called_once_with(expected_preset)
    for field, value in expected.items():
        if field in ("tone_curve", "gamma_lift"):
            assert getattr(settings, field) is value
        else:
            assert getattr(settings, field) == value


def test_fast_tonemap_speed_reaches_still_preparation_with_detection_disabled() -> None:
    from frame_compare.vs.types import TonemapResult

    source = MagicMock(is_hdr=True, width=1920, height=1080, num_frames=3, hdr_metadata=None)
    output = MagicMock()
    applied = MagicMock()
    config = ConfigSchema(color=ColorConfig(tonemap_speed=TonemapSpeed.FAST))

    with (
        patch("frame_compare.vs.loader.DefaultVSLoader") as loader_cls,
        patch("frame_compare.vs.tonemap.apply_tonemap") as apply_tonemap,
    ):
        loader_cls.return_value.load.return_value = source
        apply_tonemap.return_value = TonemapResult(output, applied)
        prepared = prepare_clip_for_render(
            Path("hdr_video.mkv"), "vapoursynth", config, ffmpeg_runner=MagicMock()
        )

    assert prepared.prepared_clip is output
    settings = apply_tonemap.call_args.args[1]
    assert settings.tonemap_speed is TonemapSpeed.FAST
    assert settings.dynamic_peak_detection is False
    assert apply_tonemap.call_args.kwargs == {"still_image": True}


@pytest.mark.parametrize("interruption_stage", ["before", "source", "fallback"])
def test_preparation_stops_native_admission_after_interruption(interruption_stage: str) -> None:
    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint

    async def run() -> None:
        task = asyncio.current_task()
        assert task is not None
        runner = MagicMock()
        source = MagicMock(is_hdr=True, width=1920, height=1080)
        config = ConfigSchema(color=ColorConfig(enable_tonemap=True))

        def load(_path: Path) -> object:
            task.cancel()
            if interruption_stage == "fallback":
                raise VapourSynthNotFoundError()
            return source

        with (
            patch("frame_compare.vs.loader.DefaultVSLoader") as loader_cls,
            patch("frame_compare.vs.tonemap.apply_tonemap") as tonemap,
        ):
            loader_cls.return_value.load.side_effect = load
            if interruption_stage == "before":
                task.cancel()
            with pytest.raises(_RunInterrupt):
                prepare_clip_for_render(Path("ref.mkv"), "auto", config, ffmpeg_runner=runner)
            assert loader_cls.return_value.load.call_count == (
                0 if interruption_stage == "before" else 1
            )
            tonemap.assert_not_called()
            runner.probe_hdr.assert_not_called()
        assert task.cancelling() == 1
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())


@pytest.mark.parametrize(
    "stage, expected_calls",
    [
        ("before_probe", []),
        ("probe_true", ["probe"]),
        ("probe_false", ["probe"]),
        ("libplacebo_frame", ["probe", "frame"]),
        ("fallback_frame", ["frame"]),
        ("conversion", ["probe", "frame", "bicubic"]),
        ("placebo_failure", ["probe", "frame", "props", "placebo"]),
        ("placebo_success", ["probe", "frame", "props", "placebo"]),
    ],
)
def test_preparation_tonemap_dispatch_stops_after_interruption(
    stage: str, expected_calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import vapoursynth as vs

    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint
    from frame_compare.vs.tonemap_runtime import LibplaceboRuntimeState

    calls: list[str] = []
    for variable in (
        "FRAME_COMPARE_REQUIRE_LIBPLACEBO",
        "FRAME_COMPARE_DISABLE_LIBPLACEBO",
        "FRAME_COMPARE_LIBPLACEBO_PROBE",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(
        "frame_compare.vs.tonemap._LIBPLACEBO_RUNTIME_STATE", LibplaceboRuntimeState()
    )

    async def run() -> None:
        task = asyncio.current_task()
        assert task is not None
        clip = MagicMock()
        clip.format.id = vs.RGBS
        clip.format.color_family = vs.YUV if stage == "conversion" else vs.RGB
        clip.format.bits_per_sample = 10 if stage == "conversion" else 16
        core = MagicMock()
        source = MagicMock(clip=clip, is_hdr=True, width=1920, height=1080, hdr_metadata=None)

        def detect_plugins(_core: object) -> dict[str, bool]:
            if stage == "before_probe":
                task.cancel()
            return {"libplacebo": stage != "fallback_frame"}

        def probe() -> bool:
            calls.append("probe")
            if stage in {"probe_true", "probe_false"}:
                task.cancel()
            return stage != "probe_false"

        def frame(_index: int) -> MagicMock:
            calls.append("frame")
            if stage in {"libplacebo_frame", "fallback_frame"}:
                task.cancel()
            return MagicMock(props={"_Matrix": 9, "_Transfer": 16, "_Primaries": 9})

        def operation(name: str):
            def native(*_args: object, **_kwargs: object) -> MagicMock:
                calls.append(name)
                if (name == "placebo" and stage in {"placebo_failure", "placebo_success"}) or (
                    name == "bicubic" and stage == "conversion"
                ):
                    task.cancel()
                if name == "placebo" and stage == "placebo_failure":
                    raise RuntimeError("native tonemap failed")
                return clip

            return native

        clip.get_frame.side_effect = frame
        clip.resize.Bicubic.side_effect = operation("bicubic")
        clip.std.SetFrameProps.side_effect = operation("props")
        core.placebo.Tonemap.side_effect = operation("placebo")
        clip.resize.Point.side_effect = operation("point")
        clip.std.Expr.side_effect = operation("expr")
        clip.std.Levels.side_effect = operation("levels")
        monkeypatch.setattr("frame_compare.vs.env.detect_plugins", detect_plugins)
        monkeypatch.setattr("frame_compare.vs.tonemap_runtime.probe_libplacebo_runtime", probe)
        monkeypatch.setattr(vs, "core", core)
        with patch("frame_compare.vs.loader.DefaultVSLoader") as loader_cls:
            loader_cls.return_value.load.return_value = source
            with pytest.raises(_RunInterrupt):
                prepare_clip_for_render(
                    Path("hdr.mkv"), "vapoursynth", get_default_config(), ffmpeg_runner=MagicMock()
                )
        # Exercise the real prepare -> dispatch -> conversion/libplacebo/fallback
        # chain; only native entry points and the probe's external result are faked.
        assert calls == expected_calls
        assert task.cancelling() == 1
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
