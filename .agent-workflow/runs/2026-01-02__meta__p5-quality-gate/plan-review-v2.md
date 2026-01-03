---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v2
TARGET: Meta → Phase 5 Quality Gate Fixes
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v2.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v2.md
---

# Plan Review Report: Phase 5 Quality Gate Fixes

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single meta slice: unblock Phase 5 quality gate. |
| 2 | Dependencies | PASS | No new deps; fixes are constrained to tests/scripts/docs + regeneration command. |
| 3 | File List | PASS | All touched files are explicitly listed. |
| 4 | Contract Impact | PASS | Canonical contracts not edited; regeneration only. |
| 5 | Types Complete | FAIL | Plan introduces new helper functions but does not list any one-line backticked signature bullets required by `validate_spec_anchors.py`. |
| 6 | Tests Complete | PASS | Verification commands + acceptance criteria cover each blocker and the full suite. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit, including Docker “zero skips” rule. |
| 8 | Decision-Minimizing | FAIL | Plan cannot pass the required spec-anchor validation gate as written; Coding Agent would need to decide how to “make the plan pass” (bad). |
| 9 | Determinism Defined | PASS | N/A for this slice beyond “zero skips” and strict warnings. |

## Additional Quality Checks

- Error Codes: OK (no new error classes)
- Failure Modes: OK (Pillow deprecation and `find_spec` ValueError are explicitly handled)
- Derived Outputs: OK (regeneration command is specified; no hand edits)
- Rollback Guidance: OK (regeneration + isolated test/script changes)
- SSOT Update Audit (if SSOT changed this loop): N/A (plan claims no SSOT edits)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How to satisfy the mandatory plan gate: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v2.md` currently fails (no signature bullets).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Make plan pass `validate_spec_anchors.py` (blocking, plan-only)**
   - Section: Plan → add a new section `## Functions to implement` (or equivalent)
   - Problem: The plan includes no signature bullets of the form `- \`name(args...) -> Return\``, so `validate_spec_anchors.py` fails immediately.
   - Required Change:
     - Add at least one signature bullet for a function name that appears in the anchored SSOT sections.
     - Update `## Spec Anchors (SSOT)` to include the exact SSOT heading that contains that function name.
   - Recommended minimal fix:
     - Add `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` → Section: "3.2 Conftest Organization" to Spec Anchors.
     - Under `## Functions to implement`, add a signature bullet for an SSOT-referenced conftest function (e.g., `pytest_configure(...) -> None` or `mock_vs(...) -> ...`) so the validator has a concrete name to check.

2. **Remove ambiguous scope language (plan-only, clarity)**
   - Section: Plan → `## Changes Since plan-v1`
   - Problem: “Added comprehensive testing improvements for long-term reliability” is not backed by concrete file changes and invites scope creep.
   - Required Change: Either delete this bullet or replace it with a concrete, file-scoped list of changes already enumerated elsewhere.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v2.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
