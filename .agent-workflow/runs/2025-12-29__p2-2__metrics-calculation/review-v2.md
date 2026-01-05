---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v2
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/verify-v3.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v3.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v2.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Metrics Calculation (Revision 2)

## Verdict: APPROVED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-29
**Files Reviewed:** 4

- src/frame_compare/analysis/metrics.py
- tests/analysis/test_metrics.py
- .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md
- .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md

## Process Gates
- [x] Plan Review was approved
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
OK: Spec Anchors valid

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest --cov
201 passed, coverage: 94.33%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
No violations

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
✓ All derived views are fresh

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✓ All requirements traced
```

## Checklist Results

### Fix Verification

- [x] `calculate_metrics` propagates `PluginNotFoundError`/`SourceLoadError` per SSOT
- [x] Docstring updated with error contract
- [x] Propagation tests added for both errors

## Issues Found

None.

## Next Steps

### If APPROVED

- ✅ Phase 2 Item 2.2 complete
- ➡️ Proceed to next unchecked checklist item

## NEXT AGENT PROMPT (COPY/PASTE)

### ✅ Run Complete: 2025-12-29__p2-2__metrics-calculation

**Orchestrator Actions:**
1. Commit the changes:
   ```bash
   git add -A
   git commit -m "feat(analysis): implement metrics calculation" \
     -m "Run: 2025-12-29__p2-2__metrics-calculation" \
     -m "Closes Phase 2 Item 2.2"
   ```

2. Verify master checklist is updated
3. Pick the next unchecked item from the checklist

---

### To Start Next Run

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID

NEW_RUN_ID
(ORCHESTRATOR: replace `NEW_RUN_ID` with the next run’s confirmed RUN_ID before running the Planning Agent)

## Target
Pick the next unchecked checklist item (Planning Agent will read the checklist).

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task
Pick the next unchecked checklist item and create a detailed Implementation Plan.

## Output

Write file: .agent-workflow/runs/NEW_RUN_ID/plan-v1.md
