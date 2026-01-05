---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v5
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v5.md
---

# Plan Review Report: Cache I/O Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v5.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope items are explicit. |
| 2 | Dependencies | PASS | SSOT anchors cover cache operations, schema, invalidation rules, and AnalysisConfig fields. |
| 3 | File List | PASS | Exact files listed. |
| 4 | Contract Impact | PASS | Declared NO. |
| 5 | Types Complete | PASS | Public signatures listed; `validate_spec_anchors.py` passes. |
| 6 | Tests Complete | FAIL | New invalidation-trigger tests are listed, but the plan no longer specifies the behaviors they are validating for `load_cached_metrics` / `save_metrics_cache` (it defers to plan-v4). |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | “Other functions: As specified in plan-v4” is not SSOT and makes the plan non-standalone; Coding must consult older plan text and/or invent missing details. |
| 9 | Determinism Defined | PASS | Deterministic cache-key encoding rules and deterministic test helpers are specified. |

## Additional Quality Checks

- Error Codes: OK — cache I/O uses `CacheLoadResult.reason`.
- Failure Modes: Issue — plan does not specify exception policy for `save_metrics_cache` / `load_cached_metrics` in this version (it was present in earlier plans but not in plan-v5).
- Derived Outputs: OK — none.
- Rollback Guidance: OK — STOP instruction is present, but must name the next artifact (`plan-v6.md`) when stopping.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. The full, testable behavior of `load_cached_metrics` and `save_metrics_cache` (currently referenced indirectly via plan-v4, not via SSOT or explicit plan-v5 steps).
2. Exception propagation policy for `save_metrics_cache` and `load_cached_metrics` in this plan version.

## Concrete Edits Required (plan-v6.md) — plan-only

> [!IMPORTANT]
> This is plan-v5 review (iteration cap exceeded). Keep changes surgical and self-contained; do not churn unrelated sections.

1. **Make the plan standalone (remove cross-version dependency)**
   - Section: `src/frame_compare/analysis/cache_io.py`
   - Problem: `Other functions: As specified in plan-v4.` is not SSOT and forces the Coding Agent to consult older plan versions.
   - Required Change: Replace that line with explicit, SSOT-anchored requirements that fit in plan-v6, e.g. short bullets referencing:
     - SSOT `"### 3.3 Cache Operations"` failure mapping + clips semantics
     - SSOT `"### 5.2 Cache File Schema (v2)"` required keys + `fps` serialization/deserialization

2. **Re-add explicit exception/IO policy (no contradictions)**
   - Section: `src/frame_compare/analysis/cache_io.py`
   - Problem: plan-v5 does not state whether `save_metrics_cache` propagates `OSError` and whether `load_cached_metrics` catches `OSError` on read.
   - Required Change: Add a short “Exception policy” block (must be consistent with SSOT):
     - `compute_cache_key`: may propagate `OSError` from `Path.stat()`
     - `save_metrics_cache`: may propagate `OSError` from filesystem writes
     - `load_cached_metrics`: does not raise; returns `CacheLoadResult(... reason=...)` per SSOT mapping

3. **Make STOP instruction workflow-specific**
   - Section: `## Notes for Coding Agent`
   - Required Change: “If SSOT ambiguity encountered: STOP and return to Planning with CHANGES REQUIRED; emit `plan-v6.md`.”

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v6.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-4__cache-io

## Revision Required (plan-only; keep it surgical)
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v5.md
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v5.md
Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v6.md

## Hard Rules
- Include `## Changes Since plan-v5` listing only the deltas that address this review.
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
