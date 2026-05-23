"""CLI override mapping and application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, cast

from pydantic import ValidationError

from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.schema import ConfigSchema, OverlayMode, ToneCurve, TonemapPreset
from frame_compare.config.utils import deep_merge
from frame_compare.errors import normalize_pydantic_errors


class TonemapCliOverrides(TypedDict, total=False):
    tm_preset: TonemapPreset | None
    tm_target: int | None
    tm_curve: ToneCurve | None


@dataclass(frozen=True, slots=True)
class CLIConfigOverrides:
    """Typed set of CLI values that persist into config overrides."""

    input_dir: Path | None = None
    tm_preset: TonemapPreset | None = None
    tm_target_nits: int | None = None
    tm_curve: ToneCurve | None = None
    frame_count: int | None = None
    seed: int | None = None
    overlay_mode: OverlayMode | None = None
    no_upload: bool = False
    force_interactive_alignment: bool = False


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
    cli_args: CLIConfigOverrides,
) -> ConfigSchema:
    """Apply CLI arguments as config overrides."""
    from frame_compare.config.schema import ConfigSchema

    overrides: dict[str, object] = {}
    cli_values = _cli_override_values(cli_args)
    for cli_name, value in cli_values.items():
        if value is None:
            continue

        # Flag-style booleans (default False) must not clobber config when omitted.
        # Since Typer provides False even when not explicitly passed, treat only
        # an explicit True as an override for these options.
        if cli_name in _FLAG_ONLY_OVERRIDES and value is not True:
            continue

        if cli_name in _INVERTED_FLAGS:
            value = not value

        _set_nested(overrides, CLI_OVERRIDE_MAP[cli_name], value)

    if cli_args.force_interactive_alignment is True:
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


def _cli_override_values(cli_args: CLIConfigOverrides) -> dict[str, object]:
    return {
        "tm_preset": cli_args.tm_preset,
        "tm_target": cli_args.tm_target_nits,
        "tm_curve": cli_args.tm_curve,
        "frame_count": cli_args.frame_count,
        "seed": cli_args.seed,
        "overlay": cli_args.overlay_mode,
        "no_upload": cli_args.no_upload,
        "force_interactive_alignment": cli_args.force_interactive_alignment,
        "input": str(cli_args.input_dir) if cli_args.input_dir is not None else None,
    }


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
