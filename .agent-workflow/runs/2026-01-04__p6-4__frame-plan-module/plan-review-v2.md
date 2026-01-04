---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v2
TARGET: Phase 6 → Item 6.4 (FramePlan Module)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v2.md
---

# Plan Review Report: FramePlan Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v2.md

Plan-v2 fixes the prior STOP-gate issue:
- `validate_spec_anchors.py` passes for `plan-v2.md`.
- SSOT `frame-plan-module.md` examples now use `InsufficientFramesError(path=Path("<frame-plan>"), count=<available>, required=<requested>)`, aligning with `errors-module.md` and `contracts/error_codes.yaml` for FC-3004.

Remaining issues are plan-mechanical and must be resolved to make the plan fully implementation-ready (zero decisions).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: FramePlan + FC-3004 drift fix only. |
| 2 | Dependencies | PASS | Correctly identifies FC-3004 SSOT sources; no new deps introduced. |
| 3 | File List | FAIL | SSOT was edited this run but `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md` is not listed in “Files to Create/Modify”. |
| 4 | Contract Impact | PASS | Contracts are not changed; plan restores runtime to existing SSOT. |
| 5 | Types Complete | FAIL | Plan changes a public exception constructor but does not list a one-line signature for `InsufficientFramesError` in the required backticked form. |
| 6 | Tests Complete | FAIL | `tests/test_errors.py` changes include “add a focused test” but no exact test function name is specified. |
| 7 | Verification Complete | PASS | Includes spec-anchor validation + targeted + full gates with explicit pass criteria. |
| 8 | Decision-Minimizing | PASS | Algorithm + FC-3004 mapping are specified; no design choices left for frame selection logic. |
| 9 | Determinism Defined | PASS | Cross-session determinism test is explicitly required and scoped to pure-Python. |

## Additional Quality Checks

- Error Codes: OK — FC-3004 alignment is explicitly in-scope; no new codes introduced.
- Failure Modes: OK — `count > num_frames` and `count == 0` are specified.
- Derived Outputs: OK — contracts not touched.
- Rollback Guidance: OK — plan includes STOP guidance if unexpected callers exist.
- SSOT Update Audit (this loop): OK — `frame-plan-module.md` updates are implementable and align to `errors-module.md` + FC-3004 contract template; code-fence heading fix is acceptable.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to treat the SSOT edits to `frame-plan-module.md` as part of this run’s file list (required for run completeness).
2. Exact public signature documentation for the FC-3004 exception constructor change (required for “types complete”).
3. Exact new/updated test name for the FC-3004 payload-shape assertion (required for “tests complete”).

## Concrete Edits Required (plan-v3)

1. **Add missing SSOT file to file list**
   - Section: “Files to Create/Modify”
   - Problem: SSOT edits are claimed under “Changes Since plan-v1” but the modified spec file is not listed.
   - Required Change: Add an explicit entry:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md` (MODIFY)
     - List the exact headings changed (at minimum: “4.3 Complete Algorithm”, “5. Error Handling”, and any code-fence formatting fix location).

2. **Add backticked one-line signature for `InsufficientFramesError`**
   - Section: `src/frame_compare/errors.py` (MODIFY)
   - Problem: The plan changes a public API signature but does not list it in the required one-line signature format.
   - Required Change: Add a signature bullet like:
     - `InsufficientFramesError(path: Path, count: int, required: int) -> None`

3. **Name the new `tests/test_errors.py` test explicitly**
   - Section: `tests/test_errors.py` (MODIFY)
   - Problem: “Add a focused test …” is not implementation-ready without a concrete test name.
   - Required Change: Specify the exact test function name and its assertions (minimum):
     - asserts `.context.details` keys are exactly `path`, `count`, `required`
     - asserts `.code == "FC-3004"`

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-4__frame-plan-module

## Revision Required
Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v2.md
Write file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
