---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v7
TARGET: Meta → Phase 5 → Quality Gate Fixes (Docker-first)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v6.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - Dockerfile
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v7.md
---

# Plan Review Report: Phase 5 Quality Gate Fixes (Docker-first)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md`

The plan is close and is directionally correct, but it is not implementation-ready because it fails the spec-anchor validator and leaves typed signature wiring inconsistent between SSOT and the plan. This is a stop condition for Coding.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: “Phase 5 Docker-first quality gate pass” with explicit out-of-scope items. |
| 2 | Dependencies | PASS | Correctly identifies Docker + VS + libplacebo + tests gate coupling. |
| 3 | File List | PASS | Explicit list for Dockerfile, tonemap, tests, docker gate script, docs. |
| 4 | Contract Impact | PASS | Declares NO canonical contract changes; no derived-contract gates required. |
| 5 | Types Complete | FAIL | Planned signatures are not type-complete and do not match anchored SSOT signatures (fails `validate_spec_anchors.py`). |
| 6 | Tests Complete | PASS | Adds a concrete unit test for runtime-failure fallback; keeps Docker integration as the primary gate. |
| 7 | Verification Complete | PASS | Includes local gates + `lint-imports` + Docker integration gate with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | `_apply_libplacebo` signature/return contract is inconsistent between SSOT and plan (hdr_metadata param + `| None`), forcing the Coding Agent to reconcile. |
| 9 | Determinism Defined | PASS | Fallback trigger behavior is deterministic; no randomness introduced. |

## Additional Quality Checks

- Error Codes: OK (no new error types introduced; continues to use `TonemapError` FC-4003 for fatal conversion/preset errors)
- Failure Modes: OK (explicit runtime libplacebo failure → DEBUG log + fallback)
- Derived Outputs: OK (no contract-derived outputs in scope)
- Rollback Guidance: OK (must STOP if SSOT/anchors cannot be validated)
- SSOT Update Audit (required): **Issue**
  - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` defines `_apply_libplacebo(...)` returning `vs.VideoNode` in the signature block, while the same section mandates “Return `None` on runtime failure”.
  - The plan’s `_apply_libplacebo(...) -> vs.VideoNode | None` is consistent with the behavioral rule, but the SSOT signature block must be updated so anchors/validators and type-checking are aligned and the Coding Agent does not have to guess.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

Blocking decisions to remove (must be resolved in SSOT + plan wiring):

1. Exact `_apply_libplacebo` signature (include `hdr_metadata` param or not) and exact return annotation (`vs.VideoNode | None` vs `vs.VideoNode`).
2. Plan signature lines must match the anchored SSOT signatures exactly (validator currently fails).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix SSOT signature/typing mismatch for `_apply_libplacebo` (blocking)**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Under heading: `### 5.2 libplacebo Integration` change the `_apply_libplacebo` signature block so it matches the stated runtime-failure behavior:
     - Add the optional metadata parameter to remove drift with current implementation/tests:
       - `hdr_metadata: HDRMetadata | None = None`
     - Update the return annotation to include `None`:
       - `) -> vs.VideoNode | None:`
     - Update the “Returns:” line(s) directly under that block to reflect that `None` is allowed only for runtime-failure fallback signaling (conversion/preset errors still raise `TonemapError(FC-4003)`).

2. **Revise plan signatures to be type-complete and SSOT-matching (blocking)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v7.md` (new plan; do not edit plan-v6 in place)
   - Section: `## Functions to Implement/Modify`
   - Required change:
     - Replace the plan’s function signature bullets with exact one-line signatures copied from the SSOT blocks under:
       - `### 3.3 Tonemapping`
       - `### 5.2 libplacebo Integration`
     - After updating SSOT per item (1), the plan must list (verbatim) the updated `_apply_libplacebo(...)` signature, including types and `| None`.

3. **Spec Anchors must use exact headings (validator hygiene)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v7.md`
   - Section: `## Spec Anchors (SSOT)`
   - Required change: copy/paste the headings exactly as they appear in the SSOT docs (including numbering text), so `validate_spec_anchors.py` can match anchors deterministically.

## Ready for Implementation

Not ready. Fix the SSOT signature mismatch and re-issue the plan so the spec-anchor validator passes and Decision Points Remaining becomes NONE.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "### 5.2 libplacebo Integration" add/change:
  - Update the `_apply_libplacebo` signature block to include `hdr_metadata: HDRMetadata | None = None`.
  - Update the `_apply_libplacebo` return annotation to `-> vs.VideoNode | None` to match the “return None on runtime failure” rule.
  - Update the `Returns:` text under `_apply_libplacebo` to explicitly permit `None` only for runtime-failure fallback signaling (conversion/preset errors still raise `TonemapError(FC-4003)`).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v7.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v7.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- After revising `plan-v7.md`, run:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v7.md`
