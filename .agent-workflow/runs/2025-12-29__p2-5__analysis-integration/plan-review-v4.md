---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v4
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v4.md
---

# Plan Review Report: Analysis Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v4.md

SSOT now defines the “importable without VapourSynth installed” invariant and the plan anchors it; the plan also adds a deterministic `ast`-based test. Remaining blocker: the proposed `ast` test is not correct/complete as written (it allows top-level `if` blocks that are not `TYPE_CHECKING`, and it does not actually enforce “only under `if TYPE_CHECKING:`”); this leaves a Coding-Agent decision about what the test should assert.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; scope expansion is now SSOT-justified. |
| 2 | Dependencies | PASS | SSOT explicitly defines import-time VS dependency rules. |
| 3 | File List | PASS | Explicit list of modified files and added test. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | PASS | `calculate_metrics(...) -> FrameMetrics` is listed and SSOT-anchored. |
| 6 | Tests Complete | FAIL | The `ast` test logic is underspecified/incorrect, leaving discretion. |
| 7 | Verification Complete | PASS | Commands + pass criteria present; anchors validate. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must decide how to correctly implement the `ast` verification. |
| 9 | Determinism Defined | N/A | Export/invariant slice; no algorithmic output. |

## Additional Quality Checks

- Error Codes: OK — none changed.
- Failure Modes: OK — invariant is explicitly SSOT-defined.
- Derived Outputs: OK — none required.
- Rollback Guidance: OK — STOP rule present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact `ast` verification semantics (what is allowed at top-level besides `if TYPE_CHECKING:` and how to detect it).

## Concrete Edits Required (plan-only)

1. **Fix the `ast` test to be mechanically correct and fully specified**
   - Section: `tests/analysis/test_metrics.py` → `test_no_toplevel_vapoursynth_import`
   - Problem:
     - Current pseudo-logic treats *any* top-level `ast.If` as allowed, even if it is not `if TYPE_CHECKING:`.
     - It does not enforce the SSOT requirement “outside `if TYPE_CHECKING:` blocks”.
   - Required Change (deterministic, no discretion):
     - Specify that the test must:
       1) Parse `src/frame_compare/analysis/metrics.py` and iterate top-level nodes.
       2) Fail on any top-level `import vapoursynth` or `from vapoursynth import ...`.
       3) For top-level `if` blocks: allow imports from `vapoursynth` **only** when the `if` condition is exactly `TYPE_CHECKING` (or `typing.TYPE_CHECKING`) and the import occurs within that `if` body.
       4) Fail on `vapoursynth` imports inside any other top-level `if` condition.
     - If the plan wants to keep the test minimal, it may alternatively require a strict rule: “no top-level vapoursynth imports anywhere, including inside TYPE_CHECKING”; but then the SSOT section must be updated to match. Prefer aligning the test with SSOT as written.

2. **Add the missing CODEX workflow input reference (artifact hygiene)**
   - Plan header: `INPUTS`
   - Problem: Plan references `analysis-module.md` edits and adds a new SSOT section, but does not list the prior plan version it supersedes (optional but recommended) and references a `review-v1.md` in plan-v3 (inconsistent provenance).
   - Required Change: Ensure `INPUTS` only lists actual, existing artifacts used for this plan version (e.g., remove stale `review-v1.md` references if present in the current plan header for v4).

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-5__analysis-integration

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v4.md
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v4.md
Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
