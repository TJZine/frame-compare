---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v6
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v6.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v6.md
---

# Plan Review Report: VapourSynth Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v6.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; scope is stable. |
| 2 | Dependencies | PASS | Dependencies and optional-VS behavior are specified. |
| 3 | File List | PASS | Files are explicit and minimal for this slice. |
| 4 | Contract Impact | PASS | Canonical contracts not touched. |
| 5 | Types Complete | PASS | Public signatures are listed. |
| 6 | Tests Complete | PASS | Export tests + integration smoke test logic specified. |
| 7 | Verification Complete | FAIL | Plan’s own verification step (`validate_spec_anchors.py`) fails due to an invalid Spec Anchor heading string. |
| 8 | Decision-Minimizing | FAIL | Spec Anchor typo requires Coding Agent to “fix the plan” to proceed, which is disallowed. |
| 9 | Determinism Defined | PASS | No nondeterminism introduced. |

## Additional Quality Checks

- Error Codes: OK — no new errors.
- Failure Modes: OK — `pytest.importorskip("vapoursynth")` + runtime skip logic included.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — no further scope changes needed.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Fixing the Spec Anchor line so the plan passes `validate_spec_anchors.py`.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Fix Spec Anchor heading typo (plan-only, surgical)**
   - Section: `## Spec Anchors (SSOT)` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v6.md`
   - Problem: Line uses `Section: "Public Exports (vs/**init**.py)"`, but the SSOT heading is `## Public Exports (vs/__init__.py)`; validators require an exact match.
   - Required Change: replace that line with:
     - `Section: "Public Exports (vs/__init__.py)"`

2. **Update the validator command in the revised plan**
   - Section: `## Verification Commands`
   - Required Change (plan-v7): point `validate_spec_anchors.py` at `plan-v7.md`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v7.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-30__p3-6__vs-integration

## Revision Required (surgical; no churn)
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v6.md
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v6.md
Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v7.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not change scope/SSOT; only fix the anchor typo and update the validator command to reference `plan-v7.md`.
