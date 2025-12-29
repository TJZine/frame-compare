---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v1
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v1.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/verify-v1.md
---

# Verification Failed: Frame Selection (Phase 2.3)

## Summary

**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
**Implementation Report:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v1.md

## Implementation Review

- [x] All listed files created
- [x] Spec anchors valid

## Verification Results

### Quality Gates

- `validate_spec_anchors.py`: **PASS**
- `pyright`: **PASS**
- `ruff`: **PASS**
- `pytest`: **PASS**
- `lint-imports`: **PASS**

### Contract Gates

- `generate_contract_views.py --check`: **FAIL**

  ```text
  STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md differs from generated
  STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md differs from generated
  STALE: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py differs from generated
  ```

  > **Root Cause:** Stale contract views detected. This may be due to environmental drift or prior runs. Even though the plan claimed "Contracts touched: NO", the new code (raising `SelectionError` with specific codes) may have triggered updates in error documentation, or prior drift wasn't fully cleaned.
- `validate_traceability.py --check`: **PASS**

## Issues Found

1. **Stale Contracts**: CLI-related contracts and error documentation are stale and must be regenerated.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-3__frame-selection

## Issue to Fix

Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/verify-v1.md

The Contract Freshness gate failed due to stale artifacts.

## Files to Read

1. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md

## Your Task

Fix the verification failure.

1. **Regenerate Contract Views**:
   - Run: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
   - Verify: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`

2. **Re-run Verification**:
   - Ensure `pytest` and `lint-imports` still pass.

3. **Update Implementation Report**:
   - Create `impl-v2.md`
   - List the contract files as "Modified" or "Generated" in the new report.
   - Attach the output of `generate_contract_views.py --check` as evidence.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v2.md
