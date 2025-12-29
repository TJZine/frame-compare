---
RUN_ID: 2025-12-28__p1-3__logging-infrastructure
VERSION: v1
TARGET: Phase 1 → Item 1.3 Logging Infrastructure
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v1.md
---

# Plan Review Report: Logging Infrastructure (Phase 1.3)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v1.md

Primary blocker: the plan anchors to SSOT that is internally inconsistent for correlation-id injection and log-level filtering. Per structlog docs, `structlog.contextvars.merge_contextvars` only merges structlog-managed context set via `structlog.contextvars.bind_contextvars`, but the SSOT snippet currently sets a standalone `ContextVar` that will not be merged into log output. Additionally, SSOT’s wrapper_class level mapping is not aligned with `structlog.make_filtering_bound_logger` API.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 1.3), explicit out-of-scope list. |
| 2 | Dependencies | PASS | Structlog dependency exists; phase dependency stated. |
| 3 | File List | PASS | File list is explicit (no “and related files”). |
| 4 | Contract Impact | PASS | “Contracts touched: NO” present. |
| 5 | Types Complete | PASS | Public signatures are listed and backticked. |
| 6 | Tests Complete | FAIL | Test mechanics are underspecified (how to assert renderer/filtering, how to avoid global structlog config leakage, missing invalid-input behavior cases). |
| 7 | Verification Complete | PASS | Commands + explicit pass criteria present. |
| 8 | Decision-Minimizing | FAIL | Remaining decisions include how run_id enters logs and how to validate filtering/renderers deterministically. |
| 9 | Determinism Defined | FAIL | Deterministic assertions for logging output/config are not fully specified; current acceptance criteria mentions “colored output” (non-deterministic). |

## Additional Quality Checks

- Error Codes: Issue — plan should explicitly state “no new FC-xxxx errors introduced”.
- Failure Modes: Issue — define behavior for unknown `level`/`format` (fallback vs raise) and whether repeated `configure_logging()` calls are supported.
- Derived Outputs: OK — none.
- Rollback Guidance: Issue — add a one-liner rollback note (e.g., revert created module and tests if SSOT changes are rejected).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
- Whether `run_id` is injected via structlog contextvars (`bind_contextvars`) or via a custom processor reading `_run_id`.
- What the authoritative behavior is for invalid `format` / invalid `level` inputs (fallback vs error).
- How to test JSON/console renderer selection and level filtering deterministically without flaky stdout/ANSI assertions.
- Whether and how to reset global structlog configuration between tests (`structlog.reset_defaults()` vs other).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Update SSOT first: correlation-id injection + level filtering**
   - Files:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`
   - Under heading: `### 4.3 Logging + Correlation IDs` add/change:
     - Add missing import in the code snippet: `from pathlib import Path` (snippet currently uses `Path` without import).
     - Ensure `run_id` will be present in logs when using `structlog.contextvars.merge_contextvars` by updating `new_run_id()` to also bind into structlog contextvars (example: call `structlog.contextvars.bind_contextvars(run_id=run_id)` after setting `_run_id`).
     - Fix the `configure_logging()` wrapper_class level mapping to align with `structlog.make_filtering_bound_logger` API (use `structlog.make_filtering_bound_logger(level)` directly, or explicitly specify the accepted string values and normalization).

2. **Revise plan-v2 to remove ambiguity and align anchors**
   - Section: `## Spec Anchors (SSOT)`
     - Copy/paste exact heading lines (including the heading text verbatim) and avoid anchoring to SSOT sections whose code samples conflict with the utils-module SSOT (e.g., monitoring’s implementation-path snippets). If monitoring is needed, anchor only to headings that define required fields/behavior (e.g., JSON log shape and presence of `run_id`), not file placement.
   - Section: tests (`tests/utils/test_logging.py`)
     - Specify exact mechanics to validate:
       - JSON vs console renderer selection (e.g., via `structlog.get_config()` processors list, and/or by running a sample event through the configured processor chain and parsing JSON output).
       - Level filtering behavior (explicit, deterministic assertion).
       - Test isolation: reset structlog global config per-test (e.g., `structlog.reset_defaults()`) and clear any contextvars state to prevent cross-test pollution.
     - Add explicit negative cases if SSOT defines fallback behavior (invalid `level`, invalid `format`).
   - Section: Acceptance Criteria
     - Replace “colored console format” with a deterministic requirement (e.g., “ConsoleRenderer configured”).

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v2.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-3__logging-infrastructure

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
- Under heading: "### 4.3 Logging + Correlation IDs" add/change:
  - Add missing import in the snippet: `from pathlib import Path`
  - In `new_run_id()`: after setting `_run_id`, also bind into structlog contextvars (e.g., `structlog.contextvars.bind_contextvars(run_id=run_id)`) so `merge_contextvars` includes `run_id`
  - In `configure_logging()`: replace the current wrapper_class level mapping with a `structlog.make_filtering_bound_logger(...)` usage that matches structlog’s documented accepted inputs (int or specific strings), and state the exact fallback behavior for unknown levels

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v1.md
Write file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
