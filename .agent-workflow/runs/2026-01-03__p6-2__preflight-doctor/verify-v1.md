---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v1
TARGET: Phase 6 → Item 6.2
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v1.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/verify-v1.md
---

# Verification Handoff: Preflight & Doctor

## Summary

**Date:** 2026-01-03
**Plan Reference:** .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md
**Plan Review Report:** .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v4.md
**Implementation Report:** .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v1.md

## Implementation Review

### Plan Review Gate

- [x] Plan Review Report exists
- [x] Verdict: APPROVED

### Plan Compliance

- [x] All files in plan were created
- [x] Implementation matches plan (types, functions, signatures)
- [x] 8 doctor checks in deterministic order
- [x] Unit tests implemented (12 preflight + 15 doctor = 27 total)

## Verification Results

### Quality Gates ✅

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md

$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q
443 passed, 2 skipped
Required test coverage of 80.0% reached. Total coverage: 89.88%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

### Contract Gates ❌

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py differs from generated

Run 'UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py' to regenerate
```

## Contract Gate Failed

**Root Cause:** The `NoVideosFoundError` signature was modified to accept `(path: Path, patterns: list[str] | None = None)`. This change triggers regeneration of error-codes.md and related derived views.

**Note:** The impl-v1.md claims contract views were NOT touched ("Contract Impact: NO"), but the error signature change does affect the error-codes derived view.

---

## NEXT AGENT PROMPT (COPY/PASTE)

### Contract Gate Failed (contracts were touched)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-01-03__p6-2__preflight-doctor

## Issue to Fix

Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/verify-v1.md
The contract freshness gate failed due to NoVideosFoundError signature change.

## Required Commands

Run:

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
Then verify:
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`

## Output

Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v2.md
Include the command outputs and list any generated files changed.
