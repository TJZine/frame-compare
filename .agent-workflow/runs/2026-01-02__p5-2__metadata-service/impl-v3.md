---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v3
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v6.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v6.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v3.md
  - src/frame_compare/services/metadata.py
  - tests/services/test_metadata.py
---

# Implementation Report: Metadata Service (Design Fix)

## Summary
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v6.md
**Plan Review Report:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v6.md (APPROVED)

## Files Changed (Exact Paths)

### Modified
- `src/frame_compare/services/metadata.py` — Removed source normalization (returns parser output verbatim).
- `tests/services/test_metadata.py` — Updated assertions to expect `"Blu-ray"`, added exception fallback test.

## Implementation Notes

- **Source Normalization:** Removed code that converted `"Blu-ray"` to `"BluRay"`. The service now faithfully returns whatever the underlying parser produces (`guessit` returns `"Blu-ray"`).
- **Exception Handling:** Confirmed `try...except` guards are in place. Added `test_parse_filename_parsers_raise_falls_back_to_stem` to verify that if both parsers fail, the system falls back to a normalized filename stem without crashing.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — [exit 0]
- `.venv/bin/ruff check .` — [exit 0]
- `.venv/bin/pytest -q --ignore tests/vs/` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented

- [x] Phase 5.2: Metadata Service (Design Fixes)

## Open Questions

- NONE

## Ready for Verification

All plan requirements implemented and verified. Ready for Verification Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Context
This is a revision (impl-v3) addressing design fixes from plan-v6.md.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v3.md
2. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v6.md
3. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v6.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/verify-v3.md
