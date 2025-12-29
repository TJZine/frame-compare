---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v2
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md
---

# Implementation Plan: Error Handling Module

## Changes Since plan-v1

- **Fix 1 (Contract Impact):** Changed to `Contracts touched: NO`. Moved contract gates to Verification as optional safety checks.
- **Fix 2 (Workflow commands):** Added `validate_run_id.py`, `validate_run_artifacts.py`, `validate_spec_anchors.py` to Verification Commands.
- **Fix 3 (File list):** Added `docs/DECISIONS.md` and `CHANGELOG.md` updates. Added explicit note that derived outputs must not be edited.
- **Fix 4 (PublishError):** Defined as pure marker base class (no FC code) per pattern from SSOT. No SSOT update required — already consistent.
- **Fix 5 (Mechanically checkable signatures):** Rewrote all error class entries with full `__init__` signatures and instance attributes.
- **Fix 6 (Tests):** Added parametric test approach, explicit test list for all new exception classes, negative cases, and determinism rules.
- **Fix 7 (SSOT/contract drift):** Added explicit out-of-scope statement for contract-only codes (FC-1006, FC-3010/3011/3012, FC-5010/5011).
- **Fix 8 (Decision points):** Resolved all open decisions with explicit specifications.

## Context

**Phase:** 1 (Core Infrastructure)
**Module:** `frame_compare.errors`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`
**Dependencies:** None. This is a **leaf module** — may only import Python stdlib and `typing`. Must NOT import any other `frame_compare` modules.

> [!IMPORTANT]
> Phase 1.1 Config Module already implemented: `ErrorContext`, `FrameCompareError`, and all `ConfigError` subclasses (FC-1001 to FC-1005). This plan extends that foundation.

## Scope

This plan covers:

- [x] `ErrorContext` dataclass (exists)
- [x] `FrameCompareError` base class (exists)
- [x] `ConfigError` hierarchy FC-1001 to FC-1005 (exists)
- [ ] `DependencyError` hierarchy (FC-2001, FC-2002, FC-2003, FC-2004, FC-2005, FC-2006, FC-2007, FC-2010)
- [ ] `InputError` hierarchy (FC-3001 to FC-3009)
- [ ] `ProcessingError` hierarchy (FC-4001 to FC-4007, FC-4010 to FC-4018)
- [ ] `NetworkError` hierarchy (FC-5001 to FC-5008)
- [ ] `InternalError` hierarchy (FC-9001 to FC-9003)
- [ ] `ExitCode` enum and `get_exit_code()` helper
- [ ] `format_error_console()` and `format_error_json()` utilities
- [ ] Comprehensive unit tests

This plan does NOT cover:

- Result[T, E] pattern (deferred to future phase)
- CLI error handlers (Phase 1.4)
- Logging infrastructure (Phase 1.3)
- **Contract-only codes not in SSOT `errors-module.md`:** FC-1006, FC-3010, FC-3011, FC-3012, FC-5010, FC-5011 are reserved in contracts but have no SSOT class definition. Out of scope for this run.

## Contract Impact

**Contracts touched:** NO

No modifications to `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml` are planned. All FC codes implemented in this slice already exist in the contract.

Contract gates are run as **optional safety checks** during verification to confirm no unintended drift occurred.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.2 Dependency Errors (FC-2xxx)" — DependencyError subclasses
  - Section: "3.3 Input Errors (FC-3xxx)" — InputError subclasses
  - Section: "3.4 Processing Errors (FC-4xxx)" — ProcessingError and module-level aliases
  - Section: "3.5 Network Errors (FC-5xxx)" — NetworkError subclasses
  - Section: "3.6 Internal Errors (FC-9xxx)" — InternalError subclasses
  - Section: "4. Exit Code Mapping" — `ExitCode(IntEnum)` and `get_exit_code()`
  - Section: "5. Error Formatting Utilities" — `format_error_console()` and `format_error_json()`

## Files to Create/Modify

### 1. MODIFY `src/frame_compare/errors.py`

**Purpose:** Complete the error type hierarchy started in Phase 1.1.

**Import constraints (leaf module):** May only import `dataclasses`, `enum`, `pathlib`, `typing`, and Python stdlib. Must NOT import any `frame_compare.*` modules.

#### Already exists (from Phase 1.1 — do not modify)

- `type JSONValue`, `type ErrorDetails`
- `normalize_pydantic_errors()`, `_to_json_value()`
- `class ErrorContext` (frozen dataclass with `to_dict()`)
- `class FrameCompareError` (base with `code`, `name`, `hint` properties)
- `class ConfigError`, `ConfigNotFoundError`, `ConfigParseError`, `ConfigValidationError`, `PresetNotFoundError`, `PresetInvalidError`

#### New base classes to add

```python
class DependencyError(FrameCompareError):
    """Base class for dependency errors (FC-2xxx)."""

class InputError(FrameCompareError):
    """Base class for input errors (FC-3xxx)."""

class ProcessingError(FrameCompareError):
    """Base class for processing errors (FC-4xxx)."""

class NetworkError(FrameCompareError):
    """Base class for network errors (FC-5xxx)."""

class InternalError(FrameCompareError):
    """Base class for internal errors (FC-9xxx)."""

class ServiceError(FrameCompareError):
    """Base class for service layer errors (marker, no FC code)."""

class PublishError(ServiceError):
    """Base class for publish errors (marker, no FC code). Concrete publish errors use NetworkError subclasses."""
```

#### DependencyError subclasses (FC-2xxx)

| Class | `__init__` Signature | Attributes | Code |
|-------|---------------------|------------|------|
| `VapourSynthNotFoundError` | `__init__(self) -> None` | — | FC-2001 |
| `VapourSynthError` | `__init__(self, details: str) -> None` | — | FC-2002 |
| `PluginNotFoundError` | `__init__(self, plugin: str) -> None` | `.plugin: str` | FC-2003 |
| `LibplaceboError` | `__init__(self, details: str) -> None` | — | FC-2004 |
| `FFmpegNotFoundError` | `__init__(self) -> None` | — | FC-2005 |
| `FFmpegError` | `__init__(self, details: str, returncode: int \| None = None) -> None` | — | FC-2006 |
| `DoviToolNotFoundError` | `__init__(self) -> None` | — | FC-2007 |
| `PythonVersionError` | `__init__(self, version: str) -> None` | — | FC-2010 |

#### InputError subclasses (FC-3xxx)

| Class | `__init__` Signature | Attributes | Code |
|-------|---------------------|------------|------|
| `NoVideosFoundError` | `__init__(self, path: Path, patterns: list[str] \| None = None) -> None` | `.path: Path` | FC-3001 |
| `VideoOpenError` | `__init__(self, path: Path, reason: str \| None = None) -> None` | `.path: Path` | FC-3002 |
| `VideoCorruptError` | `__init__(self, path: Path) -> None` | `.path: Path` | FC-3003 |
| `InsufficientFramesError` | `__init__(self, path: Path, count: int, required: int) -> None` | `.path: Path` | FC-3004 |
| `IncompatibleVideosError` | `__init__(self, details: str) -> None` | — | FC-3005 |
| `DirectoryNotFoundError` | `__init__(self, path: Path) -> None` | `.path: Path` | FC-3006 |
| `DirectoryNotWritableError` | `__init__(self, path: Path) -> None` | `.path: Path` | FC-3007 |
| `FileTooLargeError` | `__init__(self, path: Path, size: int, limit: int) -> None` | `.path: Path` | FC-3008 |
| `PathEscapesRootError` | `__init__(self, root: Path, candidate: Path) -> None` | `.root: Path`, `.candidate: Path` | FC-3009 |

#### ProcessingError subclasses (FC-4xxx)

| Class | `__init__` Signature | Attributes | Code |
|-------|---------------------|------------|------|
| `FrameExtractionError` | `__init__(self, frame: int, clip: str \| Path) -> None` | — | FC-4001 |
| `MetricsCalculationError` | `__init__(self, details: str) -> None` | — | FC-4002 |
| `TonemapError` | `__init__(self, details: str) -> None` | — | FC-4003 |
| `RenderError` | `__init__(self, details: str \| None = None) -> None` | — | FC-4004 |
| `AudioAlignmentError` | `__init__(self, details: str) -> None` | — | FC-4005 |
| `CacheCorruptionError` | `__init__(self, path: Path) -> None` | `.path: Path` | FC-4006 |
| `CacheVersionMismatchError` | `__init__(self, expected: str, found: str) -> None` | — | FC-4007 |
| `MemoryError_` | `__init__(self) -> None` | — | FC-4010 |
| `TimeoutError_` | `__init__(self, operation: str, timeout: float) -> None` | — | FC-4011 |

**Processing module-level aliases (per SSOT section 3.4):**

| Class | Parent | `__init__` Signature | Code |
|-------|--------|---------------------|------|
| `AnalysisError` | `ProcessingError` | (abstract base, no concrete instantiation) | — |
| `SelectionError` | `AnalysisError` | `__init__(self, reason: str, requested: int, available: int) -> None` | FC-4012 |
| `EncodingError` | `RenderError` | `__init__(self, output_path: Path, details: str) -> None` | FC-4013 |
| `OverlayError` | `RenderError` | `__init__(self, details: str) -> None` | FC-4014 |
| `SourceLoadError` | `ProcessingError` | `__init__(self, path: Path, details: str) -> None` | FC-4015 |

**Service-level aliases (per SSOT):**

| Class | Parent | `__init__` Signature | Code |
|-------|--------|---------------------|------|
| `MetadataError` | `ServiceError` | `__init__(self, details: str) -> None` | FC-4016 |
| `ReportError` | `ServiceError` | `__init__(self, details: str) -> None` | FC-4017 |
| `DoviError` | `ServiceError` | `__init__(self, path: Path, details: str) -> None` | FC-4018 |

#### NetworkError subclasses (FC-5xxx)

| Class | `__init__` Signature | Attributes | Code |
|-------|---------------------|------------|------|
| `NetworkUnreachableError` | `__init__(self) -> None` | — | FC-5001 |
| `SlowpicsError` | `__init__(self, details: str) -> None` | — | FC-5002 |
| `SlowpicsRateLimitedError` | `__init__(self, retry_after: int \| None = None) -> None` | — | FC-5003 |
| `SlowpicsUnavailableError` | `__init__(self) -> None` | — | FC-5004 |
| `TmdbError` | `__init__(self, details: str) -> None` | — | FC-5005 |
| `TmdbRateLimitedError` | `__init__(self, retry_after: int \| None = None) -> None` | — | FC-5006 |
| `NetworkTimeoutError` | `__init__(self, service: str, timeout: float) -> None` | — | FC-5007 |
| `SSLError` | `__init__(self, details: str) -> None` | — | FC-5008 |

#### InternalError subclasses (FC-9xxx)

| Class | `__init__` Signature | Attributes | Code |
|-------|---------------------|------------|------|
| `GenericInternalError` | `__init__(self, details: str) -> None` | — | FC-9001 |
| `AssertionError_` | `__init__(self, details: str) -> None` | — | FC-9002 |
| `UnexpectedStateError` | `__init__(self, details: str) -> None` | — | FC-9003 |

#### ExitCode enum and helper

```python
class ExitCode(IntEnum):
    SUCCESS = 0
    GENERAL_ERROR = 1       # FC-9xxx or unknown
    CONFIG_ERROR = 2        # FC-1xxx
    DEPENDENCY_ERROR = 3    # FC-2xxx
    INPUT_ERROR = 4         # FC-3xxx
    PROCESSING_ERROR = 5    # FC-4xxx
    NETWORK_ERROR = 6       # FC-5xxx
    INTERRUPTED = 130       # Ctrl+C

def get_exit_code(error: FrameCompareError) -> ExitCode:
    """Map error to exit code based on FC-xxxx prefix. Unknown codes return GENERAL_ERROR."""
```

#### Formatting utilities (per SSOT section 5)

```python
def format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str:
    """Format error for console output.

    Returns format:
        ✗ Error [FC-xxxx]: {message}

          Hint: {hint}

          [if verbose and details:] Details: {details}
          [if not verbose:] For more details, run with --verbose
    """

def format_error_json(error: FrameCompareError) -> dict[str, JSONValue]:
    """Format error for JSON output. Returns {"success": False, "error": error.context.to_dict()}."""
```

### 2. NEW `tests/test_errors.py`

**Purpose:** Comprehensive unit tests for all error types and helper functions.

**Testing strategy:** Use parametric tests for exception classes to ensure coverage and avoid test maintenance burden.

#### Parametric test for all exception classes

```python
@pytest.mark.parametrize("error_class,constructor_args,expected_code", [
    # DependencyError (FC-2xxx)
    (VapourSynthNotFoundError, (), "FC-2001"),
    (VapourSynthError, ("test details",), "FC-2002"),
    (PluginNotFoundError, ("lsmas",), "FC-2003"),
    (LibplaceboError, ("test",), "FC-2004"),
    (FFmpegNotFoundError, (), "FC-2005"),
    (FFmpegError, ("test", 1), "FC-2006"),
    (DoviToolNotFoundError, (), "FC-2007"),
    (PythonVersionError, ("3.11",), "FC-2010"),
    # InputError (FC-3xxx)
    (NoVideosFoundError, (Path("/test"),), "FC-3001"),
    (VideoOpenError, (Path("/test"),), "FC-3002"),
    (VideoCorruptError, (Path("/test"),), "FC-3003"),
    (InsufficientFramesError, (Path("/test"), 10, 20), "FC-3004"),
    (IncompatibleVideosError, ("test",), "FC-3005"),
    (DirectoryNotFoundError, (Path("/test"),), "FC-3006"),
    (DirectoryNotWritableError, (Path("/test"),), "FC-3007"),
    (FileTooLargeError, (Path("/test"), 100, 50), "FC-3008"),
    (PathEscapesRootError, (Path("/root"), Path("/other")), "FC-3009"),
    # ProcessingError (FC-4xxx)
    (FrameExtractionError, (42, "clip.mkv"), "FC-4001"),
    (MetricsCalculationError, ("test",), "FC-4002"),
    (TonemapError, ("test",), "FC-4003"),
    (RenderError, (), "FC-4004"),
    (AudioAlignmentError, ("test",), "FC-4005"),
    (CacheCorruptionError, (Path("/cache"),), "FC-4006"),
    (CacheVersionMismatchError, ("1.0", "2.0"), "FC-4007"),
    (MemoryError_, (), "FC-4010"),
    (TimeoutError_, ("op", 30.0), "FC-4011"),
    (SelectionError, ("reason", 10, 5), "FC-4012"),
    (EncodingError, (Path("/out.png"), "test"), "FC-4013"),
    (OverlayError, ("test",), "FC-4014"),
    (SourceLoadError, (Path("/src"), "test"), "FC-4015"),
    (MetadataError, ("test",), "FC-4016"),
    (ReportError, ("test",), "FC-4017"),
    (DoviError, (Path("/dv"), "test"), "FC-4018"),
    # NetworkError (FC-5xxx)
    (NetworkUnreachableError, (), "FC-5001"),
    (SlowpicsError, ("test",), "FC-5002"),
    (SlowpicsRateLimitedError, (), "FC-5003"),
    (SlowpicsUnavailableError, (), "FC-5004"),
    (TmdbError, ("test",), "FC-5005"),
    (TmdbRateLimitedError, (), "FC-5006"),
    (NetworkTimeoutError, ("slow.pics", 30.0), "FC-5007"),
    (SSLError, ("test",), "FC-5008"),
    # InternalError (FC-9xxx)
    (GenericInternalError, ("test",), "FC-9001"),
    (AssertionError_, ("test",), "FC-9002"),
    (UnexpectedStateError, ("test",), "FC-9003"),
])
def test_exception_class_contract(error_class, constructor_args, expected_code):
    """Every exception class has correct code, non-empty name, non-empty hint, and valid to_dict()."""
    error = error_class(*constructor_args)
    assert error.code == expected_code
    assert error.name  # non-empty
    assert error.hint  # non-empty
    ctx_dict = error.context.to_dict()
    assert ctx_dict["code"] == expected_code
    assert "message" in ctx_dict
```

#### ExitCode tests

- `test_exit_code_enum_values` — Assert `SUCCESS=0, GENERAL_ERROR=1, CONFIG_ERROR=2, DEPENDENCY_ERROR=3, INPUT_ERROR=4, PROCESSING_ERROR=5, NETWORK_ERROR=6, INTERRUPTED=130`
- `test_get_exit_code_config` — `get_exit_code(ConfigNotFoundError(...))` returns `ExitCode.CONFIG_ERROR`
- `test_get_exit_code_dependency` — `get_exit_code(VapourSynthNotFoundError())` returns `ExitCode.DEPENDENCY_ERROR`
- `test_get_exit_code_input` — `get_exit_code(NoVideosFoundError(...))` returns `ExitCode.INPUT_ERROR`
- `test_get_exit_code_processing` — `get_exit_code(RenderError())` returns `ExitCode.PROCESSING_ERROR`
- `test_get_exit_code_network` — `get_exit_code(SlowpicsError(...))` returns `ExitCode.NETWORK_ERROR`
- `test_get_exit_code_internal` — `get_exit_code(GenericInternalError(...))` returns `ExitCode.GENERAL_ERROR`
- `test_get_exit_code_unknown` — `get_exit_code(FrameCompareError(ErrorContext(code="FC-0000", name="UNKNOWN", message="test")))` returns `ExitCode.GENERAL_ERROR`

#### Formatting tests (with determinism rules)

- `test_format_error_console_basic` — Assert output starts with `"✗ Error [FC-"`, contains message, contains `"Hint:"` if hint exists, contains `"For more details, run with --verbose"`
- `test_format_error_console_verbose` — Assert output contains `"Details:"` when `verbose=True` and `details` is non-empty. **Determinism:** Do not assert exact dict string; assert key substrings are present.
- `test_format_error_console_no_details_verbose` — Assert no `"Details:"` line when `details` is `None` even with `verbose=True`
- `test_format_error_json` — Assert returns `{"success": False, "error": {...}}` where `error["code"]` matches

### 3. UPDATE `docs/DECISIONS.md`

**Purpose:** Document scope decisions for this slice.

**Entry to add:**

```markdown
## 2025-12-29: Error Handling Slice Scope

**Decision:** Phase 1.2 implements only error classes defined in `errors-module.md` sections 3.2–3.6 and helpers in sections 4–5.

**Rationale:** Contract `error_codes.yaml` contains reserved codes (FC-1006, FC-3010, FC-3011, FC-3012, FC-5010, FC-5011) without corresponding SSOT class definitions. These are out-of-scope for this run to avoid SSOT drift.

**Impact:** Future runs can add these classes when SSOT is updated.
```

### 4. UPDATE `CHANGELOG.md`

**Purpose:** Record changes for this release slice.

**Entry to add:**

```markdown
## [Unreleased]

### Added
- Complete error hierarchy: DependencyError (FC-2xxx), InputError (FC-3xxx), ProcessingError (FC-4xxx), NetworkError (FC-5xxx), InternalError (FC-9xxx)
- `ExitCode` enum for CLI exit code mapping
- `get_exit_code()` helper function
- `format_error_console()` and `format_error_json()` formatting utilities
- Comprehensive unit tests for all error types
```

### Derived outputs (DO NOT EDIT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Generated by `scripts/generate_contract_views.py`. Do not edit manually.

## Acceptance Criteria

- [ ] GIVEN any error class in this slice WHEN instantiated THEN `error.code` matches the FC-xxxx code from SSOT
- [ ] GIVEN any error class WHEN instantiated THEN `error.hint` is a non-empty string
- [ ] GIVEN `get_exit_code()` with FC-1xxx code THEN returns `ExitCode.CONFIG_ERROR` (2)
- [ ] GIVEN `get_exit_code()` with FC-2xxx code THEN returns `ExitCode.DEPENDENCY_ERROR` (3)
- [ ] GIVEN `get_exit_code()` with FC-3xxx code THEN returns `ExitCode.INPUT_ERROR` (4)
- [ ] GIVEN `get_exit_code()` with FC-4xxx code THEN returns `ExitCode.PROCESSING_ERROR` (5)
- [ ] GIVEN `get_exit_code()` with FC-5xxx code THEN returns `ExitCode.NETWORK_ERROR` (6)
- [ ] GIVEN `get_exit_code()` with FC-9xxx code THEN returns `ExitCode.GENERAL_ERROR` (1)
- [ ] GIVEN `get_exit_code()` with unknown code (FC-0000) THEN returns `ExitCode.GENERAL_ERROR` (1)
- [ ] GIVEN `format_error_console(verbose=False)` with details THEN output contains "For more details" line
- [ ] GIVEN `format_error_console(verbose=True)` with details THEN output contains "Details:" and key substrings
- [ ] GIVEN `format_error_json()` THEN returns `{"success": False, "error": {...}}` structure

## Verification Commands

```bash
# Quality gates (must all exit 0)
.venv/bin/pyright --warnings src/frame_compare/errors.py
.venv/bin/ruff check src/frame_compare/errors.py
.venv/bin/pytest -v tests/test_errors.py

# Workflow validation (must all exit 0)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-28__p1-2__error-handling
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-28__p1-2__error-handling
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md

# Contract gates (optional safety checks — run to confirm no drift)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Preserve existing code:** Phase 1.1 code remains unchanged. Append new classes after existing `PresetInvalidError`.

2. **Trailing underscore convention:** Use `MemoryError_`, `TimeoutError_`, `AssertionError_` to avoid shadowing builtins.

3. **Inheritance hierarchy:** `SelectionError → AnalysisError → ProcessingError`. `EncodingError` and `OverlayError → RenderError → ProcessingError`.

4. **Import constraint (leaf module):** Only stdlib + typing. No `frame_compare.*` imports.

5. **Marker base classes:** `ServiceError` and `PublishError` have no FC code. They are pure marker bases for type hierarchy.

6. **Parametric test imports:** The test file must import all exception classes to use in the parametric test.

7. **Determinism in tests:** When checking `format_error_console` output with details, do not compare exact dict strings. Check for presence of key substrings (e.g., `'"path":' in output`).

8. **Update module docstring:** Add all new FC codes to the module docstring at top of `errors.py`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-2__error-handling

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v2.md
