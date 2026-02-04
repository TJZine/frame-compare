"""Tests for CLI override logic."""

from typing import Any

from frame_compare.config.loader import get_default_config
from frame_compare.config.overrides import apply_cli_overrides


def test_apply_cli_overrides_basic() -> None:
    """Test applying basic CLI overrides."""
    config = get_default_config()
    cli_args: dict[str, Any] = {"frame_count": 50}

    new_config = apply_cli_overrides(config, cli_args)
    assert new_config.analysis.frame_count == 50
    # Original config unchanged (Pydantic models are mutable but we model_dump -> new instance)
    # Wait, apply_cli_overrides returns a new instance.


def test_apply_cli_overrides_inverts_no_upload() -> None:
    """Test that no_upload flag inverts auto_upload config."""
    config = get_default_config()
    # Default auto_upload is True
    assert config.slowpics.auto_upload is True

    cli_args: dict[str, Any] = {"no_upload": True}
    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.slowpics.auto_upload is False


def test_apply_cli_overrides_ignores_none_values() -> None:
    """Test that None values in CLI args are ignored."""
    config = get_default_config()
    cli_args: dict[str, Any] = {"frame_count": None}

    new_config = apply_cli_overrides(config, cli_args)
    assert new_config.analysis.frame_count == 10  # Default


def test_apply_cli_overrides_ignores_unknown_keys() -> None:
    """Test that unknown CLI keys are ignored."""
    config = get_default_config()
    cli_args: dict[str, Any] = {"unknown_arg": "value"}

    new_config = apply_cli_overrides(config, cli_args)
    assert new_config == config


def test_apply_cli_overrides_seed_maps_to_analysis_random_seed() -> None:
    """Test that seed maps to analysis.random_seed."""
    config = get_default_config()
    cli_args: dict[str, Any] = {"seed": 123}

    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.analysis.random_seed == 123


def test_apply_cli_overrides_force_interactive_alignment_sets_force_and_use_vspreview() -> None:
    """Test force_interactive_alignment implies use_vspreview."""
    config = get_default_config()
    assert config.audio_alignment.force_interactive is False
    assert config.audio_alignment.use_vspreview is False

    cli_args: dict[str, Any] = {"force_interactive_alignment": True}
    new_config = apply_cli_overrides(config, cli_args)

    assert new_config.audio_alignment.force_interactive is True
    assert new_config.audio_alignment.use_vspreview is True
