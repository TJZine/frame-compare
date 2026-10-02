"""Tests for CLI override logic."""

from pathlib import Path

import pytest

from frame_compare.config.loader import get_default_config
from frame_compare.config.overrides import (
    CLIConfigOverrides,
    apply_cli_overrides,
)
from frame_compare.config.schema import (
    ColorConfig,
    ConfigSchema,
    OverlayMode,
    ToneCurve,
    TonemapPreset,
)


def test_apply_cli_overrides_inverts_no_upload() -> None:
    """Test that no_upload flag inverts auto_upload config."""
    config = get_default_config()
    config.slowpics.auto_upload = True

    cli_args = CLIConfigOverrides(no_upload=True)
    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.slowpics.auto_upload is False


def test_cli_overrides_do_not_map_confirm_upload_after_report() -> None:
    """Report-confirmed upload is config-only, not a CLI override surface."""
    config = get_default_config()
    config.slowpics.confirm_upload_after_report = True

    new_config = apply_cli_overrides(config, CLIConfigOverrides(no_upload=True))

    assert new_config.slowpics.confirm_upload_after_report is True


def test_cli_overrides_do_not_map_previous_offsets() -> None:
    """Previous offset reuse mode is config-only, not a CLI override surface."""
    config = get_default_config()
    config.audio_alignment.previous_offsets = "always"

    new_config = apply_cli_overrides(config, CLIConfigOverrides(force_interactive_alignment=False))

    assert new_config.audio_alignment.previous_offsets == "always"


@pytest.mark.parametrize("false_flags", [True, False], ids=["false-flags", "empty-dto"])
def test_apply_cli_overrides_omitted_flags_preserve_config(false_flags: bool) -> None:
    config = get_default_config()
    overrides = CLIConfigOverrides()
    if false_flags:
        config.slowpics.auto_upload = False
        config.audio_alignment.force_interactive = True
        overrides = CLIConfigOverrides(no_upload=False, force_interactive_alignment=False)
    updated = apply_cli_overrides(config, overrides)
    assert updated == config
    if false_flags:
        assert updated.slowpics.auto_upload is False
        assert updated.audio_alignment.force_interactive is True


@pytest.mark.parametrize(
    ("overrides", "color", "expected"),
    [
        (
            CLIConfigOverrides(
                tm_preset=TonemapPreset.FILMIC,
                tm_curve=ToneCurve.REINHARD,
                overlay_mode=OverlayMode.DIAGNOSTIC,
            ),
            None,
            [
                ("color", "preset", TonemapPreset.FILMIC),
                ("color", "tone_curve", ToneCurve.REINHARD),
                ("screenshots", "overlay_mode", OverlayMode.DIAGNOSTIC),
            ],
        ),
        (
            CLIConfigOverrides(force_interactive_alignment=True),
            None,
            [
                ("audio_alignment", "force_interactive", True),
                ("audio_alignment", "use_vsview", True),
            ],
        ),
        (CLIConfigOverrides(input_dir=Path("inputs")), None, [("paths", "input_dir", "inputs")]),
        (
            CLIConfigOverrides(
                user_frames=[12, 24],
                random_frame_count=3,
                dark_frame_count=2,
                bright_frame_count=1,
                motion_frame_count=4,
            ),
            None,
            [
                ("analysis", "user_frames", [12, 24]),
                ("analysis", "random_frame_count", 3),
                ("analysis", "dark_frame_count", 2),
                ("analysis", "bright_frame_count", 1),
                ("analysis", "motion_frame_count", 4),
            ],
        ),
        (
            CLIConfigOverrides(tm_target_nits=400),
            ColorConfig(preset=TonemapPreset.FILMIC),
            [("color", "target_nits", 400)],
        ),
    ],
    ids=["enums", "force-interactive", "input-dir", "selectors", "target"],
)
def test_apply_cli_overrides_maps_explicit_fields(
    overrides: CLIConfigOverrides,
    color: ColorConfig | None,
    expected: list[tuple[str, str, object]],
) -> None:
    config = get_default_config() if color is None else ConfigSchema(color=color)
    updated = apply_cli_overrides(config, overrides)
    for section, field, value in expected:
        actual = getattr(getattr(updated, section), field)
        if isinstance(value, bool):
            assert actual is value
        else:
            assert actual == value
    if overrides.tm_target_nits is not None:
        assert "target_nits" in updated.color.model_fields_set


def test_apply_cli_overrides_preserves_implicit_color_target_for_unrelated_override() -> None:
    """Unrelated CLI overrides must not make default color values explicit."""
    config = ConfigSchema(color=ColorConfig(preset=TonemapPreset.FILMIC))
    assert config.color.model_fields_set == {"preset"}

    new_config = apply_cli_overrides(config, CLIConfigOverrides(random_frame_count=12))

    assert new_config.analysis.random_frame_count == 12
    assert new_config.color.model_fields_set == {"preset"}
