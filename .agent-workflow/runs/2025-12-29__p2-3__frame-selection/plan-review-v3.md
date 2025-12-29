---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v3
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v3.md
---

# Plan Review Report: Frame Selection Algorithms

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Selection-only slice; VS-dependent work explicitly deferred. |
| 2 | Dependencies | PASS | Pure Python; uses `FrameMetrics` + `AnalysisConfig` and existing `SelectionError`. |
| 3 | File List | PASS | Code/tests + docs + additive `analysis/__init__.py` export are listed. |
| 4 | Contract Impact | PASS | Declares **NO**; OK. |
| 5 | Types Complete | FAIL | Two tests still include placeholders (`...`) and omit explicit config in the inputs/expected assertions. |
| 6 | Tests Complete | FAIL | Random-mode exact expected outputs are incorrect for the SSOT algorithm; error-path tests do not specify exact assertions against `SelectionError` context/details. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit; spec-anchor validator passes. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must infer missing test inputs/assertions and reconcile wrong expected random outputs. |
| 9 | Determinism Defined | FAIL | “Exact expected outputs” are specified, but they do not match SSOT’s shuffle+greedy algorithm (so determinism contract is currently self-inconsistent). |

## Additional Quality Checks

- Error Codes: OK — `SelectionError(reason: str, requested: int, found: int)` exists and is the required error type.
- Failure Modes: Issue — “empty metrics” rule is specified, but the test must specify exact `requested` value and how it’s asserted from the exception.
- Derived Outputs: OK — `save_frames_data` is deferred and SSOT now notes this.
- Rollback Guidance: OK — STOP guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Seed-difference expected outputs (plan currently disagrees with SSOT algorithm).
2. Missing explicit inputs for `test_insufficient_candidates_raises` and `test_empty_metrics_raises` (`...` placeholders).
3. Exact assertions for `SelectionError` (where to read `reason/requested/found` from: `error.context.details`).

## Concrete Edits Required (plan-v4; plan-only)

1. **Fix random-mode exact expected outputs to match SSOT**
   - Section: test table row `test_random_mode_different_seed_exact_outputs`
   - Problem: expected lists do not match SSOT `_select_random` algorithm (`random.Random(seed)` + `shuffle` + greedy min-gap).
   - Required Change: replace expected frames with the SSOT-derived outputs for `total_frames=100`, `count=10`, `MIN_GAP=5`, `exclude=set()`:
     - seed=42: `frames=[1, 9, 15, 42, 50, 55, 65, 70, 78, 91]`
     - seed=123: `frames=[1, 7, 24, 29, 44, 50, 63, 75, 87, 93]`

2. **Remove all placeholders in test inputs/expectations**
   - Section: tests table rows `test_insufficient_candidates_raises` and `test_empty_metrics_raises`
   - Required Change:
     - `test_insufficient_candidates_raises` must specify the mode and config fully (recommended: `selection_mode=QUANTILE`, `frame_count=10`, `random_seed=42`) and explicitly state the assertion target for `requested/found` (see item 3).
     - `test_empty_metrics_raises` must specify the config fully (recommended: `selection_mode=QUANTILE`, `frame_count=10`, `random_seed=42`) and set `requested=10` explicitly.

3. **Make SelectionError assertions mechanically checkable**
   - Section: tests table rows for `SelectionError` cases (`empty_metrics`, `insufficient_candidates`)
   - Required Change: specify exact assertions, e.g.:
     - `assert exc.value.code == "FC-4012"`
     - `assert exc.value.context.details == {"reason": "<reason>", "requested": <requested>, "found": <found>}`
   - This removes ambiguity about where `reason/requested/found` are verified.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-3__frame-selection

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md
Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
