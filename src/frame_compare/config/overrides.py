"""CLI override mapping and application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

from pydantic import BaseModel, ValidationError

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
    user_frames: list[int] | None = None
    random_frame_count: int | None = None
    dark_frame_count: int | None = None
    bright_frame_count: int | None = None
    motion_frame_count: int | None = None
    seed: int | None = None
    overlay_mode: OverlayMode | None = None
    no_upload: bool = False
    force_interactive_alignment: bool = False


class CLIConfigOverrideSource(Protocol):
    """Dependency-light source of values that may override effective config."""

    @property
    def input_dir(self) -> Path | None: ...

    @property
    def tm_preset(self) -> TonemapPreset | None: ...

    @property
    def tm_target_nits(self) -> int | None: ...

    @property
    def tm_curve(self) -> ToneCurve | None: ...

    @property
    def user_frames(self) -> list[int] | None: ...

    @property
    def random_frame_count(self) -> int | None: ...

    @property
    def dark_frame_count(self) -> int | None: ...

    @property
    def bright_frame_count(self) -> int | None: ...

    @property
    def motion_frame_count(self) -> int | None: ...

    @property
    def seed(self) -> int | None: ...

    @property
    def overlay_mode(self) -> OverlayMode | None: ...

    @property
    def no_upload(self) -> bool: ...

    @property
    def force_interactive_alignment(self) -> bool: ...


def cli_config_overrides_from(source: CLIConfigOverrideSource) -> CLIConfigOverrides:
    """Project one canonical CLI override source into effective-config inputs."""
    return CLIConfigOverrides(
        input_dir=source.input_dir,
        tm_preset=source.tm_preset,
        tm_target_nits=source.tm_target_nits,
        tm_curve=source.tm_curve,
        user_frames=source.user_frames,
        random_frame_count=source.random_frame_count,
        dark_frame_count=source.dark_frame_count,
        bright_frame_count=source.bright_frame_count,
        motion_frame_count=source.motion_frame_count,
        seed=source.seed,
        overlay_mode=source.overlay_mode,
        no_upload=source.no_upload,
        force_interactive_alignment=source.force_interactive_alignment,
    )


CLI_OVERRIDE_MAP: dict[str, str] = {
    "tm_preset": "color.preset",
    "tm_target": "color.target_nits",
    "tm_curve": "color.tone_curve",
    "frames": "analysis.user_frames",
    "random_frame_count": "analysis.random_frame_count",
    "dark_frame_count": "analysis.dark_frame_count",
    "bright_frame_count": "analysis.bright_frame_count",
    "motion_frame_count": "analysis.motion_frame_count",
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
        updated = ConfigSchema.model_validate(cast(Any, merged))
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        raise ConfigValidationError(normalized) from exc

    _restore_explicit_fields(updated, config, overrides)
    return updated


def _restore_explicit_fields(
    updated: BaseModel,
    original: BaseModel,
    overrides: dict[str, object],
) -> None:
    """Preserve which nested config fields were explicitly supplied."""
    _replace_model_fields_set(updated, original.model_fields_set | set(overrides))
    for key in type(updated).model_fields:
        updated_child = getattr(updated, key, None)
        original_child = getattr(original, key, None)
        if isinstance(updated_child, BaseModel) and isinstance(original_child, BaseModel):
            value = overrides.get(key, {})
            if isinstance(value, dict):
                _restore_explicit_fields(
                    updated_child, original_child, cast(dict[str, object], value)
                )
            else:
                _replace_model_fields_set(updated_child, original_child.model_fields_set)


def _replace_model_fields_set(model: BaseModel, fields: set[str]) -> None:
    fields_set = model.model_fields_set
    fields_set.clear()
    fields_set.update(fields)


def _cli_override_values(cli_args: CLIConfigOverrides) -> dict[str, object]:
    return {
        "tm_preset": cli_args.tm_preset,
        "tm_target": cli_args.tm_target_nits,
        "tm_curve": cli_args.tm_curve,
        "frames": cli_args.user_frames,
        "random_frame_count": cli_args.random_frame_count,
        "dark_frame_count": cli_args.dark_frame_count,
        "bright_frame_count": cli_args.bright_frame_count,
        "motion_frame_count": cli_args.motion_frame_count,
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
