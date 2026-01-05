---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v1
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v1.md
  - src/frame_compare/vs/tonemap.py
  - tests/vs/test_tonemap.py
  - src/frame_compare/vs/__init__.py
  - src/frame_compare/errors.py
---

# Implementation Report: HDR Tonemapping

## Summary
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/vs/tonemap.py` — Tonemapping logic (libplacebo + fallback)
- `tests/vs/test_tonemap.py` — Unit tests for tonemapping

### Modified
- `src/frame_compare/vs/__init__.py` — Export `apply_tonemap` and `get_preset_settings`
- `src/frame_compare/errors.py` — Updated `TonemapError` to support optional custom hints (required by plan)
- `docs/DECISIONS.md` — Logged Phase 3.5 decision
- `CHANGELOG.md` — Added Phase 3.5 changes

### Regenerated (Contract Freshness)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

## Implementation Notes

- Modified `src/frame_compare/errors.py`: The plan required `TonemapError` to include specific hints (e.g., listing valid presets), but the existing `TonemapError` hardcoded the hint to "Check libplacebo support or config". Updated constructor to accept optional `hint` parameter while preserving backward compatibility.
- Mocked `vapoursynth` module in `tests/vs/test_tonemap.py` using `sys.modules` patching because the test environment lacks VapourSynth.
- Applied `type: ignore` to `vs.RGBS` usages in `tonemap.py` as strict Pyright checks flagged it as unknown in the absence of VapourSynth runtime/complete stubs.

## Local Sanity Checks (Optional)

- `.venv/bin/pyright --warnings src/frame_compare/vs/tonemap.py` — exit 0
- `.venv/bin/ruff check src/frame_compare/vs/tonemap.py tests/vs/test_tonemap.py` — exit 0
- `.venv/bin/pytest -v tests/vs/test_tonemap.py` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 3.5 Tonemapping

## Open Questions

- None

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
3. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v1.md
