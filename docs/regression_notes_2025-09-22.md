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
