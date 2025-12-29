---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v4
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v4.md
---

# Plan Review Report: Cache I/O Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope items are explicit. |
| 2 | Dependencies | PASS | SSOT schema + clips semantics are now specified and anchored. |
| 3 | File List | PASS | Exact files listed. |
| 4 | Contract Impact | PASS | Declared NO. |
| 5 | Types Complete | PASS | Public signatures listed; Spec Anchors validation passes. |
| 6 | Tests Complete | FAIL | No tests assert invalidation on file path/size/mtime changes, despite anchoring to invalidation rules. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | `compute_cache_key` behavior is under-specified in the plan (how clip path/size/mtime are encoded), leaving decisions to Coding. |
| 9 | Determinism Defined | PASS | Determinism for key stability and ordering is specified; missing coverage is file-stat invalidation. |

## Additional Quality Checks

- Error Codes: OK — cache I/O uses `CacheLoadResult.reason`; no new errors introduced.
- Failure Modes: Issue — invalidation triggers for file stat changes are not constrained by tests.
- Derived Outputs: OK — none in-scope.
- Rollback Guidance: OK — STOP instruction includes workflow action.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. How `compute_cache_key` encodes clip identity inputs (path/size/mtime) into the hash (string normalization, formatting, and delimiter choices).
2. Whether `compute_cache_key` actually changes when any of (path, size, mtime) changes (not currently enforced by tests).

## Concrete Edits Required (plan-v5.md)

> [!IMPORTANT]
> This is plan-v4 review; keep changes surgical (no broad rewrites).

1. **Specify the `compute_cache_key` encoding algorithm**
   - Section: `src/frame_compare/analysis/cache_io.py` (or a dedicated “compute_cache_key algorithm” subsection)
   - Problem: SSOT lists components but the plan doesn’t define the deterministic encoding; Coding would have to choose.
   - Required Change: Add an explicit, deterministic algorithm block (pseudocode is fine) that:
     - sorts `video_paths` deterministically
     - uses `Path.stat()` and includes `st_size` and `st_mtime`
     - encodes values to bytes with an unambiguous delimiter/format
     - hashes with SHA-256 and returns 64-char lowercase hex

2. **Add invalidation-trigger tests for path/size/mtime**
   - Section: `tests/analysis/test_cache_io.py`
   - Problem: No tests currently enforce the invalidation rules for file identity changes.
   - Required Change: Add these tests (exact names):
     - `test_compute_cache_key_changes_on_path_change`
     - `test_compute_cache_key_changes_on_size_change`
     - `test_compute_cache_key_changes_on_mtime_change`
   - Each test must create real temp files and assert that changing only the named attribute changes the key (using fixed mtimes for determinism, and changing size via writing different bytes).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-4__cache-io

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v4.md
Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v4.md
Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
