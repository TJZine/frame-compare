# Current Screenshot Pipeline Trace (2025-09-22)

Scope: `frame_compare.py` + `src/screenshot.py` + `src/vs_core.py` as of this commit.

## Clip lifecycle
- `_init_clips` (frame_compare.py) loads each video via `vs_core.init_clip`. Output: VapourSynth node (`plan.clip`) still in the source colorspace (usually YUV420/limited). Frame props mirror source (`_Matrix`, `_Transfer`, `_Primaries`, `_ColorRange`) because no adjustments occur post-load.
- No further transforms are applied to `plan.clip` before rendering; the same node is passed straight into `generate_screenshots`.

## Geometry & overlay path (generate_screenshots)
- `_plan_geometry` determines per-clip crop + scale targets but does not touch frame data.
- `_save_frame_with_fpng` receives `clip` (original node). Processing order:
  1. `work = clip` — still original props (HDR clips retain `_Matrix=9?`, `_Transfer=16/18`, `_ColorRange=1`, etc.).
  2. Optional `std.CropRel` and `resize.Spline36` to enforce geometry; these operations inherit/propagate props unchanged.
  3. If `cfg.add_frame_info` (default true) → `_apply_frame_info_overlay` uses `std.FrameEval` + `sub.Subtitle`. Overlay lands top-left-ish (style `FRAME_INFO_STYLE`); no tonemap metadata, and overlay can be skipped silently if dependencies missing (only debug log).
  4. `_ensure_rgb24` converts to RGB24 only if clip is not already RGB8. Conversion uses `resize.Point` with *no* explicit `matrix_in`/`transfer_in` hints, so VapourSynth relies on props (problematic if earlier steps stripped them). After conversion it calls `SetFrameProps` with `_Matrix/_Primaries/_Transfer/_ColorRange` hard-coded to strings (`"bt709"`, etc.). No `_Tonemapped` flag is set.
  5. Resulting node is written via `fpng.Write`. For FFmpeg path the raw file is used; no tonemap happens either way.

## Color / tonemap handling (src/vs_core)
- `process_clip_for_screenshot` exists but **is never invoked** during screenshot rendering. It only runs when `analysis.analyze_in_sdr` is enabled, and even then operates on the analysis-only clip.
- When invoked, it calls `libplacebo.Tonemap` on the *original clip* (no RGB16 conversion, no prop normalisation). Failures raise `ClipProcessError`. After success it calls `_set_sdr_props` to stamp SDR props (function is bugged: returns `std.SetFrameProps(**props)` without passing the clip, so would throw at runtime).
- There is no retry logic, no src_csp hint inference, and no fallback other than raising an exception.

## Frame props snapshot (expected real-world values)
- After `_init_clips`: `_Matrix =` source matrix (e.g. 9), `_Transfer = 16/18`, `_Primaries = 9`, `_ColorRange = 1` for HDR BT.2020 PQ/HLG.
- After geometry but before `_ensure_rgb24`: unchanged.
- After `_ensure_rgb24`: props forcibly set to strings, `_Tonemapped` absent. Because tonemap never ran, HDR footage remains in original transfer/gamut despite props claiming BT.709/BT.1886.
- Writer receives the same clip that the (optional) overlay modified (`render_clip`), so overlay does survive — but content is SDR-tagged regardless of true pixel values.

## Gaps vs legacy expectations
- No YUV→RGB16 staging, no prop normalisation, no Tonemap retries (`libplacebo.Tonemap` called directly on source node), no fallback logging.
- No verification path (Δ vs naive SDR) and no selection of non-trivial frames.
- Overlay lacks tonemap metadata, is not enforced, and sits top-left.
- Frame props lie post-conversion, creating silent mismatch.

This trace will guide the fix-up work to align with the legacy pipeline.
