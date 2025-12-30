---
RUN_ID: 2025-12-29__p3-4__color-operations
VERSION: v1
TARGET: Phase 3 → Item 3.4 Color Operations
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/impl-v1.md
  - src/frame_compare/vs/color.py
  - src/frame_compare/utils/perf.py
  - tests/vs/test_color.py
  - tests/utils/test_perf.py
---

# Implementation Report: Color Operations + Perf Spans

## Summary
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-review-v1.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/vs/color.py` — Deterministic color metadata inference and RGB conversion.
- `src/frame_compare/utils/perf.py` — Opt-in performance instrumentation (FRAME_COMPARE_PERF=1).
- `tests/vs/test_color.py` — 8 tests for color operations including SD/HD/HDR inference and RGB24 conversion.
- `tests/utils/test_perf.py` — 4 tests for perf enabled/disabled behavior.

### Modified
- `src/frame_compare/vs/types.py` — Docstring clarification for color_range default.
- `src/frame_compare/vs/props.py` — Aligned _ColorRange default to 1 (limited).
- `src/frame_compare/vs/__init__.py` — Verified exports for color operations.
- `src/frame_compare/utils/__init__.py` — Verified exports for perf helpers.
- `src/frame_compare/analysis/metrics.py` — Added perf spans around heavy loops.
- `typings/vapoursynth.pyi` — Added color constants (RANGE, MATRIX, TRANSFER, PRIMARIES) and missing VideoNode members (std, resize, get_frame).
- `pyproject.toml` — Disabled `reportMissingModuleSource` for cleaner Pyright output.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` — Documented perf.py API.
- `docs/DECISIONS.md` — Recorded color range default and perf instrumentation decisions.
- `CHANGELOG.md` — Noted color operations and range default changes.

## Implementation Notes
- **Contract Freshness:** Derived contract views were stale and were regenerated via `scripts/generate_contract_views.py`.
- **Typings:** Expanded `vapoursynth.pyi` to support `VideoNode.std` and `VideoNode.resize` which were missing and caused pyright errors in `color.py`.
- **Configuration:** Updated `pyproject.toml` to disable `reportMissingModuleSource` in Pyright, ensuring clean checks for binary dependencies like VapourSynth.
- **Inference Rules:** Implemented deterministic rules for BT.709/BT.2020 and SD/HD defaults as specified in the SSOT.

## Local Sanity Checks (Optional)

- `.venv/bin/pyright --warnings src/frame_compare/vs/color.py` — [exit 0]
- `.venv/bin/ruff check src tests` — [exit 0]
- `.venv/bin/pytest -q` — [exit 0 (193 passed)]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented
- [x] Phase 3.4: Color Operations

## Open Questions
- None. Ready for Verification.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-4__color-operations

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md
3. Read file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-review-v1.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/verify-v1.md
