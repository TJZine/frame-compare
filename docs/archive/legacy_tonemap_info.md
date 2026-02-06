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

| Preset | Tone curve | Target nits | DPD | Notes |
| ------ | ---------- | ----------- | --- | ----- |
| reference | `bt.2390` | 100 | enabled | High-quality baseline: smoothing 45f, percentile `99.995`, contrast recovery `0.30`. |
| bt2390_spec | `bt.2390` | 100 | enabled | Spec-faithful: neutral cutoff, gentle contrast recovery `0.05`. |
| filmic | `bt.2446a` | 100 | enabled | Cinematic shoulder with knee `0.58`, percentile `99.9`, subtle contrast lift. |
| spline | `spline` | 105 | enabled | Smooth spline roll-off, mids gently lifted with contrast `0.25`. |
| contrast | `bt.2390` | 110 | enabled | Punchier mids/highs, contrast recovery `0.45`, DPD kept on to protect highlights. |
| bright_lift | `bt.2390` | 130 | enabled | Aggressively brightens mids, dst_min `0.22`, contrast `0.50`, best for dark masters. |
| highlight_guard | `bt.2390` | 90 | enabled | Lowers peak brightness, smoothing 50f, keeps highlights under control on harsh grades. |

Set `preset="custom"` to honour manual `tone_curve`, `target_nits`, and `dynamic_peak_detection`. `dst_min_nits` feeds
libplacebo's `dst_min`. `knee_offset` forwards to `tone_mapping_param` for BT.2390 curves, and `dpd_preset` selects the
libplacebo peak-detection mode (`off`, `fast`, `balanced`, `high_quality`). Logs include `[TM INPUT]` and `[TM APPLIED]`
lines showing the inferred color props and the resolved curve/DPD/nits. Runtime tweaks are available via CLI flags such
as `--tm-preset`, `--tm-knee`, `--tm-dst-min`, and `--tm-dpd-preset`, making it easy to audition settings before
committing them to `config.toml`.

For finer control, additional `[color]` keys expose libplacebo’s smoothing and debugging options:

- `smoothing_period`, `scene_threshold_low`, and `scene_threshold_high` steer the HDR peak smoothing window.
- `percentile` and `contrast_recovery` allow you to match the libplacebo `high_quality` preset (`99.995` / `0.3`) or dial them back.
- `metadata` and `use_dovi` select the metadata source (`auto`, `none`, `hdr10`, `hdr10+`, `luminance`) and whether Dolby Vision RPUs are consumed.
- `visualize_lut` renders the tone-mapping LUT instead of frames, while `show_clipping` highlights clipped pixels—useful for quick QA passes.
Matching CLI overrides (`--tm-smoothing`, `--tm-scene-low`, `--tm-percentile`, `--tm-contrast`, `--tm-metadata`, `--tm-use-dovi`, `--tm-visualize-lut`, `--tm-show-clipping`) keep experimentation fast.

The screenshot writer controls the final PNG range via `[screenshots].export_range`. The default `"full"` setting expands
limited-range SDR pixels to full-range RGB just before export (recording the original value in `_SourceColorRange`), while
`"limited"` preserves the source range for workflows that expect video-range PNGs.

The optional post-tonemap gamma stage applies a limited-range (`16`–`235`) `std.Levels` adjustment after tonemapping but
before overlays, geometry, and dithering, preserving video-level encoding. Enable it with `[color].post_gamma_enable = true` (or `--tm-gamma <value>`)
when you need a gentle lift (`post_gamma ≈ 0.95`) for especially dark masters; use `--tm-gamma-disable` to force it off
for a single run.

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

# Legacy Frame Compare: Color Operations Archaeology Report

**Purpose**: Extract ground-truth from the legacy Frame Compare repo to fill the spec gap for Frame Compare 2.0 Phase 3.4 "VS Color Operations".

---

## 1) Candidate Public API (Legacy)

### Core Color Functions

- **`src/frame_compare/vs/color.py:418-519`** — `normalise_color_metadata(clip, source_props, *, color_cfg, file_name, warning_sink) -> tuple[Any, Mapping, tuple]`
  - Purpose: Main entry point for ensuring colour metadata is usable, applying heuristics and overrides when needed.
  - Notes: Returns `(clip_with_props, props_dict, (matrix, transfer, primaries, color_range))`. Calls `resolve_color_metadata`, applies overrides, runs `_guess_default_colourspace`, runs `_adjust_color_range_from_signal`, and applies frame props via `SetFrameProps`.

- **`src/frame_compare/vs/color.py:118-182`** — `_guess_default_colourspace(clip, props, matrix, transfer, primaries, color_range, *, color_cfg) -> tuple[Optional[int], ...]`
  - Purpose: Infer missing color metadata based on frame height and configuration defaults.
  - Notes: SD (≤576px) defaults to SMPTE170M, HD (≥720px) defaults to BT.709. Returns early unchanged if HDR is detected via `props_signal_hdr()`.

- **`src/frame_compare/vs/color.py:368-415`** — `_adjust_color_range_from_signal(clip, *, color_range, warning_sink, file_name, range_inferred, range_from_override) -> Optional[int]`
  - Purpose: Sample luma bounds to detect/confirm color range when metadata is missing or ambiguous.
  - Notes: Uses `_compute_luma_bounds()` to sample Y min/max. Defaults to limited if sampling unavailable. Warns if tagged limited but samples span full.

- **`src/frame_compare/vs/color.py:240-327`** — `_detect_rgb_color_range(core, clip, *, log, label, max_samples) -> tuple[Optional[int], Optional[str]]`
  - Purpose: Sample RGB plane stats to classify range as limited or full.
  - Notes: Uses `std.PlaneStats()` on RGB clip, samples multiple frame indices, classifies based on 8-bit normalised min/max thresholds (limited ≤247, full spans both ends).

### Property Helpers

- **`src/frame_compare/vs/props.py:246-270`** — `resolve_color_metadata(props) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]`
  - Purpose: Extract (matrix, transfer, primaries, range) from frame props dict.
  - Notes: Checks both `_Matrix`/`Matrix` forms. Coerces string names via mappings. Returns `(matrix, transfer, primaries, color_range)` order. Filters code=2 (unspecified) to None.

- **`src/frame_compare/vs/props.py:188-209`** — `props_signal_hdr(props) -> bool`
  - Purpose: Detect HDR from frame properties.
  - Notes: Returns True if any of: HDR primaries (code 9), HDR transfer (codes 16/18), or mastering metadata keys present. Relaxed to accept partial signals (single flag or just MDL/CLL).

### Screenshot Conversion

- **`src/frame_compare/screenshot/helpers.py:276-414`** — `ensure_rgb24(core, clip, frame_idx, *, source_props, rgb_dither, target_range, expand_to_full) -> Any`
  - Purpose: Convert clip to 8-bit RGB24 with proper color handling.
  - Notes: Uses `resize.Point` for conversion. Applies matrix_in/transfer_in/primaries_in/range_in from resolved props. Defaults missing YUV props to BT.709/limited. Optionally expands limited to full via `std.Levels`.

- **`src/frame_compare/screenshot/helpers.py:132-143`** — `resolve_resize_color_kwargs(props) -> Dict[str, int]`
  - Purpose: Build dict of `matrix_in`, `transfer_in`, `primaries_in`, `range_in` for resize calls.
  - Notes: Values only included if not None from `resolve_color_metadata()`.

### Tonemap Processing

- **`src/frame_compare/vs/tonemap.py:1049-1089`** — YUV→RGB conversion for tonemapping
  - Purpose: Convert HDR YUV to RGB48 for libplacebo processing.
  - Notes: Uses `resize.Spline36` with matrix_in, transfer_in, primaries_in, range_in. Matrix defaults to 1 if None. Range defaults to limited.

---

## 2) Behavior Rules (Legacy)

### BT.709 vs BT.2020

**Evidence**: `src/frame_compare/vs/color.py:139-166`

```python
is_sd = bool(height is not None and height <= 576)
is_hd = bool(height is not None and height >= 720)
# ...
if matrix is None:
    matrix = int(
        getattr(vs_module, "MATRIX_SMPTE170M" if is_sd else "MATRIX_BT709", 6 if is_sd else 1)
    )
if primaries is None:
    primaries = int(
        getattr(vs_module, "PRIMARIES_SMPTE170M" if is_sd else "PRIMARIES_BT709", 6 if is_sd else 1)
    )
```

**Rule**:

- **SD (height ≤ 576)**: Default matrix/primaries/transfer = SMPTE170M (code 6)
- **HD (height ≥ 720)**: Default matrix/primaries/transfer = BT.709 (code 1)
- **Intermediate (577-719)**: Falls through to HD defaults (uses `default_matrix_hd` config or BT.709)

**HDR BT.2020 Defaults** — `src/frame_compare/vs/color.py:476-502`

```python
if hdr_detected:
    if matrix is None:
        matrix = int(getattr(vs_module, "MATRIX_BT2020_CL", getattr(vs_module, "MATRIX_BT2020_NCL", 9)))
    if primaries is None:
        primaries = int(getattr(vs_module, "PRIMARIES_BT2020", 9))
    if transfer is None:
        transfer = int(getattr(vs_module, "TRANSFER_ST2084", 16))
```

**Rule**: When HDR is detected (via `props_signal_hdr`), missing props backfill to BT.2020 (matrix=9) + ST2084/PQ (transfer=16).

---

### Limited vs Full Range

**Evidence**: `src/frame_compare/vs/color.py:177-181`

```python
if color_range is None:
    color_range = configured.get("range")
    if color_range is None:
        color_range = int(getattr(vs_module, "RANGE_LIMITED", 1))
```

**Rule**: **Default range is ALWAYS limited (code 1)** when not specified.

**Evidence** for range adjustment: `src/frame_compare/vs/color.py:397-406`

```python
if range_inferred or color_range in (None, full_code):
    if 12.0 <= y_min <= 20.0 and y_max <= 245.0:
        message = f"[COLOR] {label} lacks reliable colour-range metadata; treating as limited"
        return limited_code
```

**Rule**: If range is unspecified or full, but luma samples fall within limited-range bounds (min 12-20, max ≤245), force to limited.

**Evidence** for conflict warning: `src/frame_compare/vs/color.py:407-414`

```python
if color_range == limited_code and (y_min < 4.0 or y_max > 251.0):
    message = f"[COLOR] {label} is tagged limited but sampled values span full range"
```

**Rule**: Warn (but don't override) if tagged limited but samples suggest full range.

---

### Unspecified / Missing Props

**Evidence**: `src/frame_compare/vs/props.py:234-243`

```python
def _normalise_resolved_code(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    # ...
    if code == 2:
        return None  # "Unspecified" treated as missing
    return code
```

**Rule**: VapourSynth code 2 ("unspecified") is normalised to `None`, triggering default inference.

**Evidence** for screenshot fallback: `src/frame_compare/screenshot/helpers.py:340-362`

```python
if color_family == yuv_constant:
    defaults: Dict[str, int] = {}
    if "matrix_in" not in resize_kwargs:
        defaults["matrix_in"] = int(getattr(vs, "MATRIX_BT709", 1))
    if "transfer_in" not in resize_kwargs:
        if transfer_valid:
            defaults["transfer_in"] = int(cast(int, transfer))
        else:
            defaults["transfer_in"] = int(getattr(vs, "TRANSFER_BT709", 1))
    # ... same for primaries_in
    if "range_in" not in resize_kwargs:
        defaults["range_in"] = int(getattr(vs, "RANGE_LIMITED", 1))
```

**Rule**: For YUV→RGB conversion when props missing, default to **BT.709 matrix/transfer/primaries + limited range**.

---

## 3) VapourSynth Pipeline Details

### Conversions Used

#### YUV → RGB for Screenshots

**Evidence**: `src/frame_compare/screenshot/helpers.py:380-393`

```python
converted = cast(
    Any,
    point(
        clip,
        format=vs.RGB24,
        range=output_range,
        dither_type=dither,
        **resize_kwargs,  # contains matrix_in, transfer_in, primaries_in, range_in
    ),
)
```

- **Function**: `resize.Point`
- **Parameters**: `format=vs.RGB24`, `range=<output_range>`, `dither_type=<error_diffusion|random|ordered>`, `matrix_in`, `transfer_in`, `primaries_in`, `range_in`

#### YUV → RGB for HDR Tonemapping

**Evidence**: `src/frame_compare/vs/tonemap.py:1049-1057`

```python
rgb16 = spline36(
    clip,
    format=vs_module.RGB48,
    matrix_in=matrix_in if matrix_in is not None else 1,
    transfer_in=transfer_in if transfer_in is not None else None,
    primaries_in=primaries_in if primaries_in is not None else None,
    range_in=color_range_in if color_range_in is not None else range_limited,
    dither_type="error_diffusion",
)
```

- **Function**: `resize.Spline36`
- **Parameters**: `format=vs.RGB48`, `matrix_in` (defaults 1), `range_in` (defaults limited), `dither_type="error_diffusion"`

### Limited Range Expansion

**Evidence**: `src/frame_compare/screenshot/helpers.py:175-205`

```python
def expand_limited_rgb(core: Any, clip: Any) -> Any:
    # ...
    min_in = 16 * scale
    max_in = 235 * scale
    return levels(clip, min_in=min_in, max_in=max_in, min_out=0, max_out=max_code, planes=[0, 1, 2])
```

- **Function**: `std.Levels`
- **Parameters**: Scales 16-235 → 0-255 (bit-depth aware)

### Frame Prop Application

**Evidence**: `src/frame_compare/vs/props.py:290-302`

```python
def _apply_frame_props_dict(clip: Any, props: Mapping[str, Any]) -> Any:
    # ...
    return _call_set_frame_prop(set_props, clip, **props)
```

- **Function**: `std.SetFrameProps`
- **Parameters**: `_Matrix`, `_Transfer`, `_Primaries`, `_ColorRange` as int values

---

## 4) Call Graph / Usage Hotspots

### Loading / Probing

- **Not found**: No explicit color conversion during source loading. Color metadata is read via `snapshot_frame_props()` and normalised via `normalise_color_metadata()` at rendering time.

### Analysis Metrics

- **Not found**: Analysis code does not perform color space conversion. Metrics operate on raw clip values.

### Screenshot Rendering

**Evidence**: `src/frame_compare/screenshot/helpers.py:276` (`ensure_rgb24` entry point)

- Called during PNG export to convert any format to RGB24
- Applies `resolve_resize_color_kwargs()` for color params
- Optionally expands limited→full via `expand_limited_rgb()`

### Tonemapping

**Evidence**: `src/frame_compare/vs/tonemap.py:1014-1031` (bypass path) and `1049-1089` (HDR path)

- `normalise_color_metadata()` called at line ~965 to prepare color props
- YUV→RGB48 via `resize.Spline36` for HDR clips
- `libplacebo.Tonemap` called with `dst_csp=0` (SDR), `dst_prim=1` (BT.709)
- Post-tonemap: `_normalize_rgb_props()` sets `_Matrix=0`, `_ColorRange=0` (full), preserves transfer/primaries

**Evidence**: `src/frame_compare/vs/tonemap.py:137-144`

```python
def _normalize_rgb_props(clip, transfer, primaries):
    work = _apply_set_frame_prop(clip, prop="_Matrix", intval=0)
    work = _apply_set_frame_prop(work, prop="_ColorRange", intval=0)
    if transfer is not None:
        work = _apply_set_frame_prop(work, prop="_Transfer", intval=int(transfer))
    if primaries is not None:
        work = _apply_set_frame_prop(work, prop="_Primaries", intval=int(primaries))
    return work
```

### Libplacebo src_csp Hint

**Evidence**: `src/frame_compare/vs/tonemap.py:147-152`

```python
def _deduce_src_csp_hint(transfer, primaries):
    if transfer == 16 and primaries == 9:
        return 1  # PQ + BT.2020 → HDR10
    if transfer == 18 and primaries == 9:
        return 2  # HLG + BT.2020 → HLG
    return None
```

---

## 5) Tests (Legacy)

### Color Range Detection

- **`tests/test_vs_core.py:232`** — `test_detect_rgb_color_range_identifies_limited`: Asserts PlaneStats with min ~4096, max ~50200 (16-bit) returns `RANGE_LIMITED`
- **`tests/test_vs_core.py:259`** — `test_detect_rgb_color_range_identifies_full`: Asserts PlaneStats spanning 0-65535 returns `RANGE_FULL`
- **`tests/test_vs_core.py:286`** — `test_detect_rgb_color_range_detects_undershoot`: Asserts undershooting values treated as limited

### HDR Detection

- **`tests/test_vs_core.py:128`** — `testprops_signal_hdr_accepts_transfer_only`: Asserts `{_Transfer: 16}` signals HDR
- **`tests/test_vs_core.py:134`** — `testprops_signal_hdr_accepts_primaries_only`: Asserts `{_Primaries: 9}` signals HDR
- **`tests/test_vs_core.py:140`** — `testprops_signal_hdr_detects_mastering_metadata`: Asserts MDL metadata signals HDR

### Color Metadata Defaults

- **`tests/test_vs_core.py:674`** — `test_normalise_color_metadata_infers_hd_defaults`: Asserts 1080p clip with empty props gets BT.709/limited defaults
- **`tests/test_vs_core.py:706`** — `test_normalise_color_metadata_backfills_hdr_defaults`: Asserts partial HDR props (`_Transfer: 16`) backfill to BT.2020/PQ
- **`tests/test_vs_core.py:732`** — `test_normalise_color_metadata_infers_sd_defaults`: Asserts 480p clip gets SMPTE170M defaults
- **`tests/test_vs_core.py:757`** — `test_normalise_color_metadata_honours_overrides`: Asserts color_overrides config takes precedence

### Screenshot Range Handling

- **`tests/test_screenshot.py:2097`** — `test_ffmpeg_expands_limited_range_when_exporting_full`: Asserts FFmpeg uses `scale=in_range=tv:out_range=pc`
- **`tests/test_screenshot.py:2373`** — `test_fpng_respects_limited_export_range`: Asserts limited export preserves range
- **`tests/test_screenshot.py:2429`** — `test_overlay_preserves_limited_range_metadata`: Asserts overlay doesn't corrupt range metadata
- **`tests/test_screenshot.py:2599`** — Tests `range_in` capture during resize calls

---

## 6) Constant Mappings (Complete)

### Matrix Codes

**Source**: `src/frame_compare/vs/props.py:18-34`

```python
_MATRIX_NAME_TO_CODE = {
    "rgb": 0, "bt709": 1, "bt.709": 1, "709": 1,
    "bt470bg": 5, "smpte170m": 6, "bt601": 6, "601": 6,
    "bt2020": 9, "bt.2020": 9, "2020": 9, "2020ncl": 9,
}
```

### Primaries Codes

**Source**: `src/frame_compare/vs/props.py:37-50`

```python
_PRIMARIES_NAME_TO_CODE = {
    "bt709": 1, "bt.709": 1, "709": 1,
    "bt470bg": 5, "smpte170m": 6, "bt601": 6, "601": 6,
    "bt2020": 9, "bt.2020": 9, "2020": 9,
}
```

### Transfer Codes

**Source**: `src/frame_compare/vs/props.py:53-67`

```python
_TRANSFER_NAME_TO_CODE = {
    "bt709": 1, "709": 1, "bt1886": 1, "gamma2.2": 1,
    "st2084": 16, "smpte2084": 16, "pq": 16,
    "hlg": 18, "arib-b67": 18,
    "smpte170m": 6, "bt601": 6, "601": 6,
}
```

### Range Codes

**Source**: `src/frame_compare/vs/props.py:70-76`

```python
_RANGE_NAME_TO_CODE = {
    "limited": 1, "tv": 1,
    "full": 0, "pc": 0, "jpeg": 0,
}
```

### HDR Detection Constants

**Source**: `src/frame_compare/vs/props.py:6-15`

```python
_HDR_PRIMARIES_NAMES = {"bt2020", "bt.2020", "2020"}
_HDR_PRIMARIES_CODES = {9}
_HDR_TRANSFER_NAMES = {"st2084", "pq", "smpte2084", "hlg", "arib-b67"}
_HDR_TRANSFER_CODES = {16, 18}
```

---

## Summary

The legacy implementation has a complete color handling pipeline:

1. **Props extraction** via `resolve_color_metadata()` supporting both `_Matrix`/`Matrix` forms
2. **HDR detection** via `props_signal_hdr()` checking primaries=9, transfer=16/18, or MDL/CLL keys
3. **Default inference** via `_guess_default_colourspace()` based on height:
   - SD ≤576px → SMPTE170M (6)
   - HD ≥720px → BT.709 (1)
   - HDR → BT.2020 (9) + ST2084 (16)
4. **Range defaulting** to limited (1) always when unspecified
5. **Luma-based range detection** via `_adjust_color_range_from_signal()` sampling PlaneStats
6. **YUV→RGB conversion** via `resize.Point` (screenshots) or `resize.Spline36` (tonemap) with explicit matrix/transfer/primaries/range params
7. **Libplacebo tonemapping** targeting SDR (dst_csp=0) + BT.709 (dst_prim=1)

No zimg or fmtc usage found — all conversions use VapourSynth's built-in resize namespace.
