---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v3
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v3.md
  - src/frame_compare/analysis/metrics.py
  - tests/analysis/test_metrics.py
---

# Implementation Report: Metrics Calculation (Revision 2)

## Summary
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
**Review Reference:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md (CHANGES REQUIRED)

## Files Changed (Exact Paths)

### Modified
- `src/frame_compare/analysis/metrics.py` — Updated `calculate_metrics` to propagate `PluginNotFoundError` and `SourceLoadError` directly; updated docstring.
- `tests/analysis/test_metrics.py` — Added propagation tests for `PluginNotFoundError` and `SourceLoadError`.

## Implementation Notes
- **Error Propagation**: Modified `calculate_metrics` to catch `(PluginNotFoundError, SourceLoadError)` and re-raise them immediately, ensuring they bubble up to the caller unwrapped per SSOT.
- **Documentation**: Updated `calculate_metrics` docstring `Raises` section to include the newly propagated errors.
- **Testing**: Added two new tests (`test_calculate_metrics_propagates_plugin_not_found` and `test_calculate_metrics_propagates_source_load_error`) to verify the error contract.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/analysis/metrics.py` — [exit 0]
- `.venv/bin/ruff check src/frame_compare/analysis/metrics.py tests/analysis/test_metrics.py` — [exit 0]
- `.venv/bin/pytest -v tests/analysis/test_metrics.py` — [exit 0] (17 passed)

## Checklist Item Implemented
- [x] Phase 2.2 Metrics Calculation (Revision 2)

## Open Questions
- None.

## Ready for Verification

Revision addressing review comments is complete. Ready for re-verification.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-2__metrics-calculation

## Context
This is a revision (impl-v3) addressing issues from review-v1.md regarding error propagation and documentation.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v3.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md (contains the fix list)
3. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md

## Your Task
1. Verify the specific fixes were applied (error propagation + docstring)
2. Run the full verification suite
3. Confirm all review issues addressed

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/verify-v3.md
