---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v2
TARGET: Phase 6 → Item 6.4
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/verify-v2.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v2.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v2.md
  - .agent-workflow/index.md (updated)
---

# Review Report: FramePlan Module (Re-Review)

## Verdict: APPROVED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-04
**Files Reviewed:** 11
**Commit Subject:** `feat(analysis): implement Phase 6 Item 6.4 — deterministic FramePlan selection`

## Process Gates
- [x] Plan Review gate previously approved (`plan-review-v3.md`: Verdict APPROVED; Decision Points Remaining NONE)
- [x] Verification re-run complete (`verify-v2.md`)
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md

$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov
36 passed, coverage: 100%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
No violations

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
✓ All derived views are fresh

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✓ All requirements traced
```

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria for FramePlan selection + FC-3004 drift fix
- [x] Algorithms match SSOT anchors in `frame-plan-module.md` §§4.1–4.3 and error handling in §5

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] FC-3004 payload keys `path/count/required` and constructor signature match SSOT
- [x] FC-3004 message/hint now match SSOT `errors-module.md` §3.3 exactly

### Testing

- [x] Unit tests + cross-session determinism test present
- [x] Property-based invariant test present
- [x] Added targeted `test_insufficient_frames_error_details_shape`
- [x] Coverage: 100%

### Documentation

- [x] Decision log updated for Phase 6.4 (see Minor note)

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

None.

### Minor (Should Fix)

1. **Duplicate Phase 6.4 decision entry**
   - Location: `docs/DECISIONS.md`
   - Issue: Phase 6.4 entry appears twice; the later entry reflects the review/impl revision history but does not list
     `verify-v2`/`review-v2`.
   - Fix: In a follow-up docs-only cleanup, collapse into a single entry with the final artifact list.

### Suggestions (Nice to Have)

None.

## Next Steps

### If APPROVED

- ✅ Phase 6 Item 6.4 complete
- ➡️ Proceed to: next unchecked checklist item in `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`

## NEXT AGENT PROMPT (COPY/PASTE)

### ✅ Run Complete: 2026-01-04__p6-4__frame-plan-module

**Orchestrator Actions:**
1. Commit the changes:
    ```bash
   git add -A
   git commit -m "feat(analysis): add deterministic frame plan selection" \
     -m "Run: 2026-01-04__p6-4__frame-plan-module" \
     -m "Closes Phase 6 Item 6.4"
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
