"""Tests for CLI override logic."""

from dataclasses import fields
from pathlib import Path

from frame_compare.config.loader import get_default_config
from frame_compare.config.overrides import (
    CLI_OVERRIDE_MAP,
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


def test_apply_cli_overrides_basic() -> None:
    """Test applying basic CLI overrides."""
    config = get_default_config()
    cli_args = CLIConfigOverrides(random_frame_count=50)

    new_config = apply_cli_overrides(config, cli_args)
    assert new_config.analysis.random_frame_count == 50
    # Original config unchanged (Pydantic models are mutable but we model_dump -> new instance)
    # Wait, apply_cli_overrides returns a new instance.


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

    assert "slowpics.confirm_upload_after_report" not in CLI_OVERRIDE_MAP.values()
    cli_override_fields = {field.name for field in fields(CLIConfigOverrides)}
    assert "confirm_upload_after_report" not in cli_override_fields
    assert new_config.slowpics.auto_upload is False
    assert new_config.slowpics.confirm_upload_after_report is True


def test_cli_overrides_do_not_map_previous_offsets() -> None:
    """Previous offset reuse mode is config-only, not a CLI override surface."""
    config = get_default_config()
    config.audio_alignment.previous_offsets = "always"

    new_config = apply_cli_overrides(config, CLIConfigOverrides(force_interactive_alignment=False))

    assert "audio_alignment.previous_offsets" not in CLI_OVERRIDE_MAP.values()
    cli_override_fields = {field.name for field in fields(CLIConfigOverrides)}
    assert "previous_offsets" not in cli_override_fields
    assert new_config.audio_alignment.previous_offsets == "always"


def test_apply_cli_overrides_does_not_override_false_flag_defaults() -> None:
    """Flag-style booleans default False and must not override config when omitted."""
    config = get_default_config()
    config.slowpics.auto_upload = False
    config.audio_alignment.force_interactive = True

    cli_args = CLIConfigOverrides(no_upload=False, force_interactive_alignment=False)
    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.slowpics.auto_upload is False
    assert new_config.audio_alignment.force_interactive is True


def test_apply_cli_overrides_ignores_none_values() -> None:
    """Test that None values in CLI args are ignored."""
    config = get_default_config()
    cli_args = CLIConfigOverrides(random_frame_count=None)

    new_config = apply_cli_overrides(config, cli_args)
    assert new_config.analysis.random_frame_count == 10  # Default


def test_apply_cli_overrides_empty_dto_returns_original_config() -> None:
    """No override fields set returns the original config unchanged."""
    config = get_default_config()
    cli_args = CLIConfigOverrides()

    new_config = apply_cli_overrides(config, cli_args)
    assert new_config == config


def test_apply_cli_overrides_seed_maps_to_analysis_random_seed() -> None:
    """Test that seed maps to analysis.random_seed."""
    config = get_default_config()
    cli_args = CLIConfigOverrides(seed=123)

    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.analysis.random_seed == 123


def test_apply_cli_overrides_accepts_enum_cli_values() -> None:
    """Enum-backed CLI choices should flow through override application unchanged."""
    config = get_default_config()
    cli_args = CLIConfigOverrides(
        tm_preset=TonemapPreset.FILMIC,
        tm_curve=ToneCurve.REINHARD,
        overlay_mode=OverlayMode.DIAGNOSTIC,
    )

    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.color.preset == TonemapPreset.FILMIC
    assert new_config.color.tone_curve == ToneCurve.REINHARD
    assert new_config.screenshots.overlay_mode == OverlayMode.DIAGNOSTIC


def test_apply_cli_overrides_force_interactive_alignment_sets_force_and_use_vspreview() -> None:
    """Test force_interactive_alignment implies use_vspreview."""
    config = get_default_config()
    assert config.audio_alignment.force_interactive is False
    assert config.audio_alignment.use_vspreview is False

    cli_args = CLIConfigOverrides(force_interactive_alignment=True)
    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.audio_alignment.force_interactive is True
    assert new_config.audio_alignment.use_vspreview is True


def test_apply_cli_overrides_input_dir_maps_to_paths_input_dir() -> None:
    """Input directory override maps to paths.input_dir."""
    config = get_default_config()
    new_config = apply_cli_overrides(config, CLIConfigOverrides(input_dir=Path("inputs")))

    assert new_config.paths.input_dir == "inputs"


def test_apply_cli_overrides_preserves_implicit_color_target_for_unrelated_override() -> None:
    """Unrelated CLI overrides must not make default color values explicit."""
    config = ConfigSchema(color=ColorConfig(preset=TonemapPreset.FILMIC))
    assert config.color.model_fields_set == {"preset"}

    new_config = apply_cli_overrides(config, CLIConfigOverrides(random_frame_count=12))

    assert new_config.analysis.random_frame_count == 12
    assert new_config.color.model_fields_set == {"preset"}


def test_apply_cli_overrides_maps_explicit_frame_selectors() -> None:
    config = get_default_config()

    new_config = apply_cli_overrides(
        config,
        CLIConfigOverrides(
            user_frames=[12, 24],
            random_frame_count=3,
            dark_frame_count=2,
            bright_frame_count=1,
            motion_frame_count=4,
        ),
    )

    assert new_config.analysis.user_frames == [12, 24]
    assert new_config.analysis.random_frame_count == 3
    assert new_config.analysis.dark_frame_count == 2
    assert new_config.analysis.bright_frame_count == 1
    assert new_config.analysis.motion_frame_count == 4


def test_apply_cli_overrides_marks_cli_target_as_explicit_color_override() -> None:
    """CLI target override remains explicit after config rebuild."""
    config = ConfigSchema(color=ColorConfig(preset=TonemapPreset.FILMIC))

    new_config = apply_cli_overrides(config, CLIConfigOverrides(tm_target_nits=400))

    assert new_config.color.target_nits == 400
    assert "target_nits" in new_config.color.model_fields_set
