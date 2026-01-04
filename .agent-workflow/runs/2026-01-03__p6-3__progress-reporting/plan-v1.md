---
RUN_ID: 2026-01-03__p6-3__progress-reporting
VERSION: v1
TARGET: Phase 6 → Item 6.3 (Progress Reporting)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - src/frame_compare/utils/progress.py
  - src/frame_compare/orchestration/progress.py
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v1.md
---

# Implementation Plan: Progress Reporting — Reporter Selection Logic

## Context

**Phase:** 6
**Module:** orchestration + utils
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` §4.3
**Dependencies:** Phase 6.2 (Preflight & Doctor) — APPROVED

## Current State Analysis

The `ProgressReporter` protocol and all three implementations already exist in `src/frame_compare/utils/progress.py`:

- `ProgressReporter` — Protocol (start_phase, advance, set_description, complete_phase)
- `NullProgressReporter` — No-op for quiet mode
- `RichProgressReporter` — Interactive CLI with progress bar (TTY)
- `LogProgressReporter` — Milestone logging via structlog (non-interactive)

Basic smoke tests exist in `tests/utils/test_progress.py`.

The placeholder `src/frame_compare/orchestration/progress.py` needs the **reporter selection logic** that maps CLI modes to the appropriate reporter.

## Scope

This plan covers:

- [x] Use canonical `ProgressReporter` protocol from `frame_compare.utils.progress`
- [x] Use `RichProgressReporter` for interactive CLI (TTY)
- [x] Use `LogProgressReporter` for `--json` / non-interactive modes
- [x] Use `NullProgressReporter` for quiet mode
- [x] Implement reporter selection logic in orchestration (mode → reporter)
- [x] Write progress reporter tests

This plan does NOT cover:

- JSON-lines progress reporter (PLANNED per spec; not required until it exists)
- Integration with `execute_run()` / phase orchestration (Phase 6.7)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.3 Progress Reporter Selection"
  - Section: "4.3.1 Progress Reporter Tests"

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/progress.py` (MODIFY)

**Purpose:** Implement reporter selection logic that maps output modes to the appropriate `ProgressReporter` implementation.

**Types to define:**

- `OutputMode` — Enum: `INTERACTIVE`, `JSON`, `QUIET` (or use inline string literals per simplicity)

**Functions to implement (spec-anchored):**

- `select_reporter(quiet: bool = False, json_output: bool = False, force_tty: bool | None = None) -> ProgressReporter`

**Algorithm:**

1. If `quiet=True`: return `NullProgressReporter()`
2. If `json_output=True`: return `LogProgressReporter()`
3. If `force_tty is not None`:
   - If `force_tty=True`: return `RichProgressReporter()`
   - If `force_tty=False`: return `LogProgressReporter()`
4. Else detect TTY: `sys.stdout.isatty()`
   - If TTY: return `RichProgressReporter()`
   - Else: return `LogProgressReporter()`

**Priority (SSOT):**

1. `quiet` takes precedence (NullProgressReporter)
2. `json_output` takes precedence over TTY detection (LogProgressReporter)
3. TTY detection is fallback for interactive vs. non-interactive

### 2. `src/frame_compare/orchestration/__init__.py` (MODIFY)

**Purpose:** Export `select_reporter` from the orchestration package.

**Changes:**

- Add import: `from frame_compare.orchestration.progress import select_reporter`
- Add to `__all__`: `"select_reporter"`

### 3. `tests/orchestration/test_progress.py` (NEW)

**Purpose:** Unit tests for reporter selection logic.

**Tests required:**

- `test_select_reporter_quiet_returns_null()` — `quiet=True` → `NullProgressReporter`
- `test_select_reporter_json_returns_log()` — `json_output=True` → `LogProgressReporter`
- `test_select_reporter_force_tty_true_returns_rich()` — `force_tty=True` → `RichProgressReporter`
- `test_select_reporter_force_tty_false_returns_log()` — `force_tty=False` → `LogProgressReporter`
- `test_select_reporter_tty_detection_interactive(monkeypatch)` — Patch `sys.stdout.isatty` to return `True` → `RichProgressReporter`
- `test_select_reporter_tty_detection_non_interactive(monkeypatch)` — Patch `sys.stdout.isatty` to return `False` → `LogProgressReporter`
- `test_select_reporter_quiet_takes_precedence_over_json()` — `quiet=True, json_output=True` → `NullProgressReporter`
- `test_select_reporter_quiet_takes_precedence_over_force_tty()` — `quiet=True, force_tty=True` → `NullProgressReporter`
- `test_select_reporter_json_takes_precedence_over_force_tty()` — `json_output=True, force_tty=True` → `LogProgressReporter`

### 4. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append a run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-03__p6-3__progress-reporting`
- Artifact versions: plan-v1, plan-review-vN, impl-vN, verify-vN, review-vN
- Scope: Reporter selection logic for CLI modes → ProgressReporter implementations
- SSOT edits: None (existing implementation in utils/progress.py already covers protocol and implementations)
- Decision: TTY detection uses `sys.stdout.isatty()` as fallback; `force_tty` parameter allows explicit override for testing

### 5. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for progress reporter selection.

**Entry pattern:**

```
### Added
- `select_reporter()` function for CLI output mode → progress reporter mapping
```

## Acceptance Criteria

- [ ] GIVEN `quiet=True` WHEN calling `select_reporter()` THEN returns `NullProgressReporter` instance
- [ ] GIVEN `json_output=True` WHEN calling `select_reporter()` THEN returns `LogProgressReporter` instance
- [ ] GIVEN `force_tty=True` WHEN calling `select_reporter()` THEN returns `RichProgressReporter` instance
- [ ] GIVEN `force_tty=False` WHEN calling `select_reporter()` THEN returns `LogProgressReporter` instance
- [ ] GIVEN interactive TTY (`sys.stdout.isatty()=True`) and no explicit flags WHEN calling `select_reporter()` THEN returns `RichProgressReporter` instance
- [ ] GIVEN non-interactive environment (`sys.stdout.isatty()=False`) and no explicit flags WHEN calling `select_reporter()` THEN returns `LogProgressReporter` instance
- [ ] GIVEN multiple flags (e.g., `quiet=True, json_output=True`) WHEN calling `select_reporter()` THEN applies precedence: quiet > json > tty

## Verification Commands

```bash
# Type checking
.venv/bin/pyright --warnings src/frame_compare/orchestration/progress.py

# Linting
.venv/bin/ruff check src/frame_compare/orchestration/progress.py

# Unit tests
.venv/bin/pytest -v tests/orchestration/test_progress.py

# Import-linter gate
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract freshness (if any touched)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Import from utils, not orchestration:** The `ProgressReporter` protocol and implementations live in `frame_compare.utils.progress`. Import them directly; do not redefine.

2. **TTY detection:** Use `sys.stdout.isatty()` for detection. The `force_tty` parameter exists for testing and cases where the caller knows better (e.g., piped output that should still show progress).

3. **No OutputMode enum needed:** The function signature with boolean flags is simpler and matches the existing `RunRequest` pattern. An enum would add complexity without benefit.

4. **Return type:** The function returns `ProgressReporter` (the protocol type), not the concrete class. This allows future extensibility.

5. **Thread safety:** Not required. Progress reporting is single-threaded in the CLI context.

6. **No logging inside select_reporter:** This is a pure factory function. Logging happens inside the reporter implementations when needed.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-03__p6-3__progress-reporting

## Plan to Review

Read file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-review-v1.md
