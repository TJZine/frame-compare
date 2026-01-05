---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v6
TARGET: Phase 4 → Item 4.6
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v6.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/impl-v1.md
  - src/frame_compare/render/orchestrator.py
  - src/frame_compare/render/__init__.py
  - tests/render/test_orchestrator.py
  - docs/DECISIONS.md
  - CHANGELOG.md
---

# Implementation Report: Render Orchestrator

## Summary
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md
**Plan Review Report:** .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v6.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/render/orchestrator.py` — Orchestrator module with `render_batch` and `render_screenshots`.
- `tests/render/test_orchestrator.py` — 13 unit tests for orchestration logic.

### Modified
- `src/frame_compare/render/__init__.py` — Added exports for `render_batch`, `render_screenshots`, and `ProgressReporter`.
- `docs/DECISIONS.md` — Added decision for Render Orchestrator.
- `CHANGELOG.md` — Added entries for `render.orchestrator` and `ProgressReporter`.

### Generated
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

## Implementation Notes
- Switched from standard `logging` to `structlog` in `orchestrator.py` to match project convention.
- Fixed `RenderError` instantiation in `render_screenshots` to match the `FrameCompareError` hierarchy (no custom message allowed, used `raise RenderError() from e`).
- Parallelism logic in `render_batch` uses `concurrent.futures.wait` with `FIRST_COMPLETED` for bounded, fail-fast submission.
- Contract views were regenerated to ensure freshness before handoff.

## Local Sanity Checks (Optional)

- `.venv/bin/pyright src/frame_compare/render/orchestrator.py` — exit 0
- `.venv/bin/ruff check src/frame_compare/render/orchestrator.py` — exit 0
- `.venv/bin/pytest tests/render/test_orchestrator.py` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
- [x] Phase 4 → Item 4.6 (Render Orchestrator)

## Open Questions
- None.

## Ready for Verification
All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-6__orchestrator

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md
3. Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v6.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/verify-v1.md
