---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v1
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v1.md
  - src/frame_compare/analysis/selection.py
  - tests/analysis/test_selection.py
---

# Implementation Report: Frame Selection Algorithms

## Summary
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v4.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/analysis/selection.py` — Core selection algorithms (Quantile, Motion, Random, Mixed)
- `tests/analysis/test_selection.py` — 10 unit tests for selection algorithms, including deterministic RNG and error cases

### Modified
- `src/frame_compare/analysis/__init__.py` — Added `select_frames` export
- `docs/DECISIONS.md` — Logged implementation details and algorithms
- `CHANGELOG.md` — Added entry for frame selection algorithms

## Implementation Notes
- **Pure Python:** Algorithms implemented without external dependencies like numpy, using standard library `random.Random` for determinism.
- **Min Gap:** A `MIN_GAP=5` is enforced for motion and random selection phases to prevent clusters of adjacent frames.
- **Mixed Mode:** Allocation follows the 40/40/20 split (Quantile/Motion/Random) as specified.
- **Error Handling:** `SelectionError` (FC-4012) is raised with detailed context for empty metrics or if the requested frame count cannot be satisfied.

## Local Sanity Checks

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md` — exit 0
- `.venv/bin/pyright --warnings src/frame_compare/analysis/` — exit 0
- `.venv/bin/ruff check src/frame_compare/analysis/` — exit 0
- `.venv/bin/pytest -v tests/analysis/test_selection.py` — exit 0 (10 passed)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0

## Checklist Item Implemented
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Implement frame selection algorithms (Quantile, Motion, Random, Mixed)
- [x] Ensure deterministic random selection with seeds
- [x] Enforce minimum gap between selected frames
- [x] Handle error cases (empty metrics, insufficient candidates)
- [x] Export `select_frames` in analysis module

## Open Questions
- None.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-3__frame-selection

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
3. Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v4.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/verify-v1.md
