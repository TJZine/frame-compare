---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v4
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v4.md
---

# Plan Review Report: Error Handling Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Leaf-module import constraint is explicit. |
| 3 | File List | FAIL | `docs/DECISIONS.md` update is not specified with exact entry content; Coding Agent would have to draft it. |
| 4 | Contract Impact | PASS | `Contracts touched: NO` and optional contract gates include a clear condition. |
| 5 | Types Complete | PASS | SSOT anchors present; helper public signatures listed in backticks. |
| 6 | Tests Complete | FAIL | Parametric exception test is underspecified: lacks the exact instantiation argument values for each of the 44 exceptions, leaving test data choices to the Coding Agent. |
| 7 | Verification Complete | PASS | Commands + explicit pass criteria are present. |
| 8 | Decision-Minimizing | FAIL | Remaining decisions: parametric constructor args and the exact `docs/DECISIONS.md` insertion text. |
| 9 | Determinism Defined | PASS | Formatting assertions use stable substrings (Python repr) and avoid dict-order sensitivity. |

## Additional Quality Checks

- Error Codes: OK — `PublishError` SSOT ambiguity is resolved in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` (now explicitly marker-only).
- Failure Modes: OK — unknown code mapping to `GENERAL_ERROR` is explicitly tested.
- Derived Outputs: OK (N/A) — contracts are not modified in this run; derived outputs are not required to be regenerated.
- Rollback Guidance: OK — “SSOT clarification required? STOP.” is explicit.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Exact argument values to instantiate each exception in `test_exception_class_contract` (44-way param list).
2. Exact `docs/DECISIONS.md` entry content (title/date/body).

## Concrete Edits Required (for `plan-v5.md`)

> [!IMPORTANT]
> This is `plan-v4` review. Keep the revision surgical: eliminate the two remaining decision points only.

1. **Specify the exact `docs/DECISIONS.md` entry content**
   - Section: `### 3. UPDATE docs/DECISIONS.md`
   - Problem: Only says “Add entry…”; content is unspecified.
   - Required Change: Provide an exact markdown block to insert, including the date `2025-12-29`, matching the prior intent from plan-v2/plan-v3 (scope decision for contract-only codes).

2. **Specify deterministic constructor args for the 44-exception parametric test**
   - Section: `### 2. NEW tests/test_errors.py` → `test_exception_class_contract`
   - Problem: “Parametrize over all 44 exceptions” without specifying instantiation inputs is not implementation-ready.
   - Required Change: Add an explicit parametrize table/list of 44 entries in the plan of the form:
     - `(ErrorClass, args_tuple, expected_code)`
   - Determinism requirements:
     - Use consistent values: `details="test"`, `plugin="lsmas"`, `path=Path("/test")`, `root=Path("/root")`, `candidate=Path("/other")`, `frame=42`, `clip="clip.mkv"`, `operation="op"`, `timeout=30.0`, `requested=10`, `available=5`, `size=100`, `limit=50`, `service="slow.pics"`.
     - For optional args, specify whether to include them or omit them (e.g., `FFmpegError("test", 1)` and `SlowpicsRateLimitedError()` as currently implied).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-2__error-handling

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v4.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v4.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v5.md
