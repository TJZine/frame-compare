---
RUN_ID: 2026-02-04__p6-8-3__preset
VERSION: v2
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `preset` subcommands + implement all `api-design.md` CLI options
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v1.md
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v2.md
---

# Implementation Plan: CLI `preset` subcommands + api-design option completeness

## Changes Since plan-v1

- Added an explicit CLI option coverage audit (api-design global options + run options) with “already functional vs missing” status.
- Pinned deterministic `--diagnose-paths` JSON schema mapping (exact keys and which internal paths populate each value).
- Pinned `--json` success schema keys and `RunResult` → JSON mapping; pinned JSON error handling to `frame_compare.errors.format_error_json`.
- Fully specified `--root` / `--config` precedence and relative-path resolution rules, and applied them to `--write-config`, `--diagnose-paths`, and `preset apply/save`.
- Made `--input` override wiring explicit end-to-end (CLI → preflight/workspace resolution → discovery) and covered by tests.
- Expanded tests to cover `--root`/`--config` behaviors for new commands and new flag behaviors.

## Context
**Phase:** 6
**Module:** `frame_compare.cli_entry`, `frame_compare.config.presets`, `frame_compare.orchestration.preflight`, `frame_compare.orchestration.coordinator`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
**Dependencies:** Existing Config module + error types; tests must remain offline and not require VS/FFmpeg/network by default.

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2. CLI Entry Point"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`:
  - Section: "4. CLI Overrides"
  - Section: "5. Preset Management"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.4 Run Coordination"
  - Section: "5.1 Path Resolution"
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md`:
  - Section: "2. CLI Interface Design"
  - Section: "2.3 Global Options"
  - Section: "2.4 Run Command Options"
  - Section: "2.2 Commands"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`:
  - Section: "Canonical Flag Table"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`:
  - Section: "3. CLI Flag → Config Mapping"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.1 Configuration Errors (FC-1xxx) — Exit Code 2"

## CLI Option Coverage (api-design audit)

### Global options (api-design §2.3)

| Option | Expected behavior | Current status | Plan action | Tests |
|---|---|---|---|---|
| `--root PATH` | Base directory for resolving default config + workspace paths | Partially functional for `run` pipeline; not supported by preset commands | Make `preset list/apply/save` accept and use `--root`; ensure `--write-config`/`--diagnose-paths` honor it | Add CLI tests for preset + write-config/diagnose-paths root |
| `--config PATH` | Config file path override (read/write) | Functional for pipeline preflight; not honored by write-config/diagnose-paths/preset | Fully honor for: write-config, diagnose-paths, preset apply/save | Add CLI tests for config path + root |
| `--quiet` | Suppress non-essential output | Already influences progress reporter and some diagnostics | Ensure it suppresses non-essential prints for new commands; JSON output still emitted when requested | Cover via JSON tests (quiet + json) |
| `--verbose` | Debug logging / expanded error details | Not fully functional (CLI does not configure structlog; error formatter supports verbose details) | Configure logging level and verbose error formatting in CLI | Add error formatting test case under `--json` and console path |
| `--no-color` | Disable colored output | Not functional for error console and progress selection | Ensure CLI uses `Console(no_color=True)` for console errors; progress selection should avoid rich output when no-color | Add CLI test asserting progress selection path (via monkeypatch / reporter type) |

### Run command options (api-design §2.4)

| Option | Expected behavior | Current status | Plan action | Tests |
|---|---|---|---|---|
| `--input PATH` | Override input directory used for validation + discovery | Parsed into RunRequest; ignored by preflight/discovery | Wire into preflight path resolution and discovery | Add orchestration test + CLI test |
| `--no-cache` | Recompute all metrics / ignore caches | Parsed; currently no observable effect | Define and implement an observable policy for the existing `clip_probe.toml` cache: ignore reads when `--no-cache` is set | Add unit test for cache behavior with flag |
| `--from-cache-only` | Use cached snapshot only; fail if cache missing | Parsed; currently no observable effect | Enforce: when set, LoadSources must not probe and must fail if `clip_probe.toml` lacks required entries | Add unit test for failure mode |
| `--no-upload` | Skip slow.pics upload | Already used to skip `publish` phase | No change | Existing tests suffice |
| `--write-config` | Write resolved config and exit | Parsed; not implemented | Implement: resolve config + apply config-mapped CLI overrides + write to resolved config path; do not invoke pipeline | Add CLI test (also root/config precedence) |
| `--diagnose-paths` | Print path diagnostics JSON and exit | Parsed; not implemented | Implement deterministic JSON schema mapping (see below); do not invoke pipeline | Add CLI test (also root/config precedence) |
| `--tm-preset/--tm-target/--tm-curve` | Override tonemap config | Mapped via `apply_cli_overrides` | Ensure `--write-config` writes effective config including these overrides | Add CLI test for write-config persisting mapped keys |
| `--frame-count/--seed/--overlay` | Override analysis/overlay config | Mapped via `apply_cli_overrides` | Ensure `--write-config` writes effective config including these overrides | Add CLI test for write-config persisting mapped keys |
| `--json` | Machine-readable output | Only influences reporter selection; does not print run result JSON | Implement success + error JSON output for `run --json` | Add CLI tests (success + error) |

## Scope

This plan covers:
- [ ] Complete `preset` subcommands (list/apply/save) in `frame_compare.cli_entry` by delegating to `frame_compare.config.presets`
- [ ] Implement the missing/partial api-design CLI option behaviors listed in the audit above, including precedence rules and deterministic JSON schemas

This plan does NOT cover:
- Exit-code mapping work beyond existing `frame_compare.errors.get_exit_code` (separate checklist item)
- Full pipeline semantics for caches other than the existing `clip_probe.toml` (this slice implements observable semantics for `--no-cache` / `--from-cache-only` strictly around probe caching to satisfy option completeness)
- End-to-end CLI integration/E2E tests (separate checklist item)

## Normative rules (remove ambiguity)

### `--root` / `--config` resolution rules (applies to `run`, `--write-config`, `--diagnose-paths`, `preset apply/save`)

Rules:

```python
resolved_root = Path(root).resolve()

if config is not None:
    config_path = Path(config)
    if not config_path.is_absolute():
        config_path = (resolved_root / config_path).resolve()
    else:
        config_path = config_path.resolve()
else:
    config_path = resolved_root / "config" / "config.toml"
```

Reads and writes for config always use the `config_path` computed above (including `preset apply` writing updated config, and `--write-config`).

### Preset directory resolution rule

Presets live under the workspace root: `presets_dir = resolved_root / "config" / "presets"`.

### `--diagnose-paths` JSON schema (deterministic; exact key mapping)

Emit JSON with exactly these keys:

- `root`: string form of `resolved_root`
- `config`: string form of `config_path` (after resolution rules above)
- `input`: string form of `workspace.input_dir` after applying `--input` override (see wiring below)
- `output`: string form of `workspace.screenshots_dir`
- `cache`: string form of `workspace.generated_dir`

Determinism requirements: `json.dumps(sort_keys=True, separators=(",", ":"))`.

### `--json` success schema (api-design §3.3 compatibility)

For `run --json` on success, emit JSON with these keys (and only these keys unless SSOT already requires more):

- `success` (bool)
- `screenshots_dir` (string or null)
- `slowpics_url` (string or null)
- `report_path` (string or null)
- `frame_count` (int)
- `clips_processed` (int)
- `duration_seconds` (float)
- `cache_hit` (bool)
- `errors` (list of strings)

Mapping rule: `screenshots_dir` is derived from `RunResult.screenshot_dir` (stringified path) for schema compatibility.

On `FrameCompareError`, emit JSON via `frame_compare.errors.format_error_json(error)` and exit with `frame_compare.errors.get_exit_code(error)`.

### `--input` override wiring rule (end-to-end)

- CLI continues to set `RunRequest.input_dir` from `--input`.
- Orchestration must apply `--input` before validating input directory and before discovering input videos:
  - coordinator builds a config-override payload from `RunRequest.input_dir` and passes it into preflight config loading (via `prepare_preflight(..., overrides=...)`) so `WorkspacePaths.input_dir` reflects the override.

### `--no-cache` / `--from-cache-only` observable semantics (probe cache)

These flags apply to the existing `clip_probe.toml` probe snapshot cache during LoadSources:

- If `--no-cache` is true: ignore any existing `clip_probe.toml` content (start with empty cache in-memory, then overwrite the on-disk cache at end of LoadSources).
- If `--from-cache-only` is true:
  - Load `clip_probe.toml` and require a cache entry for every discovered input clip fingerprint.
  - Do not probe clips via `VSLoader` in this mode.
  - If any required entry is missing, raise a `FrameCompareError` (use an existing input/config error type already in repo; do not introduce new error codes in this slice).

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py`
**Purpose:** Implement `preset` commands; complete missing api-design option behaviors (`--write-config`, `--diagnose-paths`, `--json`, and global option precedence for new behaviors).

**Functions to implement (spec-anchored):**

- `preset_list() -> None` — list `*.toml` presets from `presets_dir` in deterministic order and print one name per line
- `preset_apply(name: str) -> None` — load config at `config_path`, apply preset overrides, write updated config back to `config_path`
- `preset_save(name: str) -> None` — load config at `config_path`, save preset into `presets_dir` as `name.toml`
- `run(...) -> None` — implement `--write-config`, `--diagnose-paths`, and `--json` output using the normative rules above (and preserve pipeline execution when these flags are not set)

**Key implementation notes:**

- `preset list/apply/save` must accept and honor `--root` and `--config` (api-design global options) without requiring Typer-wide “true global” option refactors.
- `--write-config` / `--diagnose-paths` must not invoke `runner.run` (guard these early in `run`).
- For `--write-config`, apply only config-mapped CLI overrides (per `config-reference.md` mapping); never persist runtime-only flags.
- For `--diagnose-paths`, compute workspace paths via `frame_compare.orchestration.preflight.resolve_paths(...)` using the effective config after applying `--input` override; then emit the pinned JSON schema above.
- For `--json` on the normal run path:
  - On success, print the pinned success JSON schema mapping from `RunResult`.
  - On `FrameCompareError`, print JSON via `frame_compare.errors.format_error_json(error)` (not an ad-hoc envelope).

### 2. `src/frame_compare/config/presets.py`
**Purpose:** Deterministic preset listing and stable TOML I/O, with explicit presets_dir support for root-aware CLI.

**Functions to implement (spec-anchored):**

- `list_presets(presets_dir: Path | None = None) -> list[str]` — deterministic ordering (lexicographic, case-insensitive)
- `load_preset(name: str, presets_dir: Path | None = None) -> dict[str, object]` — ensure errors are `PresetNotFoundError` / `PresetInvalidError`
- `save_preset(name: str, config: ConfigSchema, presets_dir: Path | None = None) -> Path` — stable TOML output
- `apply_preset(config: ConfigSchema, preset_name: str) -> ConfigSchema` — deterministic deep-merge precedence (preset overrides win)

### 3. `src/frame_compare/orchestration/preflight.py`
**Purpose:** Allow preflight to load config with overrides that affect path resolution (needed for `--input` to be functional).

**Key implementation notes:**

- Extend `prepare_preflight(...)` to accept an `overrides` payload (nested dict) passed to `frame_compare.config.load_config(..., overrides=...)` prior to `resolve_paths(...)` and input directory validation.
- Keep existing behavior unchanged when no overrides are provided.

### 4. `src/frame_compare/orchestration/coordinator.py`
**Purpose:** Ensure `--input`, `--no-cache`, and `--from-cache-only` have end-to-end, observable semantics consistent with this plan.

**Key implementation notes:**

- Pass a preflight override payload into `prepare_preflight(...)` derived from `RunRequest.input_dir` (when set) so discovery uses the overridden directory.
- Implement probe cache semantics:
  - `--no-cache`: skip loading `clip_probe.toml` (treat as empty) and always re-probe.
  - `--from-cache-only`: require cache hits for all clips; never probe; raise existing error if missing.

### 5. `tests/cli/test_cli_commands.py`
**Purpose:** Replace preset stubs with real behavior tests and cover the missing api-design option behaviors, including `--root`/`--config` precedence.

**Tests required:**

- `test_preset_list_prints_names_sorted_case_insensitive` — creates `{root}/config/presets/*.toml` and asserts deterministic output lines
- `test_preset_save_respects_root_and_config_writes_preset_file` — uses `--root` and a relative `--config`, asserts preset file is written under `{root}/config/presets/`
- `test_preset_apply_respects_root_and_config_updates_config_file` — uses `--root` and a relative `--config`, asserts config file updated
- `test_run_write_config_respects_root_and_config_and_does_not_invoke_runner` — asserts config file path resolution rule and no pipeline invocation
- `test_run_diagnose_paths_outputs_pinned_json_schema_and_does_not_invoke_runner` — asserts exact key set and value mapping
- `test_run_json_outputs_pinned_success_schema` — monkeypatches `runner.run` to return a `RunResult` with stable values and asserts printed JSON matches mapping
- `test_run_json_outputs_error_schema_and_exit_code` — monkeypatches `runner.run` to raise a `FrameCompareError` and asserts JSON error envelope is produced and exit code matches `get_exit_code`

### 6. `tests/orchestration/test_preflight.py`
**Purpose:** Prove `--input` overrides affect path resolution before directory validation and discovery.

**Tests required:**

- `test_prepare_preflight_overrides_input_dir_before_validation` — passes overrides setting `paths.input_dir`, creates videos only there, asserts preflight succeeds and uses the overridden directory

### 7. `tests/orchestration/test_execute_run.py`
**Purpose:** Add targeted tests for probe-cache behaviors tied to `--no-cache` and `--from-cache-only`.

**Tests required:**

- `test_execute_run_no_cache_ignores_existing_probe_cache` — writes a probe cache, runs with `no_cache=True`, asserts loader is invoked (via injected fake VSLoader) instead of cache hit
- `test_execute_run_from_cache_only_fails_when_probe_cache_missing_entry` — runs with `from_cache_only=True` and missing cache entries, asserts a `FrameCompareError` is raised

## Acceptance Criteria

- [ ] GIVEN preset files under `{root}/config/presets/` WHEN `frame-compare preset list --root {root}` runs THEN it prints preset names one per line, sorted lexicographically case-insensitively
- [ ] GIVEN a config file at `config_path` WHEN `frame-compare preset save NAME --root {root} --config {config_path}` runs THEN it writes `{root}/config/presets/NAME.toml` deterministically
- [ ] GIVEN a preset `{root}/config/presets/NAME.toml` WHEN `frame-compare preset apply NAME --root {root} --config {config_path}` runs THEN it updates `{config_path}` deterministically
- [ ] GIVEN `--input` is provided WHEN `frame-compare run` validates inputs THEN it uses the overridden input directory for existence checks and discovery
- [ ] GIVEN `--write-config` is set WHEN `frame-compare run --write-config` runs THEN it writes the effective config to `config_path` and exits 0 without invoking the pipeline
- [ ] GIVEN `--diagnose-paths` is set WHEN `frame-compare run --diagnose-paths` runs THEN it prints deterministic JSON with keys `root/config/input/output/cache` and exits 0 without invoking the pipeline
- [ ] GIVEN `--json` is set WHEN `frame-compare run --json` succeeds THEN it prints the pinned success schema JSON; WHEN it fails with `FrameCompareError` THEN it prints the pinned error schema JSON and exits with mapped exit code
- [ ] GIVEN `--no-cache` or `--from-cache-only` is set WHEN LoadSources runs THEN probe-cache behavior matches the observable semantics in this plan

## Verification Commands

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Keep outputs deterministic: stable sorting for presets, stable TOML output via `tomli_w`, stable JSON output via sorted keys + fixed separators.
- `--root`/`--config` path resolution rules are non-negotiable in this slice; implement once and reuse consistently across run + presets + write-config/diagnose-paths.
- Do not introduce new error codes in this slice. If `--from-cache-only` needs a missing-cache error, use an existing `FrameCompareError` already present in the repo.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

RUN_ID: 2026-02-04__p6-8-3__preset

TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `preset` subcommands + implement all `api-design.md` CLI options

INPUTS:
- .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v2.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md

OUTPUT:
- .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v2.md

STOP CONDITIONS (Hard):
- If verdict != APPROVED or Decision Points Remaining != NONE, Coding Agent must not proceed.
