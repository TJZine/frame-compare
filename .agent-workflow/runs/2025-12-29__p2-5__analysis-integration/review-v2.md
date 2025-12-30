---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v2
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/verify-v2.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v2.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v2.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Analysis Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-30
**Files Reviewed:** 6
**Commit Subject:** `feat(analysis): complete module integration for calculate_metrics export`

> [!NOTE]
> The commit subject must summarize the **entire checklist item** (the full run), not just the review phase.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
OK: Spec Anchors valid

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest --cov
202 passed, coverage: 94.34%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
No violations

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
✓ All derived views are fresh

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✓ All requirements traced
```

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria
- [x] Algorithms match spec anchors ("1.2 Module Structure", "3.1 calculate_metrics", "Import-Time VapourSynth Dependency (SSOT)")

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Follows patterns
- [x] Errors have codes and hints

### Testing

- [x] Tests cover main paths
- [x] Coverage: 94.34%

### Documentation

- [x] Docstrings present

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **Implementation artifact inputs are invalid (workflow requirement)**
   - Location: `.agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v2.md:1`
   - Issue: `impl-v2.md` does not list the required plan/plan-review artifacts it implements (should reference `plan-v5.md` and `plan-review-v5.md`). This violates the workflow requirement that cross-artifact references name exact inputs.
   - Fix: Issue a new implementation artifact (`impl-v3.md`) with correct `INPUTS` referencing `plan-v5.md` and `plan-review-v5.md`, and include the full, accurate file list for the run. Re-run verification and produce `verify-v3.md`.

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN `from frame_compare.analysis import calculate_metrics` WHEN Python runs (without VS) THEN import succeeds — ✓ Verified (pytest gate)
- [x] GIVEN `.venv/bin/pyright --warnings src/frame_compare/analysis/` WHEN run THEN exits 0 — ✓ Verified
- [x] GIVEN `.venv/bin/ruff check src/frame_compare/analysis/` WHEN run THEN exits 0 — ✓ Verified
- [x] GIVEN `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` WHEN run THEN exits 0 — ✓ Verified
- [x] GIVEN `.venv/bin/pytest -v tests/analysis/test_metrics.py::test_no_toplevel_vapoursynth_import` WHEN run THEN passes — ✓ Verified (pytest gate)

## Files Reviewed

- `src/frame_compare/analysis/__init__.py`
- `src/frame_compare/analysis/metrics.py`
- `tests/analysis/test_metrics.py`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
- `docs/DECISIONS.md`
- `CHANGELOG.md`

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Regenerate the implementation artifact with correct `INPUTS` referencing `plan-v5.md` and `plan-review-v5.md`, and list the full set of files modified by the run.
  2. Re-run verification and produce `verify-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-5__analysis-integration

## Issues to Fix
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v2.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v5.md
3. Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v2.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v3.md
