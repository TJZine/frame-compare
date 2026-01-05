---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v2
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v2.md
  - src/frame_compare/services/publishers.py
  - tests/services/test_publishers.py
---

# Implementation Report: Publishers Service (slow.pics) (Revision 1)

## Summary
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
**Review Reference:** .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md (CHANGES REQUIRED)

## Revisions (Addressing review-v1.md)

1. **Reverted out-of-plan modifications:**
   - Reverted `tests/vs/test_exports.py` and `tests/vs/test_tonemap.py` to their original state. These will be addressed in a separate run if needed.

2. **Aligned retry semantics with SSOT:**
   - Updated `SlowpicsPublisher._upload_with_retry` to check `if attempt >= max_retries:` before raising errors.
   - This ensures `max_retries` corresponds to the *total* number of attempts allowed, as requested in the review.
   - Updated `tests/services/test_publishers.py` to expect `max_retries - 1` sleeps (e.g., if max_retries=2, we sleep once after attempt 1 fails, then fail on attempt 2).

3. **Fixed Public API Signature:**
   - Removed `progress` parameter from `SlowpicsPublisher.upload` signature.
   - Progress reporting is now handled entirely within the convenience function `publish_to_slowpics`.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — exit 0
- `.venv/bin/ruff check .` — exit 0
- `.venv/bin/pytest tests/services/test_publishers.py` — exit 0 (14 passed)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 5.3: Publishers Service (slow.pics)

## Open Questions

- None.

## Ready for Verification

All review issues addressed. Ready for re-verification.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-3__publishers

## Context
This is a revision (impl-v2) addressing issues from review-v1.md.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v2.md
2. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md (contains the fix list)
3. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md

## Your Task
1. Verify the specific fixes were applied
2. Run the full verification suite
3. Confirm all review issues addressed

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/verify-v2.md
