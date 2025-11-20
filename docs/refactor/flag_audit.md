# Flag & Config Audit

> Source of truth for the ongoing audit of configuration, environment, and CLI flags in `frame-compare`.

## How to Use This Doc

- **Track A – Color/Tonemap & DoVi** is primarily for **Session 1** (focus on `[color]`, `--tm-*` flags, and DoVi behaviour).
- **Track B – Global Config + Flag Audit** is primarily for **Session 2** (all other config domains and flags).
- **Implementation / Dev agents**:
  - Fill in the **Implementation Notes** sections: Track A → A2, Track B → B3.
  - Check off the relevant checkboxes as you complete items.
  - Record tests and commands you ran and any fixes you applied.
- **Review / Code‑review agents**:
  - Fill in the **Review Notes** sections: Track A → A3, Track B → B4.
  - Verify the **Global Invariants** and domain checklists are satisfied.
  - Note any remaining issues, questions, or follow‑up tasks.

## Overview

- **Goal:** Ensure no CLI flag or environment setting silently overrides config when the user didn't ask for it, and that `frame_compare.run_cli` and the Click CLI behave consistently for the same inputs.
- **Tracks:**
  - **Track A – Color/Tonemap & DoVi**
  - **Track B – Global config + flag audit**

## Global Invariants (Target State)

- [x] Config + env + CLI precedence is well defined and documented.
- [x] "Flag not passed" means "no override"; config values still apply.
- [x] `frame_compare.run_cli` and `frame_compare.py` produce the same effective settings for the same config + flags.
- [x] All tri-state/boolean fields that can be set from CLI have explicit tests for:
  - [ ] No flags
  - [ ] Explicit enable flag
  - [ ] Explicit disable flag

**Critical toggles to verify across config + CLI:**

- [x] `color.use_dovi` (DoVi)
- [x] `color.visualize_lut`
- [x] `color.show_clipping`
- [x] `screenshots.use_ffmpeg`
- [x] `analysis` enable / thresholds (where applicable)
- [x] `audio_alignment.enable` / `audio_alignment.use_vspreview`
- [x] `slowpics.auto_upload`
- [x] `report.enable`
- [x] `cli.emit_json_tail`
- [x] Cache flags: `--no-cache`, `--from-cache-only`, `--show-partial`, `--show-missing/--hide-missing`

---

## Track A – Color/Tonemap & DoVi

### A1. Inventory & Baseline

- [x] List `[color]` fields from config schema.
- [x] List all `--tm-*` CLI flags and how they map into `tonemap_overrides`.
- [x] Confirm current DoVi behaviour:
  - [x] Direct `run_cli` path.
  - [x] Click CLI path. (Covered by `tests/runner/test_dovi_flags.py` default/explicit flag cases.)

#### `[color]` schema snapshot

- Tonemap core: `enable_tonemap`, `preset`, `tone_curve`, `dynamic_peak_detection`, `target_nits`, `dst_min_nits`, `knee_offset`, `dpd_preset`, `dpd_black_cutoff`.
- Per-frame tuning: `post_gamma_enable`, `post_gamma`, `smoothing_period`, `scene_threshold_low`, `scene_threshold_high`, `percentile`, `contrast_recovery`.
- Metadata and HDR toggles: `metadata`, `use_dovi`, `visualize_lut`, `show_clipping`, `dynamic_peak_detection` (stored twice as `dpd`/`dynamic_peak_detection` in JSON tail for CLI layout folding).
- Overlay controls: `overlay_enabled`, `overlay_mode`, `overlay_text_template`.
- Verification controls: `verify_enabled`, `verify_frame`, `verify_auto`, `verify_start_seconds`, `verify_step_seconds`, `verify_max_seconds`, `verify_luma_threshold`, `strict`.
- Debug/defaulting helpers: `default_matrix_hd/sd`, `default_primaries_hd/sd`, `default_transfer_sdr`, `default_range_sdr`, `color_overrides`, `debug_color`.

#### CLI `--tm-*` surface → `tonemap_overrides[...]`

- Scalar overrides map 1:1 to color config fields: `--tm-preset`, `--tm-curve`, `--tm-target` → `target_nits`, `--tm-dst-min`, `--tm-knee`, `--tm-dpd-preset`, `--tm-dpd-black-cutoff`, `--tm-gamma` (pairs with `--tm-gamma-disable` to flip `post_gamma_enable`), `--tm-smoothing`, `--tm-scene-low`, `--tm-scene-high`, `--tm-percentile`, `--tm-contrast`, `--tm-metadata`.
- Tri-state toggles write explicit booleans only when the user passes a flag: `--tm-use-dovi/--tm-no-dovi` → `use_dovi`, `--tm-visualize-lut/--tm-no-visualize-lut` → `visualize_lut`, `--tm-show-clipping/--tm-no-show-clipping` → `show_clipping`.
- `_run_cli_entry()` coalesces all of the above into a `tonemap_override` dict that feeds `runner.run(request)`; direct `frame_compare.run_cli(..., tonemap_overrides=None)` matches the unmodified config path.

#### DV sanity commands (reference)

Use these commands to compare direct vs Click CLI behaviour for a given config:

- **Direct `run_cli` (preflight‑resolved config):**

  ```pwsh
  uv run python -c "
  import json, frame_compare
  result = frame_compare.run_cli(
      None,
      None,
      quiet=False,
      verbose=False,
      no_color=True,
      root_override=None,
      report_enable_override=None,
      skip_wizard=False,
      debug_color=False,
      tonemap_overrides=None,
  )
  print(json.dumps(result.json_tail['tonemap'], indent=2))
  "
  ```

- **Click CLI (frame_compare.py):**

  ```pwsh
  uv run frame_compare.py --no-color --json-pretty
  ```

### A2. Implementation Notes (Dev Agent)

- Summary of changes:
  - [x] `tm_use_dovi`, `tm_visualize_lut`, `tm_show_clipping` only override when flags are explicitly passed (use Click `ParameterSource`).
  - [x] Any similar tri-state flags updated to follow the same pattern.
- Tests added/updated:
  - [x] `tests/runner/test_dovi_flags.py` (or similar).
  - [x] Any snapshot/JSON-tail tests that assert `use_dovi` behaviour.
- Commands run:
  - [x] `.venv/Scripts/pyright --warnings`
  - [x] `.venv/Scripts/ruff check`
  - [x] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/Scripts/pytest -q tests/runner/test_dovi_flags.py`

#### A2 Notes

- Date: 2025-11-18
- Dev Agent: Codex (implementation persona)
- Short summary: Introduced `_cli_override_value()` so every `--tm-*` option defers to config unless `ctx.get_parameter_source()` reports a real CLI flag, matching the tested DoVi behaviour for default-map runs while still allowing explicit overrides. Extended `tests/runner/test_dovi_flags.py` to cover default-map vs `--tm-target` flags plus overlay/verify JSON-tail parity so regression tests capture the end-to-end tonemap/overlay surfaces.

### A3. Review Notes (Review Agent)

- [x] Verified `frame_compare.run_cli` vs `frame_compare.py` behaviour for:
  - [x] DoVi on via config only.
  - [x] DoVi off via config only.
  - [x] Explicit `--tm-use-dovi` vs `--tm-no-dovi`.
- [x] Confirmed no other `--tm-*` flags implicitly override config when not passed.
- [x] Documentation aligned (README/CHANGELOG/DECISIONS).

#### A3 Findings

- `_cli_override_value()` gates all `--tm-*` overrides on Click `ParameterSource.COMMANDLINE`, so default_map/env values never override config when the user stays silent (`frame_compare.py:494-733`). Click’s docs confirm `Context.get_parameter_source()` only reports `COMMANDLINE` for explicit flags (source:https://github.com/pallets/click/blob/main/docs/commands-and-groups.rst@2025-11-18T10:57:24Z via Context7), which matches the behaviour under review.
- `_apply_cli_tonemap_overrides()` only mutates keys present in `tonemap_overrides`, and `json_tail["tonemap"]`/`["overlay"]`/`["verify"]` reuse the config-backed values emitted by `vs_core.resolve_effective_tonemap` (`src/frame_compare/runner.py:290-333`, `1696-1781`, `1985-2018`). That keeps DoVi, overlay, and verify telemetry identical between direct `frame_compare.run_cli` and the Click CLI.
- Regression tests cover “no flag vs `--tm-use-dovi/--tm-no-dovi`/`--tm-visualize-lut`/`--tm-show-clipping` plus overlay & verify parity), and they pass alongside static analysis: `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/runner/test_dovi_flags.py`.

#### A3 Open Questions

- None for Phase 1–2; later tracks (render/screenshots, analysis/cache, etc.) will be re-evaluated during Phase 3.

#### A3 Reviewer

- Codex review agent

#### A3 Date

- 2025-11-18

---

## Track B – Global Config + Flag Audit

### B1. Schema & Load Path

- [x] Enumerate `AppConfig` and sub-configs (Analysis, Screenshots, AudioAlignment, Slowpics, Report, Paths, Runtime, Overrides, Source, TMDB, CLI).
- [x] Document how `load_config` and `prepare_preflight` resolve:
  - [x] Config path.
  - [x] Workspace root.
  - [x] Input dir.
  - [x] Legacy config.

#### AppConfig section inventory (source: `src/datatypes.py`)

- **`[analysis]`** – dark/bright/motion frame counts, random sampling, downscale resolution, frame-step, SDR analysis toggle, thresholds (mode + quantiles/ranges), motion heuristics, windowing, frame-data filename, ignore-lead/trail windows.
- **`[screenshots]`** – `directory_name`, `use_ffmpeg`, `add_frame_info`, `single_res`, `upscale`, `mod_crop`, letterbox handling (`auto_letterbox_crop`, `pad_to_canvas`, `center_pad`, `letterbox_px_tolerance`, `letterbox_pillarbox_aware`), `compression_level`, `ffmpeg_timeout_seconds`, `odd_geometry_policy`, `rgb_dither`, `export_range`.
- **`[color]`** – tonemap, overlay, verification, and DoVi controls (full list captured in Track A → A1).
- **`[audio_alignment]`** – enable flag, reference clip label, VSPreview toggles/mode, prompt reuse, STFT parameters (`sample_rate`, `hop_length`), optional start/duration, `correlation_threshold`, `max_offset_seconds`, offsets filename, preview confirmations, `random_seed`, `frame_offset_bias`.
- **`[slowpics]`** – upload automation options (`auto_upload`, privacy, `collection_name/suffix`, `tmdb_id/category`), lifecycle toggles (`remove_after_days`, `delete_screen_dir_after_upload`), webhook + timeout knobs, open-in-browser + shortcut toggles.
- **`[report]`** – HTML report gating (`enable`, `open_after_generate`), `output_dir`, `title`, default labels, metadata verbosity, thumbnail height, slider/overlay default mode.
- **`[paths]`** – `input_dir` root (relative to workspace by default).
- **`[runtime]`** – `ram_limit_mb`, extra `vapoursynth_python_paths`.
- **`[overrides]`** – clip-specific `trim`, `trim_end`, `change_fps` dictionaries.
- **`[source]`** – preferred VapourSynth source plugin (`lsmas` vs `ffms2`).
- **`[tmdb]`** – API key, unattended flag, confirmation behaviour, `year_tolerance`, anime parsing, cache TTL/size, optional `category_preference`.
- **`[cli]`** – `emit_json_tail` plus nested `progress.style`.
- **`[naming]`** – filename parsing toggles (`always_full_filename`, `prefer_guessit`).

#### Config loader + preflight notes (sources: `src/config_loader.py`, `src/frame_compare/preflight.py`)

- **Workspace root precedence**: `--root` CLI arg ➜ `FRAME_COMPARE_ROOT` ➜ sentinel discovery (walk up until `pyproject.toml`, `.git`, or `comparison_videos` found) ➜ current working directory. `resolve_workspace_root()` throws if the resolved path sits under `site-packages`.
- **Config path resolution**: `--config` ➜ `FRAME_COMPARE_CONFIG` ➜ `<workspace>/config/config.toml`. `_seed_default_config()` writes `config/config.toml` from the packaged template when `ensure_config=True` and nothing exists. Legacy `<workspace>/config.toml` still loads but `prepare_preflight()` appends a warning encouraging migration.
- **Media/input directory**: CLI `--input` overrides `[paths].input_dir`, otherwise `resolve_subdir()` expands the configured value relative to the workspace input root (unless CLI forced an absolute path). The helper rejects paths that escape the workspace.
- **Environment toggles**: `FRAME_COMPARE_NO_WIZARD` skips the auto-wizard for fresh workspaces, `FRAME_COMPARE_CONFIG`/`FRAME_COMPARE_ROOT` act as documented above.
- **`load_config()` coercions**: normalises booleans/enums, clamps tonemap values (gamma, knee, dpd cutoff), parses metadata (`auto`, named HDR formats, or ints 0–4), ensures `[report].output_dir` stays relative, validates audio alignment ranges, and tracks `_provided_keys` on each dataclass so tonemap presets know which fields the user explicitly set.

### B2. Domain Checklists

#### CLI flag catalog (non-`--tm-*`)

- **Path + config**: `--root`, `--config`, `--input` feed directly into `prepare_preflight()` (root override ➜ workspace discovery ➜ config path ➜ media root). `--diagnose-paths` short-circuits the run to print `collect_path_diagnostics()`. `--write-config`/`--no-wizard` control config seeding/autowizard.
- **Cache / render toggles**: `--no-cache` (force recompute), `--from-cache-only` (serve snapshots, error when cache missing), `--show-partial`, paired `--show-missing/--hide-missing` (propagate to `RunRequest.show_{partial,missing}_sections`), `--no-color`, `--quiet`, `--verbose`, `--json-pretty`.
- **Report + slow.pics**: `--html-report` / `--no-html-report` toggle `report_enable_override`, `--debug-color` injects `cfg.color.debug_color=True`, and slow.pics automation inherits `[slowpics]` config (no direct CLI flags today).
- **Audio alignment**: `--audio-align-track label=index` forwards tuples to `runner.run(request).audio_track_overrides`; selection/confirmation flows patch CLI runtime structures accordingly.
- **Misc runtime**: `--diagnose-paths`, `--write-config`, `--doctor`, `wizard/preset` commands, and `--run` subcommand all funnel through `_run_cli_entry()` so `frame_compare.run_cli()` stays authoritative for runtime behaviour.

#### Screenshots / Render

- [x] Confirm `[screenshots]` fields: directory, writer, scaling, pad, compression, etc. (`src/datatypes.py:120-171` continues to mirror `cli_layout` render sections.)
- [x] Map any CLI flags that touch screenshots. (No direct CLI flags today; `debug_color` w/ tonemap pipeline is the only writer-affecting toggle.)
- [x] Verify:
  - [x] No hidden defaults override config — runner now derives the render writer from both `cfg.screenshots.use_ffmpeg` **and** `cfg.color.debug_color`, so CLI `--debug-color` no longer forces a silent writer swap (`src/frame_compare/runner.py:1658-1679`).
  - [x] JSON `render` block matches effective settings — added `tests/runner/test_cli_entry.py::test_render_writer_matches_debug_color` to exercise both `frame_compare.run_cli()` and the Click CLI with/without `--debug-color`.

#### Analysis / Cache

- [x] Review `[analysis]` config. (`src/datatypes.py:32-119` reconfirmed as source of truth for cache/save settings.)
- [x] Verify `--no-cache`, `--from-cache-only`, `--show-partial`, `--show-missing`:
  - [x] Only affect behaviour when explicitly passed — `_cli_flag_value()` now ignores Click `default_map` / env sources so `RunRequest.force_cache_refresh`, `from_cache_only`, and `RenderOptions` toggles only flip when the user provides a flag (`frame_compare.py:714-749`).
  - [x] Match documentation — regression tests `tests/runner/test_cli_entry.py::test_cli_cache_flags_ignore_default_map` and `::test_cli_cache_flags_follow_commandline` assert both the default-map safety net and the explicit-flag path.

#### Audio Alignment

- [x] Review `[audio_alignment]` config and overrides (manual trims, vspreview). (`src/datatypes.py:222-256` + `src/frame_compare/runner.py:590-672` confirmed the config-driven JSON tail fields for enable + VSPreview flags.)
- [x] Verify CLI flags (e.g., `--audio-align-track`) don't reset config when absent. Added `_cli_override_value` gating for multi-value `--audio-align-track` plus `tests/runner/test_cli_entry.py::test_cli_audio_align_track_requires_flag` to prove default_map values are ignored while explicit flags still propagate.

#### Slowpics / Report / Viewer

- [x] Review `[slowpics]`, `[report]`, and viewer-related fields (`src/datatypes.py:180-220` + `src/frame_compare/runner.py:536-687`).
- [x] Verify override semantics for `--html-report`, `--no-html-report`, etc. Gated both flags via `_cli_flag_value()` so config `[report].enable` remains authoritative unless the user passes an override, and covered with `tests/runner/test_cli_entry.py::test_cli_html_report_flags_ignore_default_map` + `::test_cli_html_report_flags_follow_commandline`. Slowpics auto-upload continues to rely solely on `cfg.slowpics.auto_upload`; CLI never injects overrides (`runner.py:536-584` warning path validated during manual trace).

#### Paths / Root / Input

- [x] Verify precedence: `--root` / `FRAME_COMPARE_ROOT` / sentinel search. `_cli_override_value()` now drops CLI `default_map` values for `--root`, `--config`, and `--input` so preflight discovery continues to resolve root + config path from env/sentinel unless the user passes a flag (`frame_compare.py:700-732`). Tests `test_cli_input_override_requires_flag` / `test_cli_input_flag_overrides_config` exercise both default and explicit behaviour.
- [x] Confirm `--config` / `FRAME_COMPARE_CONFIG` overrides and no surprise fallbacks. Manual trace (`src/frame_compare/preflight.py:215-411`) + request recorder demonstrate that config path/root overrides only flow through when `ctx.get_parameter_source()==COMMANDLINE`.

#### TMDB / Source / Runtime / CLI

- [x] Review `[tmdb]`, `[source]`, `[runtime]`, `[cli]`, `[overrides]`.
- [x] Ensure fields like `cli.emit_json_tail`, runtime flags, etc., are only overridden intentionally. Stitched `_cli_flag_value()` into `--debug-color` so the tonemap pipeline only flips into debug mode when asked, leaving `[color].debug_color` and `[cli].emit_json_tail` untouched by default maps or env. Regression tests `test_cli_debug_color_requires_flag` plus the render-writer assertions confirm both CLI entry points preserve config defaults while still honoring explicit flags.

### B3. Implementation Notes (Dev Agent)

- For each domain, record:
  - [x] Issues found (if any) and fixes applied.
  - [x] Tests updated/added.
  - [x] Any decisions on intentional precedence.

#### B3 Notes

- Date: 2025-11-18
- Dev Agent: Codex (implementation persona)
- Key changes & rationale:
  - Documented every `AppConfig` section plus CLI flag/load-precedence mapping so Phase 3 can reference a single index (Track B → B1/B2).
  - Tightened CLI tonemap overrides to ignore `default_map`/implicit values, keeping control inside config/env for “flag not passed” cases.
  - Extended `tests/runner/test_dovi_flags.py` to pin `--tm-target` CLI overrides vs default-map behaviour and to assert overlay + verify telemetry stays config-driven in both CLI and direct-run entrypoints.
  - Expanded `_cli_override_value` with `_cli_flag_value` and gated every remaining override-capable CLI flag (`--root/--config/--input`, cache toggles, HTML report, audio track, `--debug-color`) so Click `default_map`/env sources can't silently supersede config/preflight precedence (`frame_compare.py:700-757`). Backed by new tests in `tests/runner/test_cli_entry.py` (`test_cli_cache_flags_ignore_default_map`, `test_cli_html_report_flags_ignore_default_map`, `test_cli_input_override_requires_flag`, `test_cli_audio_align_track_requires_flag`, `test_cli_debug_color_requires_flag`).
  - Synced render JSON metadata with the actual writer selected when color-debug mode disables ffmpeg (`runner.py:1658-1679`) and validated both entrypoints via `tests/runner/test_cli_entry.py::test_render_writer_matches_debug_color`.
  - Commands executed for verification:
    - `./.venv/bin/pyright --warnings`
    - `./.venv/bin/ruff check`
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -q tests/runner`

### B4. Review Notes (Review Agent)

- [x] Verified behaviour against docs and expectations for each domain.
- [x] Confirmed no remaining "implicit override" patterns.
- [x] Suggested any follow-up tasks (if necessary).

#### B4 Findings

##### Screenshots / Render
- Debug toggles now respect config-first precedence: `_cli_flag_value()` only forwards `--debug-color` when a user actually passes the flag, and `runner.run` derives the render writer from `[screenshots].use_ffmpeg` gated by the effective debug flag (`frame_compare.py:739-752`, `src/frame_compare/runner.py:360-420`, `:1659-1679`). `tests/runner/test_cli_entry.py::test_cli_debug_color_requires_flag` plus `::test_render_writer_matches_debug_color` cover both Click CLI sources and direct `frame_compare.run_cli`.

##### Analysis / Cache
- `--no-cache`, `--from-cache-only`, `--show-partial`, and `--show-missing/--hide-missing` only mutate `RunRequest` when a command-line flag is present (`frame_compare.py:739-747`). `tests/runner/test_cli_entry.py::test_cli_cache_flags_ignore_default_map` / `::follow_commandline` prove the guard rails, and `src/frame_compare/runner.py:500-580` / `:1120-1188` show the corresponding cache probe + recompute paths that honour those flags.

##### Audio Alignment
- CLI audio-track overrides require explicit `--audio-align-track` inputs, so config-defined trims and offsets remain intact unless the user opts in (`frame_compare.py:708-717`, `tests/runner/test_cli_entry.py::test_cli_audio_align_track_requires_flag`). JSON tail fields for `enable`, `use_vspreview`, preview/manual offsets, and VSPreview commands all come directly from config in `src/frame_compare/runner.py:592-630`, and `tests/runner/test_audio_alignment_cli.py` exercises both config-only and CLI-override scenarios (including vspreview scripts and manual trims).

##### Slowpics / Report / Viewer
- HTML report toggles only override config when `--html-report`/`--no-html-report` is supplied (`frame_compare.py:748-752`, `tests/runner/test_cli_entry.py::test_cli_html_report_flags_*`). Slowpics upload, shortcut, and cleanup workflows remain config-driven (`frame_compare.py:322-386`, `src/frame_compare/runner.py:640-720`) with no CLI surface, matching Track B’s expectations.

##### Paths / Root / Input
- Precedence order is CLI flag → env var → sentinel search inside `src/frame_compare/preflight.py:210-333`. `_cli_override_value()` prevents `default_map` values from masquerading as overrides for `--root`, `--config`, or `--input` (`frame_compare.py:703-708`), and `tests/runner/test_cli_entry.py::test_cli_input_override_requires_flag` / `::test_cli_input_flag_overrides_config` validate both cases.

##### TMDB / Source / Runtime / CLI
- CLI runtime toggles stop at `--quiet/--verbose/--json-pretty`; `[cli].emit_json_tail` and progress styles only respect config (`src/frame_compare/runner.py:500-520`), with `tests/runner/test_cli_entry.py::test_cli_disables_json_tail_output` confirming the Click CLI obeys config defaults. TMDB/source/runtime behaviour stays config-driven (`src/frame_compare/runner.py:700-990`), and no remaining CLI knobs silently mutate `[tmdb]`, `[source]`, or `[runtime]` settings.

##### Cross-entrypoint consistency, docs, and verification
- `tests/runner/test_dovi_flags.py` plus `tests/runner/test_cli_entry.py::test_render_writer_matches_debug_color` show `frame_compare.run_cli` and the Click CLI emitting identical tonemap/debug metadata for Phases 3–6 toggles. README cache/CLI sections (README.md:340-390) and `CHANGELOG.md` (“Unreleased → Features/Bug Fixes/Chores”) describe the precedence rules documented in Track B, so docs/tests now match code. Re-ran `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/runner/test_cli_entry.py tests/runner/test_audio_alignment_cli.py tests/runner/test_dovi_flags.py` to sign off on the behaviour.

#### B4 Follow-ups

- No open issues for Track B Phases 3–6; future work can focus on net-new flags or UX.

#### B4 Reviewer

- Codex review agent

#### B4 Date

- 2025-11-18

---

## Test Commands

When closing a track or major sub-task, run:

- `.venv/Scripts/pyright --warnings`
- `.venv/Scripts/ruff check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/Scripts/pytest -q` (or a narrower subset for focused changes)

**Examples:**

- For DoVi/tonemap work in Track A:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/Scripts/pytest -q tests/runner/test_dovi_flags.py`
- For broader CLI/runtime changes in Track B:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/Scripts/pytest -q tests/runner`

---

## Open Issues / TODO

- [ ] None (no outstanding Track B items after Phase 3–6 review)

---

## Track C – Overlay Diagnostics Expansion

> Scope: Enhance the overlay’s diagnostic mode with additional HDR/DV metadata (DoVi L2 summary, MaxCLL/MaxFALL, dynamic range labels, per-frame nit metrics, etc.).

### C1. Discovery & Data Mapping (Phase 1)

- [x] Inventory existing metadata sources:
  - [x] DV metadata (L1/L2) in `metadata_utils` / `vs_core`.
  - [x] HDR mastering metadata (MaxCLL/MaxFALL) stored per clip.
  - [x] Dynamic range detection logs (`limited` vs `full`).
  - [x] Cached per-frame metrics (analysis caches, selection details).
- [x] Document overlay pipeline:
  - [x] Where `json_tail["overlay"]` is built (`runner.py`).
  - [x] How `overlay_text_template`/`overlay_mode` influence rendering.
  - [x] Where overlay text is rendered in screenshot pipeline.
- [x] Identify gating options:
  - [x] Existing diagnostic/`overlay_mode` toggles.
  - [x] Potential new config/CLI flags for expensive metrics (per-frame nits).
- [x] Record findings (files, fields, perf notes) below.

> Notes (discovery summary):
> - DV metadata source: `ClipPlan.source_frame_props` captures raw VapourSynth props during probe (`src/frame_compare/cli_runtime.py:118-155`) and `_capture_source_props_for_probe()` pushes them into cached plans before `vs_core.process_clip_for_screenshot` merges them back (`src/frame_compare/selection.py:67-104`, `src/frame_compare/vs/tonemap.py:892-939`). Any Dolby Vision RPU/L2 frame props surfaced by the source plugins therefore survive into overlay diagnostics without re-reading media. VapourSynth frame props are explicitly preserved via `ClipToProp`/`FrameProps` semantics (source:https://github.com/vapoursynth/vapoursynth/blob/master/doc/functions/video/cliptoprop.rst@2025-11-19).
> - HDR metadata source: `vs.source._is_hdr_prop()` and `_collect_blank_extension_props()` persist `MasteringDisplay*` and `ContentLightLevel*` props per clip (`src/frame_compare/vs/source.py:360-411`), which `render/overlay.extract_mastering_display_luminance()` consumes to calculate MaxCLL/MaxFALL lines inside diagnostic overlays (`src/frame_compare/render/overlay.py:72-150`).
> - Dynamic range detection: `vs/color._detect_rgb_color_range()` samples plane stats to classify limited/full (`src/frame_compare/vs/color.py:223-322`), and `vs/tonemap.process_clip_for_screenshot()` stores the decision on `TonemapInfo.range_detection`/`output_color_range` for later telemetry (`src/frame_compare/vs/tonemap.py:940-1184`).
> - Cached per-frame metrics: `analysis/selection.py` builds brightness/motion tuples and injects the numeric score + selection note into `SelectionDetail` records, which are persisted via `analysis/cache_io.save_cached_metrics()` and exposed through `json_tail["analysis"]["selection_details"]` (`src/frame_compare/analysis/selection.py:599-930`, `src/frame_compare/runner.py:1354-1476`, `src/frame_compare/analysis/cache_io.py:867-1020`). Those values are the only readily available per-frame metrics without replaying VapourSynth.
> - Overlay template path: `runner.py` writes `json_tail["overlay"]` immediately after tonemap metadata resolution (`src/frame_compare/runner.py:1544-1640`), `vs/tonemap._format_overlay_text()` formats the base template (`src/frame_compare/vs/tonemap.py:624-705`), and `screenshot._compose_overlay_text()`/`render/overlay.compose_overlay_text()` append diagnostic text before `_save_frame_with_fpng/_save_frame_with_ffmpeg` render it onto the frame (`src/screenshot.py:215-285,2525-2665`, `src/frame_compare/render/overlay.py:79-138`).
> - Gating strategy: `[color].overlay_enabled`, `[color].overlay_mode`, and `[color].debug_color/strict` already guard overlay work (`src/datatypes.py:100-152`, `src/frame_compare/runner.py:1512-1543`). Per-frame diagnostics will hang off a new `[diagnostics]` config/CLI flag so expensive metric/math runs are opt-in while default modes remain unchanged.

### C2. Implementation Plan

- [ ] DV diagnostics:
  - [ ] Include `use_dovi_label` in overlay diagnostics context.
  - [ ] Surface DV L2 summary (block info, brightness target) when available.
- [ ] HDR metadata:
  - [ ] Expose MaxCLL/MaxFALL per clip.
  - [ ] Add dynamic range classification (limited/full) to overlay data.
- [ ] Per-frame metrics (gated):
  - [ ] Determine data availability (cached vs recompute).
  - [ ] Add config/CLI toggle for expensive computations.
  - [ ] Surface frame max/avg nits and DV RPI Level 1 stats when enabled.
- [ ] Update overlay context:
  - [ ] Extend `json_tail["overlay"]["diagnostics"]` with structured data.
  - [ ] Provide default diagnostic template (multi-line) when `overlay_mode == "diagnostic"`.
- [ ] Tests & docs:
  - [ ] Add unit/integration tests covering new diagnostics.
  - [ ] Update README + docs/DECISIONS.md describing diagnostic overlay features/perf costs.

### C3. Implementation Notes (Dev Agent)

- Work performed:
  - [x] DV diagnostics added.
  - [x] HDR metadata added.
  - [x] Per-frame metrics gated + added.
  - [x] Overlay template updated.
  - [x] Tests/docs updated.
- Commands run:
  - [x] `.venv/bin/pyright --warnings` → `0 errors, 0 warnings, 0 informations`
  - [x] `.venv/bin/ruff check` → `All checks passed!`
  - [x] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/runner/test_overlay_diagnostics.py tests/runner/test_cli_entry.py tests/runner/test_dovi_flags.py tests/render/test_overlay_text.py tests/frame_compare/test_diagnostics.py` → `66 passed in 0.43s`

> Notes:
> - Date: 2025-11-19
> - Dev Agent: OverlaySleuth
> - Summary of metrics availability/gating decisions: `[diagnostics].per_frame_nits` now gates the per-frame nit estimator and surfaces its state (config + CLI override + overlay_mode) inside `json_tail["overlay"]["diagnostics"]["frame_metrics"]["gating"]`. Dolby Vision (label + L2 summary), HDR mastering metadata (MDL/MaxCLL/MaxFALL), and color-range detection all populate `json_tail["overlay"]["diagnostics"]` with optional blocks so downstream consumers can tolerate missing fields. CLI `--diagnostic-frame-metrics/--no-diagnostic-frame-metrics` toggles the same gating at runtime, and diagnostic overlays only render the per-frame measurement line when the gating conditions pass.
- Known regression: VSPreview overlay “suggested frame/seconds” hints remain stuck at 0f/0.000 s since the runner refactor. Add to backlog and restore the original behaviour so manual alignment users regain guidance.

### C4. Review Notes (Review Agent)

- Persona: **MetaSentinel**, skeptical reviewer. Confirms diagnostics and gating match plan, replays verification commands if evidence missing, records findings with file:line references.
- Tasks:
  - [ ] Review docs (`docs/refactor/flag_audit.md` Track C, `docs/DECISIONS.md`, README) to ensure overlays described accurately and Implementation Notes (C3) are filled.
  - [ ] Inspect code changes (runner overlay construction, metadata extraction, overlay templates) verifying DV/HDR/per-frame data populates `json_tail["overlay"]["diagnostics"]` and is gated properly.
  - [ ] Confirm config/CLI toggles (diagnostic mode, per-frame metric flag) behave as documented; run targeted tests if necessary.
  - [ ] Check tests cover DV/HDR inclusion, gating, template fallbacks; rerun `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/runner/test_overlay_diagnostics.py` if coding agent didn’t capture logs.
  - [ ] Record findings (with severity + file:line) and note follow-ups (e.g., missing docs, additional tests).
- Findings:
- Follow-ups:
- Commands re-run:
  - [ ] `.venv/bin/pyright --warnings`
  - [ ] `.venv/bin/ruff check`
  - [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/runner/test_overlay_diagnostics.py`
- Reviewer:
- Date:
