---
RUN_ID: 2025-12-27__p0-5__container-setup
VERSION: v1
TARGET: Phase 0 → Item 0.5 (Container Setup)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/verify-v1.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v2.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Container Setup

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-28
**Files Reviewed:** 15

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [ ] Verification handoff complete (lint-imports output missing)
- [ ] All verification gate outputs included (lint-imports missing)
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest -v
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0
collected 2 items

tests/e2e/test_cli_version.py ..                                         [100%]

============================== 2 passed in 0.02s ===============================

$ .venv/bin/pytest --cov --cov-report=term-missing
..                                                                       [100%]
TOTAL 85.71% (required 80%)

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
error: Failed to spawn: `lint-imports`
  Caused by: No such file or directory (os error 2)
```

## Checklist Results

### Correctness
- [ ] Issue: Implementation includes out-of-scope changes not listed in the plan

### Type Safety
- [x] Type hints complete
- [x] Pyright passes

### Error Handling
- [x] No changes in error hierarchy

### Testing
- [x] Tests cover main paths
- [x] Coverage: 85.71%

### Documentation
- [ ] Issue: Implementation report file list incomplete relative to actual changes

### Security
- [x] No issues found

### Performance
- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **Plan scope/contract mismatch and undocumented file changes**
   - Location: `.agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md:57` and `.agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md:64` vs `.agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v2.md:27`
   - Issue: The plan explicitly excludes docs outside the baseline and declares `Contracts touched: NO`, but implementation changed additional OPUS docs and a canonical contract, and an unplanned file was added:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/feature-parity.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/system-design.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/01-planning-agent.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/doctor_report_schema.json`
     - `.pre-commit-config.yaml`
   - Fix: Either revert these out-of-scope changes and update `docs/DECISIONS.md`/`CHANGELOG.md` accordingly, or return to Planning for a plan revision that explicitly includes these files and contract impact, then re-run Plan Review. Update the implementation report file list to match whatever set of files remains.

2. **Missing lint-imports gate in verification handoff**
   - Location: `.agent-workflow/runs/2025-12-27__p0-5__container-setup/verify-v1.md:50`
   - Issue: Verification handoff omits `lint-imports` output, which is a required gate. Local attempt failed because `lint-imports` is not available.
   - Fix: Ensure `lint-imports` is runnable (install `import-linter` per repo policy or add it to dev dependencies), rerun the command, and update the verification artifact (`verify-v2.md`) to include the gate output.

### Minor (Should Fix)

1. **DevContainer verification still pending**
   - Location: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:84`
   - Issue: The DevContainer "Reopen in Container" check remains unchecked.
   - Fix: Perform the manual DevContainer open step and update the checklist if successful.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification
- [x] GIVEN `docker compose build` WHEN run in repo root THEN build completes with exit code 0 — ✓ Verified (via verify-v1)
- [x] GIVEN built image WHEN `docker run --rm frame-compare:dev --help` THEN shows CLI help — ✓ Verified
- [x] GIVEN built image WHEN VS version check runs THEN `vs.core.version_number() >= 73` — ✓ Verified
- [x] GIVEN built image WHEN lsmas check runs THEN plugin check passes — ✓ Verified
- [x] GIVEN built image WHEN placebo check runs THEN `Tonemap` callable — ✓ Verified
- [x] GIVEN built image WHEN lsmas check runs with invalid plugin path THEN assertion fails — ✓ Verified
- [ ] GIVEN VS Code with DevContainers WHEN "Reopen in Container" THEN container opens successfully — Not verified

## Next Steps

### If CHANGES REQUIRED
- Coding Agent: Fix the following:
  1. Remove or formally re-plan the out-of-scope doc/contract/pre-commit changes, then update the implementation report file list and related decision/changelog entries to match.
  2. Restore/enable the `lint-imports` gate and re-run verification to produce `verify-v2.md` with the missing output.
  3. Complete the DevContainer manual check and update the checklist if successful.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-5__container-setup

## Issues to Fix
Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md
2. Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md
3. Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v3.md
