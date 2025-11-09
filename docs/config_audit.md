# Configuration Audit Tracker

Central log for the end-to-end configuration review requested on 2025‑11‑18. Each section records the current understanding of the options, verification status, proposed trims/consolidations, and the decision the user approves (or rejects). Update this file whenever a category is reviewed so future sessions can resume quickly.

## Workflow Overview
- **Source of truth:** `config/config.toml`, `src/config_loader.py`, `src/datatypes.py`, and the feature modules listed per category.
- **Validation hooks:** Loader invariants, tests under `tests/`, and any runtime guards exercised via `frame_compare.runner`.
- **Decision protocol:** Summaries flow to the user category-by-category. No code/doc changes land until the user explicitly approves the recommendations for that category.
- **References:** TOML structure and boolean typing follow the upstream spec (see `/toml-lang/toml` docs pulled via Context7 on 2025‑11‑18).

## Category Status Snapshot

| Category            | Status        | Notes |
| ------------------- | ------------- | ----- |
| `[analysis]`        | Updated       | Skip/ignore merge + threshold-mode enum implemented (2025‑11‑18). |
| `[audio_alignment]` | Reviewed      | Findings logged below; awaiting next steps. |
| `[screenshots]`     | Reviewed      | Findings logged below; awaiting next steps. |
| `[color]`           | Reviewed      | Findings logged below; awaiting next steps. |
| `[slowpics]`        | Not started   | Pending. |
| `[report]`          | Not started   | Pending. |
| `[tmdb]`            | Not started   | Pending. |
| `[naming]`          | Not started   | Pending. |
| `[cli]`             | Not started   | Pending. |
| `[paths]`           | Not started   | Pending. |
| `[runtime]`         | Not started   | Pending. |
| `[source]`          | Not started   | Pending. |
| `[overrides]`       | Not started   | Pending. |

---

## `[analysis]` (updated 2025‑11‑18)

**Feature surface.** Loader sanitises and normalises values in `src/config_loader.py` (step/downscale/caching checks), `src/datatypes.py` defines defaults, `src/analysis.py` executes the heuristics (metrics extraction, `_quantile`, window trims, pinned frames, cache IO), and `src/frame_compare/core.py`/`runner.py` coordinate cache paths, window intersections, and CLI telemetry. Regression tests exercising these knobs live primarily in `tests/test_analysis.py`, `tests/test_config.py`, and the runner suites inside `tests/test_frame_compare.py`.

**Health check.**
- Frame quotas & pinning (`frame_count_*`, `random_frames`, `user_frames`) are consumed in `select_frames` (`src/analysis.py:1673-2024`). Tests such as `tests/test_analysis.py::test_select_frames_respects_window` cover determinism and gap rules.
- Selection heuristics now run through `[analysis.thresholds]`: quantile mode consumes `dark_quantile` / `bright_quantile`, while `fixed_range` compares against `dark_luma_*` / `bright_luma_*` bands. Motion knobs and `screen_separation_sec` behave as before (`src/analysis.py:1968-2010`, `src/analysis.py:1450-1493`), and the CLI reflects the active mode (`src/frame_compare/runner.py:1129-1182`).
- Window management relies exclusively on the configured `ignore_lead_seconds` / `ignore_trail_seconds`: `core._resolve_selection_windows` trims the common intersection before analysis (`src/frame_compare/core.py:2015-2061`), and `select_frames` applies the same bounds when sampling auto-picked frames while still allowing pinned `user_frames` to bypass the edge rejection when explicitly requested (`src/analysis.py:1634-1897`). Unit tests for `compute_selection_window` live at `tests/test_analysis.py:158-185`.
- Pre-processing & performance knobs (`step`, `downscale_height`, `analyze_in_sdr`) are enforced when building the analysis clip (`src/analysis.py:1381-1680`) and validated in loader guards (`src/config_loader.py:233-239`). HDR flagging requires a non-null `color_cfg` and is tested via `tests/test_analysis.py::test_select_frames_hdr_tonemap`.
- Persistence (`save_frames_data`, `frame_data_filename`) gates cache construction in `src/frame_compare/core.py:1969-2005` and `src/frame_compare/runner.py:1093-1460`, with path-escape negative tests under `tests/test_paths_preflight.py`.

**Completed adjustments (2025‑11‑18).**
1. Legacy `skip_head_seconds` / `skip_tail_seconds` now serve as deprecated aliases for the authoritative `ignore_*` margins (conflicts raise `ConfigError`). Automatic frame selection enforces only the trimmed intersection, so CLI summaries, cached windows, and selection guardrails all rely on the same values.
2. Introduced `[analysis.thresholds]` with `mode = "quantile" | "fixed_range"`. Legacy `use_quantiles`, `dark_quantile`, and `bright_quantile` keys are migrated into the nested table, loader validation enforces NumPy-style `[0, 1]` bounds and ordering, and the runner exposes the active mode + payload in its JSON tail.

**Next opportunities.**
1. The trio of tonal quotas (`frame_count_dark/frame_count_bright/frame_count_motion`) plus `random_frames` still produce five separate integers in the UI (`src/frame_compare/runner.py:1159-1174`). A declarative `analysis.frame_categories` table (category + count + strategy) could reduce surface area and allow future heuristics (e.g., "mid-tone", "skin") without more top-level keys.
2. `analyze_clip` currently accepts numeric index, filename, stem, or metadata label via `_pick_analyze_file` (`src/frame_compare/core.py:1527-1571`). If we eventually merge with CLI `--clip`, ensure both use the same matching rules.

**Risks / follow-ups.**
- Add regression tests that explicitly swap `thresholds.mode` between quantile and fixed-range configurations so cache fingerprints and frame selection remain stable.
- Expand documentation snippets/examples referencing the new `[analysis.thresholds]` table (README + reference docs) to minimise confusion for existing operators.

---

## `[audio_alignment]` … *(pending detailed review)*

## `[audio_alignment]` (reviewed 2025‑11‑18)

**Feature surface.** `AudioAlignmentConfig` lives in `src/datatypes.py:238-257` and is loaded/validated in `src/config_loader.py:378-596`. Runtime behaviour spans the dedicated helper module (`src/audio_alignment.py` handles ffprobe/ffmpeg probing, waveform extraction, onset envelopes, and offsets file IO), runner orchestration (`src/frame_compare/core.py:2126-3300` for measurement, VSPreview integration, manual reuse, and trim application; `src/frame_compare/runner.py:373-937` for CLI telemetry), and presentation hooks in `cli_layout.v1.json`. Regression coverage is split across `tests/test_audio_alignment.py` (module-level guarantees), `tests/test_frame_compare.py` (mixed preview/prompt flows), and path guards in `tests/test_paths_preflight.py`.

**Health check.**
- Enabling logic respects `enable`, `use_vspreview`, and `confirm_with_screenshots`: `_maybe_apply_audio_alignment` can reuse VSPreview-only manual trims even when auto-alignment is disabled, while the config loader enforces positive sample rates, hop lengths, and max offsets plus `[0,1]` correlation thresholds (`src/config_loader.py:582-596`). Headless runs auto-confirm prompts but still surface warnings.
- Operational parameters (`sample_rate`, `hop_length`, `start_seconds`, `duration_seconds`) feed directly into `audio_alignment.measure_offsets`, which clamps hop length to ≤1% of the sample rate (`src/frame_compare/core.py:2960-3004`) before passing values to librosa/libsoundfile. This mirrors librosa’s onset-detection guidance on tuning onset envelopes and peak-picking (`Context7: /websites/librosa_doc → Onset detection examples`).
- Offsets caching + trim application: `offsets_filename` is validated against the workspace root and reused between runs (`src/frame_compare/core.py:2126-2196`). `prompt_reuse_offsets` and `use_vspreview` drive the manual reuse branch, while `frame_offset_bias` nudges frame counts toward/away from zero before writing suggestions (`src/frame_compare/core.py:3000-3070`).
- CLI telemetry summarises stream selection, offsets, correlations, and manual overrides (`src/frame_compare/runner.py:373-937`, `cli_layout.v1.json:61-346`), and docs/audio_alignment_pipeline.md stays in sync with the current behaviour.

**Opportunities / open questions.**
1. **Reference/stream validation:** `audio_alignment.reference` and CLI stream overrides accept arbitrary strings without confirming the label or index exists before runtime. We could surface early validation by cross-referencing `_plan_label` and clip metadata during config parsing so typos fail fast instead of silently falling back to the first clip (`src/frame_compare/core.py:2147-2160`).
2. **Enforce hop/sample ratios:** Although hop length is clamped at runtime, the config loader doesn’t warn when `hop_length` exceeds the “1% of `sample_rate`” heuristic recommended by onset-detection best practices (see librosa docs above). Adding a warning or auto-normalisation during load would prevent confusing behaviour where values are silently changed moments before measurement.
3. **Preview flow clarity:** `use_vspreview=true` with `enable=false` currently reuses manual trims but still logs “audio alignment disabled” warnings. Consider splitting the VSPreview-only mode into its own config flag (or documenting the manual-only expectation) so operators can opt into manual preview assistance without feeling like they misconfigured alignment (`src/frame_compare/core.py:2198-2255`).
4. **Offsets file lifecycle:** We rely on the same TOML for both manual and automatic edits; there’s no built-in retention or rotation strategy. Capturing a configurable retention count or providing an option to snapshot offsets per run would make it safer to accept suggestions in bulk.

**Next steps.**
- Decide whether you want loader-level validation for `reference` / stream overrides and hop-length heuristics.
- If VSPreview-only mode should be a distinct pathway, we can introduce a clearer config surface (e.g., `vspreview_manual_only=true`) and adjust warnings/UI copy accordingly.

---

## `[screenshots]` (reviewed 2025‑11‑18)

**Feature surface.** `ScreenshotConfig` is defined in `src/datatypes.py:76-100` and loaded via `_sanitize_section` with validation of compression levels, padding tolerances, and FFmpeg timeout bounds (`src/config_loader.py:368-429`). Geometry, range handling, and renderer orchestration reside in `src/screenshot.py` (planner `_plan_geometry`, odd-geometry pivots, FFmpeg/VapourSynth writers, export-range logic, and padding), with entry points in `src/frame_compare/runner.py:1546-1600` and `src/frame_compare/core.py:4182-4300` for directory prep and preview generation. Documentation covering odd geometry, dithering, and export range lives in `docs/geometry_pipeline.md`, `docs/config_reference.md`, and `docs/color_pipeline_alignment.md`. Tests exercise both planner and writer behaviour (`tests/test_screenshot.py` and runner smoke tests).

**Health check.**
- **Geometry/padding:** `mod_crop`, `letterbox_pillarbox_aware`, `auto_letterbox_crop`, `pad_to_canvas`, `center_pad`, and `letterbox_px_tolerance` all terminate in `_plan_geometry` (`src/screenshot.py:1634-1888`) and `_align_letterbox_pillarbox`. Odd-geometry policies (`auto`, `force_full_chroma`, `subsamp_safe`) are enforced per format, with clear warnings when `subsamp_safe` rebalance introduces one-pixel shifts. Tests like `tests/test_screenshot.py::test_auto_letterbox_crop` and `::test_pipeline_subsampling_policy` confirm these paths.
- **Renderer selection:** `use_ffmpeg` switches between VapourSynth and FFmpeg builders (`src/screenshot.py:2189-2610`). FFmpeg timeouts map through `_map_ffmpeg_compression`/`ffmpeg_timeout_seconds` and honour the doc’d “0 disables timeout” policy (see `CHANGELOG.md:47` and `docs/DECISIONS.md:42-43`). `compression_level` is constrained to a 0–2 tier and plumbed through every code path.
- **Color/export range:** `rgb_dither` toggles the final RGB24 hop only (`docs/config_reference.md:18-27`). Export range defaults to `"full"` to match sRGB displays but can preserve limited-range outputs via the new `export_range` toggle; both VapourSynth and FFmpeg backends respect `_should_expand_to_full` (`src/screenshot.py:93-105`, `src/screenshot.py:2755-2765`).
- **Paths and cleanup:** `screenshots.directory_name` is guarded by `_resolve_workspace_subdir` to prevent escaping the root (`src/frame_compare/core.py:4182-4190`). README warns against reusing shared directories, and the runner surfaces the resolved path in its JSON tail.

**Opportunities / open questions.**
1. **FFmpeg-specific knobs exposed in config?** Operators occasionally need per-run overrides such as PNG quantiser settings (`-pred mixed`, `-compression_level`) or forcing atomic writes for network mounts. Today these are hardcoded inside `_build_ffmpeg_writer`; consider exposing an advanced `[screenshots.ffmpeg]` table for expert overrides (consistent with FFmpeg’s image2 muxer options like `atomic_writing`, `start_number`, or `update` per FFmpeg docs).
2. **Auto-letterbox heuristics:** The current crop heuristic uses the tallest clip as a baseline and only trims vertical bars (`src/screenshot.py:1663-1695`). It doesn’t attempt horizontal pillarbox detection and assumes even bars across all clips. We could inspect both axes (perhaps reusing letterbox detection logic already available in the runner) or expose tolerances per axis to minimise false positives.
3. **Directory lifecycle clarity:** `screenshots.directory_name` stays relative, but there’s no config surface for retaining multiple runs (e.g., timestamped subdirectories) or cleaning up partial FFmpeg renders when timeouts hit. A `rotation`/`max_runs` option or built-in `atomic_writing` equivalent (ffmpeg image2 muxer supports this) could reduce manual housekeeping.
4. **Export range + overlay interplay:** When `export_range="full"`, overlays include `_SourceColorRange=1` metadata, but limited-range exports drop the tag entirely (`docs/color_pipeline_alignment.md:21`). We may want to keep `_SourceColorRange` in both modes for provenance (set to 0/1) so downstream tooling can always inspect it.
5. **Single-resolution vs upscale semantics:** `single_res` overrides target height regardless of `upscale`. Operators sometimes expect `single_res` to act as “render exactly this height even when it means downscaling bigger clips.” Documenting or splitting the flag (e.g., `single_res_mode = {cap, force}`) could avoid confusion.

**Next steps.**
- Decide if we should expose FFmpeg-specific image2 options or keep them internal.
- Confirm whether broader letterbox/pillarbox detection or directory lifecycle controls are worth implementing before we move to the next category.

---

## `[color]` (reviewed 2025‑11‑18)

**Feature surface.** `ColorConfig` (tonemap/overlay/verification controls) lives in `src/datatypes.py:99-139` and is loaded with extensive validation in `src/config_loader.py:407-575`. The runtime pipeline is implemented in `src/vs_core.py` (`process_clip_for_screenshot`, libplacebo setup, verification overlay) and `src/screenshot.py` (overlay rendering, export range). Runner telemetry surfaces the applied preset plus resolved parameters (`src/frame_compare/runner.py:1566-1599`), and docs (`docs/hdr_tonemap_overview.md`, `docs/color_pipeline_alignment.md`, README) explain presets and CLI overrides. Tests hit both VapourSynth helpers (`tests/test_vs_core.py`) and screenshot overlay cases.

**Health check.**
- **Presets & overrides:** `[color].preset` seeds tone curve, target nits, dynamic peak detection, and smoothing defaults; CLI `--tm-*` flags override fields per run. Loader guards ensure numeric bounds (target nits > 0, knee offset 0–1, dpd cutoff ≤0.05, percentile 0–100). Disabling `dynamic_peak_detection` forces `dpd_preset="off"` and zeroes the cutoff, keeping libplacebo stable.
- **Verification & overlays:** `verify_*` knobs control the sample window used by the SDR vs tonemapped diff; overlay text template supports {preset}/{tone_curve}/{dynamic_peak_detection} placeholders and the diagnostic mode adds resolution + mastering info. `color.strict` escalates overlay/verification failures to hard errors, while the default logs warnings and continues, aligning with the documentation (`docs/hdr_tonemap_overview.md:19-95`).
- **Metadata & range:** The pipeline forces `_Matrix=0`, `_ColorRange=0`, and sets `_Tonemapped` frame props, while `[screenshots].export_range` (documented in `docs/color_pipeline_alignment.md`) controls whether SDR outputs expand to full-range RGB. `[color].metadata` accepts string or numeric codes for auto/none/hdr10/hdr10+/luminance, with validation ensuring values stay within 0–4.
- **Debugging knobs:** `post_gamma_enable` + `post_gamma`, `visualize_lut`, `show_clipping`, and `debug_color` provide targeted QA paths without editing scripts; CLI flags exist for most options, keeping experimentation quick.

**Opportunities / follow-ups.**
1. **Preset provenance & customization:** Operators often tweak `target_nits` or `dst_min_nits` after picking a preset, but the overlay still reports the original preset name. We could log or annotate overlays when manual overrides are applied (for example, “reference*” or `reason=custom`) so screenshots clearly show deviations from stock presets.
2. **Dynamic peak detection guardrails:** Today `dpd_preset` accepts a string and we only zero the cutoff when `dynamic_peak_detection=false`. Consider auto-switching to a different preset when `target_nits` exceeds ~120 or smoothing is zeroed, or at least documenting the recommended combinations (libplacebo’s guidance suggests longer smoothing for high nits). Pulling best-practice snippets from libplacebo docs would strengthen the guidance.
3. **Verification window configurability:** The default `verify_start_seconds=10`, `verify_step_seconds=10`, and `verify_max_seconds=90` work for long-form HDR but are overkill for short clips. Exposing a preset (e.g., “fast verification”) or auto-adjusting based on clip duration could make verification more reliable on short promos without manual config tweaks.
4. **Dolby Vision metadata path:** We currently treat `use_dovi` as a boolean/auto flag but offer no control over the fallback behaviour when RPUs are missing or invalid. A future enhancement could let operators specify `use_dovi="prefer"` vs `"require"` so the CLI can surface harder warnings when expected metadata is absent.
5. **Docs parity for new knobs:** Some of the newer options (`visualize_lut`, `show_clipping`, `overlay_mode="diagnostic"`) are explained in `docs/hdr_tonemap_overview.md` but not in the quick-reference tables. Updating `docs/README_REFERENCE.md` to list them would reduce hunting.

**Next steps.**
- Let me know if you want implementation work on preset provenance, DPD guardrails, or verification presets; otherwise I can continue to `[slowpics]` once you approve this section’s findings.

---

## `[slowpics]` … *(pending detailed review)*

---

## `[report]` … *(pending detailed review)*

---

## `[tmdb]` … *(pending detailed review)*

---

## `[naming]` … *(pending detailed review)*

---

## `[cli]` … *(pending detailed review)*

---

## `[paths]` … *(pending detailed review)*

---

## `[runtime]` … *(pending detailed review)*

---

## `[source]` … *(pending detailed review)*

---

## `[overrides]` … *(pending detailed review)*
