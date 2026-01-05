---
RUN_ID: 2026-01-05__p6-7-4__probe-props-preservation
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Preserve HDR/DoVi Props + tonemap_prop_keys)
INPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/verify-v1.md
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Probe Prop Preservation Helpers

## Verdict: APPROVED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-05
**Files Reviewed:** 7
**Commit Subject:** `feat(orchestration): implement Phase 6.7 probe props preservation`

### Files Reviewed
- src/frame_compare/orchestration/probe_props.py
- tests/orchestration/test_probe_props.py
- src/frame_compare/orchestration/__init__.py
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
- .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md
- .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
- .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md

$ .venv/bin/pyright --warnings src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py
0 errors, 0 warnings

$ .venv/bin/ruff check src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py
All checks passed

$ .venv/bin/pytest -q tests/orchestration/test_probe_props.py
9 passed

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria
- [x] Algorithms match SSOT anchors (orchestration-module.md §3.5.2–§3.5.3)

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Pure functions; no error handling required

### Testing

- [x] Tests cover selection rules, ordering, TOML-safe filtering, DolbyVisionRPU sentinel
- [x] Tests are deterministic and in-memory

### Documentation

- [x] Public exports updated in orchestration __init__

### SSOT Drift (Hard Gate)

- [x] No drift detected vs orchestration-module.md

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

None.

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] Normalization strips underscores and lowercases
- [x] Tonemap prop keys selection and deterministic ordering
- [x] Preserved props limited to tonemap-related keys only
- [x] Sorted original-key order in preserved props
- [x] Non-TOML-safe values dropped (except DolbyVisionRPU sentinel)
- [x] DolbyVisionRPU preserved with value 1 and original key

## Next Steps

### If APPROVED

- ✅ Phase 6 Item 6.7 (probe props preservation) complete
- ➡️ Proceed to next checklist item

## NEXT AGENT PROMPT (COPY/PASTE)

### ✅ Run Complete: 2026-01-05__p6-7-4__probe-props-preservation

**Orchestrator Actions:**
1. Commit the changes:
    ```bash
   git add -A
   git commit -m "feat(orchestration): implement Phase 6.7 probe props preservation" \
     -m "Run: 2026-01-05__p6-7-4__probe-props-preservation" \
     -m "Closes Phase 6 Item 6.7"
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

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Pick the next unchecked checklist item and create a detailed Implementation Plan.

## Output

Write file: .agent-workflow/runs/NEW_RUN_ID/plan-v1.md
