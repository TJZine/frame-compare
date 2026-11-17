"""Configuration subsystem error classes."""

from __future__ import annotations

import re
from difflib import get_close_matches
from pathlib import Path
from tomllib import TOMLDecodeError
from typing import cast, get_args, get_origin

from pydantic import BaseModel

from frame_compare.errors import ErrorContext, FrameCompareError, JSONValue

_SECRET_CONFIG_LOCATIONS = frozenset(
    {
        ("slowpics", "webhook_url"),
        ("tmdb", "api_key"),
    }
)


def _redact_config_input(value: JSONValue, location: tuple[str, ...]) -> JSONValue:
    if any(location[: len(secret)] == secret for secret in _SECRET_CONFIG_LOCATIONS):
        return "<redacted>"
    if not any(secret[: len(location)] == location for secret in _SECRET_CONFIG_LOCATIONS):
        return value
    if isinstance(value, dict):
        return {key: _redact_config_input(item, (*location, key)) for key, item in value.items()}
    if isinstance(value, list):
        # An invalid array of config tables still has its section's location.
        return [_redact_config_input(item, location) for item in value]
    return value


def _config_location(error: dict[str, JSONValue]) -> tuple[str, ...]:
    location = error.get("loc")
    return tuple(str(part) for part in location) if isinstance(location, list) else ()


def _config_section_fields(schema: type[BaseModel], section: tuple[str, ...]) -> tuple[str, ...]:
    annotation: object = schema
    for part in section:
        # A nullable nested model or a mapping of source selectors to overrides
        # contributes its value model to the next step through the location.
        args = get_args(annotation)
        if get_origin(annotation) is dict:
            annotation = args[1]
            continue
        annotation = next((arg for arg in args if arg is not type(None)), annotation)
        if not isinstance(annotation, type) or not issubclass(annotation, BaseModel):
            return ()
        field = annotation.model_fields.get(part)
        if field is None:
            return ()
        annotation = field.annotation
    annotation = next((arg for arg in get_args(annotation) if arg is not type(None)), annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return tuple(annotation.model_fields)
    return ()


def _config_validation_message(
    errors: list[dict[str, JSONValue]], source_path: Path | None, *, effective: bool
) -> str:
    lines: list[str] = []
    for error in errors:
        key = ".".join(_config_location(error)) or "configuration"
        if error.get("type") == "extra_forbidden":
            lines.append(f"{key}: unknown key")
            continue
        problem = str(error.get("msg", "invalid value")).removeprefix("Value error, ")
        if "input" in error:
            problem += f" (given {error['input']!r})"
        lines.append(f"{key}: {problem}")
    if effective:
        heading = "Invalid effective configuration"
        if source_path is not None:
            heading += f" (selected file: {source_path})"
    else:
        heading = (
            f"Invalid configuration in {source_path}"
            if source_path is not None
            else "Invalid configuration"
        )
    if len(lines) > 1:
        return f"{heading}:\n  " + "\n  ".join(lines)
    if lines:
        return f"{heading}: {lines[0]}"
    return heading


def _config_validation_hint(
    errors: list[dict[str, JSONValue]], schema: type[BaseModel]
) -> str | None:
    suggestions: list[str] = []
    for error in errors:
        location = _config_location(error)
        if error.get("type") != "extra_forbidden" or not location:
            continue
        key = location[-1]
        section = location[:-1]
        valid_keys = _config_section_fields(schema, section)
        closest = get_close_matches(key, valid_keys, n=3, cutoff=0)
        if closest:
            keys = ", ".join(".".join((*section, candidate)) for candidate in closest)
            suggestions.append(f"Closest valid keys for {'.'.join(location)}: {keys}.")
    if suggestions:
        return " ".join(suggestions)
    if errors:
        return "Correct the listed settings using the expected values above."
    return None


def format_toml_syntax_error(error: TOMLDecodeError) -> str:
    """Keep the parser location while omitting authored tokens from its message."""
    location = re.search(r" \(at (?:line [0-9]+, column [0-9]+|end of document)\)\Z", str(error))
    return "invalid TOML syntax" + (location.group() if location else "")


class ConfigError(FrameCompareError):
    """Base class for configuration errors."""


class ConfigNotFoundError(ConfigError):
    """Configuration file not found (FC-1001)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1001",
                name="CONFIG_NOT_FOUND",
                message=f"Configuration file not found: {path}",
                hint="Run 'frame-compare wizard' or create config/config.toml",
                details={"path": str(path)},
            )
        )
        self.path = path


class ConfigParseError(ConfigError):
    """TOML parsing failed (FC-1002)."""

    def __init__(self, path: Path, parse_details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1002",
                name="CONFIG_PARSE_ERROR",
                message=f"Failed to parse {path}: {parse_details}",
                hint="Check TOML syntax at the indicated line",
                details={"path": str(path), "parse_error": parse_details},
            )
        )
        self.path = path


class ConfigValidationError(ConfigError):
    """Config validation failed (FC-1003)."""

    def __init__(
        self,
        errors: list[dict[str, JSONValue]],
        *,
        message: str | None = None,
        hint: str | None = None,
        source_path: Path | None = None,
        schema: type[BaseModel] | None = None,
        effective: bool = False,
    ) -> None:
        sanitized_errors: list[dict[str, JSONValue]] = []
        for error in errors:
            sanitized_error = error.copy()
            if "input" in sanitized_error:
                location = _config_location(sanitized_error)
                sanitized_error["input"] = _redact_config_input(sanitized_error["input"], location)
            sanitized_errors.append(sanitized_error)

        if hint is None and schema is not None:
            hint = _config_validation_hint(sanitized_errors, schema)

        # Cast to avoid invariance issues with list[dict[str, JSONValue]] vs list[JSONValue]
        safe_errors = cast("JSONValue", sanitized_errors)

        super().__init__(
            ErrorContext(
                code="FC-1003",
                name="CONFIG_VALIDATION_ERROR",
                message=message
                or _config_validation_message(sanitized_errors, source_path, effective=effective),
                hint=hint if hint is not None else "Check field types and constraints",
                details={"validation_errors": safe_errors},
            )
        )
        self.validation_errors = sanitized_errors
        self.source_path = source_path


class PresetNotFoundError(ConfigError):
    """Preset not found (FC-1004)."""

    def __init__(self, name: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1004",
                name="PRESET_NOT_FOUND",
                message=f"Preset not found: {name}",
                hint="Run 'frame-compare preset list' to see available",
                details={"preset_name": name},
            )
        )
        self.preset_name = name


class PresetInvalidError(ConfigError):
    """Preset file has invalid TOML syntax (FC-1005)."""

    def __init__(self, path: Path, parse_details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1005",
                name="PRESET_INVALID",
                message=f"Invalid preset file: {path}",
                hint="Check TOML syntax in preset file",
                details={"path": str(path), "parse_error": parse_details},
            )
        )
        self.path = path


class PresetNameInvalidError(ConfigError):
    """Preset name is invalid (FC-1006)."""

    def __init__(self, name: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1006",
                name="PRESET_NAME_INVALID",
                message=f"Invalid preset name: {name}",
                hint="Use only letters, numbers, '_' and '-'",
                details={"preset_name": name},
            )
        )
        self.preset_name = name


class ConfigWriteError(ConfigError):
    """Configuration or preset write failed (FC-1007)."""

    def __init__(self, path: Path, *, label: str, cause: OSError) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1007",
                name="CONFIG_WRITE_ERROR",
                message=f"Failed to write {label}: {path}",
                hint="Check that the destination path is writable",
                details={"path": str(path), "error": str(cause)},
                cause=cause,
            )
        )
        self.path = path
