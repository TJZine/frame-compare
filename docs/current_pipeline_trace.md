# Current Screenshot Pipeline Trace (2025-09-28)

Scope: `frame_compare.py` + `src/screenshot.py` + `src/frame_compare/vs`.

## Stage summary (HDR path)
| Stage | Variable | Callsite | Format | _Matrix | _Transfer | _Primaries | _ColorRange | _Tonemapped | Notes |
| ----- | -------- | -------- | ------ | ------- | --------- | ---------- | ----------- | ----------- | ----- |
| 0 | `clip` | `frame_compare._init_clips → vs_core.init_clip` | Source native (usually YUV420) | Source prop (e.g. 9) | 16 or 18 | 9 | 1 (limited) | — | Raw decode straight from LWLibavSource. |
| 1 | `rgb16` | `vs_core.process_clip_for_screenshot` (`resize.Spline36`) | `RGB48` | 0 (forced) | From stage 0 | From stage 0 | 0 (forced full) | — | `_normalize_rgb_props` stamps RGB props so libplacebo can infer linearisation. |
| 2 | `tonemapped` | `_tonemap_with_retries` | `RGB48`/`RGBS` | 0 | 1 (BT.1886) | 1 (BT.709) | 0 | `placebo:{curve},dpd={dpd},dst_max={nits}` | Retries hinted → inferred → PQ fallback, logging `[TM INPUT]` / `[TM APPLIED]` / failures. |
| 3 | `tm_rgb24` | Verification path (`resize.Point`) | `RGB24` | 0 | 1 | 1 | 0 | Same as stage 2 | Used only for diff vs naive SDR, never written to disk. |
| 4a | `render_clip` (VapourSynth writer) | `_save_frame_with_fpng` | `RGB24` | 0 | 1 | 1 | 0 | Preserved | Crop/resize, optional frame-info overlay, `_apply_overlay_text` (alignment=9). Diagnostic mode layers the base template plus render resolution, HDR mastering luminance when tonemapping ran, and cached `Frame Selection Type` metadata. `_ensure_rgb24` stamps BT.709/BT.1886 full-range props for downstream sanity. |
| 4b | FFmpeg render | `_save_frame_with_ffmpeg` | File stream | N/A | N/A | N/A | N/A | N/A | FFmpeg redoes crop/scale and injects top-right `drawtext` overlay; tonemapped pixels come from stage 2 clip via `result.clip` when available. |

## SDR bypass path
- When `_props_signal_hdr` is false or `color.enable_tonemap=false`, the function returns the original clip (stage 0) untouched.
- Overlay text still resolves (reason “SDR source” or “Tonemap disabled”) so every screenshot receives a stamp.
- Verification is skipped, logging `[TM BYPASS] …` before returning.
- `_save_frame_with_fpng` / FFmpeg perform the same geometry + overlay steps on the SDR clip, then `_ensure_rgb24` converts to RGB24 for writing.

## Overlay & verification guarantees
- `process_clip_for_screenshot` runs **before** geometry planning; the resulting node is the one fed into `_plan_geometry` and ultimately into the writers.
- Verification (`verify_enabled`) occurs on the tonemapped node, selecting a non-trivial frame via `_pick_verify_frame` (skip ≥10s, sample every 10s up to 90s, fall back to brightest or midpoint). Logs `[VERIFY]` with frame/Δ before any screenshots emit.
- Overlay text is applied once per clip: VapourSynth path uses `core.text.Text(..., alignment=9)`, FFmpeg path mirrors via `drawtext` anchored top-right. The diagnostic branch now augments the base tonemap string with the render resolution summary, mastering display luminance (only when tonemapping applied), and the cached frame-selection label. Failures honour `color.strict` and raise.

## Open issues observed
- Maintain coverage to ensure `_Tonemapped` flag survives future overlay/crop rewrites (current `std.CopyFrameProps` guard keeps it intact).

This trace is the baseline for verifying ongoing changes against the retired placebo pipeline captured in the 2025-09-22 regression notes.
