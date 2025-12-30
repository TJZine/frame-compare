---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v1
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/verify-v2.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v2.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Analysis Module Integration

## Verdict: DESIGN ISSUE

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-29
**Files Reviewed:** 10
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
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md
OK: Spec Anchors valid

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest --cov
201 passed, coverage: 94.34%

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
- [x] Algorithms match spec anchors ("1.2 Module Structure", "3.1 calculate_metrics")

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

1. **Plan scope violation requires plan revision**
   - Location: `.agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md:146` and `src/frame_compare/analysis/metrics.py:1`
   - Issue: The approved plan explicitly forbids modifying other files in `analysis/`, but `metrics.py` was changed in impl-v2 to introduce lazy VapourSynth imports. This is a scope change relative to the plan and requires a revised plan + Plan Review before approval.
   - Fix: Revise the plan to include the lazy import change in `metrics.py`, re-run Plan Review, then re-run Verification against the revised plan.

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN `from frame_compare.analysis import calculate_metrics` WHEN Python interpreter runs THEN import succeeds — ✓ Verified (via pytest gate)
- [x] GIVEN `.venv/bin/pyright --warnings src/frame_compare/analysis/` WHEN run THEN exits 0 with 0 errors — ✓ Verified
- [x] GIVEN `.venv/bin/ruff check src/frame_compare/analysis/` WHEN run THEN exits 0 — ✓ Verified
- [x] GIVEN `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` WHEN run THEN exits 0 — ✓ Verified
- [x] GIVEN `.venv/bin/pytest -v tests/analysis/` WHEN run THEN all tests pass — ✓ Verified

## Files Reviewed

- `src/frame_compare/analysis/__init__.py`
- `src/frame_compare/analysis/metrics.py`
- `docs/DECISIONS.md`
- `CHANGELOG.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

## Next Steps

### If DESIGN ISSUE

- Planning Agent: Revise plan
- Problem: Plan scope explicitly disallowed `analysis/metrics.py` changes, but the fix required a lazy-import update to pass gates.
- Suggestion: Update `plan-v3.md` to include `metrics.py` in scope, document the lazy import adjustment, then re-run Plan Review and Verification.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-5__analysis-integration

## Design Issue Identified
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v1.md
See "Issues Found > Critical" section for the design problem description.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md

## Affected Contracts/Specs
None.

## Your Task
Revise the implementation plan to address the design issue.
If contracts need updating, include the contract changes in the plan.

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v3.md
