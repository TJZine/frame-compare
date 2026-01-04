---
RUN_ID: 2026-01-04__p6-6-1__vspreview-integration
VERSION: v1
TARGET: Phase 6 → Item 6.6 (VSPreview Integration)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/impl-v1.md
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/verify-v1.md
---

# Verification Report: VSPreview Integration

## Summary

**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v3.md
**Implementation Reference:** .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/impl-v1.md
**Verdict:** ❌ **FAILURE** (Contract Freshness)

## Implementation Review

### Plan Compliance

- [x] All files in plan were created/modified
- [x] Public API matches spec anchors
- [x] Layering in `importlinter.ini` matches plan

## Verification Results

### Quality Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v3.md
OK: Spec Anchors valid

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest -q
476 passed, 2 skipped

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
✖ FAILURE
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py differs from generated
```

> [!IMPORTANT]
> The addition of new error codes (`VSPreviewNotFoundError`, `VSPreviewError`) caused the generated contract views to go stale. This must be fixed to maintain SSOT consistency.

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Updates

- [ ] Marked complete: Phase 6 → Item 6.6 (VSPreview Integration) **(BLOCKED by verification failure)**

## Index Updates

- [ ] Appended to: .agent-workflow/index.md **(BLOCKED by verification failure)**

## Issues Found

### 1. Stale Contracts (Critical)

- **Issue**: `error-codes.md` and related views are outdated due to new error types.
- **Fix**: Run `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py` to regenerate.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-6-1__vspreview-integration

## Issues to Fix

Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/verify-v1.md
See "Issues Found" section.

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/impl-v1.md

## Your Task

1. Regenerate stale contract views.
2. Run `generate_contract_views.py --check` to verify.
3. Update implementation report.

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/impl-v2.md
