# Geometry pipeline notes

This document supplements `docs/current_pipeline_trace.md` with details specific to
odd-pixel geometry support that was introduced for subsampled SDR content.

## Why subsampled clips need a full-chroma pivot

VapourSynth enforces modulus-two crops and pads on formats that carry chroma
subsampling (for example 4:2:0 and 4:2:2). When two clips of the same width are
misaligned by a single pixel vertically or horizontally, attempting to crop or
pad the 4:2:0 source directly raises a "mod 2" error. The screenshot planner now
flags these plans with `requires_full_chroma` and the renderer temporarily
promotes the working clip to **YUV444P16** so that odd offsets can be applied
symmetrically without scaling. The pivot is deterministic and only active when
the planner reports odd geometry on a subsampled axis.

## Axis-aware promotion

The planner inspects the crop and pad deltas per axis and the source format's
subsampling characteristics before asking for a pivot. The renderer only
promotes when:

- The clip is SDR (HDR clips continue on the existing RGB48+tonemap path).
- The color family is YUV and the format reports subsampling along at least one
  axis.
- The plan includes an odd crop or pad on the same subsampled axis.

The axis information surfaces in logs and the Rich console, making it obvious if
we pivoted because of vertical, horizontal, or mixed odd adjustments. If a plan
is all-even or the clip is already 4:4:4/RGB, the fast path is retained.

## Dithering stages

All intermediate promotions (8/10/12-bit → 16-bit) run with `dither_type="none"`
so that the full precision is preserved for geometry work. The configured
`screenshots.rgb_dither` value only applies to the final **16-bit → RGB24** hop.
- VapourSynth path: honours the configured value directly.
- FFmpeg path: `error_diffusion` is mapped to deterministic ordered dithering to
  avoid RNG usage; `ordered` and `none` pass through unchanged.

## FFmpeg parity

When the CLI runs with `screenshots.use_ffmpeg = true` the renderer injects
`format=yuv444p16` before the crop/pad steps and appends `format=rgb24` with the
selected dithering strategy. FFmpeg does not expose per-axis subsampling
metadata in this flow, so the planner's `requires_full_chroma` flag is used as a
single decision point. The axis label from the plan is still surfaced in console
notes to show whether the promotion was driven by vertical, horizontal, or both
odd adjustments.

## Console visibility

Whenever the pivot activates the CLI emits:

- A structured INFO log (`Odd-geometry on subsampled SDR → promoting to
  YUV444P16 …`), and
- A Rich console note (`Full-chroma pivot active …`) showing the policy, axis,
  and format/backend that triggered the promotion.

The note appears for both VapourSynth and FFmpeg paths and helps operators
confirm that odd-geometry cases are handled intentionally.
