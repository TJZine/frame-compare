---
RUN_ID: 2025-12-28__p1-3__logging-infrastructure
VERSION: v2
TARGET: Phase 1 → Item 1.3 Logging Infrastructure
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v2.md
---

# Plan Review Report: Logging Infrastructure (Phase 1.3)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v2.md

SSOT updates in `utils-module.md` Section 4.3 are now directionally correct (bind into structlog contextvars; explicit invalid-input fallback). Remaining blockers are plan-only: Spec Anchors are not verbatim headings, and the proposed tests are not implementation-ready because they rely on private structlog internals and don’t fully isolate the module’s `_run_id` `ContextVar`.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice with explicit out-of-scope. |
| 2 | Dependencies | PASS | Structlog is a declared dependency; prior phase dependency is stated. |
| 3 | File List | PASS | Concrete file list and doc updates included. |
| 4 | Contract Impact | PASS | “Contracts touched: NO” present. |
| 5 | Types Complete | PASS | Public signatures listed and backticked. |
| 6 | Tests Complete | FAIL | Test isolation is incomplete (standalone `_run_id` not reset). Filtering tests depend on private attributes (`_min_level`) instead of deterministic behavior. |
| 7 | Verification Complete | PASS | Commands + explicit pass criteria present. |
| 8 | Decision-Minimizing | FAIL | Remaining decisions: how to assert filtering level and how to reset `_run_id` without ad-hoc choices. |
| 9 | Determinism Defined | FAIL | Current plan proposes assertions that may vary by structlog version (private internals). |

## Additional Quality Checks

- Error Codes: OK (explicit “no new FC-xxxx codes”).
- Failure Modes: OK (explicit fallback behavior; repeated configure allowed per SSOT).
- Derived Outputs: OK (none).
- Rollback Guidance: Issue — rollback deletes entire `src/frame_compare/utils/` and `tests/utils/` directories; should list the exact files to revert/delete to avoid collateral damage if other utils/tests exist by the time this slice runs.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
- Exact mechanism to reset module-local `_run_id` state between tests.
- Exact mechanism to validate log-level filtering without inspecting private structlog internals.
- Whether rollback should remove directories vs specific files.

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix Spec Anchors to use verbatim SSOT headings**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: Anchors use “Section: …” strings; the workflow requires exact heading text.
   - Required Change: Replace with verbatim headings copied from SSOT, e.g.:
     - In `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
       - `## 1.2 Import Constraints`
       - `### 4.3 Logging + Correlation IDs`
     - In `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
       - `### 1.3 Deterministic Test Vector Policy (SSOT)`

2. **Make test isolation fully deterministic for both structlog and `_run_id`**
   - Section: `tests/utils/test_logging.py` → `reset_structlog` fixture
   - Problem: `structlog.contextvars.clear_contextvars()` does not reset the module’s standalone `_run_id: ContextVar[str]`; `test_get_run_id_default_unknown` can fail after tests that call `new_run_id()`.
   - Required Change: Specify exactly one deterministic approach:
     - **Preferred (explicit reset):** In the fixture, import `frame_compare.utils.logging` and set its `_run_id` to empty at setup/teardown (`_run_id.set("")`), in addition to resetting structlog defaults and clearing structlog contextvars.
     - (Do not leave this as “ContextVar clearing” — the plan must state the exact reset step.)

3. **Replace private-internals filtering assertions with behavior-based assertions**
   - Section: `tests/utils/test_logging.py` → filtering tests
   - Problem: `_min_level` attribute is not a public contract; relying on it is version-fragile.
   - Required Change: Update the plan to assert filtering behavior deterministically using the configured `wrapper_class`:
     - After `configure_logging(level=...)`, obtain `wrapper_class = structlog.get_config()["wrapper_class"]`.
     - Wrap a `structlog.testing.ReturnLogger()` (or `CapturingLogger`) with `structlog.wrap_logger(..., wrapper_class=wrapper_class, processors=[...])`.
     - Assert filtered calls return `None` and allowed calls produce a value:
       - For `level="WARNING"`: `log.info(...) is None` and `log.warning(...) is not None`.
       - For unknown level fallback (INFO): `log.debug(...) is None` and `log.info(...) is not None`.
     - Specify the exact processors list used in these tests (minimal: `[structlog.processors.add_log_level]`).

4. **Fix DECISIONS artifact version reference**
   - Section: `docs/DECISIONS.md` required facts
   - Problem: Plan currently says “artifact versions (plan-v2, plan-review-v1)”.
   - Required Change: Update to reference `plan-v2` and `plan-review-v2` (the artifacts that will be used for implementation after approval).

5. **Make rollback guidance file-specific**
   - Section: `## Rollback Guidance`
   - Problem: Directory deletion is too broad.
   - Required Change: Replace with an explicit list of files to revert/delete (the docs edit + the created source/test files), without directory-wide deletes.

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v3.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-3__logging-infrastructure

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v2.md
Write file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
