---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v1
TARGET: Phase 6 → Item 6.4
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v1.md
  - src/frame_compare/analysis/frame_plan.py
  - tests/analysis/test_frame_plan.py
  - src/frame_compare/analysis/__init__.py
  - src/frame_compare/errors.py
---

# Implementation Report: FramePlan Module

## Summary

**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
**Plan Review Report:** .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v3.md (APPROVED)

## Files Changed

### Created

- `src/frame_compare/analysis/frame_plan.py` — `FramePlan` dataclass and deterministic selection logic.
- `tests/analysis/test_frame_plan.py` — Unit tests and Hypothesis property-based tests.

### Modified

- `src/frame_compare/analysis/__init__.py` — Added exports using lazy loading to safely support environments without VapourSynth.
- `src/frame_compare/errors.py` — Updated `InsufficientFramesError` to match SSOT signature (3-arg: path, count, required).
- `pyproject.toml` — Added `hypothesis>=6.0.0` to dev dependencies (required for property-based tests).
- `docs/DECISIONS.md` — Added decision log for Phase 6.4.
- `CHANGELOG.md` — Added FramePlan module entry.

### Generated (Contract Views)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

## Implementation Notes

- **Dependency Update:** Added `hypothesis` to `pyproject.toml` because the Plan explicitly required property-based testing and it was missing from the environment.
- **Lazy Imports:** Implemented `__getattr__` based lazy imports in `src/frame_compare/analysis/__init__.py` to prevent `tests/analysis/test_frame_plan.py` from crashing in environments where VapourSynth is missing (satisfying "Tests pass without VS/Docker" criterion).
- **Error Signature:** `InsufficientFramesError` now strictly follows the `(path, count, required)` signature, where `count` is the available frames and `required` is the requested amount.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — exit 0
- `.venv/bin/ruff check .` — exit 0
- `.venv/bin/pytest -q` — exit 0 (All tests passed)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0 (After regeneration)

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 6.4 FramePlan Module

## Ready for Verification

All files created per plan. Ready for Verification Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-4__frame-plan-module

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
3. Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v3.md

## Your Task

1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/verify-v1.md
