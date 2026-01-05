---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v1
TARGET: Phase 6 → Item 6.4
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/verify-v1.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v1.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: FramePlan Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-04
**Files Reviewed:** 12
**Commit Subject:** `feat(analysis): implement Phase 6 Item 6.4 — deterministic FramePlan selection`

## Process Gates
- [x] Plan was approved by Plan Review Agent (`plan-review-v3.md`: Verdict APPROVED; Decision Points Remaining NONE)
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov
35 passed, coverage: 100%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
No violations

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
✓ All derived views are fresh

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✓ All requirements traced
```

## Files Reviewed

- `.agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/verify-v1.md`
- `.agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v1.md`
- `.agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md`
- `.agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v3.md`
- `src/frame_compare/analysis/frame_plan.py`
- `tests/analysis/test_frame_plan.py`
- `src/frame_compare/analysis/__init__.py`
- `src/frame_compare/errors.py`
- `tests/test_errors.py`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`
- `.agent-workflow/index.md`

## Checklist Results

### Correctness

- [x] FramePlan selection logic matches SSOT algorithm (binning + blake2s + sort + last-bin clamp)
- [x] Cross-session determinism test exists and is safe (subprocess via `sys.executable`)

### Type Safety

- [x] Public APIs are typed (`FramePlan`, `select_uniform_seeded_frames`, `create_frame_plan`)
- [x] Pyright passes

### Error Handling

- [ ] Issue: `InsufficientFramesError` message/hint drift vs SSOT

### Testing

- [x] Unit tests cover all SSOT-required cases in `tests/analysis/test_frame_plan.py`
- [ ] Issue: Missing targeted FC-3004 payload-shape test required by `plan-v3.md`

### Documentation

- [ ] Issue: `docs/DECISIONS.md` entry missing `verify-v1` + `review-v1` artifact versions

### Security

- [x] No external I/O beyond subprocess in tests; no secrets; deterministic hashing only

### Performance

- [x] O(count) selection; no concerns for expected frame counts

## Issues Found

### Critical (Must Fix)

1. **FC-3004 message/hint drift vs SSOT**
   - Location: `src/frame_compare/errors.py` (`InsufficientFramesError`)
   - Spec: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` §3.3
   - Spec requires:
     - `message=f"Video has {count} frames, need at least {required}"`
     - `hint="Use a longer video or reduce frame_count"`
   - Current implementation differs (includes path in message and different hint phrasing).
   - Fix: Update `InsufficientFramesError` message/hint to match SSOT exactly (and keep details keys `path/count/required`).

2. **Missing FC-3004 payload-shape test required by plan**
   - Location: `tests/test_errors.py`
   - Plan: `.agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md` → “3. `tests/test_errors.py` (MODIFY)”
   - Fix: Add `test_insufficient_frames_error_details_shape` with minimum assertions:
     - `code == "FC-3004"`
     - `context.details` keys are exactly `{"path", "count", "required"}`
     - Ensure the payload uses `count/required` (not the old `requested/available` drift).

### Minor (Should Fix)

1. **DECISIONS entry missing full artifact versions**
   - Location: `docs/DECISIONS.md` (Phase 6.4 entry)
   - Fix: After `verify-v2` and `review-v2` exist, update the entry to include `verify-v2` + `review-v2` (and adjust
     gate summary if needed).

2. **Out-of-plan dependency/lockfile change not reflected in plan file list**
   - Location: `pyproject.toml`, `uv.lock`
   - Context: Plan requires Hypothesis property-based tests; adding `hypothesis` to dev deps is reasonable, but
     `plan-v3.md` “Files to Create/Modify” does not list these files.
   - Fix: No re-plan requested in this review cycle; document the dependency/lockfile update explicitly in the next
     implementation report (`impl-v2.md`) and ensure Verification references the correct diff set.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] Determinism: same inputs in-process — ✓ Verified (`tests/analysis/test_frame_plan.py`)
- [x] Determinism: cross-session — ✓ Verified (`tests/analysis/test_frame_plan.py`)
- [x] Error raising: `count > num_frames` raises FC-3004 with `count/required/path` — ✓ Verified (`tests/analysis/test_frame_plan.py`)
- [x] `count=0` returns empty plan — ✓ Verified (`tests/analysis/test_frame_plan.py`)
- [x] `seed=None` uses `42` — ✓ Verified (`tests/analysis/test_frame_plan.py`)
- [x] Hypothesis invariants — ✓ Verified (`tests/analysis/test_frame_plan.py`)

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Update `InsufficientFramesError` message/hint in `src/frame_compare/errors.py` to match SSOT `errors-module.md` §3.3.
  2. Add `test_insufficient_frames_error_details_shape` in `tests/test_errors.py` per `plan-v3.md`.
  3. Update the Phase 6.4 entry in `docs/DECISIONS.md` to include final artifact versions after re-verification.
- Re-submit for verification and review.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-4__frame-plan-module

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v3.md
3. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v2.md
