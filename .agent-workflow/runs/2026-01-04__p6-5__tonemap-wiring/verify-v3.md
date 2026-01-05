---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v3
TARGET: Phase 6 → Item 6.5 (Tonemap Wiring)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v3.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/verify-v3.md
  - .agent-workflow/index.md (updated)
---

# Verification Handoff: Tonemap Wiring Integration (v3)

## Summary

**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
**Plan Review Report:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
**Implementation Report:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v3.md
**Previous Review:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v1.md

## Critical Issues Addressed

### Issue 1: Public API export not specified in plan/SSOT

- **Status:** ✅ Fixed
- **Evidence:** Verified `probe_is_hdr_ffprobe` is NOT in `src/frame_compare/render/__init__.py:__all__`. Only `should_tonemap` and `resolve_tonemap_settings` are exported per plan-v3 §3.

### Issue 2: DECISIONS.md entry incomplete

- **Status:** ✅ Fixed
- **Evidence:** Entry at `docs/DECISIONS.md:514` now includes:
  - Full artifact versions (plan-v3, plan-review-v3, impl-v1 through impl-v3, verify-v2, review-v1)
  - SSOT edits (render-module.md §1.4.1, §1.4.4, §3.1, §7.2)
  - Contract alignment decision (FC-2001, no FC-4004)
  - Probe determinism decision
  - Out-of-scope items
  - Complete verification gate list

## Verification Results

### Quality Gates

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q
476 passed, 2 skipped, coverage: 87.98%
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Index Updates

- [x] Updated: .agent-workflow/index.md (impl-v3, verify-v3 links)

## Issues Found

None.

## Ready for Review

All Critical issues from review-v1 addressed. All verification gates passed. Handoff to Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-5__tonemap-wiring

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/verify-v3.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v3.md
3. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v1.md
4. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md

## Preconditions

- Previous Review (review-v1) Verdict: CHANGES REQUIRED
- All Critical issues from review-v1 have been addressed per verify-v3.md
- All verification gates passed

## Your Task

Confirm Critical issues are resolved. Issue final verdict.

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v2.md
