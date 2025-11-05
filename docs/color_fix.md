# Colour Pipeline Alignment Task

## Context Recap
- The current pipeline (`src/screenshot.py`, `src/vs_core.py`) normalises colour metadata, promotes to YUV444 for geometry, then converts to RGB24.
- Debug runs show that after geometry (`post_geometry`) clips lose `_Matrix/_Transfer/_Primaries/_ColorRange`, so both `_legacy_rgb24` and `_post_rgb24` expand to full range (`Range=0`) even for SDR limited sources.
- `Legacy/comp.py` (see `Legacy/comp.py:1015-1055`) converted directly to RGB24 with limited-range metadata intact; `Legacy/compv2.py` introduces a `process_clip_for_screenshot` helper similar to our modern pipeline and exhibits the same washout.
- Decision: only true HDR/tonemapped outputs should end up full range. SDR limited sources must stay limited.

## Objective
Restore SDR colour fidelity so the modern pipeline matches `Legacy/comp.py` while keeping HDR behaviour intact, including the FFmpeg rendering path.

## Tasks _(use `rg` / ripgrep for references)_
1. **Preserve colour props through geometry**
   - Inspect `_promote_to_yuv444p16`, crop/scale/pad, and `_save_frame_with_fpng` (≈`src/screenshot.py:984–1850`).
   - After each transformation (`Point`, `CropRel`, `Spline36`, `AddBorders`), copy `_Matrix/_Transfer/_Primaries/_ColorRange` from input to output (e.g. via `std.CopyFrameProps`) so `post_geometry` still reports `Range=1`.
   - Extend debug capture to snapshot props after each stage to confirm they persist.

2. **Align RGB24 conversion with legacy for SDR**
   - Update `_legacy_rgb24_from_clip` & `_ensure_rgb24` (`src/screenshot.py:493–640`):
     * When `_ColorRange == 1`, pass `range=vs.RANGE_LIMITED` and keep `_ColorRange` on RGB frames as 1.
     * Only force `_ColorRange = 0` when HDR tonemapping ran (tonemap enabled & `_props_signal_hdr` true).
   - Mirror the same limited/full logic inside `_save_frame_with_ffmpeg`.

3. **Ensure debug artifacts keep original metadata**
   - In `vs_core.process_clip_for_screenshot`, always supply `ColorDebugArtifacts` with original props; fallback synthesis should use pre-normalisation values and ensure a valid core.
   - Confirm debug ladder now shows `Range=1` through `post_rgb24` for limited SDR.

4. **Tests & documentation**
   - Add/extend tests in `tests/test_screenshot.py` covering:
     * limited-range SDR clip stays limited after `_ensure_rgb24`.
     * geometry pipeline preserves `_Matrix/_ColorRange`.
   - Update `docs/config_reference.md` (debug section) with logging helper:
     ```python
     import logging
     from frame_compare import run_cli

     logging.basicConfig(level=logging.INFO)
     run_cli(config_path="config/config.toml", root_override=".", debug_color=True, quiet=False, verbose=True)
     ```

5. **Verification**
   - `npx pyright --warnings`, `.venv/bin/ruff check .`, `.venv/bin/pytest`.
   - Run a debug comparison with cleanup disabled; confirm `post_geometry`, `legacy_rgb24`, `post_rgb24` all report `Range=1`, and PNGs match `Legacy/comp.py`.
   - Ensure FFmpeg output matches VapourSynth path.

## Reference Points
- `Legacy/comp.py:1015-1055`
- `Legacy/compv2.py:200-360`
- `src/screenshot.py:493-640`, `984-1850`
- `src/vs_core.py` (`process_clip_for_screenshot`)

## Resolved Questions
1. HDR/tonemapped clips stay full range; SDR limited remains limited.
2. No intentional reason to drop props during geometry.
3. FFmpeg path should mirror limited/full logic.
4. Change restores original SDR behaviour; currently everything expands to full range.
