"""Configuration loader that parses and validates user-provided TOML."""

from __future__ import annotations

import tomllib
from dataclasses import fields, is_dataclass
from typing import Any, Dict

from .datatypes import (
    AnalysisConfig,
    AppConfig,
    AudioAlignmentConfig,
    CLIConfig,
    ColorConfig,
    NamingConfig,
    OverridesConfig,
    PathsConfig,
    RuntimeConfig,
    ScreenshotConfig,
    SlowpicsConfig,
    SourceConfig,
    TMDBConfig,
)


class ConfigError(ValueError):
    """Raised when the configuration file is malformed or fails validation."""


def _coerce_bool(value: Any, dotted_key: str) -> bool:
    """Return a bool, coercing simple 0/1 representations when necessary."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "1"}:
            return normalized == "1"
        if normalized in {"true", "false"}:
            return normalized == "true"
    raise ConfigError(f"{dotted_key} must be a boolean (use true/false).")


def _sanitize_section(raw: dict[str, Any], name: str, cls):
    """
    Coerce a raw TOML table into an instance of ``cls`` with cleaned booleans.

    Parameters:
        raw (dict[str, Any]): Raw TOML section data.
        name (str): Section name used when reporting validation errors.
        cls: Dataclass type used to construct the section object.

    Returns:
        Any: Instantiated dataclass populated with values from ``raw``.

    Raises:
        ConfigError: If the section is not a table or contains invalid keys or values.
    """
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] must be a table")
    cleaned: Dict[str, Any] = {}
    cls_fields = {field.name: field for field in fields(cls)}
    bool_fields = {name for name, field in cls_fields.items() if field.type is bool}
    nested_fields = {
        name: field.type
        for name, field in cls_fields.items()
        if is_dataclass(field.type)
    }
    provided_keys = set(raw.keys())
    for key, value in raw.items():
        if key in bool_fields:
            cleaned[key] = _coerce_bool(value, f"{name}.{key}")
        elif key in nested_fields:
            if not isinstance(value, dict):
                raise ConfigError(f"[{name}.{key}] must be a table")
            cleaned[key] = _sanitize_section(value, f"{name}.{key}", nested_fields[key])
        else:
            cleaned[key] = value
    try:
        instance = cls(**cleaned)
    except TypeError as exc:
        raise ConfigError(f"Invalid keys in [{name}]: {exc}") from exc
    try:
        setattr(instance, "_provided_keys", provided_keys)
    except Exception:
        pass
    return instance


def _validate_trim(mapping: Dict[str, Any], label: str) -> None:
    """
    Ensure all trim overrides map to integer frame counts.

    Parameters:
        mapping (Dict[str, Any]): Raw trim override mapping.
        label (str): Configuration label used in error messages.

    Raises:
        ConfigError: If any trim override is not an integer.
    """
    for key, value in mapping.items():
        if not isinstance(value, int):
            raise ConfigError(f"{label} entry '{key}' must map to an integer")


def _validate_change_fps(change_fps: Dict[str, Any]) -> None:
    """
    Validate ``change_fps`` overrides as ``"set"`` or two positive integers.

    Parameters:
        change_fps (Dict[str, Any]): Mapping from clip identifiers to override values.

    Raises:
        ConfigError: If any override is not ``"set"`` or a two-integer list of positive numbers.
    """
    for key, value in change_fps.items():
        if isinstance(value, str):
            if value != "set":
                raise ConfigError(f"change_fps entry '{key}' must be a [num, den] pair or \"set\"")
        elif isinstance(value, list):
            if len(value) != 2 or not all(isinstance(v, int) and v > 0 for v in value):
                raise ConfigError(f"change_fps entry '{key}' must contain two positive integers")
        else:
            raise ConfigError(f"change_fps entry '{key}' must be a list or \"set\"")


def load_config(path: str) -> AppConfig:
    """
    Load and validate an application configuration from a TOML file.
    
    Reads the file at `path`, parses it as UTF-8 TOML (BOM is accepted), coerces and validates all top-level sections, normalizes a few fields (for example pad/overlay/source/category preferences), and returns a fully populated AppConfig ready for use by the application.
    
    Returns:
        AppConfig: The validated and normalized application configuration.
    
    Raises:
        ConfigError: If the file is not UTF-8, TOML parsing fails, required values are missing, or any validation rule is violated.
    """

    with open(path, "rb") as handle:
        raw_bytes = handle.read()
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]
    try:
        raw = tomllib.loads(raw_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ConfigError("Configuration file must be UTF-8 encoded") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Failed to parse TOML: {exc}") from exc

    app = AppConfig(
        analysis=_sanitize_section(raw.get("analysis", {}), "analysis", AnalysisConfig),
        screenshots=_sanitize_section(raw.get("screenshots", {}), "screenshots", ScreenshotConfig),
        cli=_sanitize_section(raw.get("cli", {}), "cli", CLIConfig),
        slowpics=_sanitize_section(raw.get("slowpics", {}), "slowpics", SlowpicsConfig),
        tmdb=_sanitize_section(raw.get("tmdb", {}), "tmdb", TMDBConfig),
        naming=_sanitize_section(raw.get("naming", {}), "naming", NamingConfig),
        paths=_sanitize_section(raw.get("paths", {}), "paths", PathsConfig),
        runtime=_sanitize_section(raw.get("runtime", {}), "runtime", RuntimeConfig),
        overrides=_sanitize_section(raw.get("overrides", {}), "overrides", OverridesConfig),
        color=_sanitize_section(raw.get("color", {}), "color", ColorConfig),
        source=_sanitize_section(raw.get("source", {}), "source", SourceConfig),
        audio_alignment=_sanitize_section(
            raw.get("audio_alignment", {}), "audio_alignment", AudioAlignmentConfig
        ),
    )

    normalized_style = str(app.cli.progress.style).strip().lower()
    if normalized_style not in {"fill", "dot"}:
        raise ConfigError("cli.progress.style must be 'fill' or 'dot'")
    app.cli.progress.style = normalized_style

    if app.analysis.step < 1:
        raise ConfigError("analysis.step must be >= 1")
    if app.analysis.downscale_height < 0:
        raise ConfigError("analysis.downscale_height must be >= 0")
    if 0 < app.analysis.downscale_height < 64:
        raise ConfigError("analysis.downscale_height must be 0 or >= 64")
    if app.analysis.random_seed < 0:
        raise ConfigError("analysis.random_seed must be >= 0")
    if not app.analysis.frame_data_filename:
        raise ConfigError("analysis.frame_data_filename must be set")
    if app.analysis.skip_head_seconds < 0:
        raise ConfigError("analysis.skip_head_seconds must be >= 0")
    if app.analysis.skip_tail_seconds < 0:
        raise ConfigError("analysis.skip_tail_seconds must be >= 0")
    if app.analysis.ignore_lead_seconds < 0:
        raise ConfigError("analysis.ignore_lead_seconds must be >= 0")
    if app.analysis.ignore_trail_seconds < 0:
        raise ConfigError("analysis.ignore_trail_seconds must be >= 0")
    if app.analysis.min_window_seconds < 0:
        raise ConfigError("analysis.min_window_seconds must be >= 0")

    if app.screenshots.compression_level not in (0, 1, 2):
        raise ConfigError("screenshots.compression_level must be 0, 1, or 2")
    if app.screenshots.mod_crop < 0:
        raise ConfigError("screenshots.mod_crop must be >= 0")
    if not isinstance(app.screenshots.letterbox_px_tolerance, int):
        raise ConfigError("screenshots.letterbox_px_tolerance must be an integer")
    if app.screenshots.letterbox_px_tolerance < 0:
        raise ConfigError("screenshots.letterbox_px_tolerance must be >= 0")
    pad_mode = str(app.screenshots.pad_to_canvas).strip().lower()
    if pad_mode not in {"off", "on", "auto"}:
        raise ConfigError("screenshots.pad_to_canvas must be 'off', 'on', or 'auto'")
    app.screenshots.pad_to_canvas = pad_mode

    progress_style = str(app.cli.progress.style).strip().lower()
    if progress_style not in {"fill", "dot"}:
        raise ConfigError("cli.progress.style must be 'fill' or 'dot'")
    app.cli.progress.style = progress_style

    if app.slowpics.remove_after_days < 0:
        raise ConfigError("slowpics.remove_after_days must be >= 0")
    if app.slowpics.image_upload_timeout_seconds <= 0:
        raise ConfigError("slowpics.image_upload_timeout_seconds must be > 0")

    if app.tmdb.year_tolerance < 0:
        raise ConfigError("tmdb.year_tolerance must be >= 0")
    if app.tmdb.cache_ttl_seconds < 0:
        raise ConfigError("tmdb.cache_ttl_seconds must be >= 0")
    if app.tmdb.cache_max_entries < 0:
        raise ConfigError("tmdb.cache_max_entries must be >= 0")
    if app.tmdb.category_preference is not None:
        preference = app.tmdb.category_preference.strip().upper()
        if preference not in {"", "MOVIE", "TV"}:
            raise ConfigError("tmdb.category_preference must be MOVIE, TV, or omitted")
        app.tmdb.category_preference = preference or None

    if app.runtime.ram_limit_mb <= 0:
        raise ConfigError("runtime.ram_limit_mb must be > 0")

    if app.color.target_nits <= 0:
        raise ConfigError("color.target_nits must be > 0")
    if app.color.dst_min_nits < 0:
        raise ConfigError("color.dst_min_nits must be >= 0")
    if app.color.verify_luma_threshold < 0 or app.color.verify_luma_threshold > 1:
        raise ConfigError("color.verify_luma_threshold must be between 0 and 1")
    if app.color.verify_start_seconds < 0:
        raise ConfigError("color.verify_start_seconds must be >= 0")
    if app.color.verify_step_seconds <= 0:
        raise ConfigError("color.verify_step_seconds must be > 0")
    if app.color.verify_max_seconds < 0:
        raise ConfigError("color.verify_max_seconds must be >= 0")
    overlay_mode = str(getattr(app.color, "overlay_mode", "minimal")).strip().lower()
    if overlay_mode not in {"minimal", "diagnostic"}:
        raise ConfigError("color.overlay_mode must be 'minimal' or 'diagnostic'")
    app.color.overlay_mode = overlay_mode

    preferred = app.source.preferred.strip().lower()
    if preferred not in {"lsmas", "ffms2"}:
        raise ConfigError("source.preferred must be either 'lsmas' or 'ffms2'")
    app.source.preferred = preferred

    audio_cfg = app.audio_alignment
    if audio_cfg.sample_rate <= 0:
        raise ConfigError("audio_alignment.sample_rate must be > 0")
    if audio_cfg.hop_length <= 0:
        raise ConfigError("audio_alignment.hop_length must be > 0")
    if audio_cfg.start_seconds is not None and audio_cfg.start_seconds < 0:
        raise ConfigError("audio_alignment.start_seconds must be >= 0")
    if audio_cfg.duration_seconds is not None and audio_cfg.duration_seconds <= 0:
        raise ConfigError("audio_alignment.duration_seconds must be > 0")
    if audio_cfg.correlation_threshold < 0 or audio_cfg.correlation_threshold > 1:
        raise ConfigError("audio_alignment.correlation_threshold must be between 0 and 1")
    if audio_cfg.max_offset_seconds <= 0:
        raise ConfigError("audio_alignment.max_offset_seconds must be > 0")
    if not audio_cfg.offsets_filename.strip():
        raise ConfigError("audio_alignment.offsets_filename must be set")
    if audio_cfg.random_seed < 0:
        raise ConfigError("audio_alignment.random_seed must be >= 0")

    _validate_trim(app.overrides.trim, "overrides.trim")
    _validate_trim(app.overrides.trim_end, "overrides.trim_end")
    _validate_change_fps(app.overrides.change_fps)

    return app