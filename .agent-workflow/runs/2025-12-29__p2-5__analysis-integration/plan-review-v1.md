---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v1
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v1.md
---

# Plan Review Report: Analysis Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v1.md

The plan is close, but it introduces an unanchored/public API change (`ProgressReporter` export) that cannot be implemented without additional decisions (where the runtime symbol comes from and whether it belongs in `frame_compare.utils` per SSOT). The plan also omits the workflow-required plan STOP gate (`scripts/validate_spec_anchors.py`) from Verification Commands.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Scope bullets are internally inconsistent/typoed (“Run full quality gates on `-the…”) and include an extra public export not required by the checklist or SSOT. |
| 2 | Dependencies | FAIL | SSOT dependency for `ProgressReporter` is `frame_compare.utils`, but plan exports a `ProgressReporter` “from metrics.py” without specifying a runtime source; current repo has no `frame_compare.utils.progress`. |
| 3 | File List | PASS | Explicit and minimal: `src/frame_compare/analysis/__init__.py` + docs. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | PASS | Planned public function signature listed: `calculate_metrics(...) -> FrameMetrics`. |
| 6 | Tests Complete | PASS | No new behavior; import-level acceptance criteria are sufficient for this slice. |
| 7 | Verification Complete | FAIL | Missing `scripts/validate_spec_anchors.py` command for the plan artifact. |
| 8 | Decision-Minimizing | FAIL | `ProgressReporter` export requires design decisions (location/ownership/runtime availability) not defined in SSOT. |
| 9 | Determinism Defined | N/A | Integration/export-only slice (no algorithmic output). |

## Additional Quality Checks

- Error Codes: OK — no new/changed errors.
- Failure Modes: OK — import failures covered by acceptance criteria.
- Derived Outputs: OK — no generated outputs.
- Rollback Guidance: Issue — no explicit STOP rule (recommend adding, consistent with workflow).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether `ProgressReporter` is a public runtime export of `frame_compare.analysis` (SSOT currently treats it as a `frame_compare.utils` type).
2. If exported, where the runtime `ProgressReporter` symbol is defined (metrics module vs utils module), without violating import layering.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Remove `ProgressReporter` export from this slice (plan-only)**
   - Section: `## Scope`, `src/frame_compare/analysis/__init__.py`, `## Acceptance Criteria`
   - Problem: Export is not required by Phase 2.5 checklist and not specified as a public export in `analysis-module.md`; it also likely cannot exist at runtime without additional work in `frame_compare.utils`.
   - Required Change: Delete all mentions of exporting/importing/testing `ProgressReporter` from `frame_compare.analysis` in this plan. Keep only `calculate_metrics` export integration.

2. **Add plan artifact validation gate (plan-only)**
   - Section: `## Verification Commands`
   - Problem: Missing workflow-required STOP gate.
   - Required Change: Add:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md`

3. **Fix scope/typos and add STOP rule (plan-only)**
   - Section: `## Scope`, `## Notes for Coding Agent`
   - Problem: Typo/backtick glitch and no explicit STOP/rollback guidance.
   - Required Change: Fix the scope bullet wording and add: “If SSOT ambiguity encountered, STOP and return to Planning.”

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-5__analysis-integration

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
