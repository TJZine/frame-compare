---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v3
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v2.md
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v3.md
  - src/frame_compare/render/encoders.py
  - tests/render/test_encoders.py
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
---

# Implementation Report: Render Encoders (Revision v3)

## Summary
**Date:** 2026-01-01
**Context:** Revision addressing critical issues from `review-v1.md`.

## Fixes Applied

### 1. Corrected FFprobe FPS Field
- **Issue:** `_probe_fps` was querying `r_frame_rate` (SSOT/Plan mismatch) which is unreliable for VFR content.
- **Fix:** Updated `_probe_fps` in `src/frame_compare/render/encoders.py` to query `avg_frame_rate` as required by plan-v6.
- **Verification:** Updated `tests/render/test_encoders.py` to assert `stream=avg_frame_rate` is used in the probe command.

### 2. Aligned FFmpeg Command with SSOT
- **Issue:** `_render_ffmpeg` was using `-compression_level` (Pillow-style argument) instead of the SSOT-mandated `-q:v 1`.
- **Fix:** Updated `_render_ffmpeg` in `src/frame_compare/render/encoders.py` to use `["-q:v", "1"]`.
- **Verification:** Updated `test_ffmpeg_seek_calculation` in `tests/render/test_encoders.py` to assert `-q:v 1` is present in the subprocess call.

### 3. Missing SSOT Signature
- **Issue:** `validate_spec_anchors.py` flagged `_probe_fps` as missing from the SSOT anchors.
- **Fix:** Added the `_probe_fps(video_path: Path) -> float` signature to `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` under Section 4.2.

### 4. Exception Instantiation Fixes
- **Issue:** `FrameExtractionError` and other exceptions were instantiated with incorrect arguments vs `errors.py` definition.
- **Fix:** Updated instantiation calls in `src/frame_compare/render/encoders.py` to match signatures (e.g., `FrameExtractionError(frame_number=..., clip_name=...)`).
- **Test Update:** Updated `test_render_frame_mismatch_error` to assert the actual error message produced by `FrameExtractionError`.

## Files Changed (Exact Paths)

### Modified
- `src/frame_compare/render/encoders.py` (Logic fixes)
- `tests/render/test_encoders.py` (Test updates)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` (SSOT Anchor update)

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/render/` — exit 0
- `.venv/bin/ruff check src/frame_compare/render/ tests/render/` — exit 0
- `.venv/bin/pytest -v tests/render/test_encoders.py` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Context
This is a revision (impl-v3) addressing functional correctness issues from review-v1.md.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v3.md
2. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/review-v1.md
3. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md

## Your Task
1. Verify the specific fixes (FFprobe arg, FFmpeg command, SSOT signature) were applied.
2. Re-run the full verification suite.
3. Update the master checklist.
4. Update the run index.

## Output
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/verify-v3.md
