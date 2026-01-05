---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v3
TARGET: Phase 6 → Item 6.2
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/review-v1.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v3.md
---

# Implementation Report: Preflight & Doctor (Review Fixes)

## Summary

**Date:** 2026-01-03
**Review Reference:** `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/review-v1.md`
**Verdict Addressed:** CHANGES REQUIRED (4 Critical issues)

## Issues Fixed

### Critical Issue 1: `resolve_paths` signature conflicts with SSOT

**Location:** `src/frame_compare/orchestration/preflight.py:77`
**Issue:** SSOT §5.1 defines `resolve_paths(config, root)` but code had 3-arg form.

**Fix Applied:**

- Changed public `resolve_paths(config, root)` to 2-arg SSOT signature
- Added internal `_resolve_paths_with_config_file(config, root, config_file)` for `prepare_preflight`
- Config file is now derived as `config_dir / "config.toml"` in public signature

### Critical Issue 2: Required preflight ordering test does not assert ordering

**Location:** `tests/orchestration/test_preflight.py:184`
**Issue:** Test only asserted preflight succeeds, not actual ordering `[A.mkv, b.mkv]`.

**Fix Applied:**

- Made `discover_inputs` public (was `_discover_inputs`) since it has a stable contract
- Created `TestDiscoverInputs` class with dedicated `test_discover_inputs_sorted_case_insensitive`
- Test now asserts: `result[0].name == "A.mkv"` and `result[1].name == "b.mkv"`

### Critical Issue 3: Required lsmas failure test does not assert `critical_failures`

**Location:** `tests/orchestration/test_doctor.py:112`
**Issue:** Test only checked `_check_lsmas()` returns `passed=False`, not `DoctorReport.critical_failures`.

**Fix Applied:**

- Added `test_check_lsmas_failure_included_in_critical_failures` test
- Test creates mock `DoctorCheck` and asserts `"lsmas" in report.critical_failures`

### Critical Issue 4: Decision log entry inconsistent

**Location:** `docs/DECISIONS.md:423`
**Issue:** Artifact versions incomplete, signature conflicts with SSOT.

**Fix Applied:**

- Updated artifact versions to include full chain: `plan-v4 + plan-review-v4 + impl-v1 + impl-v2 + verify-v2 + review-v1 + impl-v3`
- Corrected signature to `resolve_paths(config, root) -> WorkspacePaths` per SSOT §5.1
- Changed "SSOT Edits" to "SSOT Clarifications" with list of confirmed semantics

## Additional Improvements (Best Practices)

**User feedback:** Avoid `# pyright: ignore` in favor of proper patterns.

**Actions taken:**

1. Made `discover_inputs` public (remove underscore) — it has a stable, testable contract
2. Refactored doctor tests to access check functions via `collect_checks()` instead of importing private `_check_*` functions directly
3. Result: **Zero pyright ignore comments** in tests

## Files Changed

### Modified

- `src/frame_compare/orchestration/preflight.py` — 2-arg `resolve_paths`, public `discover_inputs`
- `src/frame_compare/orchestration/__init__.py` — Export `discover_inputs`
- `tests/orchestration/test_preflight.py` — `TestDiscoverInputs` class, ordering assertions
- `tests/orchestration/test_doctor.py` — Refactored to use `collect_checks()`, added lsmas critical_failures test
- `docs/DECISIONS.md` — Updated Phase 6.2 entry

## Local Sanity Checks

```text
$ .venv/bin/pyright --warnings src/frame_compare/orchestration/ tests/orchestration/
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest tests/orchestration/ -v --tb=short
30 passed
```

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-03__p6-2__preflight-doctor

## Context

This is impl-v3 addressing all 4 Critical issues from review-v1.md.

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v3.md
2. Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/review-v1.md

## Your Task

1. Verify all 4 Critical issues from review-v1.md have been addressed
2. Run the full verification suite
3. Update master checklist and run index

## Output

Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/verify-v3.md
