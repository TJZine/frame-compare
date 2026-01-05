---
RUN_ID: 2025-12-29__p3-4__color-operations
VERSION: v2
TARGET: Phase 3 → Item 3.4 Color Operations (Revision 1)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/impl-v2.md
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/review-v1.md
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/verify-v2.md
---

# Verification Handoff: Color Operations (Revision 1)

## Summary

**Date:** 2025-12-29
**Run ID:** 2025-12-29__p3-4__color-operations
**Context:** Verifying impl-v2 which addresses SSOT drift from review-v1.

## Review Issues from review-v1.md

| Issue | Status | Evidence |
|-------|--------|----------|
| SSOT drift: HDR matrix backfill should prefer `MATRIX_BT2020_CL` → `MATRIX_BT2020_NCL` → `9` | ✓ FIXED | Line 52-54: `matrix = getattr(vs, "MATRIX_BT2020_CL", getattr(vs, "MATRIX_BT2020_NCL", 9))` |
| Tests for preference order determinism | ✓ FIXED | Tests at lines 43-67 cover CL present, NCL fallback, and no-constants fallback cases |

## Verification Results

### Quality Gates

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q
195 passed, coverage: 94%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 1 kept, 0 broken.
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md differs from generated

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Gate Status

| Gate | Status |
|------|--------|
| Pyright | ✓ PASS |
| Ruff | ✓ PASS |
| Pytest | ✓ PASS (195 tests, 94% coverage) |
| lint-imports | ✓ PASS |
| Contract Freshness | ✗ FAIL (cli-flags-canonical.md stale) |
| Traceability | ✓ PASS |

## Contract Gate Failed

**Failed Gate:** `generate_contract_views.py --check`

**Error Output:**

```text
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md differs from generated
```

**Action Required:**
The Coding Agent must regenerate derived views before handoff:

1. Run: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
2. Verify: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-4__color-operations

## Issue to Fix

Read file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/verify-v2.md
The contract freshness gate failed.

## Required Commands

Run:

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
Then verify:
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/impl-v3.md
Include the command outputs and list any generated files changed.
