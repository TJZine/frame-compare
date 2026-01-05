---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v2
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md
  - src/frame_compare/vs/tonemap.py
  - tests/vs/test_tonemap.py
---

# Implementation Report: HDR Tonemapping (Revision 1)

## Summary
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
**Review Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md (CHANGES REQUIRED)

## Files Changed (Exact Paths)

### Modified
- `src/frame_compare/vs/tonemap.py` — Added HDR metadata detection when missing (using `_detect_hdr`)
- `tests/vs/test_tonemap.py` — Added tests for metadata detection behavior

## Implementation Notes

- Addressed Critical Issue: "SSOT drift: HDR metadata extraction missing". Imported `_detect_hdr` from `frame_compare.vs.source` and integrated it into both `_apply_libplacebo` and `_fallback_tonemap`.
- Addressed Minor Issue: "Missing test coverage for HDR metadata extraction". Added `test_apply_tonemap_detects_metadata_when_missing_libplacebo` and `test_apply_tonemap_detects_metadata_when_missing_fallback` to verify correct behavior.
- Suppressed Pyright `reportPrivateUsage` error for the `_detect_hdr` import, as cross-module internal usage within the `vs` package is intended/acceptable here.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/vs/tonemap.py` — exit 0
- `.venv/bin/ruff check src/frame_compare/vs/tonemap.py tests/vs/test_tonemap.py` — exit 0
- `.venv/bin/pytest -v tests/vs/test_tonemap.py` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 3.5 Tonemapping (Fixes applied)

## Open Questions

- None

## Ready for Verification

Fixes implemented and verified locally. Ready for re-verification.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Context
This is a revision (impl-v2) addressing issues from review-v1.md.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md (contains the fix list)
3. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md

## Your Task
1. Verify the specific fixes were applied
2. Run the full verification suite
3. Confirm all review issues addressed

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v2.md
