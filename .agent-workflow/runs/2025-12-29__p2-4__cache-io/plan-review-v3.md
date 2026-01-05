---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v3
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v3.md
---

# Plan Review Report: Cache I/O Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope items are explicit. |
| 2 | Dependencies | PASS | Spec anchors include analysis + config; exception policy is explicit. |
| 3 | File List | PASS | Complete, minimal list. |
| 4 | Contract Impact | PASS | Declared NO; no contract regeneration required. |
| 5 | Types Complete | PASS | All public signatures listed and spec-anchored; `validate_spec_anchors.py` passes. |
| 6 | Tests Complete | FAIL | Round-trip test assertions are underspecified (what “data matches” means), and there are no tests that constrain the cache file format (schema/version keys) even though this slice is “cache I/O”. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | Plan does not define the cache file schema/serialization rules or the semantics of the `clips` parameter in `load_cached_metrics`, leaving core behavior to the Coding Agent. |
| 9 | Determinism Defined | PASS | Deterministic mtimes + order-independence are explicitly required and tested. |

## Additional Quality Checks

- Error Codes: OK — plan states no Frame Compare custom exceptions raised from cache I/O functions.
- Failure Modes: Issue — without a defined schema, behavior on missing keys/shape drift is undefined (corrupted vs version mismatch vs fingerprint mismatch).
- Derived Outputs: OK — none.
- Rollback Guidance: OK — STOP instruction includes the required workflow action.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Cache file schema: keys, nested shapes, and how to serialize/deserialize `MetricsMetadata.fps` (`Fraction`).
2. Validation policy: which cache-file shape problems map to `reason="corrupted"` vs other reasons.
3. `clips` parameter semantics for `load_cached_metrics(...)` (ignored vs validated vs used for reconstruction/invalidation).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Update SSOT spec first: define cache file format + `clips` semantics**
   - Problem: Cache persistence behavior is not fully defined in SSOT, so a plan cannot be implementation-ready without forcing Coding to invent a schema.
   - Required SSOT Update:
     - Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
     - Under heading: `"### 3.3 Cache Operations"` add bullets specifying:
       - `load_cached_metrics(..., clips)` — whether `clips` is ignored (and why) or validated; if ignored, state “`fingerprint` is authoritative; do not recompute”.
       - Failure mapping for unreadable/invalid JSON and missing required keys → `reason="corrupted"`.
     - Under heading: `"## 5. Cache Strategy"` add bullets specifying the **cache file JSON schema** for v2:
       - Top-level required keys: `version` (int), `fingerprint` (str), `luminance` (list[float]), `motion` (list[float]), `metadata` (object)
       - `metadata` required keys: `frame_count` (int), `fps` (str), `config_fingerprint` (str), `clips` (list[object]), `version` (int)
       - `fps` encoding: store `str(Fraction)` and parse via `Fraction(fps_str)` on load (or explicitly specify another deterministic encoding + parsing rule)

2. **Then revise plan-v4 to re-anchor and lock tests to the SSOT schema**
   - Section: `tests/analysis/test_cache_io.py`
   - Problem: Plan currently has no test that the cache format produced/consumed matches the SSOT schema.
   - Required Change (after SSOT update): Add explicit tests (names + assertions) that:
     - `save_metrics_cache` writes JSON containing required top-level keys and `version == 2`
     - `load_cached_metrics` returns `reason="corrupted"` when required keys are missing (at least one representative missing-key case)

3. **Doc updates must list required facts**
   - Section: `docs/DECISIONS.md`, `CHANGELOG.md`
   - Problem: Plan includes these files in scope but does not list required facts to record.
   - Required Change: Add a short “Docs updates” bullet list (facts only): RUN_ID, plan/review versions, verification commands run, and the public API added/changed.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-4__cache-io

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
- Under heading: "### 3.3 Cache Operations" add/change:
  - Define whether `clips` is ignored or validated in `load_cached_metrics(...)`; if ignored, state “fingerprint is authoritative; do not recompute fingerprint from clips”.
  - Define that invalid JSON or missing required keys returns `CacheLoadResult(success=False, reason=\"corrupted\")`.
- Under heading: "## 5. Cache Strategy" add/change:
  - Define the v2 cache JSON schema (required top-level keys + required `metadata` keys).
  - Define deterministic `MetricsMetadata.fps` serialization/deserialization (e.g., store `str(Fraction)`; parse via `Fraction(fps_str)`).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v3.md
Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
