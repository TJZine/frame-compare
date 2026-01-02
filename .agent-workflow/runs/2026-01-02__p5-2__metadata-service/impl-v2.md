---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v2
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v2.md
  - src/frame_compare/services/metadata.py
  - tests/services/test_metadata.py
---

# Implementation Report: Metadata Service (Revision 2)

## Summary
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
**Plan Review Report:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v4.md (APPROVED)

## Files Changed (Exact Paths)

### Modified
- `src/frame_compare/services/metadata.py` — Added error guards to parser calls and source normalization.
- `tests/services/test_metadata.py` — Updated test expectations to match plan (revert local workaround).

## Review Issues Addressed

### Critical: parse_filename does not honor “never raises” contract
- **Fix:** Wrapped `anitopy.parse` and `guessit` calls in `try...except Exception` blocks to return empty dicts on failure, preventing exception propagation.

### Minor: Plan mismatch for source formatting
- **Fix:** Added normalization logic in `parse_filename` to convert `"Blu-ray"` (returned by `guessit`) to `"BluRay"` (expected by plan).
- **Fix:** Reverted `tests/services/test_metadata.py` assertion to expect `"BluRay"`, aligning the test with the approved plan.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — [exit 0]
- `.venv/bin/ruff check .` — [exit 0]
- `.venv/bin/pytest -q --ignore tests/vs/` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented

- [x] Phase 5.2: Metadata Service (Filename parsing + TMDB)

## Open Questions

- NONE

## Ready for Verification

All review issues addressed. Ready for Verification Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Context
This is a revision (impl-v2) addressing issues from review-v1.md.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v2.md
2. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/review-v1.md (contains the fix list)
3. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md

## Your Task
1. Verify the specific fixes were applied
2. Run the full verification suite
3. Confirm all review issues addressed

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/verify-v2.md
