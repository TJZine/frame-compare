---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v1
TARGET: Phase 6 → Item 6.5
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v1.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/verify-v1.md
---

# Verification Handoff: Tonemap Wiring

## Summary

**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
**Implementation Report:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v1.md

## Verification Results

### Quality Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest --cov
476 passed, 2 skipped, coverage: 87.98%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py differs from generated

Run 'UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py' to regenerate

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Issues Found

- **Contract Freshness Check Failed:** The implementation caused stale contract views (`cli-flags-canonical.md`, `error-codes.md`, `_generated.py`). These must be regenerated.

## Next Steps

Return to Coding Agent to run contract regeneration.

## NEXT AGENT PROMPT (COPY/PASTE)

### If Contract Gate Failed (and contracts were touched)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-5__tonemap-wiring

## Issue to Fix

Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/verify-v1.md
The contract freshness gate failed.

## Required Commands

Run:

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
Then verify:
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v2.md
Include the command outputs and list any generated files changed.
