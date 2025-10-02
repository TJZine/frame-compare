# Legacy Tonemap & Overlay Sequence (historical baseline)

Reference: Archived placebo-based pipeline confirmed on 2025-09-22.

## Clip flow
- Crop/resize decisions happen upstream; `process_clip_for_screenshot` receives the geometry-ready node plus the original frame props.
- HDR detection = `_Transfer` in {16 (PQ), 18 (HLG)} **and** `_Primaries == 9` (BT.2020). SDR flows fall straight to the RGB24 conversion branch.
- HDR path converts YUV→RGB48 via `resize.Spline36` while preserving matrix/transfer/primaries inputs and limited/full range info from props.
- `_normalize_props_for_placebo_rgb16` forces `_Matrix=0`, `_ColorRange=0` and copies `_Transfer`/`_Primaries` so `libplacebo.Tonemap` will linearize correctly.
- `_deduce_src_csp_from_props` returns 1 for PQ/2020, 2 for HLG/2020, else `None` → fed to `_tonemap_with_retries`.

## Tonemap invocation
- `_tonemap_with_retries` first tries `Tonemap(rgb16, src_csp=hint, ...)` with
  - `dst_csp=0` (BT.709 + BT.1886), `dst_prim=1`, `dst_max=TM.dst_max`, `dst_min=0.1`
  - `dynamic_peak_detection=TM.dpd`, `gamut_mapping=1`, `tone_mapping_function_s=TM.func`, `use_dovi=True` plus smoothing + scene thresholds.
- On failure: retries without `src_csp`, then assumes PQ/BT.2020 as last resort. Each failure logs `[Tonemap attempt X failed] …` with the exception.
- Successful tonemap sets a frame prop `_Tonemapped="placebo:<func>,dpd=<>,dst_max=<>"` and logs `[libplacebo] HDR->SDR …` up front.

## Overlay behavior
- Optional (`TM.overlay`) overlay via `core.text.Text` using alignment=9 (top-right). Logs `[OVERLAY] stamp applied` or `[OVERLAY] failed: …` if filter missing.
- Overlay is applied **after** tonemap but **before** dither to RGB24, guaranteeing it survives to the final writer.

## Verification path
- Enabled via `TM.verify`.
- `_pick_verify_frame` skips frame 0, scans from ~10s in (`VERIFY_START_FRAME=240`) every 240 frames up to 2000, selecting the first with luma ≥ 0.10, else brightest sampled, else middle. Logs selection.
- Produces naive SDR via `resize.Spline36` to RGB24 (BT.709/BT.1886). Tonemapped clip is also converted to RGB24 via `resize.Point`.
- Diff computed with `std.Expr('x y - abs')`, stats via `std.PlaneStats`, logs `[VERIFY] diff avg=… max=…` for the picked frame (non-zero expected on HDR).

## Fallback & error handling
- If HDR detection fails or placebo unavailable, clip converts directly to RGB24 using `resize.Spline36` with sensible matrix/range defaults.
- Any exception inside HDR branch logs `[ERROR] Color processing failed …` and falls back to SDR conversion (still dithered to RGB24).
- Verification failure logs but never crashes; tonemap retries prevent silent SDR output unless all attempts fail, in which case the fallback branch runs loudly.

Use this as the ground truth when bringing the current pipeline up to parity.
