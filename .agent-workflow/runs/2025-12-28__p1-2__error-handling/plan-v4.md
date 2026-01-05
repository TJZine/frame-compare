---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v4
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v4.md
---

# Implementation Plan: Error Handling Module

## Changes Since plan-v3

- **Fix 1:** Corrected exception count from 38 to 44.
- **Fix 2:** Added exact test function names for all tests.
- **Fix 3:** Made verification pass criteria explicit; clarified when to run optional contract gates.

## Context

**Phase:** 1 (Core Infrastructure)
**Module:** `frame_compare.errors`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`
**Dependencies:** None. **Leaf module** — may only import Python stdlib + `typing`. Must NOT import `frame_compare.*`.

Phase 1.1 already implemented: `ErrorContext`, `FrameCompareError`, `ConfigError` hierarchy (FC-1001–FC-1005).

## Scope

**In scope:** DependencyError (FC-2xxx), InputError (FC-3xxx), ProcessingError (FC-4xxx), NetworkError (FC-5xxx), InternalError (FC-9xxx), `ExitCode` enum, `get_exit_code()`, `format_error_console()`, `format_error_json()`, comprehensive tests.

**Out of scope:** Result[T,E] pattern, CLI error handlers (Phase 1.4), Logging (Phase 1.3), contract-only codes without SSOT class (FC-1006, FC-3010–3012, FC-5010–5011).

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section "3.2 Dependency Errors (FC-2xxx)"
  - Section "3.3 Input Errors (FC-3xxx)"
  - Section "3.4 Processing Errors (FC-4xxx)"
  - Section "3.5 Network Errors (FC-5xxx)"
  - Section "3.6 Internal Errors (FC-9xxx)"
  - Section "4. Exit Code Mapping"
  - Section "5. Error Formatting Utilities"

### Planned Public Signatures (Helpers)

- `get_exit_code(error: FrameCompareError) -> ExitCode`
- `format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str`
- `format_error_json(error: FrameCompareError) -> dict[str, JSONValue]`

## Files to Create/Modify

### 1. MODIFY `src/frame_compare/errors.py`

**Purpose:** Complete error hierarchy. Preserve Phase 1.1 code; append new classes.

#### New Base Classes

| Class | Parent | Notes |
|-------|--------|-------|
| `DependencyError` | `FrameCompareError` | Base for FC-2xxx |
| `InputError` | `FrameCompareError` | Base for FC-3xxx |
| `ProcessingError` | `FrameCompareError` | Base for FC-4xxx |
| `NetworkError` | `FrameCompareError` | Base for FC-5xxx |
| `InternalError` | `FrameCompareError` | Base for FC-9xxx |
| `ServiceError` | `FrameCompareError` | Marker base (no FC code) |
| `PublishError` | `ServiceError` | Marker base; never instantiated |
| `AnalysisError` | `ProcessingError` | Marker base for analysis errors |

#### DependencyError Subclasses (FC-2xxx) — 8 classes

| Class | `__init__` Signature | Attrs | Code |
|-------|---------------------|-------|------|
| `VapourSynthNotFoundError` | `(self) -> None` | — | FC-2001 |
| `VapourSynthError` | `(self, details: str) -> None` | — | FC-2002 |
| `PluginNotFoundError` | `(self, plugin: str) -> None` | `.plugin` | FC-2003 |
| `LibplaceboError` | `(self, details: str) -> None` | — | FC-2004 |
| `FFmpegNotFoundError` | `(self) -> None` | — | FC-2005 |
| `FFmpegError` | `(self, details: str, returncode: int \| None = None) -> None` | — | FC-2006 |
| `DoviToolNotFoundError` | `(self) -> None` | — | FC-2007 |
| `PythonVersionError` | `(self, version: str) -> None` | — | FC-2010 |

#### InputError Subclasses (FC-3xxx) — 9 classes

| Class | `__init__` Signature | Attrs | Code |
|-------|---------------------|-------|------|
| `NoVideosFoundError` | `(self, path: Path, patterns: list[str] \| None = None) -> None` | `.path` | FC-3001 |
| `VideoOpenError` | `(self, path: Path, reason: str \| None = None) -> None` | `.path` | FC-3002 |
| `VideoCorruptError` | `(self, path: Path) -> None` | `.path` | FC-3003 |
| `InsufficientFramesError` | `(self, path: Path, count: int, required: int) -> None` | `.path` | FC-3004 |
| `IncompatibleVideosError` | `(self, details: str) -> None` | — | FC-3005 |
| `DirectoryNotFoundError` | `(self, path: Path) -> None` | `.path` | FC-3006 |
| `DirectoryNotWritableError` | `(self, path: Path) -> None` | `.path` | FC-3007 |
| `FileTooLargeError` | `(self, path: Path, size: int, limit: int) -> None` | `.path` | FC-3008 |
| `PathEscapesRootError` | `(self, root: Path, candidate: Path) -> None` | `.root`, `.candidate` | FC-3009 |

#### ProcessingError Subclasses (FC-4xxx) — 16 classes

| Class | `__init__` Signature | Attrs | Code |
|-------|---------------------|-------|------|
| `FrameExtractionError` | `(self, frame: int, clip: str \| Path) -> None` | — | FC-4001 |
| `MetricsCalculationError` | `(self, details: str) -> None` | — | FC-4002 |
| `TonemapError` | `(self, details: str) -> None` | — | FC-4003 |
| `RenderError` | `(self, details: str \| None = None) -> None` | — | FC-4004 |
| `AudioAlignmentError` | `(self, details: str) -> None` | — | FC-4005 |
| `CacheCorruptionError` | `(self, path: Path) -> None` | `.path` | FC-4006 |
| `CacheVersionMismatchError` | `(self, expected: str, found: str) -> None` | — | FC-4007 |
| `MemoryError_` | `(self) -> None` | — | FC-4010 |
| `TimeoutError_` | `(self, operation: str, timeout: float) -> None` | — | FC-4011 |
| `SelectionError` | `(self, reason: str, requested: int, available: int) -> None` | — | FC-4012 |
| `EncodingError` | `(self, output_path: Path, details: str) -> None` | — | FC-4013 |
| `OverlayError` | `(self, details: str) -> None` | — | FC-4014 |
| `SourceLoadError` | `(self, path: Path, details: str) -> None` | — | FC-4015 |
| `MetadataError` | `(self, details: str) -> None` | — | FC-4016 |
| `ReportError` | `(self, details: str) -> None` | — | FC-4017 |
| `DoviError` | `(self, path: Path, details: str) -> None` | — | FC-4018 |

**Inheritance:** `SelectionError` → `AnalysisError` → `ProcessingError`. `EncodingError`, `OverlayError` → `RenderError` → `ProcessingError`. `MetadataError`, `ReportError`, `DoviError` → `ServiceError`.

#### NetworkError Subclasses (FC-5xxx) — 8 classes

| Class | `__init__` Signature | Code |
|-------|---------------------|------|
| `NetworkUnreachableError` | `(self) -> None` | FC-5001 |
| `SlowpicsError` | `(self, details: str) -> None` | FC-5002 |
| `SlowpicsRateLimitedError` | `(self, retry_after: int \| None = None) -> None` | FC-5003 |
| `SlowpicsUnavailableError` | `(self) -> None` | FC-5004 |
| `TmdbError` | `(self, details: str) -> None` | FC-5005 |
| `TmdbRateLimitedError` | `(self, retry_after: int \| None = None) -> None` | FC-5006 |
| `NetworkTimeoutError` | `(self, service: str, timeout: float) -> None` | FC-5007 |
| `SSLError` | `(self, details: str) -> None` | FC-5008 |

#### InternalError Subclasses (FC-9xxx) — 3 classes

| Class | `__init__` Signature | Code |
|-------|---------------------|------|
| `GenericInternalError` | `(self, details: str) -> None` | FC-9001 |
| `AssertionError_` | `(self, details: str) -> None` | FC-9002 |
| `UnexpectedStateError` | `(self, details: str) -> None` | FC-9003 |

**Total new FC-coded exception classes: 44** (8 + 9 + 16 + 8 + 3)

#### ExitCode and Helpers

Per SSOT Section 4–5. `ExitCode(IntEnum)` with values: SUCCESS=0, GENERAL_ERROR=1, CONFIG_ERROR=2, DEPENDENCY_ERROR=3, INPUT_ERROR=4, PROCESSING_ERROR=5, NETWORK_ERROR=6, INTERRUPTED=130.

`get_exit_code()` returns `GENERAL_ERROR` for unknown code prefixes.

### 2. NEW `tests/test_errors.py`

**Exact test function names:**

#### Parametric exception test

- `test_exception_class_contract` — Parametrize over all 44 FC-coded exceptions listed in tables above (in table order). Each iteration asserts: `error.code` matches expected, `error.name` non-empty, `error.hint` non-empty, `error.context.to_dict()` has keys `code`, `name`, `message`.

#### ExitCode tests

- `test_exit_code_enum_values` — Assert `SUCCESS=0, GENERAL_ERROR=1, CONFIG_ERROR=2, DEPENDENCY_ERROR=3, INPUT_ERROR=4, PROCESSING_ERROR=5, NETWORK_ERROR=6, INTERRUPTED=130`.
- `test_get_exit_code_config` — `get_exit_code(ConfigNotFoundError(...))` returns `ExitCode.CONFIG_ERROR`.
- `test_get_exit_code_dependency` — `get_exit_code(VapourSynthNotFoundError())` returns `ExitCode.DEPENDENCY_ERROR`.
- `test_get_exit_code_input` — `get_exit_code(NoVideosFoundError(...))` returns `ExitCode.INPUT_ERROR`.
- `test_get_exit_code_processing` — `get_exit_code(RenderError())` returns `ExitCode.PROCESSING_ERROR`.
- `test_get_exit_code_network` — `get_exit_code(SlowpicsError(...))` returns `ExitCode.NETWORK_ERROR`.
- `test_get_exit_code_internal` — `get_exit_code(GenericInternalError(...))` returns `ExitCode.GENERAL_ERROR`.
- `test_get_exit_code_unknown` — `get_exit_code(FrameCompareError(ErrorContext(code="FC-0000", name="UNKNOWN", message="test")))` returns `ExitCode.GENERAL_ERROR`.

#### Formatting tests

- `test_format_error_console_basic` — Assert output starts with `"✗ Error [FC-"`, contains message, contains `"Hint:"`, contains `"For more details, run with --verbose"`.
- `test_format_error_console_verbose_with_details` — Use `CacheCorruptionError(Path("/cache"))`. Assert output contains `"Details:"`, `"'path'"`, `"/cache"`.
- `test_format_error_console_verbose_no_details` — Use `RenderError()` (no details). Assert no `"Details:"` line.
- `test_format_error_json` — Assert returns `{"success": False, "error": {...}}` where `error["code"]` matches.

### 3. UPDATE `docs/DECISIONS.md`

Add entry documenting scope decision for contract-only codes.

### 4. UPDATE `CHANGELOG.md`

**Edit rule:** Append bullets under existing `## [Unreleased]` → `### Added` section. If `### Added` is missing, create it under `[Unreleased]`. Do NOT create duplicate headers.

**Entry:**

```markdown
- Complete error hierarchy: DependencyError, InputError, ProcessingError, NetworkError, InternalError
- `ExitCode` enum for CLI exit code mapping
- `get_exit_code()` helper function
- `format_error_console()` and `format_error_json()` formatting utilities
```

## Acceptance Criteria

- [ ] Every new exception class has correct FC code, non-empty name, non-empty hint
- [ ] `get_exit_code()` maps FC-1xxx→2, FC-2xxx→3, FC-3xxx→4, FC-4xxx→5, FC-5xxx→6, FC-9xxx→1, unknown→1
- [ ] `format_error_console(verbose=False)` includes "For more details" line
- [ ] `format_error_console(verbose=True)` with details includes `"Details:"`, key, and value substrings
- [ ] `format_error_json()` returns `{"success": False, "error": {...}}`

## Verification Commands

```bash
# Quality gates
.venv/bin/pyright --warnings src/frame_compare/errors.py
.venv/bin/ruff check src/frame_compare/errors.py
.venv/bin/pytest -v tests/test_errors.py

# Workflow validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-28__p1-2__error-handling
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-28__p1-2__error-handling
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v4.md
```

**Pass criteria:** All commands exit 0; `pyright` emits no warnings; `ruff` emits no findings; pytest exits 0.

**Optional contract gates (run only if files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` changed in this run; otherwise skip):**

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

## Notes for Coding Agent

1. **Preserve Phase 1.1 code.** Append after `PresetInvalidError`.
2. **Trailing underscores:** `MemoryError_`, `TimeoutError_`, `AssertionError_`.
3. **Marker bases:** `ServiceError`, `PublishError`, `AnalysisError` are never instantiated.
4. **Leaf module:** Only stdlib imports.
5. **Test determinism:** Use Python repr substrings (`'path'`), not JSON (`"path"`).
6. **SSOT clarification required? STOP.** Do not improvise; return to planning.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-2__error-handling

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v4.md
