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

- [ ] Config + env + CLI precedence is well defined and documented.
- [ ] "Flag not passed" means "no override"; config values still apply.
- [ ] `frame_compare.run_cli` and `frame_compare.py` produce the same effective settings for the same config + flags.
- [ ] All tri-state/boolean fields that can be set from CLI have explicit tests for:
  - [ ] No flags
  - [ ] Explicit enable flag
  - [ ] Explicit disable flag

**Critical toggles to verify across config + CLI:**

- [ ] `color.use_dovi` (DoVi)
- [ ] `color.visualize_lut`
- [ ] `color.show_clipping`
- [ ] `screenshots.use_ffmpeg`
- [ ] `analysis` enable / thresholds (where applicable)
- [ ] `audio_alignment.enable` / `audio_alignment.use_vspreview`
- [ ] `slowpics.auto_upload`
- [ ] `report.enable`
- [ ] `cli.emit_json_tail`
- [ ] Cache flags: `--no-cache`, `--from-cache-only`, `--show-partial`, `--show-missing/--hide-missing`

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

- [ ] Verified `frame_compare.run_cli` vs `frame_compare.py` behaviour for:
  - [ ] DoVi on via config only.
  - [ ] DoVi off via config only.
  - [ ] Explicit `--tm-use-dovi` vs `--tm-no-dovi`.
- [ ] Confirmed no other `--tm-*` flags implicitly override config when not passed.
- [ ] Documentation aligned (README/CHANGELOG/DECISIONS).

#### A3 Findings

-

#### A3 Open Questions

-

#### A3 Reviewer

-

#### A3 Date

-

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

- [ ] Confirm `[screenshots]` fields: directory, writer, scaling, pad, compression, etc.
- [ ] Map any CLI flags that touch screenshots.
- [ ] Verify:
  - [ ] No hidden defaults override config.
  - [ ] JSON `render` block matches effective settings.

#### Analysis / Cache

- [ ] Review `[analysis]` config.
- [ ] Verify `--no-cache`, `--from-cache-only`, `--show-partial`, `--show-missing`:
  - [ ] Only affect behaviour when explicitly passed.
  - [ ] Match documentation.

#### Audio Alignment

- [ ] Review `[audio_alignment]` config and overrides (manual trims, vspreview).
- [ ] Verify CLI flags (e.g., `--audio-align-track`) don't reset config when absent.

#### Slowpics / Report / Viewer

- [ ] Review `[slowpics]`, `[report]`, and viewer-related fields.
- [ ] Verify override semantics for `--html-report`, `--no-html-report`, etc.

#### Paths / Root / Input

- [ ] Verify precedence: `--root` / `FRAME_COMPARE_ROOT` / sentinel search.
- [ ] Confirm `--config` / `FRAME_COMPARE_CONFIG` overrides and no surprise fallbacks.

#### TMDB / Source / Runtime / CLI

- [ ] Review `[tmdb]`, `[source]`, `[runtime]`, `[cli]`, `[overrides]`.
- [ ] Ensure fields like `cli.emit_json_tail`, runtime flags, etc., are only overridden intentionally.

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

### B4. Review Notes (Review Agent)

- [ ] Verified behaviour against docs and expectations for each domain.
- [ ] Confirmed no remaining "implicit override" patterns.
- [ ] Suggested any follow-up tasks (if necessary).

#### B4 Findings

-

#### B4 Follow-ups

-

#### B4 Reviewer

-

#### B4 Date

-

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

- [ ] …
