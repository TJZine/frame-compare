---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v11
TARGET: Meta → Phase 5 → Quality Gate Fixes (Docker-first)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v10.md
  - Dockerfile
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v11.md
---

# Plan Review Report: Phase 5 Quality Gate Fixes (Docker-first)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md`

This plan resolves the prior review’s two blockers (pseudocode indentation and a mandated libplacebo success test) and the Spec Anchor STOP gate passes. However, `plan-v10.md` still contains copy/paste-incorrect pseudocode that would lead the Coding Agent to implement invalid code (`TonemapError(...)` constructor usage and an undefined `tone_curve_map`), which reintroduces design decisions and likely breaks runtime/tests.

## Spec Anchor STOP Gate (Required)

Ran:

`UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md`

Result: **PASS (exit 0)**

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; parity gaps explicitly deferred. |
| 2 | Dependencies | PASS | Docker build/runtime + tonemap + Docker gate coupling is explicit. |
| 3 | File List | PASS | Concrete list; no ambiguous “related files”. |
| 4 | Contract Impact | PASS | No canonical contract edits. |
| 5 | Types Complete | PASS | Signature bullets align with SSOT; STOP gate passes. |
| 6 | Tests Complete | PASS | Pseudocode indentation is correct; libplacebo success test is mandated. |
| 7 | Verification Complete | PASS | Includes static gates + import-lint + Docker gate with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Plan pseudocode contains invalid/undefined identifiers (forces Coding Agent to infer the correct implementation). |
| 9 | Determinism Defined | PASS | Deterministic fallback rules + deterministic Docker gate. |

## Additional Quality Checks

- Error Codes: **Issue** — plan’s RGB48 conversion wrapper calls `TonemapError(...)` with the wrong constructor shape; must use `TonemapError(reason=..., hint=...)` per `src/frame_compare/errors.py`.
- Failure Modes: OK (runtime libplacebo failure → DEBUG + fallback; conversion/preset errors remain `TonemapError(FC-4003)`).
- Derived Outputs: OK (no contract-derived outputs).
- Rollback Guidance: OK.
- SSOT Update Audit: OK (SSOT indentation fix + `_apply_libplacebo` signature are sound; validator now sees the anchored `def` blocks).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Correct construction of `TonemapError` during RGB48 conversion failure (plan currently wrong).
2. Exact symbol to use for tone-curve mapping (`tone_curve_map` is undefined in current codebase; plan must mandate the existing mapping constant name).
3. Whether to pass `dst_csp=0` to `core.placebo.Tonemap` (not specified in SSOT; plan must not introduce new kwargs without an SSOT anchor).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix RGB48 conversion error wrapping to match actual `TonemapError` API (blocking)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md` (new plan; do not edit plan-v10 in place)
   - Section: `src/frame_compare/vs/tonemap.py` → “Change 2: Update input conversion to RGB48”
   - Problem: `raise TonemapError(f"Failed to convert to RGB48: {e}")` is invalid (constructor is `TonemapError(reason: str, hint: str | None = None)`).
   - Required change: update the plan snippet to use:
     - `raise TonemapError(reason=f"Failed to convert to RGB48: {e}") from e`
     - (Optional) include a deterministic hint string if desired, but do not change error codes.

2. **Remove undefined `tone_curve_map` and mandate the existing mapping symbol (blocking)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md`
   - Section: `src/frame_compare/vs/tonemap.py` → “Change 3: Post-tonemap RGBS conversion + runtime failure handling”
   - Problem: `tone_curve_map` is not defined in the current module; the implementation uses `_TONE_CURVE_MAP`.
   - Required change: update the plan snippet to reference the existing mapping symbol (`_TONE_CURVE_MAP`) and keep the SSOT “unsupported tone curve” behavior.

3. **Do not introduce `dst_csp` kwarg without SSOT anchor (blocking)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md`
   - Section: `src/frame_compare/vs/tonemap.py` → “Change 3…”
   - Problem: `dst_csp=0` is not specified in SSOT `### 5.2 libplacebo Integration`.
   - Required change: remove `dst_csp=0` from the plan snippet unless SSOT is explicitly updated to require it (SSOT update is not requested for this plan-only revision).

## Ready for Implementation

Not ready. Requires a plan-only revision (`plan-v11.md`) that removes remaining implementation decisions and makes the pseudocode mechanically correct.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v11.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md

## Hard Rules
- Do not edit plan-v10 in place; write plan-v11.md with `## Changes Since plan-v10`.
- Spec Anchors must remain valid; re-run:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md`
- Remove undefined identifiers from pseudocode (`tone_curve_map`) and align `TonemapError` usage to `TonemapError(reason=..., hint=...)`.
