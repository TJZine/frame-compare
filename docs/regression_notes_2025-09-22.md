# HDR Pipeline Regression Notes

Date: 2025-09-22

## Behaviour carried forward from `legacy/compv4_improved.py`
- **YUV→RGB staging** now always runs through zimg Spline36 into RGB48 with the original transfer/primaries/range values
  preserved, then normalises props (`_Matrix=0`, `_ColorRange=0`) before calling libplacebo.
- **libplacebo retry ladder** mirrors the legacy script: first try with inferred `src_csp`, fall back to placebo inference,
  then force PQ/BT.2020 while logging `[Tonemap attempt X failed]` messages.
- **Frame props** for the final clip include `_Tonemapped="placebo:<curve>,dpd=<>,dst_max=<>"`, just as the legacy
  pipeline stamped on each frame.
- **Verification** uses the same RPN diff (`std.Expr('x y - abs')`) and logs both the frame picked and Δ averages/maxes
  before any screenshots are written.
- **Overlay positioning** is reimplemented via `text.Text(..., alignment=9)` so the stamp is guaranteed to survive to the
  writer, matching the legacy overlay flow.

## Improvements / resilience upgrades
- Overlay/verification issues now emit `[OVERLAY] …` and `[VERIFY] … failed` logs and optionally abort when
  `color.strict=true` (legacy only logged).
- The auto verification frame picker skips the first 10 seconds, samples every 10 seconds, and reports the brightest
  fallback when no frame clears the luma threshold.
- Both the VapourSynth and FFmpeg writers enforce the overlay; FFmpeg uses a mirrored `drawtext` expression so sequence
  renders stay in sync.
- SDR bypasses log `[TM BYPASS reason=…]` and still normalise props to RGB full-range to avoid downstream range
  mismatches.

Use this note when validating regressions against upstream pipelines.

---

Date: 2025-09-28

## Additional parity fixes
- `_ensure_rgb24` now stamps RGB targets with integer props (`_Matrix=0`, `_Primaries=1`, `_Transfer=1`, `_ColorRange=0`) so
  exported PNGs advertise full-range BT.709/BT.1886, matching the legacy writer and avoiding MaskedMerge range clashes.
- Overlay rendering uses `std.CopyFrameProps` after `text.Text` to preserve `_Tonemapped` and other metadata, ensuring any
  downstream merge/analysis sees the same per-frame flags the tonemap stage emitted.
- Tonemap processing now falls back to the global `vs.core` object when a clip lacks a `.core` attribute (common on
  Windows community builds and Python 3.13), preventing "Clip has no associated VapourSynth core" during frame selection.
- Frame-window logic now validates `analysis.ignore_lead_seconds`, `ignore_trail_seconds`, and `min_window_seconds`,
  surfacing a clear error if these values are not numeric instead of failing with a Python type error mid-run.
- VapourSynth frame-prop stamping detects bound methods (e.g. `clip.std.SetFrameProp`) and avoids passing the clip twice,
  eliminating the `float(... VideoNode)` crash encountered on Windows/Python 3.13 during analysis tonemapping.
- Core resolution now checks `vapoursynth.get_core()` as well as `vapoursynth.core`, so environments where the singleton is
  exposed only via the helper (observed with VapourSynth R72 + Python 3.13 + uv) no longer trip the "Clip has no
  associated VapourSynth core" error.
- libplacebo detection now honours both `core.libplacebo` and `core.placebo`, matching the legacy script and fixing
  VapourSynth R72 installs that expose the namespace without the `lib` prefix.
- Analysis metrics conversion now passes the correct `matrix_in`/color metadata when converting RGB tonemapped clips to
  grayscale, preventing VapourSynth's "Matrix must be specified" error and ensuring metrics are gathered instead of
  falling back to synthetic data.
