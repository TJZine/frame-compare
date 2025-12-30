---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v2
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v2.md
---

# Plan Review Report: HDR Tonemapping

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 3.5); explicit out-of-scope list; mocked tests only. |
| 2 | Dependencies | FAIL | “Obtain core via `clip.std`” is not mechanically actionable; the plan does not specify the exact attribute chain to produce a `vs.Core` object needed for `detect_plugins(core)`. |
| 3 | File List | FAIL | Run includes SSOT edits in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` but that file is not listed under “Files to Create/Modify”. |
| 4 | Contract Impact | PASS | Canonical contracts not touched; no regen gates required. |
| 5 | Types Complete | PASS | Public signatures are listed (backticked) and anchored. |
| 6 | Tests Complete | PASS | Exact test names + assertions + failure mode included; no vague “VS-required tests”. |
| 7 | Verification Complete | PASS | Commands + explicit pass criteria provided. |
| 8 | Decision-Minimizing | FAIL | Remaining undefined behaviors force implementer choices: core acquisition exact expression, unsupported `tone_curve` handling (schema allows more values), and exact `std.Expr` strings/clamping rules for fallback + post-processing. |
| 9 | Determinism Defined | PASS | No RNG; deterministic preset table + fallback formula stated. |

## Additional Quality Checks

- Error Codes: Issue — SSOT+plan specify `TonemapError (FC-4003)` for unknown preset, but do not define behavior for unsupported `settings.tone_curve` values (must be TonemapError or deterministic mapping).
- Failure Modes: Issue — tonemap core acquisition failure mode not defined (what error is raised if core cannot be obtained as specified).
- Derived Outputs: OK — no generated outputs in this slice.
- Rollback Guidance: OK — plan includes “STOP and return to Planning” guidance.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact, testable core acquisition expression to obtain `vs.Core` from a `vs.VideoNode` (“via `clip.std`” is not sufficient).
2. Behavior for `settings.tone_curve` values outside the mapping table (config schema includes `mobius`, `linear`).
3. Exact `std.Expr` expression strings (including constant substitution and clamping rules) for:
   - fallback Reinhard formula
   - `contrast_recovery` post-processing

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: make core acquisition mechanically actionable**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 3.3 Tonemapping`
   - Problem: “Obtain `vs.Core` via `clip.std`” is underspecified; implementation and tests must know the exact attribute chain.
   - Required Change (SSOT): add a single bullet that includes the literal one-line code expression used to obtain the core, e.g.:
     - `core = <EXACT_CORE_EXPRESSION>` (must be a concrete expression; no examples, no “e.g.”)
     - and a 1-line note of what exception/error is raised if this expression cannot produce a core (TonemapError vs propagate).

2. **Update SSOT: define unsupported `tone_curve` handling**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 5.2 libplacebo Integration`
   - Problem: Mapping table lists only `bt2390/spline/reinhard`, but config schema allows additional values; behavior must be deterministic.
   - Required Change (SSOT): add a rule for `settings.tone_curve` not in the mapping table:
     - either (A) raise `TonemapError (FC-4003)` with a hint listing supported curves, or (B) define an explicit mapping for the additional allowed values.

3. **Update SSOT: pin exact `std.Expr` strings + clamping behavior**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 5.3 Fallback Handling`
   - Problem: “Use `std.Expr` with formula” is still ambiguous without the exact expression string(s) and whether values are clamped to `[0, 1]`.
   - Required Change (SSOT):
     - Provide the exact `std.Expr` expressions (one per plane or a shared expression) for the fallback formula, including how `peak` and `target_nits` are substituted.
     - State whether output MUST be clamped to `[0, 1]` (and if yes, how).
     - Provide the exact `std.Expr` (or alternative deterministic) expression used for `contrast_recovery` post-processing.

4. **Revise plan file list to include SSOT spec edits**
   - Section: `## Files to Create/Modify (Complete List)`
   - Problem: Plan claims SSOT updates but omits the modified SSOT file path, making the run file list incomplete.
   - Required Change (plan): add `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` (MODIFY) with a short bullet list of the headings changed (already in “Changes Since plan-v1”; mirror here).

## Ready for Implementation

Return to Planning Agent for SSOT+plan revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "### 3.3 Tonemapping" add/change:
  - Add the literal one-line core acquisition expression used to obtain `vs.Core` from `clip` (no examples; must be concrete).
  - Define the failure mode if core acquisition fails (wrap in `TonemapError (FC-4003)` vs propagate).
- Under heading: "### 5.2 libplacebo Integration" add/change:
  - Define deterministic behavior when `settings.tone_curve` is not in the mapping table (raise `TonemapError (FC-4003)` with hint, or explicit mapping for all allowed values).
- Under heading: "### 5.3 Fallback Handling" add/change:
  - Provide exact `std.Expr` expression string(s) for the fallback Reinhard formula (including constants substitution) and define clamping behavior.
  - Provide exact expression/operation for `contrast_recovery` post-processing (deterministic; no “boost mid-tones” ambiguity).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
