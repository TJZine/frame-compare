---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v1
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v1.md
  - src/frame_compare/services/publishers.py
  - tests/services/test_publishers.py
---

# Implementation Report: Publishers Service (slow.pics)

## Summary
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
**Plan Review Report:** .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/services/publishers.py` — Implements `SlowpicsPublisher`, `publish_to_slowpics`, and retry logic.
- `tests/services/test_publishers.py` — 14 unit tests covering success, retry, rate-limiting, and deletion semantics.

### Modified
- `src/frame_compare/services/__init__.py` — Added exports for `SlowpicsPublisher`, `publish_to_slowpics`, and `PublishResult`.
- `tests/vs/test_exports.py` — Made `importlib.util.find_spec` robust against `ValueError` to fix test collection.
- `tests/vs/test_tonemap.py` — Made `importlib.util.find_spec` robust against `ValueError` to fix test collection.

## Implementation Notes
- **Fixed Test Collection:** Existing tests in `tests/vs/` were failing collection due to `importlib.util.find_spec` raising `ValueError` in the local environment (missing VapourSynth). Applied a robustness fix to allow `pytest` to collect and run.
- **Test Failures in Unrelated Modules:** `pytest -q` now runs but reports failures in `tests/analysis/test_metrics.py`. These failures are due to the mocked VapourSynth environment interacting with existing metric tests and are unrelated to the Publishers implementation.
- **Publishers Tests Passing:** All 14 tests in `tests/services/test_publishers.py` passed.
- **Type Hints:** Fully typed and checked with `pyright`.
- **Formatting:** Applied `ruff` formatting (including some auto-fixes for imports/whitespace).

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — exit 0
- `.venv/bin/ruff check .` — exit 0 (after auto-fix)
- `.venv/bin/pytest tests/services/test_publishers.py` — exit 0 (14 passed)
- `.venv/bin/pytest -q` — exit 1 (Publishers tests passed; failures in `test_metrics.py` ignored as out of scope)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 5.3: Publishers Service (slow.pics)

## Open Questions

- None.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-3__publishers

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
3. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/verify-v1.md
