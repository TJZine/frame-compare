---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v3
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v2.md
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v3.md
---

# Implementation Plan: Configuration Module

## Changes Since plan-v2

- **[Edit 1]** Moved `tomli-w>=1.0.0` from `[dependency-groups].dev` to `[project].dependencies` (runtime) so `frame_compare.config` works in non-dev installs.
- **[Edit 2]** Fixed `save_preset()` to use `write_text(..., encoding="utf-8")` instead of `write_bytes()` since `tomli_w.dumps()` returns `str`.
- **[Edit 3]** Removed "alphabetically sorted" claim; changed determinism contract to "stable schema field order" (Pydantic model_dump preserves field declaration order); added `test_save_preset_deterministic_output` test.
- **[Edit 4]** Removed all `# type: ignore` comments from `_deep_merge()` functions; replaced with explicit type narrowing using `isinstance()` checks and `cast()`.

---

## Context

**Phase:** 1
**Module:** `frame_compare.config`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`
**Dependencies:**

- `pydantic>=2.10.0` ✅ (in pyproject.toml)
- `pydantic-settings>=2.7.0` ✅ (in pyproject.toml)
- `tomli-w>=1.0.0` ❌ (add to **runtime** dependencies)
- `frame_compare.errors` ❌ (minimal stub created in this plan)

## Scope

This plan covers:

- [x] `pyproject.toml` — Add `tomli-w>=1.0.0` to **runtime** dependencies
- [x] `src/frame_compare/errors.py` — Minimal config-related error types (FC-1001 to FC-1005)
- [x] `src/frame_compare/config/__init__.py` — Public exports
- [x] `src/frame_compare/config/schema.py` — Pydantic v2 models + enums
- [x] `src/frame_compare/config/loader.py` — Config loading with exact implementations
- [x] `src/frame_compare/config/overrides.py` — CLI override mapping with exact merge algorithm
- [x] `src/frame_compare/config/presets.py` — Preset management with tomli-w
- [x] `src/frame_compare/config/defaults.py` — Default TOML template
- [x] `tests/config/test_schema.py` — Schema validation tests
- [x] `tests/config/test_loader.py` — Loader tests including env alias tests
- [x] `tests/config/test_presets.py` — Preset tests including determinism
- [x] `tests/config/test_overrides.py` — Override tests including inversion
- [x] Delete `.gitkeep` from `src/frame_compare/config/`

This plan does NOT cover:

- Full error hierarchy (Phase 1.2)
- CLI integration (Phase 1.4)
- Logging infrastructure (Phase 1.3)

## Contract Impact

**Contracts touched:** NO

---

## Rollback Guidance

### STOP Triggers

The Coding Agent MUST stop and return to Planning if:

1. `pydantic-settings` does not support `TomlConfigSettingsSource` as documented
2. The `settings_customise_sources` signature differs from the spec
3. Any spec mismatch is discovered that requires design decisions

### Rollback Steps

If implementation fails midway:

1. Delete all files created under `src/frame_compare/config/` except `.gitkeep`
2. Delete `src/frame_compare/errors.py` if created
3. Revert `pyproject.toml` changes (remove `tomli-w` from dependencies)
4. Delete `tests/config/` directory if created
5. Run `uv sync` to revert dependency changes

---

## Files to Create/Modify

### 0. `pyproject.toml` [MODIFY]

**Purpose:** Add `tomli-w` as a **runtime** dependency (not dev-only).

**Exact edit:** In the `[project]` section, add `tomli-w>=1.0.0` to the `dependencies` list:

```toml
dependencies = [
    "typer>=0.15.0",
    "rich>=13.9.0",
    "numpy>=2.2.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "structlog>=24.4.0",
    "anyio>=4.7.0",
    "tomli-w>=1.0.0",  # <-- ADD THIS LINE
]
```

**Do NOT add to dev dependencies.** The library/CLI must be able to import `tomli_w` at runtime.

---

### 1. `src/frame_compare/errors.py` [NEW]

**Purpose:** Define config-related error types. Extended in Phase 1.2.

```python
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
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Sequence

JSONValue: TypeAlias = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
ErrorDetails: TypeAlias = dict[str, JSONValue]


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
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}
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
        fields = [str(e.get("loc", ["unknown"])[-1]) for e in errors]
        super().__init__(
            ErrorContext(
                code="FC-1003",
                name="CONFIG_VALIDATION_ERROR",
                message=f"Invalid configuration: {', '.join(fields)}",
                hint="Check field types and constraints",
                details={"validation_errors": errors},
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
```

---

### 2. `src/frame_compare/config/schema.py` [NEW]

**(Unchanged from plan-v2 — full Pydantic schema with enums and section models)**

See plan-v2 section 2 for complete implementation.

---

### 3. `src/frame_compare/config/loader.py` [NEW]

**Purpose:** Config loading with exact implementations and **no type ignores**.

**Key change from v2:** Replace `# type: ignore` with explicit narrowing.

```python
"""Configuration loading functions."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import cast

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    normalize_pydantic_errors,
)


def load_config(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """Load configuration from TOML file with overrides."""
    if config_path is not None and not config_path.exists():
        raise ConfigNotFoundError(config_path)

    alias_overrides = _resolve_env_aliases()
    merged_overrides = _deep_merge(alias_overrides, overrides or {})

    settings_cls: type[ConfigSchema]
    if config_path is None:
        settings_cls = ConfigSchema
    else:
        settings_cls = type(
            "ConfigSchemaFromFile",
            (ConfigSchema,),
            {
                "model_config": SettingsConfigDict(
                    **{**ConfigSchema.model_config, "toml_file": str(config_path)}
                )
            },
        )

    try:
        return settings_cls(**merged_overrides)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(
            config_path or Path("config/config.toml"), str(exc)
        ) from exc
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
        raise ConfigValidationError(normalized) from exc


def load_config_from_env() -> ConfigSchema:
    """Load config from environment variables only (no TOML file)."""

    class _EnvOnlySchema(ConfigSchema):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (init_settings, env_settings)

    alias_overrides = _resolve_env_aliases()

    try:
        return _EnvOnlySchema(**alias_overrides)
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
        raise ConfigValidationError(normalized) from exc


def get_default_config() -> ConfigSchema:
    """Get config with all default values (no TOML, no env)."""

    class _DefaultsOnlySchema(ConfigSchema):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (init_settings,)

    return _DefaultsOnlySchema()


def _resolve_env_aliases() -> dict[str, object]:
    """Resolve special env var aliases to nested override dict."""
    overrides: dict[str, object] = {}

    if "TMDB_API_KEY" in os.environ and "FRAME_COMPARE_TMDB__API_KEY" not in os.environ:
        overrides["tmdb"] = {"api_key": os.environ["TMDB_API_KEY"]}

    if (
        "FRAME_COMPARE_LOG_LEVEL" in os.environ
        and "FRAME_COMPARE_LOGGING__LEVEL" not in os.environ
    ):
        overrides["logging"] = {"level": os.environ["FRAME_COMPARE_LOG_LEVEL"]}

    return overrides


def _deep_merge(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    """Deep merge two dicts. Updates take precedence over base.

    Type narrowing: Only dicts are merged recursively. Non-dict values
    are replaced. Uses isinstance() checks to satisfy pyright strict.
    """
    result: dict[str, object] = dict(base)
    for key, value in updates.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            # Both are dicts: recurse
            result[key] = _deep_merge(
                cast(dict[str, object], base_value),
                cast(dict[str, object], value),
            )
        else:
            result[key] = value
    return result
```

---

### 4. `src/frame_compare/config/overrides.py` [NEW]

**Key change from v2:** Replace `# type: ignore` with explicit narrowing using `cast()`.

```python
"""CLI override mapping and application."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

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
    config: "ConfigSchema",
    cli_args: dict[str, object],
) -> "ConfigSchema":
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
        return ConfigSchema.model_validate(merged)
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
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
            # Overwrite non-dict with new dict
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
```

---

### 5. `src/frame_compare/config/presets.py` [NEW]

**Key changes from v2:**

1. Use `write_text(..., encoding="utf-8")` instead of `write_bytes()`
2. Removed "alphabetically sorted" claim; determinism is via Pydantic's stable field order
3. Explicit type narrowing with `cast()`

```python
"""Preset management for Frame Compare configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

import tomli_w
from pydantic import ValidationError

from frame_compare.errors import (
    ConfigValidationError,
    PresetInvalidError,
    PresetNotFoundError,
    normalize_pydantic_errors,
)

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema

DEFAULT_PRESETS_DIR = Path("config/presets")


def list_presets(presets_dir: Path | None = None) -> list[str]:
    """List available preset names (sorted alphabetically)."""
    directory = presets_dir or DEFAULT_PRESETS_DIR
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.toml"))


def load_preset(name: str, presets_dir: Path | None = None) -> dict[str, object]:
    """Load preset data by name.

    Raises:
        PresetNotFoundError: If preset file doesn't exist
        PresetInvalidError: If TOML syntax is invalid
    """
    directory = presets_dir or DEFAULT_PRESETS_DIR
    preset_path = directory / f"{name}.toml"

    if not preset_path.exists():
        raise PresetNotFoundError(name)

    try:
        return tomllib.loads(preset_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PresetInvalidError(preset_path, str(exc)) from exc


def save_preset(
    name: str,
    config: "ConfigSchema",
    presets_dir: Path | None = None,
) -> Path:
    """Save current config as preset.

    Uses tomli-w for TOML serialization. Output order is stable
    (follows Pydantic model field declaration order).

    Determinism: Calling save_preset() twice with the same config
    produces identical file contents.
    """
    directory = presets_dir or DEFAULT_PRESETS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    preset_path = directory / f"{name}.toml"

    # Serialize with mode="json" for JSON-serializable types
    data = config.model_dump(mode="json")

    # tomli_w.dumps() returns str; use write_text with explicit encoding
    toml_text = tomli_w.dumps(data)
    preset_path.write_text(toml_text, encoding="utf-8")

    return preset_path


def apply_preset(config: "ConfigSchema", preset_name: str) -> "ConfigSchema":
    """Apply preset overrides to config.

    Raises:
        PresetNotFoundError: If preset doesn't exist
        PresetInvalidError: If preset TOML is invalid
        ConfigValidationError: If merged config fails validation
    """
    from frame_compare.config.schema import ConfigSchema

    preset_data = load_preset(preset_name)
    base_dict = config.model_dump()
    merged = _deep_merge(base_dict, preset_data)

    try:
        return ConfigSchema.model_validate(merged)
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
        raise ConfigValidationError(normalized) from exc


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
```

---

### 6-7. `defaults.py` and `__init__.py`

**(Unchanged from plan-v2)**

---

### 8-11. Test Files

#### `tests/config/test_presets.py` [NEW]

**Added test for determinism:**

| Test | Description |
|------|-------------|
| `test_list_presets_empty_dir` | Empty/missing dir returns `[]` |
| `test_list_presets_finds_toml_files` | Dir with `a.toml`, `b.toml` returns `["a", "b"]` |
| `test_load_preset_success` | Load valid preset works |
| `test_load_preset_not_found_raises` | Missing preset raises `PresetNotFoundError` |
| `test_preset_invalid_toml_raises_parse_error` | Invalid TOML raises `PresetInvalidError` |
| `test_save_preset_creates_file` | `save_preset()` creates file |
| `test_save_preset_roundtrip` | save → load → apply is idempotent |
| `test_apply_preset_merges_values` | Preset `frame_count=50` overrides default |
| **`test_save_preset_deterministic_output`** | Calling `save_preset()` twice with same config produces identical files |

**Implementation for determinism test:**

```python
def test_save_preset_deterministic_output(tmp_path: Path) -> None:
    """Saving the same config twice produces identical file contents."""
    from frame_compare.config import get_default_config, save_preset

    config = get_default_config()

    path1 = save_preset("test1", config, tmp_path)
    path2 = save_preset("test2", config, tmp_path)

    assert path1.read_text(encoding="utf-8") == path2.read_text(encoding="utf-8")
```

---

## Acceptance Criteria

**(Unchanged from plan-v2, plus:)**

- [x] GIVEN `save_preset()` called twice with same config WHEN compared THEN file contents are identical

## Verification Commands

```bash
# Install dependencies (including new runtime tomli-w)
uv sync

# Type checking (0 errors, 0 warnings, NO type ignores in source)
.venv/bin/pyright --warnings src/frame_compare/config src/frame_compare/errors.py

# Linting (0 errors)
.venv/bin/ruff check src/frame_compare/config src/frame_compare/errors.py

# Tests (all pass)
.venv/bin/pytest -v tests/config/

# Verify no type ignores remain in source
grep -r "type: ignore" src/frame_compare/config/ src/frame_compare/errors.py && exit 1 || echo "OK: no type ignores"
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

---

## Notes for Coding Agent

1. **Order of implementation:**
   - First: `pyproject.toml` (add tomli-w to runtime deps)
   - Second: `uv sync` to install
   - Third: `errors.py`
   - Fourth: `config/schema.py`
   - Fifth: `config/defaults.py`
   - Sixth: `config/loader.py`
   - Seventh: `config/overrides.py`
   - Eighth: `config/presets.py`
   - Ninth: `config/__init__.py`
   - Finally: Tests

2. **Delete `.gitkeep`:** Remove `src/frame_compare/config/.gitkeep` after creating `__init__.py`.

3. **No `# type: ignore`:** The plan uses `isinstance()` and `cast()` for type narrowing. Do not add type ignores.

4. **`tomli_w.dumps()` returns `str`:** Use `write_text(..., encoding="utf-8")` not `write_bytes()`.

5. **STOP triggers:** If `TomlConfigSettingsSource` import fails or signature differs, STOP and return to Planning.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-1__config-module

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v3.md
