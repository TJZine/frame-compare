"""CLI override mapping and application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from frame_compare.errors import ConfigValidationError, normalize_pydantic_errors

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema

CLI_OVERRIDE_MAP: dict[str, str] = {
    "tm_preset": "color.preset",
    "tm_target": "color.target_nits",
    "tm_curve": "color.tone_curve",
    "frame_count": "analysis.frame_count",
    "random_seed": "analysis.random_seed",
    "overlay": "screenshots.overlay_mode",
    "no_upload": "slowpics.auto_upload",
    "input": "paths.input_dir",
    "output": "report.output_dir",
}

_INVERTED_FLAGS: frozenset[str] = frozenset({"no_upload"})


def apply_cli_overrides(
    config: ConfigSchema,
    cli_args: dict[str, object],
) -> ConfigSchema:
    """Apply CLI arguments as config overrides."""
    from frame_compare.config.schema import ConfigSchema

    overrides: dict[str, object] = {}
    for cli_name, config_path in CLI_OVERRIDE_MAP.items():
        if cli_name not in cli_args or cli_args[cli_name] is None:
            continue

        value = cli_args[cli_name]
        if cli_name in _INVERTED_FLAGS:
            value = not value

        _set_nested(overrides, config_path, value)

    if not overrides:
        return config

    base_dict = config.model_dump()
    merged = _deep_merge(base_dict, overrides)

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


def _deep_merge(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    """Deep merge two dicts. Updates take precedence."""
    result: dict[str, object] = dict(base)
    for key, value in updates.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            result[key] = _deep_merge(
                cast(dict[str, object], base_value),
                cast(dict[str, object], value),
            )
        else:
            result[key] = value
    return result
