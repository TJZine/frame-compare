# Tonemap Range Harmonisation Task

## Context Snapshot
- Recent HDR comparisons show that **tonemapped RGB clips remain in limited range** (16–235) while we stamp `_ColorRange=0` (full). Downstream conversions interpret that metadata literally, leading to washed-out PNGs and inconsistent debug output (`legacy_rgb24` vs `post_rgb24`).
- Past incidents: `MaskedMerge` failures and fpng resize errors occurred when overlays operated on RGB clips carrying YUV metadata or mismatched range hints.
- Current debug trace (frame 9940) highlights the problem:
  - `post_normalisation`: Matrix=9, Transfer=16, Range=1, `Ymax≈693`.
  - `post_geometry`: Matrix=0, Transfer=1, Range=0, `Ymax≈49882` (≈195 in 8-bit).
  - `legacy_rgb24`: Range=1, `Ymax≈195` (looks correct).
  - `post_rgb24`: Range=0, `Ymax≈183` (washed out when viewed as full-range).
- Code landmarks:
  - `src/vs_core.py:1531-1570` — tonemap stage forces `_ColorRange=0`.
  - `src/screenshot.py:1898-2068` — geometry pipeline copies props; `_restore_color_props` currently skips range when tonemap applied.
  - `_ensure_rgb24` (`src/screenshot.py:561-679`) assumes the metadata is accurate; sets `range=RANGE_FULL` when `_ColorRange=0`.
  - Overlays (`_apply_frame_info_overlay`, `_apply_overlay_text`) rely on `text.Text`/`sub.Subtitle`, which blend 8-bit nodes and expect consistent range metadata.

## Objective
Keep tonemapped HDR clips limited unless we explicitly expand them, ensuring:
1. Pixel values and metadata stay aligned throughout geometry, overlays, debug exports, and writers.
2. Overlay nodes never see mismatched ranges that trigger `MaskedMerge` or VapourSynth resize errors.
3. Debug PNGs (`post_geometry`, `legacy_rgb24`, `post_rgb24`) remain visually identical for limited sources; intentional full-range expansion remains opt-in via `_FORCE_FULL_RANGE_RGB`.

## Required Changes
1. **Tonemap metadata**
   - In `process_clip_for_screenshot`, stop forcing `_ColorRange=0` after tonemap; preserve the original range unless an explicit expansion occurs.
   - Maintain `_Transfer`/`_Primaries` consistency. When libplacebo outputs still reference PQ, ensure `_normalize_rgb_props` reflects the correct values.
2. **Range detection helper**
   - Add utility (e.g., `vs_core._detect_rgb_range`) that samples the tonemapped clip (single frame or `PlaneStats`) to decide whether the numeric values fill full or limited range.
   - Cache detection per clip to avoid repeated stats calls.
3. **Geometry pipeline**
   - Use the detected range when calling `_restore_color_props` and `_ensure_rgb24`.
   - Guard `_restore_color_props` against reapplying YUV `_Matrix` codes to RGB clips when tonemap applied.
   - After overlays, re-copy frame props and assert `_Matrix==0` for RGB clips. Log and correct mismatches before final writer.
4. **RGB conversion updates**
   - In `_ensure_rgb24`, only request `range=RANGE_FULL` when `_FORCE_FULL_RANGE_RGB` is true or detection reports full-range data. Otherwise, keep limited.
   - When expansion is required, call `_expand_limited_rgb` immediately after tonemap so metadata matches pixels.
5. **Overlay safeguards**
   - Ensure `_apply_frame_info_overlay` / `_apply_overlay_text` return clips with the same `_ColorRange`/`_Matrix` as input.
   - Add warning (and optional strict failure) when overlay backends coerce metadata unexpectedly.
6. **Error handling**
   - Add explicit assertions to catch future range/metadata mismatches before they propagate to fpng or MaskedMerge.

## Testing & Verification
1. **Unit tests**
   - Mock tonemap result with limited-range RGB stats; confirm `_ensure_rgb24` produces identical values and range metadata.
   - Add regression covering overlay application on tonemapped clips to ensure metadata remains RGB/full vs limited as intended.
2. **Integration tests**
   - Extend `tests/test_screenshot.py` to simulate HDR pipeline, verifying:
     - `debug_state.capture_stage` snapshots share the same histograms.
     - Final fpng writes succeed without range errors.
   - Keep SDR scenarios intact; assert no behavioural change when `_FORCE_FULL_RANGE_RGB=False`.
3. **Manual validation**
   - Run HDR comparison with `--debug-color` and inspect:
     - `post_geometry`, `legacy_rgb24`, `post_rgb24` stats.
     - Overlay PNGs to ensure highlights match.
   - Confirm SDR comparisons unaffected.

## Documentation & Housekeeping
1. Update `docs/color_pipeline_alignment.md` with new range-detection behaviour and overlay safeguards.
2. Append decision log entry to `docs/DECISIONS.md` capturing the rationale.
3. Add CHANGELOG bullet describing the HDR tonemap range fix.
4. If config knobs are introduced (e.g. to force expansion), document them in `config_reference.md`.

## Handoff Notes for Next Session
- Re-run `uv run pyright`, `uv run ruff check`, and `uv run pytest` after implementing.
- Preserve existing `_FORCE_FULL_RANGE_RGB` flag semantics; ensure new detection integrates with it.
- Watch for interactions with verification path (`_compute_verification`) since it converts clips to RGB24; ensure range metadata is correct there too.
- Past overlay-induced failures (MaskedMerge, resize) were caused by mismatched `_ColorRange`. Treat any future metadata change as high-risk; add logging when detection flips range.
- Remember AGENTS.md invariants: add/update tests with behaviour changes, keep error boundaries explicit, update docs and changelog.

Once these changes are implemented and verified, HDR tonemapped screenshots should align with legacy outputs without sacrificing SDR correctness or overlay stability.

