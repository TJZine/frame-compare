---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v1
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v1.md
---

# Plan Review Report: Frame Selection Algorithms

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (selection algorithms + unit tests) with explicit deferrals. |
| 2 | Dependencies | PASS | Correctly avoids VS dependency; uses `FrameMetrics` + `AnalysisConfig`. |
| 3 | File List | FAIL | `src/frame_compare/analysis/__init__.py` update is not specified precisely (must preserve existing exports from Phase 2.1). |
| 4 | Contract Impact | PASS | Declares **NO** for canonical contracts; OK. |
| 5 | Types Complete | FAIL | Helper function signatures in plan do not match SSOT `### 4.3 Selection Algorithms` (extra params + different types). SSOT itself is internally inconsistent on `save_frames_data`. |
| 6 | Tests Complete | FAIL | Several tests are described but not mechanically checkable without additional algorithm decisions (quantile selection exactness, mixed allocation rounding, motion/random min-gap behavior). |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit and include `lint-imports`. |
| 8 | Decision-Minimizing | FAIL | Plan leaves implementation choices (“numpy optional”, percentile/threshold method, allocation rounding, helper signatures) to the Coding Agent. |
| 9 | Determinism Defined | FAIL | Determinism constraints exist, but the underlying selection rules (esp. quantiles and min-gap) are not specified precisely enough to make deterministic expected outputs. |

## Additional Quality Checks

- Error Codes: Issue — plan says “verify SelectionError exists; if not create stub” (not acceptable in this run). `SelectionError` exists and its constructor is `SelectionError(reason: str, requested: int, found: int)`; plan must lock this down.
- Failure Modes: Issue — plan includes `frame_count=0` as an error case, but `AnalysisConfig.frame_count` is constrained to `ge=1`; either remove this case or update SSOT to explicitly require a guard.
- Derived Outputs: Issue — plan defers `save_frames_data` persistence, but SSOT `### 3.2 select_frames` currently specifies a write to `{cache_dir}/frame_selection.json` even though `select_frames(metrics, config)` has no `cache_dir` parameter; SSOT must be clarified.
- Rollback Guidance: OK — STOP guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Quantile selection definition (SSOT `### 3.2 select_frames` describes fixed percentiles; SSOT `### 4.3 Selection Algorithms` describes threshold quantiles; plan tests assume “5 darkest + 5 brightest” for `frame_count=10`).
2. Whether helper function signatures should follow SSOT or the plan’s expanded parameter lists.
3. Mixed-mode allocation rounding rules and exact dark/bright split (currently partially specified; still leaves adjustments/rounding decisions).
4. Whether numpy is used (plan explicitly allows a choice).
5. Whether `save_frames_data` is implemented now or deferred (SSOT mismatch).
6. Exact `src/frame_compare/analysis/__init__.py` export list change (additive vs overwrite).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT spec first: make `select_frames` behavior internally consistent**
   - Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
   - Under heading: `### 3.2 select_frames` add/change:
     - Define quantile selection in one unambiguous way that scales for arbitrary `config.frame_count` (either fixed-percentile list generation rule or threshold-based rule), including:
       - exact percentile/quantile index rule (e.g., `idx = int(q * (n - 1))` with tie-breaker by frame index)
       - exact split between dark and bright for a given `count` (e.g., `dark = count // 2`, `bright = count - dark`)
     - Define mixed allocation rounding exactly:
       - `quantile_count = frame_count * 40 // 100`
       - `motion_count = frame_count * 40 // 100`
       - `random_count = frame_count - quantile_count - motion_count`
     - Clarify `save_frames_data` behavior for this function signature:
       - Either remove it from `select_frames` and move to cache phase, or specify how `{cache_dir}` is determined without adding new parameters.

2. **Update SSOT spec first: reconcile helper function signatures**
   - Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
   - Under heading: `### 4.3 Selection Algorithms` add/change (pick one; must match the plan):
     - Option A (preferred): update helper signatures to include `exclude: set[int]` and `min_gap: int` where needed, matching the intended algorithm, OR
     - Option B: require helpers to keep SSOT signatures, and specify that exclude/min-gap are handled in `select_frames` (then the plan must not add params).

3. **Revise plan to remove implementation choices**
   - Section: `src/frame_compare/analysis/selection.py` notes
   - Required change:
     - Remove “If numpy is preferred…” — choose pure Python only for this slice.
     - Remove `frame_count=0` edge case (or, if SSOT updated to require it, add an explicit `SelectionError` reason string and test).
     - Specify `SelectionError` constructor usage exactly: `raise SelectionError(reason=<string>, requested=config.frame_count, found=len(frames))`.

4. **Make tests fully deterministic and mechanically checkable**
   - Section: `tests/analysis/test_selection.py`
   - Required change:
     - Provide explicit deterministic input vectors (exact `luminance`/`motion` lists, `AnalysisConfig` fields) and explicit expected outputs OR explicit invariant assertions that are sufficient given SSOT.
     - For min-gap, define the exact rule used in assertions (e.g., `abs(a-b) >= MIN_GAP` for all pairs).
     - For breakdown, define whether lists must be disjoint and how they relate to `frames` (recommended: `sorted(frames) == sorted(set(sum(breakdown lists)))` and no overlaps).

5. **Specify `analysis/__init__.py` export change precisely**
   - Section: `src/frame_compare/analysis/__init__.py`
   - Required change:
     - State “add `select_frames` to existing exports without removing any existing exports from Phase 2.1”, and include the exact `__all__` after modification (or a minimal, explicit additive diff).

## Ready for Implementation

Return to Planning Agent for revision after SSOT clarification. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-3__frame-selection

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
- Under heading: "### 3.2 select_frames" add/change:
  - Define quantile selection precisely for arbitrary `frame_count`, including index/percentile rule and dark/bright split.
  - Define mixed allocation rounding exactly (`40/40/20` with `random = remainder`).
  - Clarify or remove `save_frames_data` behavior so it is implementable with the current `select_frames(metrics, config)` signature.
- Under heading: "### 4.3 Selection Algorithms" add/change:
  - Reconcile helper function signatures with the intended algorithm (either update signatures to include `exclude`/`min_gap` or explicitly require those concerns be handled in `select_frames`).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
