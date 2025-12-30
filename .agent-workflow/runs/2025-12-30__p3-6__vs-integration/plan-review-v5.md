---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v5
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v5.md
---

# Plan Review Report: VapourSynth Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v5.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: exports + export tests + VS runtime smoke test + lint-imports gate. |
| 2 | Dependencies | PASS | Depends on existing vs submodules; optional VS runtime handled via `pytest.importorskip`. |
| 3 | File List | PASS | Concrete list; `src/frame_compare/vs/__init__.py` marked (MODIFY). |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | Public signatures listed and SSOT includes `tonemap(` call-form. |
| 6 | Tests Complete | PASS | Export tests and integration smoke test are fully specified and deterministic. |
| 7 | Verification Complete | PASS | Includes run validators + pyright/ruff/pytest + lint-imports. |
| 8 | Decision-Minimizing | FAIL | Spec Anchors contain a non-verbatim heading (`Public Exports (vs/**init**.py)`), so `validate_spec_anchors.py` fails; Coding Agent would be forced to “fix the plan”, which is disallowed. |
| 9 | Determinism Defined | PASS | No nondeterminism introduced. |

## Additional Quality Checks

- Error Codes: OK — no new errors.
- Failure Modes: OK — smoke test skip semantics pinned.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — no new spec/contract churn required.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Fixing the Spec Anchor string to match the SSOT heading exactly.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Fix Spec Anchors heading typo (plan-only)**
   - Section: `## Spec Anchors (SSOT)` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v5.md`
   - Problem: `Section: "Public Exports (vs/**init**.py)"` is not a real heading; SSOT heading is `Public Exports (vs/__init__.py)` and validators require exact match.
   - Required Change: replace that line with:
     - `Section: "Public Exports (vs/__init__.py)"`

2. **Update validator reference for revised plan**
   - Section: `## Verification Commands`
   - Required Change (plan-v6): update `validate_spec_anchors.py` to point to `plan-v6.md`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v6.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-30__p3-6__vs-integration

## Revision Required
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v5.md
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v5.md
Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v6.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Keep changes minimal; do not change SSOT unless required by this report.
