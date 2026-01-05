---
RUN_ID: 2025-12-28__p1-3__logging-infrastructure
VERSION: v2
TARGET: Phase 1 → Item 1.3 Logging Infrastructure
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/monitoring.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v1.md
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v2.md
---

# Implementation Plan: Logging Infrastructure (Phase 1.3)

## Changes Since plan-v1

- **SSOT updated first:** Added `from pathlib import Path` and `import logging`, added `bind_contextvars(run_id=run_id)` to `new_run_id()`, fixed level mapping to use `logging` module constants with explicit fallback documentation.
- **Tests Complete fix:** Added explicit test mechanics for renderer/level validation, test isolation with `structlog.reset_defaults()`, and ContextVar clearing.
- **Decision-Minimizing fix:** Removed ambiguity about run_id injection (now explicitly via `bind_contextvars` per updated SSOT).
- **Determinism fix:** Replaced "colored console format" with "ConsoleRenderer is in processors list".
- **Added:** Error behavior documentation (no new FC-xxxx codes, fallback behavior for invalid inputs).
- **Added:** Rollback guidance.

## Context

**Phase:** 1 (Core Infrastructure)
**Module:** `frame_compare.utils.logging`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` Section 4.3
**Dependencies:** Phase 1.2 Error Handling complete (`src/frame_compare/errors.py` exists)

## Scope

This plan covers:

- [x] Create `src/frame_compare/utils/logging.py` with structlog configuration
- [x] Implement correlation ID tracking via `ContextVar` + `bind_contextvars`
- [x] Write unit tests for logging configuration and correlation IDs

This plan does NOT cover:

- Other utils module files (`result.py`, `types.py`, `progress.py`, `paths.py`, `subproc.py`)
- The full `utils/__init__.py` re-exports (will be minimal, logging-only)
- Log rotation / file handling (spec shows `log_file` accepted but not implemented)

## Contract Impact

**Contracts touched:** NO

## Error Handling

**No new FC-xxxx error codes introduced.** This module does not raise typed exceptions; it silently falls back on invalid inputs per SSOT documentation.

## Rollback Guidance

If SSOT changes are rejected or implementation fails, revert:

1. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` Section 4.3
2. Delete `src/frame_compare/utils/` directory
3. Delete `tests/utils/` directory

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: "4.3 Logging + Correlation IDs"
  - Section: "1.2 Import Constraints"
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

- `new_run_id() -> str`
- `get_run_id() -> str`
- `configure_logging(level: str = "INFO", format: str = "console", log_file: Path | None = None) -> None`

All signatures and behavior are defined in SSOT Section "4.3 Logging + Correlation IDs".

### 3. `tests/utils/__init__.py` [NEW]

**Purpose:** Test package marker.

### 4. `tests/utils/test_logging.py` [NEW]

**Purpose:** Unit tests for logging configuration and correlation IDs.

**Test isolation (required in every test):**

```python
@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog and contextvars before each test."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
```

**Tests required:**

- `test_new_run_id_returns_8_char_hex` — Assert `re.fullmatch(r"[0-9a-f]{8}", result)` is truthy.
- `test_new_run_id_sets_context_var` — Call `new_run_id()`, then verify `get_run_id()` returns the same value.
- `test_new_run_id_binds_to_structlog_contextvars` — Call `new_run_id()`, then verify `structlog.contextvars.get_contextvars()["run_id"]` equals the returned value.
- `test_get_run_id_default_unknown` — In fresh fixture context (after reset), assert `get_run_id() == "unknown"`.
- `test_configure_logging_json_format` — Call `configure_logging(format="json")`, get config via `structlog.get_config()`, assert `JSONRenderer` is in the processors list (check `isinstance(p, structlog.processors.JSONRenderer)`).
- `test_configure_logging_console_format` — Call `configure_logging(format="console")`, get config, assert `ConsoleRenderer` is in processors list.
- `test_configure_logging_unknown_format_falls_back_to_console` — Call `configure_logging(format="invalid")`, assert `ConsoleRenderer` is in processors list.
- `test_configure_logging_level_filtering` — Call `configure_logging(level="WARNING")`, get config, assert `wrapper_class` is a filtering bound logger with minimum level 30.
- `test_configure_logging_unknown_level_falls_back_to_info` — Call `configure_logging(level="INVALID")`, assert filtering level is 20 (INFO).

### 5. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-28__p1-3__logging-infrastructure` + artifact versions (plan-v2, plan-review-v1)
- Scope: logging.py only from utils module; other utils files deferred
- SSOT edits: Updated Section 4.3 with `bind_contextvars`, `import logging`, fallback docs
- Verification gates: pyright, ruff, pytest

### 6. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for logging infrastructure.

**Entry format (append to Unreleased section):**

```markdown
### Added
- Structured logging infrastructure with structlog (json/console formats)
- Correlation ID tracking for run tracing (`new_run_id`, `get_run_id`)
```

## Acceptance Criteria

- [ ] GIVEN `configure_logging(format="json")` is called WHEN `structlog.get_config()` is inspected THEN `JSONRenderer` is in the processors list
- [ ] GIVEN `configure_logging(format="console")` is called WHEN config is inspected THEN `ConsoleRenderer` is in processors list
- [ ] GIVEN `configure_logging(format="invalid")` is called WHEN config is inspected THEN `ConsoleRenderer` is in processors list (fallback)
- [ ] GIVEN `configure_logging(level="WARNING")` is called WHEN filtering bound logger is checked THEN minimum level is 30
- [ ] GIVEN `configure_logging(level="INVALID")` is called WHEN filtering bound logger is checked THEN minimum level is 20 (INFO fallback)
- [ ] GIVEN `new_run_id()` is called WHEN result is checked THEN it matches regex `[0-9a-f]{8}`
- [ ] GIVEN `new_run_id()` is called WHEN `get_run_id()` is called THEN it returns the same value
- [ ] GIVEN `new_run_id()` is called WHEN `structlog.contextvars.get_contextvars()` is checked THEN `run_id` key exists with the returned value
- [ ] GIVEN fresh context (after reset) WHEN `get_run_id()` is called THEN returns `"unknown"`

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/utils
.venv/bin/ruff check src/frame_compare/utils
.venv/bin/pytest -v tests/utils
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Import constraints:** `utils.logging` may only import from stdlib (`logging`, `uuid`, `contextvars`, `pathlib`) and `structlog`. Do NOT import from `frame_compare.errors`.

2. **Test isolation is critical:** The `autouse` fixture in the test file must reset both structlog global config and contextvars to prevent cross-test pollution.

3. **Checking wrapper_class level:** After `configure_logging()`, the bound logger's minimum level can be verified via `structlog.get_config()["wrapper_class"]` inspection. The `make_filtering_bound_logger(level_num)` returns a class with `_min_level` attribute.

4. **log_file parameter:** Accept it in the signature but do not implement file logging. Add comment: `# TODO: File handler implementation deferred`

5. **Docstrings:** All public functions must have docstrings matching the SSOT.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-3__logging-infrastructure

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v2.md
