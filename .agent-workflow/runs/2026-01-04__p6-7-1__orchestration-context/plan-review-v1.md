---
RUN_ID: 2026-01-04__p6-7-1__orchestration-context
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Runtime Context Types)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-review-v1.md
---

# Plan Review Report: Orchestration Runtime Context Types (ClipState / RunContext)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (context types + trim/frame-count invariants) with clear out-of-scope list. |
| 2 | Dependencies | PASS | Dependencies are explicitly listed and appear to exist in-repo. |
| 3 | File List | PASS | File list is explicit and minimal for this slice. |
| 4 | Contract Impact | PASS | No canonical contracts touched. |
| 5 | Types Complete | FAIL | Planned method signatures are not provided as backticked one-line signatures; this will fail the repo’s `validate_spec_anchors.py` gate (expects bullets like `- \`name(args) -> ret\``). |
| 6 | Tests Complete | PASS | Tests are named and assertions are deterministic (clamping + invariants) without external deps. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit (file-scoped pyright/ruff/pytest). |
| 8 | Decision-Minimizing | PASS | Behavior is anchored to SSOT; only signature formatting is missing. |
| 9 | Determinism Defined | PASS | Deterministic computation; no randomness or unstable outputs in-scope. |

## Additional Quality Checks

- Error Codes: OK (no new errors in this slice).
- Failure Modes: OK (explicit ValueError on negative trim start is specified).
- Derived Outputs: OK (no generated views in this slice).
- Rollback Guidance: OK (SSOT is anchored; do not invent behavior).
- SSOT Update Audit (if SSOT changed this loop): N/A

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. The plan does not list the planned method signatures in the required backticked bullet format; implementation could proceed, but the plan artifact will fail `validate_spec_anchors.py`, which is a STOP gate.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Add backticked method signatures for Spec Anchor validation**
   - Section: `src/frame_compare/orchestration/context.py` → “Methods to implement (spec-anchored)”
   - Problem: Missing backticked one-line signatures (required by workflow validator).
   - Required Change: Replace the existing method bullets with backticked signature bullets:
     - `effective_num_frames(self) -> int`
     - `with_trim(self, *, trim_start_frames: int, trim_end_frame_inclusive: int | None) -> ClipState`

## Ready for Implementation

Return to Planning (or Mechanical Auto-Fix Mode) for a plan-only correction. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-1__orchestration-context

## Revision Required
Read file: .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-v1.md
Write file: .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
