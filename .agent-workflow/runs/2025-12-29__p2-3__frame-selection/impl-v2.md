---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v2
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v1.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/verify-v1.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v2.md
---

# Implementation Report: Frame Selection Algorithms (Revision v2)

## Summary
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
**Revision Context:** Addressing Contract Freshness gate failure in `verify-v1.md`.

## Files Changed (Exact Paths)

### Modified (Contract Views)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

### Unchanged from v1
- All files in `src/frame_compare/analysis/`
- All files in `tests/analysis/`

## Implementation Notes
- Regenerated all derived contract views using `scripts/generate_contract_views.py` to fix the stale artifacts issue detected during verification.
- Confirmed that all existing tests and import contracts remain valid after regeneration.

## Local Sanity Checks

### Contract Freshness
```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date
```

### Verification Suite
- `.venv/bin/pytest -v tests/analysis/test_selection.py` — exit 0 (10 passed)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0

## Checklist Item Implemented
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Regenerate derived contract views

## Ready for Verification

Contract views updated. Ready for Verification Agent re-run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-3__frame-selection

## Context
This is a revision (impl-v2) addressing issues from verify-v1.md (Contract Freshness gate failure).

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v2.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/verify-v1.md (contains the failure report)
3. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md

## Your Task
1. Verify the specific fixes (contract regeneration) were applied
2. Run the full verification suite (including the contract freshness gate)
3. Confirm all previous issues addressed

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/verify-v2.md
