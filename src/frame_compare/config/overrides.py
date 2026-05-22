"""CLI override mapping and application."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict, cast

from pydantic import ValidationError

from frame_compare.config.schema import ConfigSchema, ToneCurve, TonemapPreset
from frame_compare.config.utils import deep_merge
from frame_compare.errors import ConfigValidationError, normalize_pydantic_errors


class TonemapCliOverrides(TypedDict, total=False):
    tm_preset: TonemapPreset | None
    tm_target: int | None
    tm_curve: ToneCurve | None


CLI_OVERRIDE_MAP: dict[str, str] = {
    "tm_preset": "color.preset",
    "tm_target": "color.target_nits",
    "tm_curve": "color.tone_curve",
    "frame_count": "analysis.frame_count",
    "seed": "analysis.random_seed",
    "overlay": "screenshots.overlay_mode",
    "no_upload": "slowpics.auto_upload",
    "force_interactive_alignment": "audio_alignment.force_interactive",
    "input": "paths.input_dir",
}

_INVERTED_FLAGS: frozenset[str] = frozenset({"no_upload"})
_FLAG_ONLY_OVERRIDES: frozenset[str] = frozenset(
    {
        "no_upload",
        "force_interactive_alignment",
    }
)


def apply_cli_overrides(
    config: ConfigSchema,
    cli_args: Mapping[str, object],
) -> ConfigSchema:
    """Apply CLI arguments as config overrides."""
    from frame_compare.config.schema import ConfigSchema

    overrides: dict[str, object] = {}
    for cli_name, config_path in CLI_OVERRIDE_MAP.items():
        if cli_name not in cli_args or cli_args[cli_name] is None:
            continue

        # Flag-style booleans (default False) must not clobber config when omitted.
        # Since Typer provides False even when not explicitly passed, treat only
        # an explicit True as an override for these options.
        if cli_name in _FLAG_ONLY_OVERRIDES and cli_args[cli_name] is not True:
            continue

        value = cli_args[cli_name]
        if cli_name in _INVERTED_FLAGS:
            value = not value

        _set_nested(overrides, config_path, value)

    if cli_args.get("force_interactive_alignment") is True:
        _set_nested(overrides, "audio_alignment.use_vspreview", True)

    if not overrides:
        return config

    base_dict = config.model_dump()
    merged = deep_merge(base_dict, overrides)

    try:
        # Cast merged dict to Any to satisfy static type checkers on kwargs unpacking
        return ConfigSchema.model_validate(cast(Any, merged))
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        raise ConfigValidationError(normalized) from exc


def _set_nested(d: dict[str, object], path: str, value: object) -> None:
    """Set a value in a nested dict using dotted path notation."""
    keys = path.split(".")
    current: dict[str, object] = d
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        next_level = current[key]
        if not isinstance(next_level, dict):
            current[key] = {}
            next_level = current[key]
        current = cast(dict[str, object], next_level)
    current[keys[-1]] = value
