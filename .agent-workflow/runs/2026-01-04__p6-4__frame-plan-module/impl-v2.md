---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v2
TARGET: Phase 6 → Item 6.4
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v2.md
  - src/frame_compare/errors.py
  - tests/test_errors.py
  - docs/DECISIONS.md
---

# Implementation Report: FramePlan Module (Revision 1)

## Summary

**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
**Review Report:** .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v1.md (CHANGES REQUIRED)

## Files Changed

### Modified

- `src/frame_compare/errors.py` — Updated `InsufficientFramesError` message and hint to match SSOT exactly.
- `tests/test_errors.py` — Added `test_insufficient_frames_error_details_shape` to verify FC-3004 compliance.
- `docs/DECISIONS.md` — Updated Phase 6.4 entry with full artifact history.

## Fixes Implemented

### Critical

1. **FC-3004 message/hint drift:**
   - Updated `InsufficientFramesError` to use `f"Video has {count} frames, need at least {required}"` and `"Use a longer video or reduce frame_count"`.
   - Verified against `errors-module.md` §3.3.

2. **Missing usage test:**
   - Added `test_insufficient_frames_error_details_shape` to `tests/test_errors.py`.
   - Verifies `FC-3004` code and `path/count/required` details keys.

### Minor

1. **DECISIONS entry:** Updated to include `verify-v1`, `review-v1`, and `impl-v2`.
2. **Dependency Note:** Documenting that `hypothesis` was added to `pyproject.toml` (and `uv.lock`) in `impl-v1` to support property-based tests required by the plan, though not explicitly listed in the plan file list.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — exit 0
- `.venv/bin/ruff check .` — exit 0
- `.venv/bin/pytest -q` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 6.4 FramePlan Module

## Ready for Verification

All issues from review-v1.md addressed. Ready for Verification Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-4__frame-plan-module

## Context

This is a revision (impl-v2) addressing issues from review-v1.md.

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v2.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v1.md (contains the fix list)
3. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md

## Your Task

1. Verify the specific fixes were applied
2. Run the full verification suite
3. Confirm all review issues addressed

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/verify-v2.md
