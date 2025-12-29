"""Frame Compare error types (minimal stub for config module).

Error Codes:
    FC-1001: CONFIG_NOT_FOUND
    FC-1002: CONFIG_PARSE_ERROR
    FC-1003: CONFIG_VALIDATION_ERROR
    FC-1004: PRESET_NOT_FOUND
    FC-1005: PRESET_INVALID
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
type ErrorDetails = dict[str, JSONValue]


def normalize_pydantic_errors(
    errors: Sequence[dict[str, object]],
) -> list[dict[str, JSONValue]]:
    """Convert Pydantic validation error payloads to JSONValue-safe format."""
    result: list[dict[str, JSONValue]] = []
    for err in errors:
        safe_err: dict[str, JSONValue] = {}
        for key, value in err.items():
            safe_err[key] = _to_json_value(value)
        result.append(safe_err)
    return result


def _to_json_value(value: object) -> JSONValue:
    """Recursively convert a value to JSONValue."""
    if value is None:
        return None
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        # cast to list of objects to iterate safely
        val_list = cast("list[object]", value)
        return [_to_json_value(v) for v in val_list]
    if isinstance(value, dict):
        # cast to dict of objects to iterate safely
        val_dict = cast("dict[object, object]", value)
        return {str(k): _to_json_value(v) for k, v in val_dict.items()}
    return str(value)


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured error information."""

    code: str
    name: str
    message: str
    details: ErrorDetails | None = None
    hint: str | None = None
    cause: BaseException | None = None

    def to_dict(self) -> dict[str, JSONValue]:
        result: dict[str, JSONValue] = {
            "code": self.code,
            "name": self.name,
            "message": self.message,
        }
        if self.hint:
            result["hint"] = self.hint
        if self.details:
            result["details"] = self.details
        return result


class FrameCompareError(Exception):
    """Base exception for all Frame Compare errors."""

    def __init__(self, context: ErrorContext) -> None:
        self.context = context
        super().__init__(context.message)

    @property
    def code(self) -> str:
        return self.context.code

    @property
    def name(self) -> str:
        return self.context.name

    @property
    def hint(self) -> str | None:
        return self.context.hint

    def __str__(self) -> str:
        base = f"[{self.code}] {self.context.message}"
        if self.hint:
            base += f"\nHint: {self.hint}"
        return base

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.context!r})"


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
