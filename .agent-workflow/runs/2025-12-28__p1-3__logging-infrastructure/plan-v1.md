---
RUN_ID: 2025-12-28__p1-3__logging-infrastructure
VERSION: v1
TARGET: Phase 1 → Item 1.3 Logging Infrastructure
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/monitoring.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v1.md
---

# Implementation Plan: Logging Infrastructure (Phase 1.3)

## Context

**Phase:** 1 (Core Infrastructure)
**Module:** `frame_compare.utils.logging`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` Section 4.3
**Supporting Doc:** `docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/monitoring.md` Sections 2, 4
**Dependencies:** Phase 1.2 Error Handling complete (`src/frame_compare/errors.py` exists)

## Scope

This plan covers:

- [x] Create `src/frame_compare/utils/logging.py` with structlog configuration
- [x] Implement correlation ID tracking via `ContextVar`
- [x] Write unit tests for logging configuration and correlation IDs

This plan does NOT cover:

- Other utils module files (`result.py`, `types.py`, `progress.py`, `paths.py`, `subproc.py`)
- The full `utils/__init__.py` re-exports (will be minimal, logging-only)
- Log rotation / file handling (spec shows this as config-driven, not implementation)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: "4.3 Logging + Correlation IDs"
  - Section: "1.2 Import Constraints"
- `docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/monitoring.md`:
  - Section: "2. Logging"
  - Section: "4. Tracing"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `src/frame_compare/utils/__init__.py` [NEW]

**Purpose:** Package init with minimal re-exports for logging.

**Exports:**

- `configure_logging`
- `new_run_id`
- `get_run_id`

### 2. `src/frame_compare/utils/logging.py` [NEW]

**Purpose:** Structlog configuration and correlation ID tracking.

**Types to define:**

- `_run_id: ContextVar[str]` — module-level ContextVar for correlation ID

**Functions to implement (spec-anchored):**

- `new_run_id() -> str` — Generate UUID4 hex[:8], set in ContextVar, return it
- `get_run_id() -> str` — Return current correlation ID or "unknown"
- `configure_logging(level: str = "INFO", format: str = "console", log_file: Path | None = None) -> None` — Configure structlog processors

**Implementation notes:**

- Use `structlog.contextvars.merge_contextvars` processor to inject run_id
- Use `structlog.make_filtering_bound_logger(level)` for level filtering
- Level string must map to structlog log level (DEBUG=10, INFO=20, WARNING=30, ERROR=40)
- For `format="json"`: use `structlog.processors.JSONRenderer()`
- For `format="console"`: use `structlog.dev.ConsoleRenderer()`
- `log_file` parameter is accepted but not implemented (for future file handler)

### 3. `tests/utils/__init__.py` [NEW]

**Purpose:** Test package marker.

### 4. `tests/utils/test_logging.py` [NEW]

**Purpose:** Unit tests for logging configuration and correlation IDs.

**Tests required:**

- `test_new_run_id_returns_8_char_hex` — Verify format is 8 hex chars
- `test_new_run_id_sets_context_var` — Verify get_run_id returns the set value
- `test_get_run_id_default_unknown` — Verify returns "unknown" when not set (fresh context)
- `test_configure_logging_json_format` — Verify JSONRenderer is used
- `test_configure_logging_console_format` — Verify ConsoleRenderer is used
- `test_configure_logging_level_filtering` — Verify log level filtering works

### 5. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-28__p1-3__logging-infrastructure` + artifact versions
- Scope: logging.py only from utils module; other utils files deferred
- SSOT edits: none
- Verification gates: pyright, ruff, pytest

### 6. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for logging infrastructure.

**Entry format:**

```
## [Unreleased]
### Added
- Structured logging infrastructure with structlog (json/console formats)
- Correlation ID tracking for run tracing
```

## Acceptance Criteria

- [ ] GIVEN `configure_logging(format="json")` is called WHEN structlog logs THEN output is valid JSON
- [ ] GIVEN `configure_logging(format="console")` is called WHEN structlog logs THEN output is colored console format
- [ ] GIVEN `configure_logging(level="WARNING")` is called WHEN INFO is logged THEN it is filtered out
- [ ] GIVEN `new_run_id()` is called WHEN checked THEN returns 8-character hex string
- [ ] GIVEN `new_run_id()` is called WHEN `get_run_id()` is called THEN returns the same value
- [ ] GIVEN fresh context WHEN `get_run_id()` is called THEN returns "unknown"

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/utils
.venv/bin/ruff check src/frame_compare/utils
.venv/bin/pytest -v tests/utils
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Import constraints:** `utils.logging` may only import from stdlib, structlog, and `pathlib.Path`. Do NOT import from `frame_compare.errors` in logging.py (unlike other utils files).

2. **Level mapping:** structlog uses numeric levels. Map string level to structlog constant:

   ```python
   import logging
   level_num = getattr(logging, level.upper(), logging.INFO)
   ```

3. **ContextVar isolation in tests:** Use `contextvars.copy_context().run()` or reset the ContextVar between tests to avoid test pollution.

4. **log_file parameter:** Accept it in the signature but do not implement file logging. Add a comment: `# TODO: File handler implementation deferred`

5. **Docstrings:** All public functions must have docstrings per spec.

---

> **Proposed RUN_ID:** 2025-12-28__p1-3__logging-infrastructure
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2025-12-28__p1-3__logging-infrastructure` before running Plan Review Agent.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-3__logging-infrastructure

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v1.md
