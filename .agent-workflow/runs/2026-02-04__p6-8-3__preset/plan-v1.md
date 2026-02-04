---
RUN_ID: 2026-02-04__p6-8-3__preset
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — `preset` subcommands + api-design CLI options
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v1.md
---

# Implementation Plan: CLI `preset` subcommands + api-design CLI options

## Context
**Phase:** 6
**Module:** `frame_compare.cli_entry`, `frame_compare.config.presets`, `frame_compare.orchestration.preflight`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
**Dependencies:** Config module + error types already exist; tests must remain offline and not require VS/FFmpeg/network by default.

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2. CLI Entry Point"
  - Section: "5. Preflight"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`:
  - Section: "4. CLI Overrides"
  - Section: "5. Preset Management"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`:
  - Section: "3. CLI Flag → Config Mapping"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`:
  - Section: "Canonical Flag Table"
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md`:
  - Section: "2. CLI Interface Design"
  - Section: "2.3 Global Options"
  - Section: "2.4 Run Command Options"
  - Section: "2.2 Commands"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.1 Configuration Errors (FC-1xxx) — Exit Code 2"

## Scope
This plan covers:
- [ ] Implement `frame-compare preset list` / `preset apply NAME` / `preset save NAME` per `cli-module.md`
- [ ] Make the api-design CLI options functional (not just parsed), specifically:
  - [ ] `--input` affects preflight input discovery and validation
  - [ ] `--write-config` writes resolved config and exits without running the pipeline
  - [ ] `--diagnose-paths` prints JSON path diagnostics and exits without running the pipeline
  - [ ] `--json` prints machine-readable output for `run` success + error cases

This plan does NOT cover:
- ExitCode enum or error-to-exit-code mapping work (checklist items after this bundle)
- CLI integration/E2E tests (separate checklist item)
- Wizard/doctor behavior changes (only incidental refactors if required to share helpers)

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py`
**Purpose:** Replace preset stubs with real commands; implement api-design option behaviors for `run`.

**Functions to implement (spec-anchored):**

- `preset_list() -> None` — list `*.toml` presets in the canonical presets directory and print deterministically
- `preset_apply(name: str) -> None` — merge preset into current config and write updated config
- `preset_save(name: str) -> None` — write current config to `presets/{name}.toml` deterministically
- `run(...) -> None` — implement behaviors for `--write-config`, `--diagnose-paths`, and `--json` output (while preserving existing pipeline execution semantics when those flags are not set)

**Key implementation notes:**

- Preset directory (SSOT): treat the canonical preset location as `config/presets` relative to the working directory (matches existing `frame_compare.config.presets.DEFAULT_PRESETS_DIR` and `cli-module.md` comments).
- `preset list`:
  - Use `frame_compare.config.presets.list_presets()`.
  - Print one preset name per line, with no extra headers (scripting-friendly).
  - Determinism: ordering must be lexicographic, case-insensitive (enforced in `config/presets.py` in this plan).
- `preset save NAME`:
  - Load config from `config/config.toml` when present; otherwise, save defaults (`get_default_config()`).
  - Use `frame_compare.config.presets.save_preset(name, config, presets_dir=None)`.
  - On success: no output (exit 0). (Errors should be routed through the same `FrameCompareError` handling pattern used by `run`.)
- `preset apply NAME`:
  - Load config from `config/config.toml` when present; otherwise, apply to defaults (`get_default_config()`).
  - Apply preset via `frame_compare.config.presets.apply_preset(config, name)` and then write the resulting config to `config/config.toml`.
  - TOML output: use `tomli_w.dumps(config.model_dump(mode="json", exclude_none=True))` for stable, deterministic output (dict insertion order).
- `run` option behaviors:
  - `--write-config`:
    - Must NOT call `runner.run(...)`.
    - Build an effective `ConfigSchema` by loading existing config if present, else defaults; then apply CLI overrides via `frame_compare.config.apply_cli_overrides(...)` using only the flags mapped to config keys (see `config-reference.md` mapping).
    - Write the effective config to `config/config.toml` (create `config/` if missing) and exit 0.
    - Runtime-only flags (e.g., `--no-cache`, `--from-cache-only`, `--json`, `--quiet`, `--verbose`, `--no-color`) must not be persisted (they should only affect runtime / output).
  - `--diagnose-paths`:
    - Must NOT call `runner.run(...)`.
    - Resolve a `ConfigSchema` as above (load if present else defaults) and apply CLI overrides that affect path resolution (at minimum: `--input`; include others if they map to path-like keys).
    - Use `frame_compare.orchestration.preflight.resolve_paths(effective_config, root)` to compute absolute paths.
    - Print JSON exactly matching the operations doc example keys: `root`, `config`, `input`, `output`, `cache`.
    - Output must be deterministic JSON (sort keys, stable separators).
  - `--json` (for normal `run` execution path, i.e., not `--write-config` / `--diagnose-paths`):
    - On success, print JSON containing at least the fields specified in `api-design.md` §3.3 (paths as strings; stable key ordering).
    - On `FrameCompareError`, print JSON error payload (use the existing error JSON formatter in `frame_compare.errors`) and exit with mapped exit code.

### 2. `src/frame_compare/config/presets.py`
**Purpose:** Ensure preset listing order and preset file access are deterministic and aligned with CLI expectations.

**Functions to implement (spec-anchored):**

- `list_presets(presets_dir: Path | None = None) -> list[str]` — sort deterministically (lexicographic, case-insensitive) and return preset stems
- `load_preset(name: str, presets_dir: Path | None = None) -> dict[str, object]` — unchanged behavior; ensure errors are `PresetNotFoundError` / `PresetInvalidError`
- `save_preset(name: str, config: ConfigSchema, presets_dir: Path | None = None) -> Path` — unchanged behavior; ensure stable TOML output
- `apply_preset(config: ConfigSchema, preset_name: str) -> ConfigSchema` — unchanged public behavior; used by CLI preset-apply

**Key implementation notes:**

- Deterministic ordering requirement: update `list_presets(...)` to sort stems with a casefold/lower-based key to match the CLI spec requirement.
- Do not introduce new error codes in this slice; reuse existing `FC-1004` / `FC-1005` errors for preset load failures.

### 3. `src/frame_compare/orchestration/preflight.py`
**Purpose:** Allow preflight to respect `--input` CLI overrides so api-design options are functional.

**Key implementation notes:**

- Extend `prepare_preflight(...)` to accept an optional `overrides` payload that is passed into `frame_compare.config.load_config(..., overrides=...)`.
- This enables CLI `--input` (and other config-mapped flags) to influence `workspace.input_dir` before directory existence checks and `discover_inputs(...)`.
- Keep existing behavior unchanged when `overrides` is not provided.

### 4. `tests/cli/test_cli_commands.py`
**Purpose:** Replace stub preset assertions with real behavior tests and add coverage for the newly functional CLI options.

**Tests required:**

- `test_preset_list_prints_names_sorted_case_insensitive` — creates `config/presets/*.toml` and asserts deterministic line output
- `test_preset_save_writes_preset_file` — creates a minimal `config/config.toml`, runs `preset save`, and asserts `config/presets/<name>.toml` exists and parses as TOML
- `test_preset_apply_merges_into_config_toml` — writes a base config + a preset override, runs `preset apply`, and asserts config file reflects override(s)
- `test_run_write_config_writes_config_and_does_not_invoke_runner` — runs `run --write-config` with at least one override flag and asserts file output + that `runner.run` is not called
- `test_run_diagnose_paths_outputs_json_and_does_not_invoke_runner` — runs `run --diagnose-paths` and asserts JSON shape and deterministic key set
- `test_run_json_outputs_machine_readable_result` — monkeypatches `runner.run` to return a `RunResult` and asserts JSON output fields
- `test_run_json_outputs_machine_readable_error` — monkeypatches `runner.run` to raise a `FrameCompareError` and asserts JSON error envelope

### 5. `tests/orchestration/test_preflight.py`
**Purpose:** Add a focused test proving `prepare_preflight(..., overrides=...)` affects the resolved input directory and validation.

**Tests required:**

- `test_prepare_preflight_overrides_input_dir_before_validation` — overrides `paths.input_dir`, creates video files only in the overridden directory, and asserts preflight succeeds and `workspace.input_dir` matches the override

## Acceptance Criteria

- [ ] GIVEN preset files under `config/presets/` WHEN `frame-compare preset list` runs THEN it prints preset names one per line, sorted lexicographically case-insensitively
- [ ] GIVEN an existing `config/config.toml` WHEN `frame-compare preset save NAME` runs THEN it writes `config/presets/NAME.toml` with deterministic TOML content
- [ ] GIVEN a preset `config/presets/NAME.toml` WHEN `frame-compare preset apply NAME` runs THEN it updates `config/config.toml` by applying preset overrides deterministically
- [ ] GIVEN `--input` is provided WHEN `frame-compare run` executes preflight THEN it validates/discovers videos using the overridden input directory
- [ ] GIVEN `--write-config` is set WHEN `frame-compare run --write-config` runs THEN it writes resolved config and exits 0 without invoking the pipeline
- [ ] GIVEN `--diagnose-paths` is set WHEN `frame-compare run --diagnose-paths` runs THEN it prints deterministic JSON diagnostics and exits 0 without invoking the pipeline
- [ ] GIVEN `--json` is set WHEN `frame-compare run --json` succeeds or fails THEN it prints machine-readable JSON per `api-design.md`

## Verification Commands

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Keep preset I/O deterministic: stable sorting, stable TOML output, and stable JSON output for diagnostics/results.
- Do not add network/VapourSynth/FFmpeg requirements to unit tests; keep tests filesystem-only and use monkeypatching where needed.
- If implementing `--json` output expands `RunResult` fields beyond `api-design.md`, keep the api-design-required keys present and stable; avoid adding noisy, non-deterministic fields (timestamps, durations with varying precision) unless explicitly normalized.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

RUN_ID: 2026-02-04__p6-8-3__preset

TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — `preset` subcommands + api-design CLI options

INPUTS:
- .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v1.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md

OUTPUT:
- .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v1.md

STOP CONDITIONS (Hard):
- If verdict != APPROVED or Decision Points Remaining != NONE, Coding Agent must not proceed.
