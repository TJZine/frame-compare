---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v1
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v1.md
  - src/frame_compare/analysis/metrics.py
  - tests/analysis/test_metrics.py
---

# Implementation Report: Metrics Calculation

## Summary
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/analysis/metrics.py` — Metric calculation logic (luminance, motion).
- `tests/analysis/test_metrics.py` — 15 unit tests covering calculation and integration.

### Modified
- `docs/DECISIONS.md` — Added Phase 2.2 metrics calculation decision.
- `CHANGELOG.md` — Added `calculate_metrics` to the Added section.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` — Regenerated.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Regenerated.
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py` — Regenerated.

## Implementation Notes
- **VapourSynth Typing**: Extensively used `# type: ignore` in `metrics.py` to satisfy Pyright while maintaining compatibility with the minimal `vapoursynth.pyi` stub and handling missing runtime environment issues.
- **Progress Reporting**: Implemented the `ProgressReporter` protocol and integrated it into `_calculate_luminance`.
- **Normalization**: Correctly handles integer (bit-depth based) and float (0.0-1.0) VapourSynth sample types.
- **Reference Only**: `calculate_metrics` properly analyzes only the first video in `video_paths` while associating all clips with the generated metadata.
- **Error Handling**: Explicitly checks for 0-frame clips and raises `MetricsCalculationError` (FC-4002) per SSOT.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/analysis/metrics.py` — [exit 0]
- `.venv/bin/ruff check src/frame_compare/analysis/metrics.py` — [exit 0]
- `.venv/bin/pytest -v tests/analysis/test_metrics.py` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented
- [x] Phase 2.2 Metrics Calculation

## Open Questions
- None.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-2__metrics-calculation

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
3. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/verify-v1.md
