---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v1
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v1.md
---

# Plan Review Report: HDR Tonemapping

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 3.5); clear out-of-scope list. |
| 2 | Dependencies | FAIL | Plan doesn’t pin the required internal dependencies/imports for core acquisition + plugin detection (e.g., `ensure_vs_environment()`, `detect_plugins(core)`), leaving implementation choices. |
| 3 | File List | PASS | Concrete list with explicit paths; no “and related files”. |
| 4 | Contract Impact | PASS | No canonical contract edits planned. |
| 5 | Types Complete | PASS | Public signatures listed and anchored. |
| 6 | Tests Complete | FAIL | Mentions “VS-required tests” without exact tests/fixtures; missing failure-mode tests (e.g., `settings.enabled=False`, tonemap operator failures → `TonemapError`). |
| 7 | Verification Complete | PASS | Commands + explicit pass criteria provided. |
| 8 | Decision-Minimizing | FAIL | Multiple behavior decisions are not defined in SSOT (libplacebo kwarg mapping, fallback algorithm details, invalid preset error type, preset field defaults); plan also expands public API (`TONEMAP_PRESETS`) without SSOT. |
| 9 | Determinism Defined | PASS | Determinism statement present; no RNG. |

## Additional Quality Checks

- Error Codes: Issue — plan introduces new raise sites (unknown preset) without SSOT specifying whether to use `TonemapError (FC-4003)` vs another error.
- Failure Modes: Issue — missing explicit behavior for `settings.enabled == False`, missing vapoursynth/core init errors, and missing libplacebo behavior (fallback vs warn vs error) as SSOT-backed rules.
- Derived Outputs: OK — no generated artifacts listed for this slice.
- Rollback Guidance: Issue — plan should state “if libplacebo API/kwargs cannot be pinned from SSOT, STOP and return to Planning”.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact `core.placebo.Tonemap(...)` kwarg mapping for `TonemapSettings` fields (`tone_curve`, `target_nits`, `source_peak`, `contrast_recovery`, `gamma_lift`) is not specified in SSOT.
2. Exact fallback tonemap algorithm (including input/output scaling and VS operations) is not specified in SSOT.
3. Behavior for `TonemapSettings.enabled == False` is not specified in SSOT.
4. Error semantics for unknown preset in `get_preset_settings()` are not specified in SSOT.
5. Whether `TONEMAP_PRESETS` is part of the public API is not specified in SSOT.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: pin tonemap behavior + libplacebo mapping**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Problem: `### 3.3 Tonemapping`, `### 5.2 libplacebo Integration`, and `### 5.3 Fallback Handling` do not define enough detail to implement without choosing kwargs/algorithms.
   - Required Change (SSOT): edit `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
     - Under heading: `### 3.3 Tonemapping` add bullets specifying:
       - What `apply_tonemap()` MUST do when `settings.enabled` is `False` (expected: deterministic no-op return of `clip`).
       - How `core` is obtained (exactly one method; must not create a new Core per call).
       - Missing libplacebo rule: fallback vs error vs warning (pick exactly one).
     - Under heading: `### 5.2 libplacebo Integration` add a deterministic mapping table:
       - `TonemapSettings` field → exact `core.placebo.Tonemap` keyword argument name/value mapping (including how `tone_curve` string values map).
       - How `target_nits` and `source_peak` are applied, including what happens when `hdr_metadata` is `None`.
       - Whether `contrast_recovery` / `gamma_lift` are passed to libplacebo, implemented as post-processing, or treated as no-ops (choose exactly one path per field).
     - Under heading: `### 5.3 Fallback Handling` add a deterministic algorithm spec:
       - Exact formula and expected working range (e.g., float domain assumptions) and which VS ops are used (`std.Expr` vs other).
       - Exact output format/transfer expectations (or explicit “no format conversion here; caller handles”).

2. **Update SSOT: presets must resolve to full TonemapSettings**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Problem: `## 4. Tonemap Presets` defines only (curve, target_nits), but the implementation needs deterministic values for the other `TonemapSettings` fields and whether `preset` is set.
   - Required Change (SSOT): under heading `## 4. Tonemap Presets` add bullets specifying:
     - For each preset, which `TonemapSettings` fields are set explicitly (at minimum: `preset`, `tone_curve`, `target_nits`) and which MUST remain at default values (e.g., `source_peak=None`, `contrast_recovery=0.0`, `gamma_lift=False`), unless SSOT defines overrides.

3. **Revise plan to remove non-SSOT public API expansion**
   - Section: “Files to Create/Modify” → `src/frame_compare/vs/__init__.py`
   - Problem: Plan exports `TONEMAP_PRESETS` publicly without SSOT requiring it; this expands API surface and adds churn risk.
   - Required Change (plan): remove `TONEMAP_PRESETS` from `__init__.py` export plan and adjust tests to validate the 7 preset names without importing a new public constant.

4. **Make tests fully specified and aligned to repo patterns**
   - Section: `tests/vs/test_tonemap.py` (NEW)
   - Problem: “VS-required tests” are listed but not defined; failure-mode coverage is incomplete.
   - Required Change (plan):
     - Either remove “VS-required tests” from scope for this run (recommended, since repo currently uses mocks in `tests/vs/*`), or specify exact fixtures/files/markers to add.
     - Add explicit tests for:
       - `settings.enabled == False` returns original `clip` unchanged (once SSOT defines expected behavior).
       - Underlying libplacebo/fallback exception path → `TonemapError` raised (once SSOT defines wrapping vs propagation).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "### 3.3 Tonemapping" add/change:
  - Define `apply_tonemap()` behavior when `settings.enabled == False` (no-op vs error; choose one).
  - Define the exact `core` acquisition method (single, deterministic; must not create a new Core per call).
  - Define missing libplacebo rule (fallback vs error vs warning; choose one).
- Under heading: "### 5.2 libplacebo Integration" add/change:
  - Add a mapping table: `TonemapSettings` fields (`tone_curve`, `target_nits`, `source_peak`, `contrast_recovery`, `gamma_lift`) → exact `core.placebo.Tonemap` kwargs (include `tone_curve` value mapping).
  - Specify how `hdr_metadata` is used when provided vs when `None`.
- Under heading: "### 5.3 Fallback Handling" add/change:
  - Specify the exact fallback tonemap algorithm (formula, assumed value ranges, and which VS ops are used) and output expectations.
- Under heading: "## 4. Tonemap Presets" add/change:
  - Specify how each preset resolves to a full `TonemapSettings` (at minimum `preset`, `tone_curve`, `target_nits`), and which remaining fields MUST stay at defaults unless overridden.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
