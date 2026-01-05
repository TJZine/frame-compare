---
RUN_ID: 2026-01-04__p6-7-3__probe-cache-io
VERSION: v2
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache I/O)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/impl-v2.md
  - src/frame_compare/orchestration/probe_cache.py (MODIFIED)
  - tests/orchestration/test_probe_cache.py (MODIFIED)
  - tests/orchestration/test_probe_cache_io.py (DELETED)
---

# Implementation Report: Probe Cache I/O Fixes (v2)

## Summary

**Date:** 2026-01-05
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
**Plan Review Report:** .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md (APPROVED)
**Review Report:** .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/review-v1.md (CHANGES REQUIRED)

## Issues Addressed from review-v1.md

### Critical #1: HDR metadata persistence format deviates from SSOT

**Location:** `src/frame_compare/orchestration/probe_cache.py:89-110, 159-170`
**Fix Applied:**

- Refactored `save_clip_probe_cache` to persist HDR metadata as a nested `hdr_metadata` table per SSOT §3.5.1
- Refactored `load_clip_probe_cache` to read from nested `hdr_metadata` table instead of flat fields
- Added type cast for `hdr_table` to `dict[str, Any]` to fix pyright unknown type errors

### Critical #2: Cache writer does not create parent directory

**Location:** `src/frame_compare/orchestration/probe_cache.py:174`
**Fix Applied:**

- Added `cache_path.parent.mkdir(parents=True, exist_ok=True)` before writing TOML file
- Ensures fresh workspaces don't fail when writing cache

### Cosmetic #4: Ruff UP038 in isinstance check

**Location:** `src/frame_compare/orchestration/probe_cache.py:162`
**Fix Applied:**

- Changed `isinstance(..., (str, int, float))` to `isinstance(..., str | int | float)`

### Critical #3: Out-of-plan test file path

**Location:** `tests/orchestration/test_probe_cache_io.py`
**Fix Applied:**

- Merged all I/O tests from `test_probe_cache_io.py` into `test_probe_cache.py` per plan-v2
- Deleted `test_probe_cache_io.py`
- Added new test `test_hdr_metadata_persisted_as_nested_table` to assert SSOT-compliant structure
- Added new test `test_save_clip_probe_cache_creates_parent_directories` to verify mkdir behavior

## Files Changed (Exact Paths)

### Modified

- `src/frame_compare/orchestration/probe_cache.py` — Nested `hdr_metadata` table + mkdir before save + UP038 fix
- `tests/orchestration/test_probe_cache.py` — Merged I/O tests with new assertions

### Deleted

- `tests/orchestration/test_probe_cache_io.py` — Merged into `test_probe_cache.py`

## Implementation Notes

All changes are SSOT-compliant fixes per review-v1.md. No scope additions or deviations.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — exit 0 (0 errors, 0 warnings)
- `.venv/bin/ruff check .` — exit 0 (All checks passed)
- `.venv/bin/pytest -q` — exit 0 (501 passed, 2 skipped)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0 (2 kept, 0 broken)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0 (OK)

## Checklist Item Implemented

> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 6.7.3 — Probe Snapshot Cache I/O (fixes for review-v1)

## Open Questions

None.

## Ready for Verification

All 3 Critical issues from review-v1.md addressed. All quality gates pass. Ready for Verification Agent gate run.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-7-3__probe-cache-io

## Context

This is a revision (impl-v2) addressing issues from review-v1.md.

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/impl-v2.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/review-v1.md (contains the fix list)
3. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md

## Your Task

1. Verify the specific fixes were applied
2. Run the full verification suite
3. Confirm all review issues addressed

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/verify-v2.md
