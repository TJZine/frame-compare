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

- [ ] List `[color]` fields from config schema.
- [ ] List all `--tm-*` CLI flags and how they map into `tonemap_overrides`.
- [ ] Confirm current DoVi behaviour:
  - [ ] Direct `run_cli` path.
  - [ ] Click CLI path.

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
  - [ ] `tm_use_dovi`, `tm_visualize_lut`, `tm_show_clipping` only override when flags are explicitly passed (use Click `ParameterSource`).
  - [ ] Any similar tri-state flags updated to follow the same pattern.
- Tests added/updated:
  - [ ] `tests/runner/test_dovi_flags.py` (or similar).
  - [ ] Any snapshot/JSON-tail tests that assert `use_dovi` behaviour.
- Commands run:
  - [ ] `.venv/Scripts/pyright --warnings`
  - [ ] `.venv/Scripts/ruff check`
  - [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/Scripts/pytest -q tests/runner/test_dovi_flags.py`

#### A2 Notes

- Date:
- Dev Agent:
- Short summary of scenarios tested and results.

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

- [ ] Enumerate `AppConfig` and sub-configs (Analysis, Screenshots, AudioAlignment, Slowpics, Report, Paths, Runtime, Overrides, Source, TMDB, CLI).
- [ ] Document how `load_config` and `prepare_preflight` resolve:
  - [ ] Config path.
  - [ ] Workspace root.
  - [ ] Input dir.
  - [ ] Legacy config.

### B2. Domain Checklists

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
  - [ ] Issues found (if any) and fixes applied.
  - [ ] Tests updated/added.
  - [ ] Any decisions on intentional precedence.

#### B3 Notes

- Date:
- Dev Agent:
- Key changes & rationale:

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
