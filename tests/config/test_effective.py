"""Tests for effective run-config resolution helpers."""

from __future__ import annotations

from pathlib import Path

from frame_compare.config.effective import (
    build_preflight_input_dir_override,
    load_effective_config,
    resolve_effective_config,
)
from frame_compare.config.loader import get_default_config
from frame_compare.config.overrides import CLIConfigOverrides


def test_build_preflight_input_dir_override_is_narrow() -> None:
    assert build_preflight_input_dir_override(None) is None
    assert build_preflight_input_dir_override(Path("inputs")) == {"paths": {"input_dir": "inputs"}}


def test_resolve_effective_config_applies_cli_overrides_without_mutating_base() -> None:
    config = get_default_config()
    config.slowpics.auto_upload = True

    updated = resolve_effective_config(
        config,
        CLIConfigOverrides(random_frame_count=7, no_upload=True),
    )

    assert updated.analysis.random_frame_count == 7
    assert updated.slowpics.auto_upload is False
    assert config.analysis.random_frame_count == 10
    assert config.slowpics.auto_upload is True


def test_load_effective_config_passes_base_overrides_through_loader_then_applies_cli() -> None:
    captured: dict[str, object] = {}

    def _fake_load_config(
        config_path: Path | None,
        overrides: dict[str, object] | None = None,
    ):
        captured["config_path"] = config_path
        captured["overrides"] = overrides
        config = get_default_config()
        if overrides is not None:
            paths = overrides.get("paths")
            if isinstance(paths, dict):
                input_dir = paths.get("input_dir")
                if isinstance(input_dir, str):
                    config.paths.input_dir = input_dir
        config.slowpics.auto_upload = True
        return config

    updated = load_effective_config(
        Path("config/config.toml"),
        cli_overrides=CLIConfigOverrides(no_upload=True),
        load_config_fn=_fake_load_config,
        base_overrides={"paths": {"input_dir": "incoming"}},
    )

    assert captured == {
        "config_path": Path("config/config.toml"),
        "overrides": {"paths": {"input_dir": "incoming"}},
    }
    assert updated.paths.input_dir == "incoming"
    assert updated.slowpics.auto_upload is False
