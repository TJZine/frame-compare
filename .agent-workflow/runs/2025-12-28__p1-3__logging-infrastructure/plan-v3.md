---
RUN_ID: 2025-12-28__p1-3__logging-infrastructure
VERSION: v3
TARGET: Phase 1 → Item 1.3 Logging Infrastructure
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/monitoring.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v2.md
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v3.md
---

# Implementation Plan: Logging Infrastructure (Phase 1.3)

## Changes Since plan-v2

- **Spec Anchors fix:** Now use exact verbatim headings from SSOT (e.g., "### 4.3 Logging + Correlation IDs").
- **Test isolation fix:** Added explicit `_run_id.set("")` reset in addition to structlog reset.
- **Filtering tests fix:** Replaced private `_min_level` assertions with behavior-based assertions using `structlog.wrap_logger` + `structlog.testing.ReturnLogger`.
- **DECISIONS version fix:** Updated to reference plan-v3/plan-review-v2.
- **Rollback fix:** Now lists exact files instead of directory-wide deletes.

## Context

**Phase:** 1 (Core Infrastructure)
**Module:** `frame_compare.utils.logging`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`
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

If implementation fails, revert/delete these specific files:

1. Revert: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` (Section 4.3 changes)
2. Delete: `src/frame_compare/utils/__init__.py`
3. Delete: `src/frame_compare/utils/logging.py`
4. Delete: `tests/utils/__init__.py`
5. Delete: `tests/utils/test_logging.py`

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: "### 4.3 Logging + Correlation IDs"
  - Section: "### 1.2 Import Constraints"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "### 1.3 Deterministic Test Vector Policy (SSOT)"

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

All signatures and behavior are defined in SSOT Section "### 4.3 Logging + Correlation IDs".

### 3. `tests/utils/__init__.py` [NEW]

**Purpose:** Test package marker.

### 4. `tests/utils/test_logging.py` [NEW]

**Purpose:** Unit tests for logging configuration and correlation IDs.

**Test isolation fixture (required, autouse):**

```python
import pytest
import structlog
from frame_compare.utils import logging as logging_module

@pytest.fixture(autouse=True)
def reset_logging_state():
    """Reset structlog config and module ContextVar before each test."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    logging_module._run_id.set("")
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    logging_module._run_id.set("")
```

**Tests required:**

- `test_new_run_id_returns_8_char_hex` — Assert `re.fullmatch(r"[0-9a-f]{8}", result)` is truthy.
- `test_new_run_id_sets_context_var` — Call `new_run_id()`, verify `get_run_id()` returns same value.
- `test_new_run_id_binds_to_structlog_contextvars` — Call `new_run_id()`, verify `structlog.contextvars.get_contextvars()["run_id"]` equals returned value.
- `test_get_run_id_default_unknown` — After fixture reset, assert `get_run_id() == "unknown"`.
- `test_configure_logging_json_format` — Call `configure_logging(format="json")`, get config, assert any processor `isinstance(..., structlog.processors.JSONRenderer)`.
- `test_configure_logging_console_format` — Call `configure_logging(format="console")`, assert `ConsoleRenderer` in processors.
- `test_configure_logging_unknown_format_falls_back_to_console` — Call `configure_logging(format="invalid")`, assert `ConsoleRenderer` in processors.

**Behavior-based filtering tests (no private internals):**

```python
def test_configure_logging_level_filtering_warning():
    """WARNING level: INFO filtered, WARNING allowed."""
    configure_logging(level="WARNING")
    wrapper_class = structlog.get_config()["wrapper_class"]
    log = structlog.wrap_logger(
        structlog.testing.ReturnLogger(),
        wrapper_class=wrapper_class,
        processors=[structlog.processors.add_log_level],
    )
    assert log.info("test") is None  # filtered
    assert log.warning("test") is not None  # allowed

def test_configure_logging_unknown_level_falls_back_to_info():
    """Unknown level falls back to INFO: DEBUG filtered, INFO allowed."""
    configure_logging(level="INVALID")
    wrapper_class = structlog.get_config()["wrapper_class"]
    log = structlog.wrap_logger(
        structlog.testing.ReturnLogger(),
        wrapper_class=wrapper_class,
        processors=[structlog.processors.add_log_level],
    )
    assert log.debug("test") is None  # filtered
    assert log.info("test") is not None  # allowed
```

### 5. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-28__p1-3__logging-infrastructure` + artifact versions (plan-v3, plan-review-v2)
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

- [ ] GIVEN `configure_logging(format="json")` WHEN config inspected THEN `JSONRenderer` in processors
- [ ] GIVEN `configure_logging(format="console")` WHEN config inspected THEN `ConsoleRenderer` in processors
- [ ] GIVEN `configure_logging(format="invalid")` WHEN config inspected THEN `ConsoleRenderer` in processors (fallback)
- [ ] GIVEN `configure_logging(level="WARNING")` WHEN wrapped logger used THEN `log.info()` returns `None` and `log.warning()` returns non-None
- [ ] GIVEN `configure_logging(level="INVALID")` WHEN wrapped logger used THEN `log.debug()` returns `None` and `log.info()` returns non-None
- [ ] GIVEN `new_run_id()` called WHEN result checked THEN matches `[0-9a-f]{8}`
- [ ] GIVEN `new_run_id()` called WHEN `get_run_id()` called THEN returns same value
- [ ] GIVEN `new_run_id()` called WHEN `structlog.contextvars.get_contextvars()` checked THEN `run_id` key exists
- [ ] GIVEN fresh context (after reset) WHEN `get_run_id()` called THEN returns `"unknown"`

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/utils
.venv/bin/ruff check src/frame_compare/utils
.venv/bin/pytest -v tests/utils
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Import constraints:** `utils.logging` may only import from stdlib and `structlog`. Do NOT import from `frame_compare.errors`.

2. **Test isolation is critical:** The fixture must reset both structlog and the module's `_run_id` ContextVar.

3. **Behavior-based filtering:** Use `structlog.wrap_logger` with `structlog.testing.ReturnLogger()` to verify filtering without private internals.

4. **log_file parameter:** Accept in signature, add comment: `# TODO: File handler implementation deferred`

5. **Docstrings:** All public functions must have docstrings matching the SSOT.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-3__logging-infrastructure

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v3.md
