---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v3
TARGET: Meta → Phase 5 Quality Gate Fixes
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v2.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v3.md
---

# Plan Review Report: Phase 5 Quality Gate Fixes

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single meta slice: unblock Phase 5 quality gate. |
| 2 | Dependencies | PASS | No new deps; fixes are constrained to tests/scripts/docs + regeneration command. |
| 3 | File List | PASS | All touched files are explicitly listed. |
| 4 | Contract Impact | PASS | Canonical contracts not edited; regeneration only. |
| 5 | Types Complete | FAIL | Plan adds signature bullets for helper functions, but they are not present in the anchored SSOT sections, so `validate_spec_anchors.py` fails. |
| 6 | Tests Complete | PASS | Verification commands + acceptance criteria cover each blocker and full-suite gates. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit, including Docker “zero skips” rule. |
| 8 | Decision-Minimizing | FAIL | The plan cannot pass required validators as written; implementation would require ad-hoc decisions about how to reconcile SSOT/signature coverage. |
| 9 | Determinism Defined | PASS | N/A for this slice (beyond strict warnings + zero skips). |

## Additional Quality Checks

- Error Codes: OK (no new error classes)
- Failure Modes: OK (Pillow deprecation and `find_spec` ValueError are explicitly targeted)
- Derived Outputs: OK (regeneration command specified; no hand edits)
- Rollback Guidance: OK (isolated, reversible changes)
- SSOT Update Audit (if SSOT changed this loop): N/A (plan-v3 does not claim SSOT edits)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. The plan fails a mandatory gate: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v3.md` with:
   - `function signatures not found in anchored SSOT sections: _vs_needs_mock() -> bool, _vs_spec_available() -> bool`

## Concrete Edits Required (CHANGES REQUIRED)

1. **Update SSOT to document the new helper functions (blocking)**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` → `### 3.2 Conftest Organization`
   - Problem: Plan-v3 introduces `_vs_needs_mock` / `_vs_spec_available`, but the anchored SSOT sections do not mention these names, so `validate_spec_anchors.py` fails.
   - Required Change: Under `### 3.2 Conftest Organization`, add a short “VapourSynth availability guard” snippet (or bullets) that includes the function names:
     - `_vs_needs_mock() -> bool` (used in `tests/conftest.py` to decide whether to install a global `vapoursynth` mock)
     - `_vs_spec_available() -> bool` (used in `tests/vs/test_exports.py` and `tests/vs/test_tonemap.py` to avoid `find_spec` raising `ValueError`)

2. **Revise plan after SSOT update**
   - Section: `## Spec Anchors (SSOT)` / `## Functions to Implement`
   - Problem: Plan-v3 currently claims “No SSOT spec changes” while its signatures require SSOT coverage.
   - Required Change: After updating SSOT, update the plan’s “SSOT edits” notes to reflect the SSOT update, and ensure `validate_spec_anchors.py` passes.

## Ready for Implementation

Return to Planning Agent for SSOT update + plan revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
- Under heading: "### 3.2 Conftest Organization" add/change:
  - Add a short “VapourSynth availability guard” note/snippet that includes these function names and their purpose:
    - `_vs_needs_mock() -> bool`
    - `_vs_spec_available() -> bool`

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v3.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
