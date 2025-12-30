---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v3
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v3.md
---

# Plan Review Report: HDR Tonemapping

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 3.5); out-of-scope list is explicit. |
| 2 | Dependencies | PASS | Imports and layering are identified; core acquisition is now pinned in SSOT. |
| 3 | File List | PASS | Explicit files listed, including SSOT spec edits and docs updates. |
| 4 | Contract Impact | PASS | Canonical contracts not touched. |
| 5 | Types Complete | PASS | Public signatures listed and anchored. |
| 6 | Tests Complete | PASS | Exact test names + required assertions + negative cases included. |
| 7 | Verification Complete | PASS | Commands + pass criteria provided. |
| 8 | Decision-Minimizing | FAIL | Two SSOT gaps/inconsistencies still force implementation choices (RGBS conversion call signature; contrast_recovery Expr differs between libplacebo vs fallback sections). |
| 9 | Determinism Defined | PASS | Determinism rules + clamping specified for fallback. |

## Additional Quality Checks

- Error Codes: OK — no new errors; `TonemapError (FC-4003)` is consistently used for unsupported curves/presets/tonemap failures.
- Failure Modes: Issue — RGBS conversion behavior (and its failure mode) is not pinned, so “convert to RGBS via resize.Bicubic” still requires parameter choices.
- Derived Outputs: OK — no generated outputs in this slice.
- Rollback Guidance: OK — STOP-on-ambiguity guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact, deterministic RGB→RGBS (and YUV→RGBS) conversion call signature (what function, what kwargs; whether to always convert; what to do if already RGBS).
2. Exact `contrast_recovery` post-processing behavior is inconsistent:
   - `### 5.2 libplacebo Integration` specifies `std.Expr` `"x 0.5 - {factor} * 0.5 +"` (no clamp).
   - `### 5.3 Fallback Handling` specifies a different expression including clamping (`0 max 1 min`).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: pin exact RGBS conversion**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 5.2 libplacebo Integration` and `### 5.3 Fallback Handling`
   - Problem: “Convert/ensure RGBS via resize.Bicubic” is not mechanically actionable without the exact call and condition.
   - Required Change (SSOT): add a single, deterministic rule used by both paths:
     - The exact function call used to convert to RGBS (one-line snippet; include the `format` constant source).
     - The exact condition for “already RGBS” (no-op vs reconvert).
     - The failure mode if conversion raises (wrap in `TonemapError (FC-4003)` vs propagate).

2. **Update SSOT: unify `contrast_recovery` expression and clamping**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 5.2 libplacebo Integration` and `### 5.3 Fallback Handling`
   - Problem: libplacebo path and fallback path differ; implementation must choose which one is correct.
   - Required Change (SSOT):
     - Specify one exact `std.Expr` string for `contrast_recovery` (including whether to clamp to `[0, 1]`).
     - Specify the exact `std.Expr` invocation shape (e.g., `expr=[expr, expr, expr]` for planes `[0,1,2]`).

## Ready for Implementation

Return to Planning Agent for SSOT+plan revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "### 5.2 libplacebo Integration" add/change:
  - Pin the exact RGBS conversion rule: the literal one-line conversion call (including how `RGBS` is referenced/imported) and the exact “already RGBS” condition (no-op vs reconvert).
  - Update `contrast_recovery` post-processing to the single canonical `std.Expr` string (and specify whether it clamps to `[0, 1]`).
  - Specify the exact `std.Expr` invocation shape used for RGB planes (e.g., `expr=[expr, expr, expr]`).
- Under heading: "### 5.3 Fallback Handling" add/change:
  - Reuse the exact same RGBS conversion rule as `### 5.2 libplacebo Integration` (no divergence).
  - Reuse the exact same canonical `contrast_recovery` expression + clamping rule + invocation shape as `### 5.2 libplacebo Integration`.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v3.md
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
