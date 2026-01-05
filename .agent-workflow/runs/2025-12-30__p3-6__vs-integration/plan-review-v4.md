---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v4
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v4.md
---

# Plan Review Report: VapourSynth Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: finalize exports + export tests + VS runtime smoke test + lint-imports gate. |
| 2 | Dependencies | PASS | Depends on existing vs submodules; uses `pytest.importorskip` for optional VS runtime. |
| 3 | File List | PASS | Concrete list; `src/frame_compare/vs/__init__.py` marked (MODIFY). |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | Public signatures listed; SSOT now includes `tonemap(` call-form. |
| 6 | Tests Complete | PASS | Export tests and integration smoke test are fully specified and deterministic. |
| 7 | Verification Complete | PASS | Includes run validators + pyright/ruff/pytest + lint-imports. |
| 8 | Decision-Minimizing | FAIL | Spec Anchors still contain invalid heading text `Public Exports (vs/**init**.py)`; must be verbatim `Public Exports (vs/__init__.py)` to pass `validate_spec_anchors.py`. |
| 9 | Determinism Defined | PASS | No nondeterminism introduced. |

## Additional Quality Checks

- Error Codes: OK — no new errors.
- Failure Modes: OK — skip semantics pinned (`importorskip` + `is_vapoursynth_available()` gate).
- Derived Outputs: OK — none.
- Rollback Guidance: OK — no spec/contract churn beyond SSOT export clarification already done.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Fixing Spec Anchors to pass validators (currently would require the Coding Agent to edit the plan, which is disallowed).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Fix Spec Anchors heading string (plan-only)**
   - Section: `## Spec Anchors (SSOT)` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v4.md`
   - Problem: Uses `Section: "Public Exports (vs/**init**.py)"` which is not a real heading; `validate_spec_anchors.py` requires exact heading text.
   - Required Change (plan): replace with:
     - `Section: "Public Exports (vs/__init__.py)"`

2. **Update validator reference for next plan version**
   - Section: `## Verification Commands`
   - Required Change (plan-v5): update `validate_spec_anchors.py` to point to `plan-v5.md`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-30__p3-6__vs-integration

## Revision Required
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v4.md
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v4.md
Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Keep changes minimal; do not change SSOT unless required by this report.
