---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v1
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v1.md
---

# Plan Review Report: Cache I/O Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope items present. |
| 2 | Dependencies | FAIL | Plan relies on `AnalysisConfig` field set for cache invalidation but does not anchor to config SSOT (`config-module.md`) or enumerate required fields; warning/error behavior for corrupted/unreadable cache is also not assigned to a layer. |
| 3 | File List | PASS | Exact files listed; no “and related files”. |
| 4 | Contract Impact | PASS | Declared NO; no contract artifacts listed for regeneration. |
| 5 | Types Complete | FAIL | Public API signature for `save_metrics_cache` conflicts with the plan’s own test snippet (extra `fingerprint` arg). This leaves a public API decision for implementation. |
| 6 | Tests Complete | FAIL | Test list omits required cache behaviors (legacy filename) and includes an invalid call signature; determinism controls for file mtimes are not specified. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit (exit 0). |
| 8 | Decision-Minimizing | FAIL | Multiple behavior choices remain (legacy filename support, which config fields are fingerprinted, where “warn” occurs, IO error handling). |
| 9 | Determinism Defined | FAIL | Deterministic inputs/controls for `compute_cache_key` tests (mtime control) and stable serialization expectations are not fully specified. |

## Additional Quality Checks

- Error Codes: Issue — plan imports `CacheCorruptionError (FC-4006)` but does not specify if/when it is raised/logged vs returning `CacheLoadResult(..., reason="corrupted")`. State explicitly “no new errors; no raises from cache_io” or anchor + define raise/log behavior.
- Failure Modes: Issue — behavior for missing/unstat’able video paths in `compute_cache_key` and for cache read/write permission errors is unspecified.
- Derived Outputs: OK — no generated artifacts in this slice.
- Rollback Guidance: Issue — “STOP if ambiguous” is present but does not specify the required action (return to Planning with CHANGES REQUIRED) when SSOT gaps are found.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Whether `save_metrics_cache` takes a `fingerprint` argument or derives it from `metrics.metadata.config_fingerprint` (must match SSOT).
2. Which `AnalysisConfig` fields are included in the cache key (SSOT implies thresholds; config SSOT enumerates exact fields).
3. Whether and how to support legacy cache filename (`generated.compframes`) per cache strategy SSOT.
4. Which layer emits the “Miss (warn)” behavior for corrupted cache (this slice vs a caller).
5. How to handle IO/stat failures (propagate vs map to `CacheLoadResult(reason=...)`).

## Concrete Edits Required (for plan-v2.md)

1. **Fix public API signature drift**
   - Section: `src/frame_compare/analysis/cache_io.py` + `tests/analysis/test_cache_io.py`
   - Problem: `save_metrics_cache` signature is specified as `save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None`, but the plan’s test snippet calls `save_metrics_cache(metrics, tmp_path, fingerprint)`.
   - Required Change: Make all examples/tests match SSOT exactly; explicitly state fingerprint source (`metrics.metadata.config_fingerprint`) and remove any extra args from tests/snippets.

2. **Anchor and enumerate config fields used in cache key**
   - Section: `## Spec Anchors (SSOT)` + `compute_cache_key` algorithm + tests
   - Problem: Plan fingerprints only `frame_count`, `selection_mode`, `random_seed`, but SSOT calls out “thresholds”, and the exact `AnalysisConfig` fields live in `config-module.md`.
   - Required Change:
     - Add a spec anchor to `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md` under the exact heading `"2.2 Section Schemas"`.
     - Update the `compute_cache_key` algorithm to include (at minimum) `AnalysisConfig.dark_quantile` and `AnalysisConfig.bright_quantile` in addition to fields already listed (or explicitly justify exclusion by SSOT anchor).
     - Add/adjust unit tests to prove that changing each fingerprinted field changes the key (explicit test names).

3. **Add legacy cache filename behavior or explicitly mark out-of-scope**
   - Section: `src/frame_compare/analysis/cache_io.py` algorithm + tests
   - Problem: Cache strategy SSOT says the runner “may also read/write the legacy `generated.compframes` filename at workspace root”, but the plan doesn’t specify support or an out-of-scope statement.
   - Required Change: Choose one (must be explicit):
     - **In-scope:** specify exact read precedence (e.g., prefer `cache_dir/cache.compframes`, else fallback to legacy) and whether writes also update legacy; add unit tests for fallback behavior.
     - **Out-of-scope:** add an out-of-scope bullet in `## Scope` explaining legacy filename support is deferred and why (and which future phase will implement it).

4. **Define corrupted/unreadable cache handling and “warn” responsibility**
   - Section: `load_cached_metrics` algorithm + tests + notes
   - Problem: SSOT invalidation rules include “Cache file corrupt → Miss (warn)”, but the plan doesn’t state where the warning is emitted; it also imports `CacheCorruptionError` without defining usage.
   - Required Change:
     - Explicitly state whether `load_cached_metrics` logs/emits a warning itself or whether the caller is responsible (and how that will be satisfied given Phase 2.2 is out-of-scope).
     - If `CacheCorruptionError` is not raised/used here, remove the import from the planned file and say “no new errors raised in cache_io”.

5. **Make determinism requirements testable**
   - Section: `tests/analysis/test_cache_io.py`
   - Problem: `compute_cache_key` depends on file mtimes; tests do not specify how to set mtimes deterministically across platforms/filesystems.
   - Required Change: Specify deterministic test setup (e.g., `os.utime(..., (fixed, fixed))`) and add assertions for key format (hex length) if required by SSOT.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-4__cache-io

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
