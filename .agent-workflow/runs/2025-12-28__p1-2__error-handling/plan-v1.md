---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v1
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v1.md
---

# Implementation Plan: Error Handling Module

## Context

**Phase:** 1 (Core Infrastructure)
**Module:** `frame_compare.errors`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`
**Dependencies:** None (leaf module). Phase 1.1 Config Module already implemented base types and Config errors.

## Scope

This plan covers:

- [x] `ErrorContext` dataclass (already exists from Phase 1.1)
- [x] `FrameCompareError` base class (already exists)
- [x] `ConfigError` hierarchy (FC-1001 to FC-1005 — already implemented)
- [ ] Complete `DependencyError` hierarchy (FC-2xxx)
- [ ] Complete `InputError` hierarchy (FC-3xxx)
- [ ] Complete `ProcessingError` hierarchy (FC-4xxx)
- [ ] Complete `NetworkError` hierarchy (FC-5xxx)
- [ ] Complete `InternalError` hierarchy (FC-9xxx)
- [ ] `ExitCode` enum
- [ ] `get_exit_code(error) -> ExitCode` helper
- [ ] `format_error_console()` and `format_error_json()` utilities
- [ ] Unit tests for new error types and helpers

This plan does NOT cover:

- Result[T, E] pattern (optional, will be added in a future phase if needed)
- CLI error handlers (Phase 1.4)
- Logging infrastructure (Phase 1.3)

## Contract Impact

**Contracts touched:** YES

If YES:

- **Canonical files:** `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`
- **Derived outputs:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` (generated)
- **Regeneration:** `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
- **Freshness gate:** `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
- **Traceability gate:** `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`

> [!NOTE]
> No changes to the contracts are planned in this phase. All FC-xxxx codes already exist in `error_codes.yaml`. This section is present for workflow compliance.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.2 Dependency Errors (FC-2xxx)" — Defines all dependency error classes
  - Section: "3.3 Input Errors (FC-3xxx)" — Defines all input error classes
  - Section: "3.4 Processing Errors (FC-4xxx)" — Defines all processing error classes
  - Section: "3.5 Network Errors (FC-5xxx)" — Defines all network error classes
  - Section: "3.6 Internal Errors (FC-9xxx)" — Defines all internal error classes
  - Section: "4. Exit Code Mapping" — Defines `ExitCode` enum and `get_exit_code()`
  - Section: "5. Error Formatting Utilities" — Defines `format_error_console()` and `format_error_json()`

- `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`:
  - All FC-xxxx codes are authoritative here

## Files to Create/Modify

### 1. `src/frame_compare/errors.py` (MODIFY)

**Purpose:** Complete the error type hierarchy started in Phase 1.1.

**Types to add (per Spec Anchors):**

Already exists (from Phase 1.1):

- `JSONValue`, `ErrorDetails` type aliases
- `ErrorContext` dataclass
- `FrameCompareError` base class
- `ConfigError`, `ConfigNotFoundError`, `ConfigParseError`, `ConfigValidationError`, `PresetNotFoundError`, `PresetInvalidError`

**New base classes to add:**

- `DependencyError(FrameCompareError)` — Base for FC-2xxx
- `InputError(FrameCompareError)` — Base for FC-3xxx
- `ProcessingError(FrameCompareError)` — Base for FC-4xxx
- `NetworkError(FrameCompareError)` — Base for FC-5xxx
- `InternalError(FrameCompareError)` — Base for FC-9xxx
- `ServiceError(FrameCompareError)` — Alias base for service-layer errors

**DependencyError subclasses (FC-2xxx):**

- `VapourSynthNotFoundError() -> DependencyError` — FC-2001
- `VapourSynthError(details: str) -> DependencyError` — FC-2002
- `PluginNotFoundError(plugin: str) -> DependencyError` — FC-2003
- `LibplaceboError(details: str) -> DependencyError` — FC-2004
- `FFmpegNotFoundError() -> DependencyError` — FC-2005
- `FFmpegError(details: str, returncode: int | None = None) -> DependencyError` — FC-2006
- `DoviToolNotFoundError() -> DependencyError` — FC-2007
- `PythonVersionError(version: str) -> DependencyError` — FC-2010

**InputError subclasses (FC-3xxx):**

- `NoVideosFoundError(path: Path, patterns: list[str] | None = None) -> InputError` — FC-3001
- `VideoOpenError(path: Path, reason: str | None = None) -> InputError` — FC-3002
- `VideoCorruptError(path: Path) -> InputError` — FC-3003
- `InsufficientFramesError(path: Path, count: int, required: int) -> InputError` — FC-3004
- `IncompatibleVideosError(details: str) -> InputError` — FC-3005
- `DirectoryNotFoundError(path: Path) -> InputError` — FC-3006
- `DirectoryNotWritableError(path: Path) -> InputError` — FC-3007
- `FileTooLargeError(path: Path, size: int, limit: int) -> InputError` — FC-3008
- `PathEscapesRootError(root: Path, candidate: Path) -> InputError` — FC-3009

**ProcessingError subclasses (FC-4xxx):**

- `FrameExtractionError(frame: int, clip: str | Path) -> ProcessingError` — FC-4001
- `MetricsCalculationError(details: str) -> ProcessingError` — FC-4002
- `TonemapError(details: str) -> ProcessingError` — FC-4003
- `RenderError(details: str | None = None) -> ProcessingError` — FC-4004
- `AudioAlignmentError(details: str) -> ProcessingError` — FC-4005
- `CacheCorruptionError(path: Path) -> ProcessingError` — FC-4006
- `CacheVersionMismatchError(expected: str, found: str) -> ProcessingError` — FC-4007
- `MemoryError_(details: str | None = None) -> ProcessingError` — FC-4010
- `TimeoutError_(operation: str, timeout: float) -> ProcessingError` — FC-4011
- `AnalysisError(ProcessingError)` — Base for analysis errors
- `SelectionError(reason: str, requested: int, available: int) -> AnalysisError` — FC-4012
- `EncodingError(output_path: Path, details: str) -> RenderError` — FC-4013
- `OverlayError(details: str) -> RenderError` — FC-4014
- `SourceLoadError(path: Path, details: str) -> ProcessingError` — FC-4015
- `MetadataError(details: str) -> ServiceError` — FC-4016
- `ReportError(details: str) -> ServiceError` — FC-4017
- `DoviError(path: Path, details: str) -> ServiceError` — FC-4018

**NetworkError subclasses (FC-5xxx):**

- `NetworkUnreachableError() -> NetworkError` — FC-5001
- `SlowpicsError(details: str) -> NetworkError` — FC-5002
- `SlowpicsRateLimitedError(retry_after: int | None = None) -> NetworkError` — FC-5003
- `SlowpicsUnavailableError() -> NetworkError` — FC-5004
- `TmdbError(details: str) -> NetworkError` — FC-5005
- `TmdbRateLimitedError(retry_after: int | None = None) -> NetworkError` — FC-5006
- `NetworkTimeoutError(service: str, timeout: float) -> NetworkError` — FC-5007
- `SSLError(details: str) -> NetworkError` — FC-5008

**InternalError subclasses (FC-9xxx):**

- `GenericInternalError(details: str) -> InternalError` — FC-9001
- `AssertionError_(details: str) -> InternalError` — FC-9002
- `UnexpectedStateError(details: str) -> InternalError` — FC-9003

**New enums/functions to add:**

- `ExitCode(IntEnum)` — SUCCESS=0, GENERAL_ERROR=1, CONFIG_ERROR=2, DEPENDENCY_ERROR=3, INPUT_ERROR=4, PROCESSING_ERROR=5, NETWORK_ERROR=6, INTERRUPTED=130
- `get_exit_code(error: FrameCompareError) -> ExitCode` — Map error code prefix to exit code
- `format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str` — Console-friendly format
- `format_error_json(error: FrameCompareError) -> dict[str, JSONValue]` — JSON-serializable format

### 2. `tests/test_errors.py` (NEW)

**Purpose:** Unit tests for all error types and helper functions.

**Tests required (grouped by category):**

**ErrorContext tests:**

- `test_error_context_minimal` — Minimal fields work
- `test_error_context_full` — All fields work
- `test_error_context_to_dict_minimal` — JSON serialization without optional fields
- `test_error_context_to_dict_full` — JSON serialization with all fields

**FrameCompareError tests:**

- `test_frame_compare_error_properties` — Properties accessible
- `test_frame_compare_error_str` — String format includes code and message
- `test_frame_compare_error_repr` — Repr format

**DependencyError tests:**

- `test_vapoursynth_not_found_error` — FC-2001
- `test_vapoursynth_error` — FC-2002 with details
- `test_plugin_not_found_error` — FC-2003 with plugin name
- `test_ffmpeg_error` — FC-2006 with returncode

**InputError tests:**

- `test_no_videos_found_error` — FC-3001 with patterns
- `test_video_open_error` — FC-3002 with reason
- `test_insufficient_frames_error` — FC-3004 with count/required
- `test_path_escapes_root_error` — FC-3009 with root/candidate

**ProcessingError tests:**

- `test_frame_extraction_error` — FC-4001
- `test_cache_corruption_error` — FC-4006
- `test_selection_error` — FC-4012

**NetworkError tests:**

- `test_slowpics_error` — FC-5002
- `test_network_timeout_error` — FC-5007 with service/timeout
- `test_slowpics_rate_limited_error` — FC-5003 with retry_after

**InternalError tests:**

- `test_generic_internal_error` — FC-9001
- `test_assertion_error` — FC-9002

**ExitCode tests:**

- `test_exit_code_enum_values` — All values match spec
- `test_get_exit_code_config` — FC-1xxx → 2
- `test_get_exit_code_dependency` — FC-2xxx → 3
- `test_get_exit_code_input` — FC-3xxx → 4
- `test_get_exit_code_processing` — FC-4xxx → 5
- `test_get_exit_code_network` — FC-5xxx → 6
- `test_get_exit_code_internal` — FC-9xxx → 1

**Formatting tests:**

- `test_format_error_console_basic` — Without verbose
- `test_format_error_console_verbose` — With verbose shows details
- `test_format_error_json` — Returns valid structure

## Acceptance Criteria

- [ ] GIVEN any error class WHEN instantiated THEN `error.code` matches the FC-xxxx code from `error_codes.yaml`
- [ ] GIVEN any error class WHEN instantiated THEN `error.hint` is a non-empty string
- [ ] GIVEN `get_exit_code()` called with a ConfigError WHEN mapping THEN returns `ExitCode.CONFIG_ERROR` (2)
- [ ] GIVEN `get_exit_code()` called with a DependencyError WHEN mapping THEN returns `ExitCode.DEPENDENCY_ERROR` (3)
- [ ] GIVEN `get_exit_code()` called with an InputError WHEN mapping THEN returns `ExitCode.INPUT_ERROR` (4)
- [ ] GIVEN `get_exit_code()` called with a ProcessingError WHEN mapping THEN returns `ExitCode.PROCESSING_ERROR` (5)
- [ ] GIVEN `get_exit_code()` called with a NetworkError WHEN mapping THEN returns `ExitCode.NETWORK_ERROR` (6)
- [ ] GIVEN `get_exit_code()` called with an InternalError WHEN mapping THEN returns `ExitCode.GENERAL_ERROR` (1)
- [ ] GIVEN `format_error_console()` with verbose=False WHEN formatting THEN output does NOT include details dict
- [ ] GIVEN `format_error_console()` with verbose=True WHEN formatting THEN output includes details dict
- [ ] GIVEN `format_error_json()` called WHEN formatting THEN output is a dict with `success=False` and `error` key

## Verification Commands

```bash
# Quality gates (must all exit 0)
.venv/bin/pyright --warnings src/frame_compare/errors.py
.venv/bin/ruff check src/frame_compare/errors.py
.venv/bin/pytest -v tests/test_errors.py

# Contract gates (must pass)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Preserve existing code:** Phase 1.1 already created `ErrorContext`, `FrameCompareError`, and all `ConfigError` subclasses. Do NOT delete or break these. Append new exception classes after the existing ones.

2. **Trailing underscore convention:** For errors that shadow builtins (`MemoryError_`, `TimeoutError_`, `AssertionError_`), use trailing underscore to avoid conflicts.

3. **Inheritance hierarchy:** Follow exact hierarchy from spec. For example, `SelectionError` extends `AnalysisError`, which extends `ProcessingError`. `EncodingError` and `OverlayError` extend `RenderError`.

4. **Type imports:** Use `from pathlib import Path` and ensure `Path` is imported (it already is from Phase 1.1).

5. **Error code prefixes:** All codes already exist in `error_codes.yaml`. Match codes exactly:
   - FC-1xxx: Config (already done)
   - FC-2xxx: Dependency
   - FC-3xxx: Input
   - FC-4xxx: Processing
   - FC-5xxx: Network
   - FC-9xxx: Internal

6. **`PublishError` base class:** The spec mentions `PublishError(ServiceError)` as FC-5xxx alias but no concrete subclass uses it yet. Add as empty class for forward compatibility.

7. **Test file location:** Create `tests/test_errors.py` at root tests directory (not in a subdirectory).

8. **docmodule update:** Update the module docstring at the top of `errors.py` to include all FC-xxxx codes.

---

> **Proposed RUN_ID:** 2025-12-28__p1-2__error-handling
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2025-12-28__p1-2__error-handling` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-2__error-handling

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v1.md
