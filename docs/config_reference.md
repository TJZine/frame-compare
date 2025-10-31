# Configuration reference supplements

This page captures additional context for configuration keys that were added as
part of the odd-geometry remediation. Refer to `docs/README_REFERENCE.md` for
the complete tables; the sections below focus on behaviour and operator
trade-offs.

## `[screenshots].odd_geometry_policy`

| Value | Behaviour | When to use |
| ----- | --------- | ----------- |
| `"auto"` (default) | Promote to YUV444P16 only when the planner detects an odd crop or pad on an axis that is subsampled (vertical for 4:2:0/4:2:2, horizontal for 4:2:2). Keeps the fast path for even-only operations and for clips that are already 4:4:4/RGB. | Recommended. Balances quality and performance without operator input. |
| `"force_full_chroma"` | Always pivot SDR clips to YUV444P16 before geometry, regardless of crop/pad parity. Guarantees symmetric behaviour for custom edits at the expense of additional processing. | When matching pixel grids from different masters matters more than render time. |
| `"subsamp_safe"` | Never pivot. The planner rebalance crops/pads to even numbers instead, logging a warning about potential one-pixel shifts. | Legacy compatibility or when deterministic pivoting is undesirable. |

The policy has no effect on HDR content (the HDR→SDR pipeline continues to run in high-bit-depth RGB).

## `[screenshots].rgb_dither`

Controls how the final 16-bit frame is quantised to RGB24.

- `"error_diffusion"` (default): VapourSynth uses error diffusion; FFmpeg falls back to deterministic ordered dithering for repeatability.
- `"ordered"`: Forces ordered dithering in both backends.
- `"none"`: Disable dithering during the final RGB24 hop (not recommended for noisy footage).

Earlier conversions (8/10/12-bit → 16-bit) always run with `dither_type="none"` to maintain determinism. The setting only applies to the last conversion step when producing PNG output.

## `[color]` automatic range detection

The pipeline now samples the luma plane when range metadata is missing or indicates full-range SDR. When samples land inside the studio range (≈16–235 for 8-bit sources), the clip is treated as limited and a warning is emitted. This prevents washed-out PNG exports for masters that omit container/VUI flags. Operators can still force behaviour per clip via `[color].color_overrides`, and mismatches (metadata says limited but the signal spans 0–255) surface as warnings for manual review.

## `[color].debug_color`

Setting `debug_color = true` (or supplying `--debug-color` to the CLI) activates the colour investigation toolkit:

- PlaneStats min/max values and frame-property metadata (`_Matrix`, `_Transfer`, `_Primaries`, `_ColorRange`) are logged after post-normalisation, post-geometry, the legacy RGB24 conversion, and the final `_ensure_rgb24` stage.
- Intermediate PNGs are emitted to `screens/debug/<clip>/<frame>_{post_normalisation|post_geometry|legacy_rgb24|post_rgb24}.png`, enabling pixel-for-pixel comparisons with the legacy pipeline.
- Frame-info overlays and diagnostic text are suppressed so each debug PNG represents raw image content.

Use this mode when tracking range regressions between the modern pipeline and `Legacy/comp.py`. Debug artefacts share frame indices with the main output directory, making diffs straightforward.

## `[report]`

The HTML report bundles the rendered screenshots with a slider-based viewer and
metadata, giving teams an offline alternative to slow.pics uploads. All paths
remain relative to the workspace root and require no HTTP server.

| Key | Purpose | Default |
| --- | --- | --- |
| `enable` | Generate the report bundle alongside `screens/`. | `false` |
| `open_after_generate` | Launch `index.html` in the default browser after a run. | `true` |
| `output_dir` | Target subdirectory under the workspace root. | `"report"` |
| `title` | Custom report title (falls back to inferred metadata). | `""` |
| `default_left_label` / `default_right_label` | Preferred encodes for the slider’s left/right panes. | `""` |
| `include_metadata` | Controls the JSON payload: `"minimal"` or `"full"`. | `"minimal"` |
| `thumb_height` | Reserved for future thumbnail support; keep at `0` today. | `0` |
| `default_mode` | Viewer mode (`slider`, `overlay`, `difference`, `blink`) for initial render. | `"slider"` |

The viewer now mirrors slow.pics ergonomics: zoom persists per session (slider, +/- buttons, or Ctrl/⌘ + mouse wheel), presets cover Actual/Fit/Fit Height/Fill, and you can re-anchor content with the alignment dropdown or pan (drag once zoomed past fit, or hold Space + drag). These choices are stored in `localStorage`, so switching frames keeps the same layout.
