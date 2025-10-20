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
