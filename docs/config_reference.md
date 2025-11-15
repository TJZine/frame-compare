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

## `[screenshots].auto_letterbox_crop`

Auto letterbox cropping accepts `"off"`, `"basic"`, or `"strict"` (booleans still coerce to `"off"`/`"strict"` during
config loading). Use `"off"` to preserve bars exactly as provided. `"basic"` reuses the post-aligned cropped width/height
when running the ratio heuristic, so horizontally cropped clips no longer trick the detector into shaving the other
sources vertically. `"strict"` applies the legacy behaviour unchanged: it analyses the raw source dimensions, uses the
widest clip as the target ratio, and aggressively trims top/bottom bars on any clip that appears narrower even if the
difference comes from prior horizontal crops. The planner normalises every value to one of these strings before
rendering and surfaces the resolved mode in the CLI JSON tail for quick audits.

## `[screenshots].rgb_dither`

Controls how the final 16-bit frame is quantised to RGB24.

- `"error_diffusion"` (default): VapourSynth uses error diffusion; FFmpeg falls back to deterministic ordered dithering for repeatability.
- `"ordered"`: Forces ordered dithering in both backends.
- `"none"`: Disable dithering during the final RGB24 hop (not recommended for noisy footage).

Earlier conversions (8/10/12-bit → 16-bit) always run with `dither_type="none"` to maintain determinism. The setting only applies to the last conversion step when producing PNG output.

## `[screenshots].export_range`

Controls the RGB range written to PNG files at the end of the pipeline.

| Value | Behaviour | When to use |
| ----- | --------- | ----------- |
| `"full"` (default) | Expands limited-range SDR (16–235) to full-range RGB (0–255) before saving, stamping `_SourceColorRange=1` for provenance. | General-purpose comparisons on PC displays and browsers that expect sRGB PNGs. |
| `"limited"` | Preserves the detected source range, matching Rec.709 video behaviour. `_SourceColorRange` is omitted. | Workflows that rely on video-range PNGs or downstream tooling that compensates for studio range. |

## `[color]` automatic range detection

The pipeline now samples the luma plane when range metadata is missing or indicates full-range SDR. When samples land inside the studio range (≈16–235 for 8-bit sources), the clip is treated as limited and a warning is emitted. This prevents washed-out PNG exports for masters that omit container/VUI flags. Operators can still force behaviour per clip via `[color].color_overrides`, and mismatches (metadata says limited but the signal spans 0–255) surface as warnings for manual review.

## `[color].debug_color`

Setting `debug_color = true` (or supplying `--debug-color` to the CLI) activates the colour investigation toolkit:

- PlaneStats min/max values and frame-property metadata (`_Matrix`, `_Transfer`, `_Primaries`, `_ColorRange`) are logged after post-normalisation, post-geometry, the legacy RGB24 conversion, and the final `_ensure_rgb24` stage.
- Intermediate PNGs are emitted to `screens/debug/<clip>/<frame>_{post_normalisation|post_geometry|legacy_rgb24|post_rgb24}.png`, enabling pixel-for-pixel comparisons with the legacy pipeline.
- Frame-info overlays and diagnostic text are suppressed so each debug PNG represents raw image content.

Use this mode when tracking range regressions between the modern pipeline and `Legacy/comp.py`. Debug artefacts share frame indices with the main output directory, making diffs straightforward.

```python
import logging
from frame_compare import run_cli

logging.basicConfig(level=logging.INFO)
run_cli(
    config_path="config/config.toml",
    root_override=".",
    debug_color=True,
    quiet=False,
    verbose=True,
)
```

## `[color].dst_min_nits`, `knee_offset`, and preset tuning

- `dst_min_nits` lifts the HDR toe before the final RGB24 conversion. Values between **0.18–0.25** keep detail in crushed shadows while avoiding milky blacks. Lower values increase contrast at the cost of near-black texture.
- `knee_offset` (default **0.50**) controls the BT.2390 shoulder; smaller values compress highlights earlier while larger values push the roll-off further out. The extended preset map (`reference`, `bt2390_spec`, `filmic`, `spline`, `contrast`, `bright_lift`, `highlight_guard`) records the preferred knee alongside target nits and DPD behaviour.
- CLI overrides are available via `--tm-dst-min` and `--tm-knee` for ad-hoc tuning without editing the config file.

## `[color].dpd_preset` and `dpd_black_cutoff`

- `dpd_preset` selects libplacebo's dynamic-peak-detection profile: `off`, `fast`, `balanced`, or `high_quality`. The presets default to `high_quality` for stills, but you can switch per run with `--tm-dpd-preset`.
- `dpd_black_cutoff` (default **0.01**) skips a fraction of PQ blacks when sampling highlights for DPD. Keep it within **0–0.05**. When `[color].dynamic_peak_detection = false`, the loader and CLI coerce the preset to `off` and zero out the cutoff.

## `[color].smoothing_period`, `scene_threshold_low`, `scene_threshold_high`

- `smoothing_period` controls the IIR window (in frames) used by dynamic peak detection. Increase it (default **45**) to dampen short-lived highlights; set to `0` to disable smoothing.
- `scene_threshold_low` / `scene_threshold_high` (defaults **0.8** / **2.4**) define the range of scene brightness changes (in % PQ) where smoothing relaxes to avoid sluggish scene transitions. Keep `scene_threshold_high >= scene_threshold_low`.

## `[color].percentile` and `contrast_recovery`

- `percentile` (default **99.995**) decides which brightness percentile counts as the scene peak. Values slightly below 100 (for example `99.99`) continue to mimic libplacebo’s `high_quality` preset.
- `contrast_recovery` (default **0.3**) blends a fraction of the high-frequency HDR detail back after tone mapping. Higher values increase perceived sharpness but can introduce ringing on some content.

## `[color].metadata`, `use_dovi`, `visualize_lut`, `show_clipping`

- `metadata` picks the tone-mapping metadata source: `auto`, `none`, `hdr10`, `hdr10+`, or `luminance` (or the numeric codes `0-4`).
- `use_dovi` lets you force (`true`), disable (`false`), or auto-detect (`auto`) Dolby Vision RPU usage when available.
- `visualize_lut` toggles libplacebo’s LUT visualisation, replacing the output frames with the tone-mapping curve for debugging.
- `show_clipping` highlights pixels clipped during tone mapping (handy for quick QA runs).

## `[color].post_gamma_enable` / `post_gamma`

Set `post_gamma_enable = true` to apply a limited-range (`16`–`235`) `std.Levels` gamma adjustment after tonemapping and before overlays/geometry. This stage is disabled by default; when enabled, keep `post_gamma` close to **1.00** (for example, `0.95` for a subtle lift). The CLI provides `--tm-gamma <value>` to tweak a single run and `--tm-gamma-disable` to force the stage off without editing `config.toml`.

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
