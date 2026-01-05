---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v5
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v5.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md

Notes:
- `scripts/validate_spec_anchors.py` passes for `plan-v5.md`.
- Critical audit of SSOT changes introduced earlier in this RUN_ID: OK (ffprobe FPS sourcing, cache schema + versioning, error propagation list, `load_cached_offsets` semantics).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (5.1) + explicit utils progress dependency. |
| 2 | Dependencies | PASS | External deps are explicit (ffmpeg/ffprobe); progress impls match utils SSOT surface. |
| 3 | File List | PASS | Includes `tests/utils/*` and services files; docs + import-linter updates included. |
| 4 | Contract Impact | PASS | Explicit **NO**. |
| 5 | Types Complete | PASS | Public signatures listed and SSOT-anchored (validator passes). |
| 6 | Tests Complete | FAIL | Alignment tests are underspecified (no concrete TOML fixture/expected parsed result; no explicit `pytest.approx` tolerances; missing cache key/value assertions). |
| 7 | Verification Complete | PASS | Commands listed and include `tests/services/` + `tests/utils/`. |
| 8 | Decision-Minimizing | FAIL | Plan relies on “same as plan-v3/v4” for key test vectors and leaves `align_clips` cache behavior/order unspecified (SSOT gap). |
| 9 | Determinism Defined | FAIL | Numeric tolerance and ordering expectations are not defined for several tests. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: Issue — `align_clips` cache hit/partial-hit behavior is not specified (SSOT gap), but the plan includes a cache-related test.
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: OK.
- SSOT Update Audit (if SSOT changed this loop): N/A (no new SSOT changes proposed in plan-v5).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact deterministic fixtures and assertions for cache read/write tests (`load_cached_offsets`, `save_offsets_cache`).
2. `align_clips` cache behavior (full hit vs partial vs miss) and output ordering guarantees.
3. Explicit numeric tolerance for correlation score assertions.

## Concrete Edits Required (plan-v6)

1. **Update SSOT first: make `align_clips` cache semantics explicit**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` → `### 2.2 Public API`
   - Problem: `align_clips` does not specify whether/how it uses `load_cached_offsets`, and does not explicitly state output ordering.
   - Required Change (minimal bullets; no prose):
     - Define output ordering: returned `list[AlignmentResult]` is in the same order as the input `comparisons`.
     - Define cache read semantics when `config.cache_results` is True:
       - Full cache hit (all requested keys present): return cached results without calling ffprobe/ffmpeg.
       - Partial hit: compute only missing comparisons, then return combined results in `comparisons` order.

2. **Make alignment/cache tests mechanically checkable (plan-only)**
   - Section: Plan → `tests/services/test_alignment.py`
   - Problem: Plan lists tests but omits the concrete fixture text and the exact expected `AlignmentResult` assertions.
   - Required Change:
     - Add a concrete TOML fixture block (version + one entry) and the exact expected parsed dict/`AlignmentResult` (use the plan-v3 fixture content).
     - For `test_cross_correlate_identical_signals`, specify `pytest.approx(1.0, abs=1e-6)` for `correlation_score`.
     - For `test_save_offsets_cache_writes_toml`, specify the exact asserts (file exists; contains `version = "1"`; contains section header for the expected key; contains required fields).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v6.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- Under heading: "### 2.2 Public API" add/change:
  - For `align_clips(...) -> list[AlignmentResult]`, add an explicit rule: returned results are in the same order as the input `comparisons`.
  - Add cache read semantics when `config.cache_results` is True:
    - Full cache hit (all requested keys present): return cached results without calling ffprobe/ffmpeg.
    - Partial hit: compute only missing comparisons and then return combined results in `comparisons` order.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v5.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
