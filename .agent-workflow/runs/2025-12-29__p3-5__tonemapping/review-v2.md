---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v2
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v2.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v2.md
  - .agent-workflow/index.md (updated)
---

# Review Report: HDR Tonemapping

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-30
**Files Reviewed:** 6
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
25 passed in 0.04s

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
- [x] Coverage updated via verify-v2 (25 tests)

### Documentation

- [x] Docstrings present

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **Implementation artifact missing required plan review input**
   - Location: `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md:6`
   - Issue: `impl-v2.md` does not list the required plan review artifact (`plan-review-v5.md`) in INPUTS. Workflow requires `impl-vN.md` to reference exact plan and plan-review versions implemented.
   - Fix: Emit `impl-v3.md` with INPUTS including `plan-v5.md` and `plan-review-v5.md` (plus review-v1.md). Re-run verification and produce `verify-v3.md`.

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

- `src/frame_compare/vs/tonemap.py`
- `tests/vs/test_tonemap.py`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v2.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md`

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Regenerate the implementation artifact with correct INPUTS including `plan-review-v5.md`.
  2. Re-run verification and produce `verify-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Issues to Fix
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v2.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md
3. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v2.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v3.md
