---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v2
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v2.md
---

# Plan Review Report: Metrics Calculation

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v2.md

The plan is substantially improved: SSOT now defines deterministic plane extraction + normalization, clip selection is unambiguous, and the plan passes `scripts/validate_spec_anchors.py`. One blocker remains: the plan adds a new behavioral contract (0-frame clips raise `MetricsCalculationError (FC-4002)`) that is not specified in SSOT, so the Coding Agent would be implementing behavior that is not anchored.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; Phase 2.5 exports removed from scope. |
| 2 | Dependencies | PASS | Cache I/O + VS loading dependencies identified; numpy implied by SSOT and tests. |
| 3 | File List | PASS | Complete and minimal for this slice. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | PASS | Public signatures listed; plan anchors validate successfully. |
| 6 | Tests Complete | FAIL | “empty clip raises” tests encode behavior not defined in SSOT. |
| 7 | Verification Complete | PASS | Exact commands + explicit pass criteria provided (includes plan anchor validation). |
| 8 | Decision-Minimizing | FAIL | Empty-clip behavior is a remaining SSOT decision point. |
| 9 | Determinism Defined | PASS | Luminance/motion normalization is deterministic in SSOT and reflected in plan. |

## Additional Quality Checks

- Error Codes: OK — `FC-4002` is used and asserted where specified.
- Failure Modes: Issue — 0-frame clip behavior is not SSOT-defined (raise vs return empty arrays).
- Derived Outputs: OK — none required.
- Rollback Guidance: OK — STOP rule present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether a 0-frame clip is an error (raise `MetricsCalculationError`) or returns empty metric arrays.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT spec first: define 0-frame clip behavior**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
   - Under heading: `### 4.1 Luminance Calculation` add/change (pick one and be explicit):
     - **Option A (matches current plan/tests):** If `clip.num_frames == 0`, raise `MetricsCalculationError (FC-4002)` before any progress callbacks; no values are returned.
     - **Option B:** If `clip.num_frames == 0`, return `[]` (and `calculate_metrics` returns empty arrays) and specify downstream expectations.
   - Under heading: `### 4.2 Motion Scoring` add/change:
     - Mirror the same 0-frame behavior as luminance (raise or return empty), and explicitly define output invariants for that case.
   - Under heading: `### 3.1 calculate_metrics` add/change:
     - Clarify the 0-frame behavior at the public API boundary (propagate `MetricsCalculationError` if Option A).

2. **Then revise the plan to match the chosen SSOT option**
   - If SSOT chooses Option A: keep the two “empty clip raises” tests as written (and anchor the expectation to the updated SSOT).
   - If SSOT chooses Option B: replace the “empty clip raises” tests with deterministic assertions on empty outputs (and update Acceptance Criteria accordingly).

## Ready for Implementation

Return to Planning Agent for SSOT clarification + plan revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-2__metrics-calculation

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md

- Under heading: "### 4.1 Luminance Calculation" add/change:
  - Define deterministic behavior for `clip.num_frames == 0` (either raise `MetricsCalculationError (FC-4002)` or return empty list; choose one).

- Under heading: "### 4.2 Motion Scoring" add/change:
  - Mirror the same `clip.num_frames == 0` behavior and define output invariants for that case.

- Under heading: "### 3.1 calculate_metrics" add/change:
  - State the public API behavior for 0-frame reference clips (propagate `MetricsCalculationError` if choosing raise).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
