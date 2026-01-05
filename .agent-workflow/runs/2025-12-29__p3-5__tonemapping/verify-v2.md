---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v2
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v2.md
  - .agent-workflow/index.md (updated)
---

# Verification Handoff: HDR Tonemapping (Revision 1)

## Summary

**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
**Review Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md (CHANGES REQUIRED)
**Implementation Report:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md

## Fix Verification

### Critical Issues (Must Fix)

#### 1. SSOT drift: HDR metadata extraction missing

- **Issue:** Implementation fell back to default 1000 nits instead of extracting metadata from frame 0 when `hdr_metadata` was None.
- **Fix:** Imported `_detect_hdr` from `frame_compare.vs.source` and integrated it into both tonemapping paths.
- **Verification:**
  - Code inspection confirms `_detect_hdr` usage in `_apply_libplacebo` and `_fallback_tonemap`.
  - New tests `test_apply_tonemap_detects_metadata_when_missing_libplacebo` and `test_apply_tonemap_detects_metadata_when_missing_fallback` pass.
- **Result:** ✓ FIXED

### Minor Issues (Should Fix)

#### 1. Missing test coverage for HDR metadata extraction

- **Issue:** No tests verified the auto-extraction behavior.
- **Fix:** Added unit tests verifying `_detect_hdr` is called and its result used.
- **Verification:** `pytest -v tests/vs/test_tonemap.py` confirms 25 tests passed (up from 23).
- **Result:** ✓ FIXED

## Verification Results

### Quality Gates

```text
$ .venv/bin/pyright --warnings src/frame_compare/vs/tonemap.py
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check src/frame_compare/vs/tonemap.py tests/vs/test_tonemap.py
All checks passed!

$ .venv/bin/pytest -v tests/vs/test_tonemap.py
25 passed in 0.04s

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 1 kept, 0 broken.
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Index Updates

- [x] Updated to reference `impl-v2` and `verify-v2` with `PENDING_REVIEW`.

## Ready for Review

All review issues addressed and verified. Handoff to Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-5__tonemapping

## Files to Read

1. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v2.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md
3. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md
4. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md

## Preconditions

- Previous verdict was CHANGES REQUIRED
- Verification confirms fixes applied

## Your Task

Perform final quality review on the revision and issue verdict.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v2.md
