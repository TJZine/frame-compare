# Configuration Audit Tracker

Central log for the end-to-end configuration review requested on 2025‑11‑18. Each section records the current understanding of the options, verification status, proposed trims/consolidations, and the decision the user approves (or rejects). Update this file whenever a category is reviewed so future sessions can resume quickly.

## Workflow Overview
- **Source of truth:** the workspace config generated after first run, `src/config_loader.py`, `src/datatypes.py`, and the feature modules listed per category.
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
| `[slowpics]`        | Reviewed      | Findings logged below; awaiting next steps. |
| `[report]`          | Reviewed      | Findings logged below; awaiting next steps. |
| `[tmdb]`            | Reviewed      | Findings logged below; awaiting next steps. |
| `[naming]`          | Reviewed      | Findings logged below; awaiting next steps. |
| `[cli]`             | Not started   | Pending. |
| `[paths]`           | Reviewed      | Findings logged below; awaiting next steps. |
| `[runtime]`         | Reviewed      | Findings logged below; awaiting next steps. |
| `[source]`          | Not started   | Pending. |
| `[overrides]`       | Reviewed      | Findings logged below; awaiting next steps. |

---

## `[analysis]` (updated 2025‑11‑18)

**Feature surface.** Loader sanitises and normalises values in `src/config_loader.py` (step/downscale/caching checks), `src/datatypes.py` defines defaults, `src/analysis.py` executes the heuristics (metrics extraction, `_quantile`, window trims, pinned frames, cache IO), and `src/frame_compare/core.py`/`runner.py` coordinate cache paths, window intersections, and CLI telemetry. Regression tests exercising these knobs live primarily in `tests/test_analysis.py`, `tests/test_config.py`, and the runner suites split across `tests/runner/test_cli_entry.py`, `tests/runner/test_audio_alignment_cli.py`, and `tests/runner/test_slowpics_workflow.py`.

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

**Feature surface.** `AudioAlignmentConfig` lives in `src/datatypes.py:238-257` and is loaded/validated in `src/config_loader.py:378-596`. Runtime behaviour now splits cleanly between `src/audio_alignment.py` (ffprobe/ffmpeg probing, waveform extraction, onset envelopes, and offsets file IO), the new orchestration module `src/frame_compare/alignment_runner.py` (measurement, `_AudioAlignmentSummary`/display dataclasses, VSPreview integration, manual reuse, and trim application), runner telemetry plumbing (`src/frame_compare/runner.py:372-940`), and presentation hooks in `cli_layout.v1.json`. Regression coverage spans `tests/test_audio_alignment.py` (module-level guarantees), `tests/runner/test_audio_alignment_cli.py` (preview/prompt flows plus formatter tests), and path guards in `tests/test_paths_preflight.py`.

**Health check.**
- Enabling logic respects `enable`, `use_vspreview`, and `confirm_with_screenshots`: `alignment_runner.apply_audio_alignment` still reuses VSPreview-only manual trims even when auto-alignment is disabled, while the config loader enforces positive sample rates, hop lengths, and max offsets plus `[0,1]` correlation thresholds (`src/config_loader.py:582-596`). Headless runs auto-confirm prompts but surface warnings via the shared reporter.
- Operational parameters (`sample_rate`, `hop_length`, `start_seconds`, `duration_seconds`) feed directly into `audio_alignment.measure_offsets`. The new module clamps hop length to ≤1% of the sample rate before invoking librosa/libsoundfile (`src/frame_compare/alignment_runner.py`), mirroring librosa’s onset-detection guidance on tuning onset envelopes and peak-picking (`Context7: /websites/librosa_doc → Onset detection examples`).
- Offsets caching + trim application: `offsets_filename` is validated against the workspace root and reused between runs (`src/frame_compare/alignment_runner.py`). `prompt_reuse_offsets`/`use_vspreview` drive the manual reuse branch, while `frame_offset_bias` nudges frame counts toward/away from zero before writing suggestions.
- CLI telemetry summarises stream selection, offsets, correlations, and manual overrides via `alignment_runner.format_alignment_output` (`src/frame_compare/runner.py:372-940`, `cli_layout.v1.json:61-346`), and docs/audio_alignment_pipeline.md stays in sync with the current behaviour.

VSPreview orchestration now lives under `src/frame_compare/vspreview.py`: `render_script` + `persist_script` guarantee deterministic workspace-relative files (timestamp + UUID) before `write_script` hands them to `launch`. The launcher logs missing executables or `VAPOURSYNTH_PYTHONPATH` entries and accepts an injected subprocess runner so CI never shells out to a real binary. `apply_manual_offsets` keeps the summary + `json_tail["audio_alignment"]` (`offsets_sec`/`offsets_frames`, `vspreview_manual_*`) in sync while warning about unknown clip names. `tests/test_vspreview.py` covers script rendering, persistence failures, launcher injection/missing-backend telemetry, and manual-offset propagation.

**Opportunities / open questions.**
1. **Reference/stream validation:** `audio_alignment.reference` and CLI stream overrides accept arbitrary strings without confirming the label or index exists before runtime. We could surface early validation by cross-referencing `_plan_label` and clip metadata during config parsing so typos fail fast instead of silently falling back to the first clip (`src/frame_compare/alignment_runner.py`’s `_resolve_alignment_reference`).
2. **Enforce hop/sample ratios:** Although hop length is clamped at runtime, the config loader doesn’t warn when `hop_length` exceeds the “1% of `sample_rate`” heuristic recommended by onset-detection best practices (see librosa docs above). Adding a warning or auto-normalisation during load would prevent confusing behaviour where values are silently changed moments before measurement.
3. **Preview flow clarity:** `use_vspreview=true` with `enable=false` currently reuses manual trims but still logs “audio alignment disabled” warnings. Consider splitting the VSPreview-only mode into its own config flag (or documenting the manual-only expectation) so operators can opt into manual preview assistance without feeling like they misconfigured alignment (`src/frame_compare/alignment_runner.py` around `_reuse_vspreview_manual_offsets_if_available`).
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

## `[slowpics]` (reviewed 2025‑11‑19)

**Feature surface.** `SlowpicsConfig` (`src/datatypes.py:150-163`) and loader validation (`src/config_loader.py:370-439`) cover auto-upload toggles, TMDB wiring, visibility flags, cleanup behaviour, webhook delivery, timeout heuristics, and shortcut creation. The setup wizard prompts for these values (`src/frame_compare/core.py:763-786`), the doctor command surfaces the network requirement (`src/frame_compare/core.py:856-980`), and runner orchestration injects warnings, JSON-tail metadata, and collection-title derivation before invoking the uploader (`src/frame_compare/runner.py:333-700`). Runtime execution lives in `src/slowpics.py:200-430`, which enforces screenshot naming, sizes HTTP adapters, requires XSRF tokens, scales timeouts, and redacts webhook hosts. CLI post-run handling launches browsers, copies URLs to the clipboard, emits `.url` shortcuts, and conditionally deletes screenshots (`frame_compare.py:280-360`). Regression coverage spans `tests/runner/test_slowpics_workflow.py` (cleanup, TMDB propagation, reporting) and `tests/test_slowpics.py:1-460` (adapter sizing, timeout math, dependency failures).

**Health check.**
- Template defaults keep uploads opt-in, blank out webhook/TMDB identifiers, and enable deletion, matching README guidance (`README.md:233-423`). The CLI always warns when auto-upload is active, and doctor warns when network readiness is uncertain.
- `_prepare_legacy_plan` validates `<frame> - <label>.png` names before any HTTP calls, `_build_legacy_headers` refuses to proceed without an XSRF token, `_post_direct_webhook` retries with exponential backoff while redacting hostnames, and `_compute_image_upload_timeout` scales read timeouts with file size so large PNGs don’t stall on slow links.
- JSON tail + layout data persist TMDB metadata, final/derived titles, suffixes, deletion status, and auto-upload flags so automation has ground truth after each run.
- Tests cover upload-plan validation, timeout calculations, HTTP adapter sizing, concurrency, cleanup safeguards, and JSON-tail reporting, keeping the module verifiable.

**Opportunities.**
1. **Docs parity:** `docs/README_REFERENCE.md:145-156` lists only a subset of keys. Expand the reference tables (and README config section) to enumerate `collection_suffix`, `remove_after_days`, visibility flags, shortcut controls, webhook, timeout, and TMDB category—plus mention timeout/concurrency behaviour from `src/slowpics.py`.
2. **Secrets handling:** Webhook URLs and TMDB identifiers live in user configs that might be shared between machines. Document best practices (environment variables or encrypted stores) so operators don’t accidentally share live webhooks/API keys when enabling uploads.
3. **Readiness checks:** Doctor currently warns only about network access. Add probes for `requests_toolbelt` (required for uploads) and optionally a lightweight slow.pics connectivity test so operators catch missing dependencies before toggling auto-upload.
4. **Timeout & concurrency tuning:** `_DEFAULT_UPLOAD_CONCURRENCY = 3` and `_MIN_UPLOAD_THROUGHPUT_BYTES_PER_SEC = 256 * 1024` are hard-coded. Consider exposing a config knob (e.g., `[slowpics].max_workers` or throughput override) for large batches or constrained links.
5. **Cleanup transparency:** `delete_screen_dir_after_upload` only triggers when the run created the screenshots directory and the path stays under the workspace root. Document that nuance and explore retention/rotation controls (see `[screenshots]` follow-ups) so operators can keep recent PNGs while still cleaning old directories.

**Risks / follow-ups.**
- Update docs to cover the full config surface and timeout heuristics.
- Add doctor checks for upload dependencies/network readiness before enabling auto-upload.
- Evaluate exposing max-worker/throughput knobs in the uploader.
- Clarify cleanup semantics to prevent accidental deletions and align with future retention settings.

---

## `[report]` (reviewed 2025‑11‑19)

**Feature surface.** `ReportConfig` (`src/datatypes.py:225-237`) plus loader validation (`src/config_loader.py:598-628`) govern enablement, browser auto-open, output directory, optional title/labels, metadata verbosity, thumbnail placeholder, and initial viewer mode. Runner orchestration respects `--html-report` / `--no-html-report`, evaluates overrides, resolves an output subdirectory under the workspace root, and invokes `src/report.py:116-312` to bundle assets + data (`src/frame_compare/runner.py:2072-2149`). CLI post-run handling logs the final `index.html`, optionally opens it via `webbrowser`, and records JSON-tail metadata (`frame_compare.py:360-396`). Tests cover generator payloads (`tests/test_report.py`) and CLI/runner wiring in `tests/runner/test_cli_entry.py`. Docs describe the viewer in `README.md:233-320`, `docs/config_reference.md:97-120`, and changelog entries highlight the October 2025 rollout.

**Health check.**
- Loader enforces safe paths: `report.output_dir` must be relative, contain no `..`, and is resolved via `_resolve_workspace_subdir` before writing (`src/config_loader.py:598-607`, `src/frame_compare/core.py:2088-2098`). Static assets copy alongside `data.json`, and titles/default labels are stripped to `None` when blank.
- JSON tail exposes report state (`enabled`, `path`, `open_after_generate`, `mode`) so automation can download or publish the bundle even when CLI output is quiet. CLI also warns when generation fails and disables the report block to avoid stale metadata.
- The renderer sanitises encode labels via `_sanitise_label`, enforces unique safe labels, and builds per-frame/category metadata; tests confirm expected payload structure and viewer stats.
- README and reference docs explain the viewer experience (slider/overlay/difference/blink, zoom/pan persistence), and changelog entries document the CLI toggles plus offline workflow.

**Opportunities.**
1. **`default_mode` validation mismatch:** Docs advertise `slider`, `overlay`, `difference`, and `blink`, but the loader currently restricts `report.default_mode` to `slider`/`overlay` (`src/config_loader.py:612-615`). Attempting to use `difference` or `blink` results in a `ConfigError`, so either expand validation and layout handling or update docs/UI copy to reflect the real options.
2. **Unused `thumb_height`:** The config exposes `thumb_height` yet the generator ignores it (docs label it “reserved”). Consider hiding the knob until thumbnail support ships or implement the intended behaviour to prevent confusion.
3. **Wizard discoverability:** The initial setup wizard skips `[report]`, so new users must edit the config manually to enable offline bundles. Adding wizard prompts (or at least doctor guidance) would make the feature more discoverable.
4. **Output lifecycle:** Unlike screenshots (which can auto-delete after slow.pics uploads), report directories accumulate indefinitely. Provide a retention/cleanup toggle or document best practices for rotating `report.output_dir` to keep workspaces tidy.

**Risks / follow-ups.**
- Align loader validation, docs, and viewer implementation for `default_mode`.
- Decide whether to implement or hide `thumb_height` until thumbnail support exists.
- Extend the wizard/doctor surfaces so operators can enable reports without manual edits.
- Consider retention/cleanup guidance for report directories.

---

## `[tmdb]` (reviewed 2025‑11‑19)

**Feature surface.** `TMDBConfig` (`src/datatypes.py:165-177`) defines API key, unattended/confirmation flags, year tolerance, anime parsing toggle, cache TTL/size, and category preference. Loader guards enforce non-negative values and normalise `category_preference` to `MOVIE`/`TV` (`src/config_loader.py:441-451`). Wizard prompts let operators set a TMDB identifier for slow.pics but do not yet collect API keys (`src/frame_compare/core.py:771-778`). Runtime behaviour now flows through `core.resolve_tmdb_workflow` (shared by CLI + runner) which calls `_resolve_tmdb_blocking` inside `src/frame_compare/core.py` for HTTPX-backed retries, then surfaces prompts via `_prompt_manual_tmdb` / `_prompt_tmdb_confirmation`. The async resolver lives in `src/tmdb.py:200-1100`, and runner integration (`src/frame_compare/runner.py:540-777`) pipes TMDB data into layout data, JSON tails, and slow.pics naming. Tests cover resolver caching/errors (`tests/test_tmdb.py`), config validation (`tests/test_config.py`), and CLI flows (manual overrides, slow.pics propagation) in `tests/runner/test_slowpics_workflow.py`.

**Health check.**
- Resolver enforces API key presence, caches HTTP responses with bounded TTL, supports IMDb/TVDB external IDs, handles anime title variants via GuessIt/Anitopy (configurable), and raises `TMDBAmbiguityError` when multiple candidates tie within `_AMBIGUITY_MARGIN`.
- Runner respects unattended/confirmation settings: interactive sessions can confirm matches, provide manual overrides, or skip TMDB entirely; unattended mode auto-accepts best candidates. When TMDB is disabled or fails, user-facing warnings land in the reporter and JSON tail.
- Slow.pics integration backfills `[slowpics].tmdb_id`/`tmdb_category` when metadata resolves, ensuring uploads/tagging stay consistent. Layout + JSON tail preserve TMDB fields for downstream automation.
- Tests exercise caching, TTL expiration, external ID handling, ambiguous flows, manual overrides, and CLI interactions so regressions are caught.

**Opportunities.**
1. **Wizard discoverability:** The initial wizard never asks for `[tmdb].api_key`, so users must edit the config manually to unlock TMDB lookups. Add prompts (or doctor guidance) to surface the requirement earlier.
2. **Rate limiting & retries:** ✅ Phase 5 updated `_resolve_tmdb_blocking` to wrap `httpx.HTTPTransport(retries=...)` with exponential backoff plus shared workflow logging; future work could still monitor sustained 429 responses for friendlier guidance.
3. **Anime parsing control:** `[tmdb].enable_anime_parsing` toggles Anitopy usage, but docs only mention it briefly. Expand README/reference coverage with pros/cons (e.g., potential mismatches when both GuessIt and Anitopy disagree) so users know when to disable it.
4. **Category preference UX:** `category_preference` accepts MOVIE/TV but provides no CLI flag or wizard hook. Consider exposing a CLI flag (`--tmdb-category`) or warning when lookups repeatedly fall back to the non-preferred category.

**Risks / follow-ups.**
- Add wizard/doctor messaging about supplying TMDB keys via env vars to avoid storing secrets in config files.
- Improve documentation around anime parsing, category preference, and manual override flow (`docs/audio_alignment_pipeline.md`/README currently only hint at TMDB usage).
- Ensure future features reading TMDB metadata (e.g., HTML report, JSON tail consumers) are aware of optional fields (language/year) when matches fail.

---

## `[naming]` (reviewed 2025‑11‑19)

**Feature surface.** `NamingConfig` (`src/datatypes.py:179-184`) exposes two toggles: `always_full_filename` (fallback to full filenames when duplicates arise) and `prefer_guessit` (choose GuessIt over Anitopy parsing). Loader simply deserialises the section (`src/config_loader.py:372`), and runtime heuristics live in `src/utils.py:1-200` (`parse_filename_metadata`, release-group extraction, anime-specific labels) plus `dedupe_labels` in `src/frame_compare/metadata.py:39-75`. Runner invokes `metadata.parse_metadata(files, cfg.naming)` before planning, feeding labels into CLI layout, JSON tail, and slow.pics titles (`src/frame_compare/runner.py:494-520`). Tests under `tests/runner/test_cli_entry.py` verify overrides, deduping, and prefer-full-filename behaviour.

**Health check.**
- GuessIt + Anitopy fallback: when `prefer_guessit=True` the parser leverages GuessIt metadata (title, episode, release group, year), otherwise Anitopy provides anime-centric fields; both paths standardise episodes via `_normalize_episode_number`.
- `metadata.dedupe_labels` guarantees unique labels by switching to full filenames when configured, or by appending version tags (e.g., `v2`) or ordinal suffixes (`#2`) when short labels collide. Tests assert dedupe safety (`tests/runner/test_cli_entry.py`).
- Metadata dictionaries include release group, normalized episode markers, year, and fallback file name, enabling slow.pics/JSON tails to display consistent labels.

**Opportunities.**
1. **Docs coverage:** Neither README nor `docs/README_REFERENCE.md` explain `[naming].prefer_guessit` / `always_full_filename`. Add a table with examples (e.g., anime vs. live action naming) so operators understand the trade-offs.
2. **Granular control:** Current config is binary. Consider exposing per-directory or pattern-based controls (e.g., prefer Anitopy only for `[anime]` folders) or allowing custom label templates (include release group / resolution).
3. **CLI/wizard discoverability:** The wizard and CLI flags never mention naming options; adding prompts or `--prefer-guessit/--prefer-anitopy` flags would make the feature more accessible.
4. **Metadata enrichment:** We discard GuessIt’s `edition`, `other`, or audio cues that might render useful UI labels. Document or expose a hook for custom label formatting without editing core code.

**Risks / follow-ups.**
- Update docs to describe both knobs and the dedupe behaviour so users know why labels change.
- Consider structured label templates to avoid hardcoding `[Group] Title SxxEyy` logic inside `_build_label`.
- Evaluate adding CLI overrides (`--label-full-file-name`, `--label-prefer-anitopy`) for ad-hoc runs.

---

## `[cli]` (reviewed 2025‑11‑19)

**Feature surface.** `CLIConfig` (`src/datatypes.py:187-205`) currently exposes two knobs: `emit_json_tail` (default `true`) and `progress.style` (`fill` or `dot`). Loader normalises and validates the progress style (`src/config_loader.py:369-389`, `431-434`). Runtime consumption happens inside `runner.run`: the reporter flags `progress_style` for layout sections and suppresses JSON output when `emit_json_tail` is false (`src/frame_compare/runner.py:333-360`). Tests cover both behaviours: disabling the JSON tail (`tests/runner/test_cli_entry.py`) and progress-style binding in the Rich layout renderer (`tests/cli/test_layout.py:17-30`, relocated from `tests/test_cli_layout.py`). The template comments mention these keys, but README/reference docs omit them.

**Health check.**
- Validation rejects invalid styles up front and falls back to `"fill"` at runtime if configs drift, preventing layout crashes.
- Quiet/verbose behaviour is still governed by CLI flags rather than config, so the `[cli]` section only affects default JSON emission and progress look-and-feel; that separation is clear in code.
- When `emit_json_tail = false`, CLI output shows only Rich sections; `frame_compare.py:360-396` respects that flag.

**Opportunities.**
1. **Documentation gap:** Neither README nor `docs/README_REFERENCE.md` document `[cli]` options. Add entries describing JSON tail suppression (e.g., for CI logs) and progress style (fill vs dot) so users don’t have to inspect the template comments.
2. **Wizard discoverability:** The setup wizard never mentions `[cli]`; exposing prompts (or CLI flags like `--json-tail/--no-json-tail`) would improve usability, especially for operators who always want machine-readable output.
3. **Layout overrides:** Many users customise Rich layout paths or want to disable certain sections; consider expanding `[cli]` to include defaults for quiet/verbose, layout file overrides, or progress-bar enablement, rather than leaving everything flag-only.
4. **Testing for invalid configs:** Loader guards exist, but there’s no Doc/test ensuring incompatible combinations (e.g., emit_json_tail=false + automation expecting JSON). A doctor check or README warning could help automation teams avoid surprises.

**Risks / follow-ups.**
- Extend docs (and possibly wizard prompts) to cover `[cli]` keys.
- Evaluate adding env/flag overrides for `emit_json_tail` so automation doesn’t require config edits.
- Consider future `[cli]` fields (custom layout path, quiet default) and document the plan to avoid ad-hoc CLI flags.

---

## `[paths]` (reviewed 2025‑11‑19)

**Feature surface.** `PathsConfig` currently exposes `[paths].input_dir` (default `comparison_videos`). Loader deserialises the section (`src/config_loader.py:373`), while runtime enforcement lives in ADR‑driven helpers inside `src/frame_compare/core.py`: `_discover_workspace_root`, `_resolve_workspace_subdir`, `_is_writable_path`, `_path_is_within_root`, and `_abort_if_site_packages`. Wizard prompts let operators choose the relative input directory under the workspace root (`src/frame_compare/core.py:756-782`), doctor reports root/input paths and writability (`src/frame_compare/core.py:856-980`), and the `--diagnose-paths` command prints JSON diagnostics for root/config/media/screen directories (`frame_compare.py:200-320`). Runner uses `_resolve_workspace_subdir` to locate media, screenshots, analysis caches, report directories, VSPreview workspaces, etc. (`src/frame_compare/runner.py:260-2149`). Tests `tests/test_paths_preflight.py` exercise escape/writability guards, and ADR 0001 documents the root-lock policy (`docs/adr/0001-paths-root-lock.md`).

**Health check.**
- Root detection order honours `--root`, `FRAME_COMPARE_ROOT`, sentinel discovery, and rejects paths under `site-packages`/`dist-packages`. `prepare_preflight` ensures config/screen directories exist (or are created) and refuses to run when directories fall outside the workspace.
- `_resolve_workspace_subdir` guarantees subdirectories remain under the resolved root unless explicitly allowed (`allow_absolute=True` for ffmpeg temp files, etc.), preventing path traversal. That guard backs every path derived from config (screenshots directories, caches, reports, VSPreview scripts, etc.).
- `frame_compare --diagnose-paths` plus README guidance give users a supported way to inspect resolved directories and permission states before long runs.
- Tests cover path-escape attempts, non-writable directories, and CLI error messages so regressions are caught quickly (`tests/test_paths_preflight.py`, `tests/runner/test_cli_entry.py`).

**Opportunities.**
1. **Docs clarity:** Reference docs describe `[paths].input_dir` briefly, but ADR details (site-packages rejection, diag tool, config seeding) live elsewhere. Consolidate guidance in README/reference so operators don’t have to read ADRs for basic path info.
2. **Multi-root workflows:** Some users run comparisons from multiple media roots. Consider supporting a list of search paths or per-run overrides beyond `--input` (e.g., named presets or CLI arguments for multiple directories) to reduce config editing.
3. **Doctor coverage:** Doctor currently reports root and config issues; consider adding explicit warnings when `[paths].input_dir` doesn’t exist or is empty, mirroring the runtime error but earlier in the workflow.
4. **Wizard enhancements:** The wizard lists subdirectories but doesn’t explain the site-packages restriction or `--diagnose-paths`. Add guidance to reduce confusion when users pick non-writable locations.

**Risks / follow-ups.**
- Update docs (README + reference) to highlight ADR 0001 constraints and the `--diagnose-paths` workflow.
- Evaluate whether to expose optional absolute paths (with explicit opt-in) for advanced users while keeping defaults safe.
- Enhance doctor/wizard messaging to warn about empty/non-existent input directories before runs fail.

---

## `[runtime]` (reviewed 2025‑11‑19)

**Feature surface.** `RuntimeConfig` (`src/datatypes.py:209-216`) exposes `ram_limit_mb` and `vapoursynth_python_paths`. Loader validation ensures the RAM limit is positive (`src/config_loader.py:453-454`). `_init_clips` applies the limit via `vs_core.set_ram_limit` before indexing clips (`src/frame_compare/core.py:1884-1950`), and VS core functions enforce positive values (`src/vs_core.py:688`). `vapoursynth_python_paths` feeds VSPreview script generation and runtime configuration, with paths expanded and handed to VS core (`src/frame_compare/core.py:3291-3340`, `src/frame_compare/runner.py:519`). The feature is documented lightly in README (`[runtime].ram_limit_mb`, `VAPOURSYNTH_PYTHONPATH`) and validated by config tests (`tests/test_config.py`).

**Health check.**
- RAM guard prevents VapourSynth from exceeding memory limits on large clips; number is enforced during clip initialization and fails early when invalid.
- VapourSynth Python paths propagate into VSPreview scripts and runner configuration, giving operators a supported way to inject custom module locations.
- README and reference tables mention the RAM guard and environment variable for module paths, so the essentials are discoverable.

**Opportunities.**
1. **Docs depth:** Expand reference docs to explain how `ram_limit_mb` interacts with VapourSynth (e.g., recommended values for 4K vs 1080p) and show how `vapoursynth_python_paths` plays with `VAPOURSYNTH_PYTHONPATH`. Currently, operators must infer behaviour from template comments.
2. **Wizard support:** The setup wizard skips `[runtime]`. Consider prompting for RAM limits on constrained machines or at least documenting how to adjust the setting post-wizard.
3. **Diagnostics:** `--diagnose-paths` covers directories but not runtime environment (e.g., whether VapourSynth imports succeed). Adding doctor checks for VapourSynth module discovery would tie into `vapoursynth_python_paths`.
4. **Per-workload overrides:** Some workflows may need temporary RAM guard adjustments; exposing CLI flags (e.g., `--ram-limit`) or environment overrides would reduce config edits.

**Risks / follow-ups.**
- Enhance documentation/wizard guidance for `[runtime]`.
- Consider CLI/env overrides for `ram_limit_mb` and python paths.
- Add doctor diagnostics to detect missing VapourSynth modules and recommend editing `[runtime].vapoursynth_python_paths`.

---

## `[source]` (reviewed 2025‑11‑19)

**Feature surface.** `SourceConfig` (`src/datatypes.py:217-221`) exposes a single knob: `preferred`, defaulting to `"lsmas"`. Loader validation restricts the value to `"lsmas"` or `"ffms2"` (`src/config_loader.py:575-577`). Runtime plumbs the choice into VapourSynth via `vs_core.configure(..., source_preference=cfg.source.preferred)` used by runner and VSPreview scripts (`src/frame_compare/core.py:3291-3340`, `src/frame_compare/runner.py:519`). `vs_core` enforces the preference and raises informative errors when unsupported values are provided or when liblsmash/FFMS2 binaries are missing (`src/vs_core.py:310-480`). Tests cover config validation (`tests/test_config.py`), while docs only briefly mention the key (`docs/README_REFERENCE.md:175`).

**Health check.**
- Loader guards and VS core validation ensure only supported plugins are configured, preventing late failures.
- Preference flows through both runtime and VSPreview scripts, so manual alignment and CLI rendering stay in sync.
- Error messages hint at required dependencies (e.g., brew install l-smash) when LSmas libraries are missing.

**Opportunities.**
1. **Docs depth:** README/reference only list the key without explaining when to switch to `ffms2` (e.g., for exotic codecs or OS X). Expand documentation with guidance/examples.
2. **Wizard discoverability:** The initial wizard does not prompt for source preference. Adding an optional question (LSMAS vs FFMS2) would help operators who know their pipelines upfront.
3. **Fallback strategy:** If `lsmas` fails at runtime, the pipeline currently errors. Consider an optional fallback to FFMS2 with warnings, or at least a CLI flag to override on the fly (`--source ffms2`).
4. **Per-clip overrides:** Some sources require different loaders. Exposing per-file overrides (similar to `[overrides]` trims) would add flexibility.

**Risks / follow-ups.**
- Improve docs/wizard messaging so operators understand the trade-offs between LSMAS and FFMS2.
- Evaluate CLI/env overrides and auto-fallback strategies for better resiliency.
- Consider per-clip loader overrides for edge cases.

---

## `[overrides]` (reviewed 2025‑11‑19)

**Feature surface.** `OverridesConfig` (`src/datatypes.py:261-268`) exposes per-clip `trim`, `trim_end`, and `change_fps` maps. Loader validation enforces integer trims and `["num","den"]` or `"set"` for FPS overrides (`src/config_loader.py:630-632`). `planner.build_plans` normalises keys (index, filename, stem, release group, `file_name`) and applies matching overrides to clip plans (`src/frame_compare/planner.py`). Runner telemetry discloses active overrides (`src/frame_compare/runner.py:507-1160`), and tests (`tests/runner/test_cli_entry.py`, `tests/test_planner.py`) cover both config parsing and runtime behaviour alongside naming logic.

**Health check.**
- Strict validation prevents malformed overrides from slipping through.
- Matching logic supports multiple identifiers per clip, so operators can target overrides without renaming files.
- JSON tail/layout output reflects applied trims/FPS overrides, aiding visibility.

**Opportunities.**
1. **Docs coverage:** README/reference barely mention `[overrides]`. Add a table with examples (`trim = { "0" = 120, "encode.mkv" = -24 }`, `change_fps = { "clip" = [24000,1001], "1" = "set" }`) and explain lookup precedence.
2. **Wizard + diagnostics:** The wizard doesn’t surface overrides, and typos silently no-op. Consider prompts or doctor warnings for override keys that did not match any clip.
3. **Additional override types:** Operators often ask for per-clip overlay toggles, color overrides, or render exclusions. Plan how to extend overrides (or introduce sibling sections) without bloating the schema.
4. **Runtime feedback:** Add explicit log lines (“Applied trim override: clip=Foo +120f”) to reduce guesswork when overrides apply.

**Risks / follow-ups.**
- Document lookup rules and add wizard/doctor guidance for `[overrides]`.
- Detect/report unused override entries.
- Expand override capabilities (color/report toggles) carefully to avoid schema sprawl.
