---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v5
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v5.md
---

# Implementation Plan: Error Handling Module

## Changes Since plan-v4

- **Fix 1:** Added exact `docs/DECISIONS.md` entry content with date and body.
- **Fix 2:** Added explicit 44-entry parametric test table with deterministic constructor args.

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
  - Section: "3.2 Dependency Errors (FC-2xxx) — Exit Code 3"
  - Section: "3.3 Input Errors (FC-3xxx) — Exit Code 4"
  - Section: "3.4 Processing Errors (FC-4xxx) — Exit Code 5"
  - Section: "3.5 Network Errors (FC-5xxx) — Exit Code 6"
  - Section: "3.6 Internal Errors (FC-9xxx) — Exit Code 1"
  - Section: "4. Exit Code Mapping"
  - Section: "5. Error Formatting Utilities"

## Planned Public Signatures (Helpers)

- `get_exit_code(error: FrameCompareError) -> ExitCode`
- `format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str`
- `format_error_json(error: FrameCompareError) -> dict[str, JSONValue]`

## Files to Create/Modify

### 1. MODIFY `src/frame_compare/errors.py`

**Purpose:** Complete error hierarchy. Preserve Phase 1.1 code; append new classes.

*(Exception class tables unchanged from plan-v4 — see SSOT for exact signatures)*

#### Summary of new classes (44 FC-coded exceptions)

- **DependencyError (8):** VapourSynthNotFoundError, VapourSynthError, PluginNotFoundError, LibplaceboError, FFmpegNotFoundError, FFmpegError, DoviToolNotFoundError, PythonVersionError
- **InputError (9):** NoVideosFoundError, VideoOpenError, VideoCorruptError, InsufficientFramesError, IncompatibleVideosError, DirectoryNotFoundError, DirectoryNotWritableError, FileTooLargeError, PathEscapesRootError
- **ProcessingError (16):** FrameExtractionError, MetricsCalculationError, TonemapError, RenderError, AudioAlignmentError, CacheCorruptionError, CacheVersionMismatchError, MemoryError_, TimeoutError_, SelectionError, EncodingError, OverlayError, SourceLoadError, MetadataError, ReportError, DoviError
- **NetworkError (8):** NetworkUnreachableError, SlowpicsError, SlowpicsRateLimitedError, SlowpicsUnavailableError, TmdbError, TmdbRateLimitedError, NetworkTimeoutError, SSLError
- **InternalError (3):** GenericInternalError, AssertionError_, UnexpectedStateError
- **Marker bases (3):** ServiceError, PublishError, AnalysisError

#### ExitCode and Helpers

Per SSOT Section 4–5. `ExitCode(IntEnum)`: SUCCESS=0, GENERAL_ERROR=1, CONFIG_ERROR=2, DEPENDENCY_ERROR=3, INPUT_ERROR=4, PROCESSING_ERROR=5, NETWORK_ERROR=6, INTERRUPTED=130.

### 2. NEW `tests/test_errors.py`

#### Parametric test with exact constructor args (44 entries)

```python
@pytest.mark.parametrize("error_class,args,expected_code", [
    # DependencyError (FC-2xxx)
    (VapourSynthNotFoundError, (), "FC-2001"),
    (VapourSynthError, ("test",), "FC-2002"),
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
def test_exception_class_contract(error_class, args, expected_code):
    """Every exception has correct code, non-empty name, non-empty hint, valid to_dict()."""
    error = error_class(*args)
    assert error.code == expected_code
    assert error.name
    assert error.hint
    ctx_dict = error.context.to_dict()
    assert ctx_dict["code"] == expected_code
    assert "message" in ctx_dict
```

#### ExitCode tests

- `test_exit_code_enum_values` — Assert `SUCCESS=0, GENERAL_ERROR=1, CONFIG_ERROR=2, DEPENDENCY_ERROR=3, INPUT_ERROR=4, PROCESSING_ERROR=5, NETWORK_ERROR=6, INTERRUPTED=130`.
- `test_get_exit_code_config` — `get_exit_code(ConfigNotFoundError(Path("/test")))` returns `ExitCode.CONFIG_ERROR`.
- `test_get_exit_code_dependency` — `get_exit_code(VapourSynthNotFoundError())` returns `ExitCode.DEPENDENCY_ERROR`.
- `test_get_exit_code_input` — `get_exit_code(NoVideosFoundError(Path("/test")))` returns `ExitCode.INPUT_ERROR`.
- `test_get_exit_code_processing` — `get_exit_code(RenderError())` returns `ExitCode.PROCESSING_ERROR`.
- `test_get_exit_code_network` — `get_exit_code(SlowpicsError("test"))` returns `ExitCode.NETWORK_ERROR`.
- `test_get_exit_code_internal` — `get_exit_code(GenericInternalError("test"))` returns `ExitCode.GENERAL_ERROR`.
- `test_get_exit_code_unknown` — `get_exit_code(FrameCompareError(ErrorContext(code="FC-0000", name="UNKNOWN", message="test")))` returns `ExitCode.GENERAL_ERROR`.

#### Formatting tests

- `test_format_error_console_basic` — Assert output starts with `"✗ Error [FC-"`, contains message, `"Hint:"`, `"For more details, run with --verbose"`.
- `test_format_error_console_verbose_with_details` — Use `CacheCorruptionError(Path("/cache"))`. Assert contains `"Details:"`, `"'path'"`, `"/cache"`.
- `test_format_error_console_verbose_no_details` — Use `RenderError()`. Assert no `"Details:"` line.
- `test_format_error_json` — Assert returns `{"success": False, "error": {...}}`.

### 3. UPDATE `docs/DECISIONS.md`

**Exact entry to insert** (append at end of file):

```markdown
## 2025-12-29: Error Handling Slice Scope (Phase 1.2)

**Decision:** Phase 1.2 implements only error classes defined in `errors-module.md` sections 3.2–3.6 and helpers in sections 4–5.

**Rationale:** Contract `error_codes.yaml` contains reserved codes (FC-1006, FC-3010, FC-3011, FC-3012, FC-5010, FC-5011) without corresponding SSOT class definitions. These are deferred to avoid SSOT drift.

**Impact:** Future runs may add these classes when SSOT is updated with concrete signatures.
```

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
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v5.md
```

**Pass criteria:** All commands exit 0; `pyright` emits no warnings; `ruff` emits no findings; pytest exits 0.

**Optional contract gates (run only if files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` changed):**

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

## Notes for Coding Agent

1. **Preserve Phase 1.1 code.** Append after `PresetInvalidError`.
2. **Trailing underscores:** `MemoryError_`, `TimeoutError_`, `AssertionError_`.
3. **Marker bases:** `ServiceError`, `PublishError`, `AnalysisError` are never instantiated.
4. **Leaf module:** Only stdlib imports.
5. **Test determinism:** Use Python repr substrings (`'path'`), not JSON.
6. **SSOT clarification required? STOP.** Do not improvise.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-2__error-handling

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v5.md
