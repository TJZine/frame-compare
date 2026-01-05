---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v3
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v3.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v3.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v2.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v3.md
  - .agent-workflow/index.md (updated)
---

# Review Report: HDR Tonemapping

## Verdict: APPROVED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-30
**Files Reviewed:** 4
**Commit Subject:** `feat(vs): implement HDR tonemapping presets`

> [!NOTE]
> The commit subject must summarize the **entire checklist item** (the full run), not just the review phase.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ .venv/bin/pyright --warnings src/frame_compare/vs/tonemap.py
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check src/frame_compare/vs/tonemap.py tests/vs/test_tonemap.py
All checks passed!

$ .venv/bin/pytest -v tests/vs/test_tonemap.py
25 passed in 0.03s

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 1 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria
- [x] SSOT metadata extraction implemented and tested

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Follows patterns
- [x] Errors have codes and hints

### Testing

- [x] Tests cover main paths
- [x] Coverage updated via verify-v3 (25 tests)

### Documentation

- [x] Docstrings present

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

- [x] GIVEN `settings.enabled == False` WHEN `apply_tonemap()` THEN return clip unchanged — ✓ Verified
- [x] GIVEN "reference" preset WHEN `get_preset_settings()` THEN return correct settings — ✓ Verified
- [x] GIVEN libplacebo available WHEN `apply_tonemap()` THEN use libplacebo path — ✓ Verified
- [x] GIVEN libplacebo unavailable WHEN `apply_tonemap()` THEN use fallback silently — ✓ Verified
- [x] GIVEN unknown preset WHEN `get_preset_settings()` THEN raise `TonemapError(FC-4003)` — ✓ Verified
- [x] GIVEN unsupported tone_curve WHEN `apply_tonemap()` THEN raise `TonemapError(FC-4003)` — ✓ Verified
- [x] GIVEN clip already RGBS WHEN `_to_rgbs()` THEN return unchanged (no-op) — ✓ Verified
- [x] GIVEN `hdr_metadata is None` WHEN `apply_tonemap()` THEN derive metadata from frame props — ✓ Verified

## Files Reviewed

- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v2.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v3.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v3.md`

## Next Steps

### If APPROVED

- ✅ Phase 3 Item 3.5 complete
- ➡️ Proceed to: Next unchecked checklist item

## NEXT AGENT PROMPT (COPY/PASTE)

### ✅ Run Complete: 2025-12-29__p3-5__tonemapping

**Orchestrator Actions:**
1. Commit the changes:
   ```bash
   git add -A
   git commit -m "feat(vs): implement HDR tonemapping presets" \
     -m "Run: 2025-12-29__p3-5__tonemapping" \
     -m "Closes Phase 3 Item 3.5"
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
