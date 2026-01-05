---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v2
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v2.md
---

# Plan Review Report: Cache I/O Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope (legacy filename + warnings) is explicit. |
| 2 | Dependencies | PASS | Adds `config-module.md` SSOT anchor for cache-key fields; Phase dependencies stated. |
| 3 | File List | PASS | Exact files listed. |
| 4 | Contract Impact | PASS | Declares NO; no contract regeneration required. |
| 5 | Types Complete | PASS | Public signatures listed; v1 signature drift is resolved. |
| 6 | Tests Complete | FAIL | Tests do not cover all fields the plan claims are fingerprinted (`selection_mode`, `random_seed`), and do not lock the plan’s “order-independent” intent for `video_paths`. |
| 7 | Verification Complete | PASS | Explicit commands + “exit 0” pass criteria. |
| 8 | Decision-Minimizing | FAIL | Error/exception behavior is contradictory (“no exceptions raised” vs `compute_cache_key`/`save_metrics_cache` calling `stat()`/`write_text()` without a defined propagation policy). |
| 9 | Determinism Defined | PASS | Fixed mtime via `os.utime()` is specified; remaining ambiguity is limited to path-order handling (see Tests). |

## Additional Quality Checks

- Error Codes: OK — plan explicitly says no `CacheCorruptionError` and uses `CacheLoadResult.reason` strings.
- Failure Modes: Issue — missing/permission errors for `compute_cache_key` and `save_metrics_cache` are not specified (propagate vs map).
- Derived Outputs: OK — none in-scope.
- Rollback Guidance: Issue — plan’s “STOP if ambiguous” does not state the required workflow action (return to Planning with a new plan version).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Whether `compute_cache_key()` propagates `OSError` from `Path.stat()` (and if not, what it does instead).
2. Whether `save_metrics_cache()` propagates `OSError` from `mkdir()`/`write_text()` (and if not, what it does instead).
3. Whether `video_paths` order is semantically irrelevant (current algorithm sorts) and therefore must be enforced by tests.
4. Whether `selection_mode` and `random_seed` are truly part of the fingerprinted config set (algorithm includes them; tests/acceptance criteria currently do not fully cover them).

## Concrete Edits Required (for plan-v3.md)

1. **Resolve exception/IO behavior (remove contradiction)**
   - Section: `src/frame_compare/analysis/cache_io.py` → **Error handling**
   - Problem: The plan states “No exceptions raised by this module”, but `compute_cache_key` and `save_metrics_cache` necessarily can raise `OSError`.
   - Required Change: Replace with an explicit, testable policy, e.g.:
     - `load_cached_metrics` returns `CacheLoadResult(... reason=...)` for decode/read failures (as already specified)
     - `compute_cache_key` may propagate `OSError` from `Path.stat()`
     - `save_metrics_cache` may propagate `OSError` from filesystem writes
     - “No Frame Compare custom exceptions raised” (if that is the intent)

2. **Align tests with the plan’s declared fingerprinted fields**
   - Section: `tests/analysis/test_cache_io.py` → tests table + acceptance criteria
   - Problem: `compute_cache_key` fingerprints `selection_mode` and `random_seed` but there are no tests proving key changes when these fields change.
   - Required Change: Add explicit unit tests (names specified) to cover both fields, OR remove these fields from the algorithm and update acceptance criteria to match. The revised plan must pick one and be consistent.

3. **Lock path-order intent for determinism**
   - Section: `tests/analysis/test_cache_io.py`
   - Problem: Algorithm sorts `video_paths`, but tests don’t prove order-independence; the phrase “Same paths” is ambiguous.
   - Required Change: Add a test that passes the same set of paths in different orders and asserts identical keys (name it explicitly, e.g. `test_compute_cache_key_order_independent`).

4. **Make STOP/rollback instruction workflow-compliant**
   - Section: `## Notes for Coding Agent`
   - Problem: “STOP if ambiguous” does not say what to do next.
   - Required Change: Replace with: “If any SSOT ambiguity is encountered, STOP implementation and return to Planning with CHANGES REQUIRED; emit `plan-v(N+1).md`.”

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-4__cache-io

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v3.md

## Hard Rules
- Include `## Changes Since plan-v2` listing only the deltas that address this review.
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
