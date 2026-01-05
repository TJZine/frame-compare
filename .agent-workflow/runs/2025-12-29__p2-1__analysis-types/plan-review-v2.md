---
RUN_ID: 2025-12-29__p2-1__analysis-types
VERSION: v2
TARGET: Phase 2 → Item 2.1
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-review-v2.md
---

# Plan Review Report: Analysis Types

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | One slice (types only) + clear out-of-scope list. |
| 2 | Dependencies | PASS | Imports from `frame_compare.config` are specified; no VS dependency in this slice. |
| 3 | File List | PASS | Includes `docs/DECISIONS.md` + `importlinter.ini` updates. |
| 4 | Contract Impact | PASS | Declares **NO** for canonical contracts; OK. |
| 5 | Types Complete | FAIL | Spec Anchors list includes `### 3.1 calculate_metrics` and a function signature, but this phase does not implement that function; keeping it introduces a signature source-of-truth decision (SSOT currently contains a typo in the signature). |
| 6 | Tests Complete | FAIL | Test list lacks explicit assertions per test (beyond one frozen test); Coding Agent would need to decide what each test verifies. |
| 7 | Verification Complete | PASS | Commands + explicit “exit 0” criteria are listed. |
| 8 | Decision-Minimizing | FAIL | `importlinter.ini` change is specified as a full rewrite (changes `name` and removes comments); Coding Agent must decide minimal diff vs rewrite. |
| 9 | Determinism Defined | PASS | Deterministic types-only slice. |

## Additional Quality Checks

- Error Codes: OK — no new errors introduced.
- Failure Modes: OK — type-only slice.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — STOP guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Whether to treat `calculate_metrics` signature in SSOT as relevant for this slice (it shouldn’t be; type-only slice).
2. Exact expectations for each unit test (not fully specified).
3. Whether to rewrite `importlinter.ini` or apply a minimal line insertion while preserving existing contract metadata/comments.

## Concrete Edits Required (plan-v3; plan-only)

1. **Remove non-slice function anchoring (`calculate_metrics`)**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: `### 3.1 calculate_metrics` is not implemented in this phase and creates an avoidable signature decision.
   - Required Change:
     - Remove `### 3.1 calculate_metrics` from Spec Anchors.
     - Remove the `calculate_metrics(...) -> FrameMetrics` signature from the plan (it is not part of this slice).

2. **Make tests mechanically checkable (add per-test assertions)**
   - Section: `tests/analysis/test_types.py`
   - Problem: test names are listed, but expected assertions aren’t.
   - Required Change: for each test, add a one-line description of what is asserted. Minimum required:
     - “creation” tests: assert each field equals the passed value.
     - default tests: assert default values (`sha1 is None`, `version == 2`).
     - frozen tests: assert assignment raises `dataclasses.FrozenInstanceError`.
     - enum test: assert `FrameSelection.mode is SelectionMode.MIXED` (or chosen explicit value).
     - CacheLoadResult failure test: assert `success is False`, `metrics is None`, `reason == "not_found"` (or chosen explicit reason).

3. **Specify minimal `importlinter.ini` edit (no rewrite)**
   - Section: `importlinter.ini` (MODIFY)
   - Problem: plan provides a rewritten block that changes `name` and drops existing comments; that’s unnecessary churn and a decision point.
   - Required Change:
     - State: “Insert a single new line `frame_compare.analysis` immediately after `frame_compare.cli_entry` in the existing `[importlinter:contract:layers]` `layers =` list; do not change `name = Layered Architecture` or remove comments.”

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-1__analysis-types

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v3.md

## Hard Rules
- Spec Anchors must pass `validate_spec_anchors.py`.
