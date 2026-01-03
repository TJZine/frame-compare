---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v4
TARGET: Meta → Phase 5 Quality Gate Fixes
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v4.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v4.md
---

# Plan Review Report: Phase 5 Quality Gate Fixes

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single meta slice: unblock Phase 5 quality gate. |
| 2 | Dependencies | PASS | No new deps; changes are constrained to tests/scripts/docs. |
| 3 | File List | PASS | File changes are explicitly enumerated. |
| 4 | Contract Impact | PASS | Canonical contracts not edited; regeneration only. |
| 5 | Types Complete | FAIL | Plan fails `validate_spec_anchors.py` due to an invalid Spec Anchor heading string. |
| 6 | Tests Complete | PASS | Acceptance criteria + verification commands cover all blockers and the full suite. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit, including Docker “zero skips”. |
| 8 | Decision-Minimizing | FAIL | Mandatory validator failure blocks implementation; Coding Agent would be forced to improvise. |
| 9 | Determinism Defined | PASS | N/A for this slice. |

## Additional Quality Checks

- Error Codes: OK (no new error classes)
- Failure Modes: OK (Pillow deprecation and `find_spec` ValueError are explicitly handled)
- Derived Outputs: OK (regeneration command specified; no hand edits)
- Rollback Guidance: OK
- SSOT Update Audit (this loop): OK (the new subsection `#### VapourSynth Availability Guards` is implementable, self-contained, and does not add external deps)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Plan cannot pass the mandatory gate:
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v4.md`
   - Error: missing heading `'#### VapourSynth Availability Guards'` in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix Spec Anchor heading string (mechanical, plan-only)**
   - Section: Plan → `## Spec Anchors (SSOT)`
   - Problem: Spec Anchors must reference the *heading title text*, not include markdown hash prefixes. The SSOT heading is `#### VapourSynth Availability Guards` but the heading title is `VapourSynth Availability Guards`.
   - Required Change: Replace
     - `Section: "#### VapourSynth Availability Guards"`
     with either
     - `Section: "VapourSynth Availability Guards"`
     or remove the extra anchor and rely on `Section: "3.2 Conftest Organization"` (which contains the subsection).

## Ready for Implementation

Return to Planning Agent for a mechanical-only plan revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v4.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v4.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
