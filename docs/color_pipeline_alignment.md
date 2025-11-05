# Colour Pipeline Alignment Notes

These notes capture the recent fixes that bring the modern pipeline back in sync with `Legacy/comp.py`, outline when the changes are active, and list scenarios worth validating in future investigations.

## Summary of Changes
- **Metadata preservation** – After every crop/resize/pad step we now re-apply the original `_Matrix`, `_Transfer`, `_Primaries`, and `_ColorRange` props. This prevents viewers or later filters from re-interpreting subsampled SDR clips.
- **Tonemap range detection** – HDR tonemap output now samples RGB frames via `PlaneStats` to decide whether pixels remain limited, stamping `_ColorRange` (and `_SourceColorRange` when remapping) so downstream geometry and overlays stay truthful.
- **RGB conversion parity** – `_legacy_rgb24_from_clip` and `_ensure_rgb24` mirror the legacy script by only hinting the input matrix. The new `_FORCE_FULL_RANGE_RGB` switch (default `False`) controls whether we expand limited-range SDR to full-range RGB; flipping it to `True` stretches 16–235 to 0–255 while keeping the source range recorded in `_SourceColorRange`.
- **Range expansion helper** – `_expand_limited_rgb` applies `std.Levels` to SDR RGB before writing PNGs when the override is enabled.
- **Debug staging** – Colour debug snapshots now report accurate metadata at every stage (`post_geometry` retains the original range, `legacy_rgb24` and `post_rgb24` reflect the final RGB choice).
- **Tonemapped HDR metadata** – `_restore_color_props` skips `_ColorRange` once tonemapping runs and now snapshots frame props directly from the tonemapped RGB node before geometry. This keeps overlays/resizes from re-stamping YUV matrices onto RGB frames and avoids fpng resize failures.

## Behavioural Impact
- **Limited SDR encodes (e.g. Blu-ray AVC)** stay limited through geometry and can optionally be promoted to full-range RGB at the end by setting `_FORCE_FULL_RANGE_RGB = True`. Legacy compatibility remains when the flag is `False`.
- **HDR sources** still stamp `_Tonemapped` but now expose colour range derived from sampled RGB output, preventing metadata/pixel mismatches without altering the rendered clip.
- **Metadata inference** still defaults to limited when the container omits range information and frame sampling fails (e.g. empty clips), matching the old script’s behaviour.
- **Geometry-heavy workflows** (odd padding, scaling) no longer lose their colour tags, so external viewers or downstream filters should render them consistently with `comp.py`.

## Watchlist & Regression Risks
- **Metadata drop** – If VapourSynth filters are swapped for alternatives that do not accept metadata reapplication, `_restore_color_props` may silently fail. Logs and debug output should be checked whenever geometry filters change.
- **Full-range override side effects** – With `_FORCE_FULL_RANGE_RGB = True`, HDR-to-SDR tonemap remains untouched, but SDR overlays now contain both `_ColorRange=0` and `_SourceColorRange=1`. Consumers that inspect `_SourceColorRange` must be aware that this key may not exist when the flag is off.
- **Old viewers** – Some image viewers ignore `_ColorRange`. Whenever the flag is toggled to full-range, verify the PNGs against the source to confirm the expected look.
- **HDR geometry regressions** – If another stage starts pulling metadata from the source clips instead of the tonemapped node, fpng will reject RGB frames tagged with `_Matrix`/`_Transfer` values from YUV. Re-run the HDR regression set if geometry helpers change.

## Test Recommendations
Run a targeted debug pass (`--debug-color --verbose`) and compare PNGs against the legacy script for:

| Scenario | Example | What to verify |
| --- | --- | --- |
| 1080p Blu-ray AVC (limited SDR) | `Black.Sails.S01E08...x264-EbP.mkv` | `post_geometry` retains Matrix/Range, PNG matches legacy output. |
| 1080p AMZN / WEB-DL (often full-range) | AMZN/Netflix/Disney+ episodes | Ensure section does not trigger unwanted expansion; metadata stays full-range. |
| 1080p Remux (10-bit SDR) | `REMUX.AVC.DTS-HD` | Validate the limited-to-full conversion when override is on; check the `_SourceColorRange` prop. |
| 4K HDR Remux | PQ/HLG masters | Confirm tonemap path still runs, `_Tonemapped` survives overlays, metadata remains full-range. |
| Anime encodes with sparse metadata | Fansub or encode groups with missing container tags | Check `_adjust_color_range_from_signal` warnings and ensure defaults still produce correct RGB. |
| HDR screenshots with overlays | Recent comparisons | Verify `_Matrix`/`_Transfer` no longer reverts to YUV during geometry stages and fpng completes without Resize 1026 errors. |

## Useful Logging Hooks
```python
import logging
from frame_compare import run_cli

logging.basicConfig(level=logging.INFO)
run_cli(
    config_path="config/config.toml",
    root_override=".",
    debug_color=True,
    verbose=True,
)
```

## When to Revisit
- Introducing new geometry filters, alternative writers, or colour-managed viewers.
- Adding automated full-range expansion (`_FORCE_FULL_RANGE_RGB = True`) to production defaults; ensure end-users expect full-range SDR PNGs.
- Investigating sources with mixed or incorrect metadata (e.g. hybrid SDR/HDR, tinted anime masters) where `_adjust_color_range_from_signal` currently falls back to limited.
