---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v1
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v8.md
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v8.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/impl-v1.md
  - src/frame_compare/vs/__init__.py
  - tests/vs/test_exports.py
  - tests/vs/test_integration.py
---

# Implementation Report: VapourSynth Module Integration

## Summary
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v8.md
**Plan Review Report:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v8.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `tests/vs/test_exports.py` — Verifies public symbols and `__all__` completeness.
- `tests/vs/test_integration.py` — Real VS integration smoke test (marked `@pytest.mark.vs_required`).

### Modified
- `src/frame_compare/vs/__init__.py` — Completed public exports, added `tonemap` alias for `apply_tonemap`.
- `docs/DECISIONS.md` — Logged integration decisions.
- `CHANGELOG.md` — Added Phase 3.6 changes.

### Regenerated (Contract Freshness)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

## Implementation Notes

- **Tonemap Alias:** Implemented `from .tonemap import apply_tonemap as tonemap` in `vs/__init__.py` per Spec Section 8.
- **Test Robustness:**
  - `test_exports.py` handles missing `vapoursynth` by mocking it at import time, ensuring exports can be verified even in no-VS environments.
  - `test_integration.py` uses `pytest.importorskip("vapoursynth")` and checks for `MagicMock` to avoid failure if another test mocked the module in the same session.
- **Contract Freshness:** Regenerated all derived contract views before handoff.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/vs` — exit 0
- `.venv/bin/ruff check src/frame_compare/vs` — exit 0
- `.venv/bin/pytest -v tests/vs/test_exports.py tests/vs/test_integration.py` — exit 0 (2 passed, 1 skipped)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 3.6 Module Integration

## Open Questions

- None.

## Ready for Verification

All files implemented per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-30__p3-6__vs-integration

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v8.md
3. Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v8.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/verify-v1.md
