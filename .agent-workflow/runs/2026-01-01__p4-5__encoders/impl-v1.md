---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v1
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v6.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v1.md
  - src/frame_compare/render/encoders.py
  - src/frame_compare/utils/subproc.py
  - tests/render/test_encoders.py
  - tests/utils/test_subproc.py
---

# Implementation Report: Render Encoders

## Summary
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
**Plan Review Report:** .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v6.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/render/encoders.py` — Implemented `render_frame` (dispatch), `_render_vs`, `_render_ffmpeg`, and `_probe_fps` with overlay integration and error wrapping.
- `src/frame_compare/utils/subproc.py` — Implemented `run_subprocess` wrapper for secure execution.
- `tests/render/test_encoders.py` — 9 tests covering dispatch logic, error handling, seek calculation, and overlay integration (mocked).
- `tests/utils/test_subproc.py` — 5 tests for subprocess wrapper defaults, errors, and timeouts.

### Modified
- `src/frame_compare/render/__init__.py` — Exported `render_frame`.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` — Updated SSOT with Behavior sections and `_probe_fps` signature.
- `docs/DECISIONS.md` — Logged dispatch logic and secure subprocess decisions.
- `CHANGELOG.md` — Added entries for `render.encoders` and `utils.subproc`.

## Implementation Notes
- **Error Handling:** Strictly adhered to `errors.py` signatures. `FrameExtractionError` uses standard message format (FC-4001). `RenderError` wraps internal exceptions via `from e`.
- **SSOT Updates:** Added detailed behavior descriptions for `render_frame` and `_probe_fps` to `render-module.md` to satisfy anchor validation.
- **Overlay Integration:** Updated `_render_vs` to accept `overlay` argument directly for efficiency, while `_render_ffmpeg` relies on post-processing via `_apply_overlay_to_file`.
- **Testing:** `test_encoders.py` uses full mocking for VS (via `FakeClip`) and FFmpeg (via `mock_run_subprocess`), ensuring no external dependencies are required for unit tests.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/render/ src/frame_compare/utils/` — exit 0
- `.venv/bin/ruff check src/frame_compare/render/ src/frame_compare/utils/` — exit 0
- `.venv/bin/pytest -v tests/render/test_encoders.py tests/utils/test_subproc.py` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 4.5: Render Encoders (VS/FFmpeg strategies) [SSOT]

## Open Questions

- None

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
3. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v6.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/verify-v1.md
