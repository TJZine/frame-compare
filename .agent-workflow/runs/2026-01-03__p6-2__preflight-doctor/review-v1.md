---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v1
TARGET: Phase 6 → Item 6.2
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/verify-v2.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v2.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v1.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Preflight & Doctor

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-03
**Files Reviewed:** 15
**Commit Subject:** `feat(orchestration): implement Phase 6 Item 6.2 — preflight and doctor`

## Process Gates

- [x] Plan was approved by Plan Review Agent (`Verdict: APPROVED`, `Decision Points Remaining: NONE`)
- [x] Verification handoff complete
- [x] All verification gate outputs included (pyright, ruff, pytest+cov, lint-imports, contract freshness)
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q
443 passed, 2 skipped
Required test coverage of 80.0% reached. Total coverage: 89.88%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date
```

## Files Reviewed

- `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/verify-v2.md`
- `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v2.md`
- `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v1.md`
- `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md`
- `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v4.md`
- `src/frame_compare/orchestration/preflight.py`
- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/orchestration/__init__.py`
- `src/frame_compare/utils/types.py`
- `src/frame_compare/utils/__init__.py`
- `src/frame_compare/errors.py`
- `tests/orchestration/test_preflight.py`
- `tests/orchestration/test_doctor.py`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` (anchors: §4.1, §5.1)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` (anchor: §3.1)
- `docs/DECISIONS.md`

## Checklist Results

### Correctness

- [ ] Issue: `resolve_paths` public signature does not match SSOT / plan
- [ ] Issue: Two “required tests” do not assert the required behavior
- [ ] Issue: Decision log entry conflicts with SSOT and is missing revision artifact versions

### Type Safety

- [x] Type hints present on new/changed functions and dataclasses
- [x] Pyright passes (per verification)

### Error Handling

- [x] `NoVideosFoundError` has `FC-3001` and stable `details` keys; includes `path` and `patterns` instance attributes

### Testing

- [ ] Issue: `test_prepare_preflight_discovers_inputs_sorted_case_insensitive` does not verify ordering
- [ ] Issue: `test_check_lsmas_plugin_fails_when_missing` does not verify `DoctorReport.critical_failures` includes `"lsmas"`

### Documentation

- [ ] Issue: `docs/DECISIONS.md` Phase 6.2 entry asserts “SSOT Edits: None” despite plan-v4 describing SSOT clarifications, and documents a `resolve_paths(..., config_file)` signature that contradicts SSOT §5.1

### Security

- [x] Network check (`slow.pics`) is mocked in unit tests; no network required for default unit test runs

## Issues Found

### Critical (Must Fix)

1. **`resolve_paths` signature conflicts with SSOT / plan**
   - Location: `src/frame_compare/orchestration/preflight.py:77`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:461`, `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md:145`
   - Issue: SSOT §5.1 defines `resolve_paths(config: ConfigSchema, root: Path) -> WorkspacePaths`, but implementation is `resolve_paths(config, root, config_file)` and tests rely on the 3-arg form.
   - Fix: Align code + tests to the SSOT/plan signature. One viable approach is deriving `config_file` from `config.__class__.model_config["toml_file"]` (resolving relative paths against `root`) so `resolve_paths(config, root)` can still populate `WorkspacePaths.config_file` deterministically.

2. **Required preflight ordering test does not assert ordering**
   - Location: `tests/orchestration/test_preflight.py:184`
   - Issue: Plan-v4 requires asserting discovered list order `[A.mkv, b.mkv]`, but the test currently only asserts that preflight succeeds.
   - Fix: Assert the actual ordering (e.g., by importing and testing the internal `_discover_inputs` helper, or otherwise verifying the deterministic ordering in a black-box way).

3. **Required lsmas failure test does not assert `critical_failures` behavior**
   - Location: `tests/orchestration/test_doctor.py:112`
   - Issue: Plan-v4 requires that when the core `lsmas` check fails, `DoctorReport.critical_failures` includes `"lsmas"`. The test only asserts `_check_lsmas()` returns `passed=False`.
   - Fix: Add an assertion that exercises `run_doctor(...)` and checks `critical_failures` contains `"lsmas"` for a failing core check.

4. **Decision log entry inconsistent and missing revision artifact versions**
   - Location: `docs/DECISIONS.md:423`
   - Issue:
     - Artifact versions omit the revision (`impl-v2`, `verify-v2`, and this `review-v1`).
     - The entry documents `resolve_paths(config, root, config_file)` and “SSOT Edits: None”, which conflicts with SSOT §5.1 and plan-v4’s stated SSOT clarifications.
   - Fix: Update the Phase 6.2 decision entry to:
     - Record the complete artifact set (plan/plan-review/impl/verify/review) without guessing.
     - Match SSOT signatures (after code is corrected).
     - Accurately reflect whether SSOT was edited during the plan loop (as described in plan-v4).

### Minor (Should Fix)

- None

### Suggestions (Nice to Have)

- Consider making the input sort key fully deterministic for case-insensitive ties (e.g., `key=(name.lower(), name)`), if SSOT later tightens determinism guarantees for mixed-case duplicates.

## Acceptance Criteria Verification

- [ ] GIVEN stable input set WHEN resolving paths THEN `resolve_paths` signature matches SSOT and produces deterministic results — blocked on Critical issues above.
- [ ] GIVEN `lint-imports` THEN orchestration layer contracts pass — ✓ Verified in `verify-v2.md`.
- [ ] GIVEN unit tests THEN preflight + doctor determinism is asserted — blocked on Critical issues above.

## Next Steps

### CHANGES REQUIRED

- Coding Agent: Address all Critical issues above in a single fix pass (review-stage fix budget is one cycle), then re-run verification and resubmit for review.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-2__preflight-doctor

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/review-v1.md
See "Issues Found > Critical" for the required fixes.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md
2. Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v4.md
3. Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/review-v1.md

## Your Task
Address all Critical issues listed in the review report. Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v3.md
