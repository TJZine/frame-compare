---
RUN_ID: 2025-12-29__p2-1__analysis-types
VERSION: v1
TARGET: Phase 2 → Item 2.1
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-review-v1.md
---

# Plan Review Report: Analysis Types

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (analysis types only) + explicit out-of-scope list. |
| 2 | Dependencies | PASS | Depends on `frame_compare.config.SelectionMode`; no runtime VS deps in this slice. |
| 3 | File List | FAIL | Missing required workflow artifacts (`docs/DECISIONS.md`) and import-contract SSOT update (`importlinter.ini`) for introducing `frame_compare.analysis` as a real module. |
| 4 | Contract Impact | PASS | Declares **NO** for canonical contracts; OK. (But SSOT specs likely need update — see below.) |
| 5 | Types Complete | FAIL | Spec Anchors aren’t verbatim headings; dataclass immutability (`frozen=True, slots=True`) is required by the plan/tests but not specified in SSOT analysis-module.md code blocks. |
| 6 | Tests Complete | FAIL | Tests assert frozen dataclasses (`FrozenInstanceError`) but SSOT currently defines mutable dataclasses; constructors/immutability behavior is therefore not SSOT-aligned. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit and include `lint-imports`. |
| 8 | Decision-Minimizing | FAIL | Coding Agent would need to decide whether to follow SSOT (`@dataclass`) or plan (`@dataclass(frozen=True, slots=True)`). |
| 9 | Determinism Defined | PASS | No randomness/output ordering in this slice; tests are deterministic. |

## Additional Quality Checks

- Error Codes: OK — no new errors introduced in this slice.
- Failure Modes: OK — type-only slice.
- Derived Outputs: OK — no generated artifacts.
- Rollback Guidance: OK — STOP guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Dataclass immutability/slots policy for analysis types (SSOT vs plan mismatch).
2. Whether to update import contracts (importlinter layers) as required by workflow when introducing `frame_compare.analysis`.
3. SSOT anchor exactness (plan uses “Section: …” instead of verbatim headings).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT spec first: decide dataclass immutability/slots**
   - Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
   - Under headings (verbatim):
     - `### 2.1 FrameMetrics`
     - `### 2.2 FrameSelection`
     - `### 2.3 CacheLoadResult`
   - Add/change (minimal):
     - Update all type code blocks to use `@dataclass(frozen=True, slots=True)` for every dataclass (`FrameMetrics`, `MetricsMetadata`, `ClipIdentity`, `FrameSelection`, `SelectionBreakdown`, `CacheLoadResult`), OR explicitly state they are plain `@dataclass` and remove immutability requirements.
     - Ensure the SSOT and the plan agree (tests must match the SSOT decision).

2. **Fix Spec Anchors (SSOT) to be mechanically valid**
   - Section: `## Spec Anchors (SSOT)`
   - Required change: replace “Section: …” entries with exact heading text (including `###`), e.g.:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md` → `### 2.1 FrameMetrics`, `### 2.2 FrameSelection`, `### 2.3 CacheLoadResult`, `### 3.1 calculate_metrics`

3. **Add missing required files to the plan**
   - Add to `## Files to Create/Modify`:
     - `docs/DECISIONS.md` (MODIFY) with required facts: RUN_ID, scope, SSOT edits (if any), import-contract changes (if any).
     - `importlinter.ini` (MODIFY): add `frame_compare.analysis` to the layers contract. Place it explicitly (recommended: immediately after `frame_compare.cli_entry`) so import direction constraints are unambiguous.

4. **Align tests with SSOT decision**
   - If SSOT is updated to frozen/slots: keep `FrozenInstanceError` test and require `@dataclass(frozen=True, slots=True)` everywhere.
   - If SSOT stays mutable: remove frozen/immutability assertions from the plan and tests.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-1__analysis-types

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
- Under heading: "### 2.1 FrameMetrics" add/change:
  - Decide and specify whether all analysis dataclasses are `@dataclass(frozen=True, slots=True)` or plain `@dataclass`.
- Under heading: "### 2.2 FrameSelection" add/change:
  - Apply the same dataclass decorator decision to `FrameSelection` and `SelectionBreakdown`.
- Under heading: "### 2.3 CacheLoadResult" add/change:
  - Apply the same dataclass decorator decision to `CacheLoadResult`.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
