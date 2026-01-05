---
RUN_ID: 2026-01-03__p6-3__progress-reporting
VERSION: v1
TARGET: Phase 6 → Item 6.3
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/verify-v1.md
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/impl-v1.md
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v2.md
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Progress Reporting — Reporter Selection Logic

## Verdict: DESIGN ISSUE

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-04
**Files Reviewed:** 13
**Commit Subject:** `feat(orchestration): implement Phase 6 Item 6.3 — progress reporter selection`

> [!NOTE]
> The `select_reporter()` implementation and unit tests look correct, but this run cannot be approved due to workflow
> gate failures and scope drift in the working tree relative to `plan-v2.md` / `impl-v1.md`.

## Process Gates
- [x] Plan was approved by Plan Review Agent (`plan-review-v2.md`: Verdict APPROVED; Decision Points Remaining NONE)
- [x] Verification handoff complete (`verify-v1.md` present, canonical gates included)
- [ ] All verification gate outputs included and consistent with repo state (see Issues Found)
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q
479 passed, 2 skipped
coverage: 90.00%
Required test coverage of 80.0% reached.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria for `select_reporter()`
- [x] Algorithm matches SSOT intent (quiet > json > force_tty > TTY auto-detect)

### Type Safety

- [x] Type hints complete for `select_reporter()`
- [x] Return type uses canonical `ProgressReporter` protocol

### Error Handling

- [x] N/A (pure selection logic; no errors introduced)

### Testing

- [x] Unit tests cover precedence and TTY branches (9 tests)
- [x] Deterministic (monkeypatch for `sys.stdout.isatty`)

### Documentation

- [x] `select_reporter()` has a docstring describing priority/invariants

### Security

- [x] No external I/O; no secrets; no subprocess/network

### Performance

- [x] O(1) selection; no concerns

## Files Reviewed

- `.agent-workflow/runs/2026-01-03__p6-3__progress-reporting/verify-v1.md`
- `.agent-workflow/runs/2026-01-03__p6-3__progress-reporting/impl-v1.md`
- `.agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v2.md`
- `.agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-review-v2.md`
- `src/frame_compare/orchestration/progress.py`
- `src/frame_compare/orchestration/__init__.py`
- `tests/orchestration/test_progress.py`
- `docs/DECISIONS.md` (Phase 6.3 entry)
- `CHANGELOG.md` (Phase 6.3 entry)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` (spec anchor context)
- `.agent-workflow/index.md` (row wiring)
- `scripts/validate_traceability.py` (unplanned diff present)
- `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md` (unplanned diff present)

## Issues Found

### Critical (Must Fix)

1. **Run artifacts fail validator due to placeholder in NEXT block**
   - Location: `.agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-review-v2.md`
   - Evidence:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2026-01-03__p6-3__progress-reporting`
     - Error: `NEXT block contains non-concrete version token in 'review-vN.md' (expected digits only, like -v1.md)`
   - Fix: Re-issue the plan/plan-review artifacts with fully concrete NEXT paths (no `vN` tokens).

2. **Scope drift / repo state inconsistent with `plan-v2.md` and `impl-v1.md`**
   - Issue: The working tree contains modified and untracked files not listed in `plan-v2.md` “Files to Create/Modify”
     nor documented in `impl-v1.md` “Files Changed (Exact Paths)” (e.g., `scripts/validate_traceability.py` refactor and
     multiple `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/**` additions).
   - Risk: The run cannot be reliably reviewed or merged as Phase 6.3-only work until the changes are isolated into
     separate, explicitly planned runs.
   - Fix: Decide which changes belong to Phase 6.3 vs a separate run, then re-plan (and re-verify) accordingly.

### Minor (Should Fix)

1. **DECISIONS entry missing full artifact versions**
   - Location: `docs/DECISIONS.md` (Phase 6.3 entry)
   - Issue: Entry lists `plan-v2 + plan-review-v2 + impl-v1` but not `verify-v1` and `review-v1` as required by
     `plan-v2.md`.
   - Fix: Update the entry once the run is ready for approval.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN `quiet=True` WHEN calling `select_reporter()` THEN returns `NullProgressReporter` instance — ✓ Verified (tests)
- [x] GIVEN `json_output=True` WHEN calling `select_reporter()` THEN returns `LogProgressReporter` instance — ✓ Verified (tests)
- [x] GIVEN `force_tty=True` WHEN calling `select_reporter()` THEN returns `RichProgressReporter` instance — ✓ Verified (tests)
- [x] GIVEN `force_tty=False` WHEN calling `select_reporter()` THEN returns `LogProgressReporter` instance — ✓ Verified (tests)
- [x] GIVEN interactive TTY and no explicit flags WHEN calling `select_reporter()` THEN returns `RichProgressReporter` — ✓ Verified (tests)
- [x] GIVEN non-interactive environment and no explicit flags WHEN calling `select_reporter()` THEN returns `LogProgressReporter` — ✓ Verified (tests)
- [x] GIVEN multiple flags WHEN calling `select_reporter()` THEN applies precedence quiet > json > tty — ✓ Verified (tests)

## Next Steps

### If DESIGN ISSUE

- Planning Agent: Revise plan to resolve scope drift and re-run Plan Review.
- Problem:
  - The run directory fails `validate_run_artifacts.py` due to placeholders in NEXT blocks.
  - The working tree includes substantial changes outside the planned/implemented file set for Phase 6.3.
- Suggestion:
  - Split non-Phase-6.3 changes (traceability validator + scaffold tests + unrelated docs tweaks) into a separate run.
  - Keep this run focused on `select_reporter()` + its unit tests + `DECISIONS`/`CHANGELOG`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-3__progress-reporting

## Design Issue Identified
Read file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/review-v1.md
See "Issues Found > Critical" section for the design problem description.

## Previous Plan
Read file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v2.md

## Affected Contracts/Specs
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md
- scripts/validate_traceability.py

## Your Task
Revise the implementation plan to resolve scope drift:
1. Decide which diffs belong to Phase 6.3 vs a separate run.
2. Ensure the revised plan’s file list matches intended diffs exactly.
3. Ensure the NEXT AGENT PROMPT blocks in plan/plan-review artifacts contain fully concrete versions (no vN tokens).
If the traceability validator changes are intended, plan them explicitly; otherwise, exclude them from Phase 6.3 and
create a separate run.

## Output
Write file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v3.md
