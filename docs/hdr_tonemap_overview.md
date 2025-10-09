# HDR → SDR Pipeline Overview

This document summarises the rebuilt tone-mapping path introduced in September 2025. It complements
`docs/legacy_tonemap_pipeline.md`, which captures the original placebo-based behaviour used as
reference.

## Summary
- All clips destined for screenshot rendering are processed through `vs_core.process_clip_for_screenshot` immediately
  before geometry adjustments. The returned node is the one written to disk.
- HDR sources (PQ/HLG + BT.2020) are converted to RGB48 via zimg, normalised (`_Matrix=0`, `_ColorRange=0`,
  `_Transfer`/`_Primaries` preserved), then tonemapped through libplacebo with retries and logging.
- SDR sources bypass tonemapping but still receive an overlay stamp (unless disabled) so the output signalling is
  unambiguous.
- Verification compares the tonemapped RGB24 output against a naive RGB24 conversion using `std.Expr('x y - abs')` on a
  representative frame picked after the opening 10 seconds. Logs surface the selected frame and Δ statistics before any
  screenshots are emitted.
- The overlay (top-right) reports the effective curve/DPD/target nits and propagates to FFmpeg renders via `drawtext`.
  Frame props are copied back after the text pass so `_Tonemapped` (and other metadata) survive downstream.
  When `color.strict=true`, overlay or verification failures abort with `ScreenshotWriterError` / `ClipProcessError`.

## Presets & configuration
`[color]` defines the behaviour, defaulting to the "reference" preset:

| Preset | Tone curve | Target nits | DPD |
| ------ | ---------- | ----------- | --- |
| reference | `bt.2390` | 100 | enabled |
| contrast  | `mobius`  | 120 | disabled |
| filmic    | `hable`   | 100 | enabled |

Set `preset="custom"` to honour manual `tone_curve`, `target_nits`, and `dynamic_peak_detection`. `dst_min_nits` feeds
libplacebo's `dst_min`. Logs include `[TM INPUT]` and `[TM APPLIED]` lines showing the inferred color props and the
resolved curve/DPD/nits.

## Log cheat sheet
- `[TM INPUT]` — Source properties at the start of processing. Includes Matrix/Transfer/Primaries/Range.
- `[Tonemap attempt A/B failed]` — Retry ladder when libplacebo rejects the hinted/inferred colours.
- `[TM APPLIED]` — Tonemap succeeded. Includes curve, dpd flag, target nits, and the src_csp hint used.
- `[TM BYPASS]` — Run completed without tonemap. `reason=` identifies SDR detection or explicit disablement.
- `[OVERLAY]` — First successful overlay application per clip, or an error message if the filter is missing.
- `[VERIFY]` — Logs chosen frame (`frame=`) plus average/max deltas. The automatic frame picker also logs
  threshold/best-frame fallbacks when necessary.

All `[VERIFY]` messages appear before any screenshot writer is invoked so silent failures cannot slip through.

## Verification frame selection
The auto-search skips the first `verify_start_seconds` (default 10s), samples every `verify_step_seconds` (default 10s)
up to `verify_max_seconds`. The first frame with `PlaneStatsAverage >= verify_luma_threshold` (default 0.10) is used.
If none qualify, the brightest sampled frame is used, otherwise the clip midpoint. `verify_frame` forces a fixed index
and `verify_auto=false` falls back to the midpoint. When verification executes, the pipeline also saves the diff stats to
logs and sets `_Tonemapped="placebo:{curve},dpd={0|1},dst_max={nits}"` on the processed frames.

## Overlay & writer behaviour
- Overlay text defaults to `Tonemapping Algorithm: {tone_curve} dpd = {dynamic_peak_detection} dst = {target_nits} nits` and accepts `{preset}` and `{reason}`
  placeholders. You can fully override the template in config.
- Diagnostic overlay mode now appends the final render resolution (original → target), the mastering display luminance parsed
  from frame props when HDR tonemapping is applied, and `Frame Selection Type: …` sourced from persisted selection metadata.
  The previous MAX/AVG measurement line has been retired to keep the overlay concise.
- VapourSynth renders apply the overlay after all geometry adjustments (`CropRel`/`Spline36`) but before the final
  dither to RGB24. FFmpeg renders append a matching `drawtext` filter positioned at `x=w-tw-10:y=10`.
- The overlay lives in the top-right corner to avoid frame info overlays (when enabled).

## Failure handling
- Missing libplacebo yields `ClipProcessError`. Tonemap retries escalate from hinted → inferred → forced PQ/2020 before
  failing hard.
- Overlay failures log `[OVERLAY]` and respect `color.strict`.
- Verification failures log `[VERIFY] … failed` and honour `color.strict`.
- When tonemap is bypassed (SDR or disabled), the code still ensures `_Matrix=0`, `_ColorRange=0`, and overlays the
  bypass reason so downstream tooling sees consistent metadata.

Refer to `docs/legacy_tonemap_pipeline.md` for the legacy flow comparison. The runtime code paths now align with that
behaviour while exposing operators in the `[color]` section for future overrides/flags.
