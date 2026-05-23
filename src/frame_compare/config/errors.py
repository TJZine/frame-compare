"""Configuration subsystem error classes."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from frame_compare.errors import ErrorContext, FrameCompareError, JSONValue


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

    def __init__(self, errors: list[dict[str, JSONValue]]) -> None:
        fields: list[str] = []
        for e in errors:
            loc = e.get("loc")
            if isinstance(loc, list) and loc:
                fields.append(str(loc[-1]))
            else:
                fields.append("unknown")

        # Cast to avoid invariance issues with list[dict[str, JSONValue]] vs list[JSONValue]
        safe_errors = cast("JSONValue", errors)

        super().__init__(
            ErrorContext(
                code="FC-1003",
                name="CONFIG_VALIDATION_ERROR",
                message=f"Invalid configuration: {', '.join(fields)}",
                hint="Check field types and constraints",
                details={"validation_errors": safe_errors},
            )
        )
        self.validation_errors = errors


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
