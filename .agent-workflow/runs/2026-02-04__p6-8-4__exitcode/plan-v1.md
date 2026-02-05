---
RUN_ID: 2026-02-04__p6-8-4__exitcode
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Exit codes (`ExitCode`, error mapping, CLI integration tests)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md
---

# Implementation Plan: CLI Exit Codes (`ExitCode` + Error→Exit Mapping + Tests)

## Context
**Phase:** 6
**Module:** `frame_compare.errors` (exit codes + mapping) and `frame_compare.cli_entry` (CLI error handling + exits)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`
**Dependencies:** Existing CLI command implementations (run/wizard/doctor/preset), existing error taxonomy (FC-1xxx…FC-9xxx)

## Scope
This plan covers:
- [ ] Implement/confirm `ExitCode` enum values per SSOT
- [ ] Implement/confirm deterministic error→exit-code mapping (`get_exit_code`) per SSOT categories
- [ ] Integrate exit-code usage across CLI commands (avoid magic numbers)
- [ ] Write/extend CLI integration tests that assert exit codes for each mapped category (including generic `FrameCompareError` with a category code)

This plan does NOT cover:
- Changing or adding new error codes / categories (no SSOT or contract edits)
- Adding new CLI commands or new CLI options
- Docker verification (no external deps required for this slice)

## Contract Impact
**Contracts touched:** NO

Contract to conform to (no edits planned):
- `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml` (per-error `exit_code` expectations by category)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "4. Exit Code Mapping"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2.2 Exit Codes"
  - Section: "8. Error Handling"
  - Section: "9. Testing Strategy"

## Files to Create/Modify

### 1. `src/frame_compare/errors.py` (MODIFY)
**Purpose:** Define the single source of truth for CLI exit codes and map `FrameCompareError` → `ExitCode` deterministically.

**Types to define/confirm:**
- `ExitCode` — `IntEnum` with the exact numeric values defined in SSOT (0, 1, 2, 3, 4, 5, 6, 130).

**Functions to implement (spec-anchored):**
- `get_exit_code(error: FrameCompareError) -> ExitCode` — map by `error.code` category prefix (`FC-1`…`FC-5`), defaulting to `GENERAL_ERROR`

**Key implementation notes:**
- Mapping must be based on `error.code` prefix (category), not on concrete subclass type, so that a generic `FrameCompareError` with e.g. `FC-3000` maps to `INPUT_ERROR`.
- Keep `ExitCode.INTERRUPTED = 130` defined here for CLI use, but do not special-case `KeyboardInterrupt` inside `get_exit_code` (CLI handles interrupts explicitly).

### 2. `src/frame_compare/cli_entry.py` (MODIFY)
**Purpose:** Ensure all CLI exits use `ExitCode` (no magic numbers) and all CLI error paths map through the SSOT exit-code mapping.

**Functions to implement (spec-anchored):**
- `handle_error(error: Exception, *, no_color: bool, verbose: bool) -> int` — print an error message (FrameCompareError → formatted), return the correct exit code for the error category

**Key implementation notes:**
- Use `int(ExitCode.<NAME>)` for all `typer.Exit(code=...)` sites:
  - `KeyboardInterrupt` / cancellation -> `ExitCode.INTERRUPTED`
  - runner returns `RunResult(success=False)` -> `ExitCode.PROCESSING_ERROR`
- `handle_error(...)` behavior:
  - If `error` is a `FrameCompareError`, use existing formatting helpers and `get_exit_code(error)`.
  - If `error` is not a `FrameCompareError`, emit a generic message to stderr and return `ExitCode.GENERAL_ERROR` (no stack trace in normal CLI flow).
- JSON error output path (`run --json`) must remain “stdout is pure JSON” and exit with the same mapped code as non-JSON mode.

### 3. `tests/test_errors.py` (MODIFY)
**Purpose:** Validate `ExitCode` values and that `get_exit_code(...)` maps based on `FC-xxxx` category prefix (including generic `FrameCompareError`).

**Tests required:**
- test_exit_code_enum_values — numeric values match SSOT
- test_get_exit_code_maps_by_error_code_prefix_for_generic_error — construct a generic `FrameCompareError` with an `FC-1xxx`/`FC-2xxx`/`FC-3xxx`/`FC-4xxx`/`FC-5xxx` code and assert the corresponding `ExitCode`

### 4. `tests/cli/test_cli_commands.py` (MODIFY)
**Purpose:** CLI integration tests for error exit codes via `CliRunner` (run command) across all mapped categories.

**Tests required:**
- test_run_exit_code_maps_by_error_category_prefix_in_json_mode — monkeypatch runner to raise a generic `FrameCompareError` with `FC-3xxx`; assert exit code is `INPUT_ERROR` and stdout is valid JSON error payload
- test_run_exit_code_is_130_on_keyboard_interrupt — monkeypatch runner to raise `KeyboardInterrupt`; assert exit code is 130

### 5. `tests/cli/test_exit_codes.py` (MODIFY)
**Purpose:** Unit-level assertion that CLI-layer `handle_error(...)` returns the correct codes for representative errors.

**Tests required:**
- Extend existing mapping test with one non-`FrameCompareError` case that returns exit code 1 (and does not raise).

## Acceptance Criteria

- [ ] GIVEN `ExitCode` is imported in CLI WHEN a CLI path exits THEN the exit code equals the corresponding `ExitCode` numeric value (no magic numbers used for 5/130/3/etc.)
- [ ] GIVEN a `FrameCompareError` with code `FC-1xxx` WHEN `get_exit_code(...)` is called THEN it returns `ExitCode.CONFIG_ERROR` (and similarly for FC-2xxx/3xxx/4xxx/5xxx)
- [ ] GIVEN a generic `FrameCompareError` (not a subclass) with an `FC-3xxx` code WHEN the CLI run command encounters it THEN CLI exits with `ExitCode.INPUT_ERROR` in both JSON and non-JSON modes
- [ ] GIVEN the user interrupts execution (Ctrl+C) WHEN `frame-compare run` or `frame-compare wizard` is running THEN exit code is 130

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/errors.py src/frame_compare/cli_entry.py tests/test_errors.py tests/cli/test_cli_commands.py tests/cli/test_exit_codes.py
.venv/bin/ruff check src/frame_compare/errors.py src/frame_compare/cli_entry.py tests/test_errors.py tests/cli/test_cli_commands.py tests/cli/test_exit_codes.py
.venv/bin/pytest -q tests/test_errors.py tests/cli/test_cli_commands.py tests/cli/test_exit_codes.py
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- Keep mapping logic centralized: `cli_entry` should not duplicate category rules; call `get_exit_code(...)`.
- Keep CLI tests hermetic: monkeypatch `runner.run` and avoid real I/O/network/external binaries.
- If any change would require modifying SSOT specs or `contracts/error_codes.yaml`, STOP and route back to Planning with a new run (do not “quietly fix” spec/contract drift inside implementation).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8-4__exitcode

## Plan to Review
Read file: .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-review-v1.md
