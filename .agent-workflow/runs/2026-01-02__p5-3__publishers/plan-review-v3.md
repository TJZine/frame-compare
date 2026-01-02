---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v3
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v3.md
---

# Plan Review Report: Publishers Service (slow.pics)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: slow.pics publisher + tests + docs updates. |
| 2 | Dependencies | PASS | SSOT aligns with `async-semantics.md` client injection; SSOT includes title + delete semantics. |
| 3 | File List | PASS | File list is explicit and minimal. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | PASS | Public API signatures are listed and spec-anchored. |
| 6 | Tests Complete | FAIL | `test_publish_to_slowpics_delete_after_upload_does_not_delete_on_error` is missing the expected exception assertion; as written, the test plan would not execute its “files remain” assertion after a raised error. Also, visibility string conversion from `SlowpicsConfig.visibility` is not specified/tested, leaving a correctness decision. |
| 7 | Verification Complete | PASS | Canonical gates listed (`pyright`, `ruff`, `pytest`, `lint-imports`, `validate_spec_anchors`) with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must choose (a) how to assert “no delete on error” while an exception is raised, and (b) whether to send `config.visibility.value` vs `str(config.visibility)` to slow.pics. |
| 9 | Determinism Defined | PASS | Retry jitter formula defined; tests patch `asyncio.sleep` and jitter source for determinism. |

## Additional Quality Checks

- Error Codes: OK (uses existing `SlowpicsError`/`SlowpicsRateLimitedError`/`SlowpicsUnavailableError`).
- Failure Modes: Issue — visibility conversion is not specified/tested (risk of sending `"Visibility.UNLISTED"` instead of `"unlisted"`).
- Derived Outputs: OK (none).
- Rollback Guidance: OK.
- SSOT Update Audit (if SSOT changed this loop): N/A (SSOT changes already landed; this is plan-only test wiring).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. How to structure the “delete_after_upload does not delete on error” test while still asserting the raised exception.
2. How to convert `SlowpicsConfig.visibility` (Enum) into the string sent to slow.pics (`config.visibility.value` vs `str(config.visibility)`).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Make the delete-on-error test mechanically executable**
   - Section: `tests/services/test_publishers.py` “Tests required” table
   - Problem: `test_publish_to_slowpics_delete_after_upload_does_not_delete_on_error` lacks the exception expectation.
   - Required Change (plan-v4):
     - Specify: wrap the publish call in `with pytest.raises(SlowpicsUnavailableError): ...` and then assert PNGs remain after the `with` block.

2. **Specify and test visibility conversion**
   - Section: `src/frame_compare/services/publishers.py` implementation details + tests
   - Problem: `SlowpicsConfig.visibility` is an Enum; plan doesn’t specify how to serialize it for the form field.
   - Required Change (plan-v4):
     - Specify: use `visibility = config.visibility.value`.
     - Add/extend one of the `_prepare_upload` seam tests to assert `visibility == config.visibility.value` (alongside the title assertion), to avoid multipart body parsing.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-3__publishers

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v3.md
Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
