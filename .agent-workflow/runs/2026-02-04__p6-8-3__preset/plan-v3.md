---
RUN_ID: 2026-02-04__p6-8-3__preset
VERSION: v3
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `preset` subcommands + implement all `api-design.md` CLI options
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v2.md
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v3.md
---

# Implementation Plan: CLI `preset` subcommands + api-design option completeness

## Changes Since plan-v2

- Re-scoped `--no-cache` / `--from-cache-only` semantics to “cached metrics” per `cli-flags-canonical.md` and SSOT cache strategy docs (analysis metrics cache + audio alignment offsets cache), removing probe-cache-specific semantics.
- Pinned the exact error types raised for cache-only failures (and therefore exit-code mapping via `get_exit_code`).
- Made `--no-color` and `--verbose` wiring concrete, and expanded the file list and tests accordingly.

## Context
**Phase:** 6
**Module:** `frame_compare.cli_entry`, `frame_compare.config.presets`, `frame_compare.orchestration.*`, `frame_compare.analysis.cache_io`, `frame_compare.services.alignment`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
**Dependencies:** Existing Config module + error types. Tests must remain offline and must not require VS/FFmpeg/network by default.

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
  - Section: "4.4.7 Output Directory Layout"
  - Section: "5.1 Path Resolution"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "5. Cache Strategy"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "2. Audio Alignment Service"
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

This section is the completeness proof for: “Implement all CLI options documented in `api-design.md`”.

### Global options (api-design §2.3)

| Option | Expected behavior | Current status | Plan action | Tests |
|---|---|---|---|---|
| `--root PATH` | Base directory for resolving default config + workspace paths | Functional for run pipeline; not supported by preset commands | Add `--root` option to preset commands and ensure write-config/diagnose-paths honor it | Add CLI tests for preset + write-config/diagnose-paths root |
| `--config PATH` | Config file path override (read/write) | Functional for run pipeline preflight; not honored by write-config/diagnose-paths/preset | Fully honor for write-config, diagnose-paths, preset apply/save | Add CLI tests for config path + root |
| `--quiet` | Suppress non-essential output | Functional | Ensure new commands do not add non-essential prints; JSON outputs still printed when requested | Covered by new CLI tests (quiet + json) |
| `--verbose` | Debug logging + expanded error details | Not functional end-to-end | Wire verbose to deterministic logging configuration + error formatting | Add CLI test that asserts logging config call + error detail formatting |
| `--no-color` | Disable colored output | Partially functional (Rich markup used for errors; Rich progress used for TTY) | Define and implement concrete behavior: disable Rich progress output and disable Rich error coloring | Add CLI test for error output and orchestration test for reporter selection |

### Run command options (api-design §2.4)

| Option | Expected behavior | Current status | Plan action | Tests |
|---|---|---|---|---|
| `--input PATH` | Override input directory used for validation + discovery | Parsed into RunRequest; ignored by preflight/discovery | Wire into preflight path resolution and discovery | Add orchestration test + CLI test |
| `--no-cache` | Ignore cached metrics | Parsed; not observable | Implement “cached metrics” semantics: bypass analysis metrics cache + audio offsets cache (SSOT cache interaction table) | Add orchestration tests for bypass behavior |
| `--from-cache-only` | Use cached snapshot/metrics only; fail if missing | Parsed; not observable | Implement “cached metrics” semantics: require analysis metrics cache (and require alignment offsets when alignment is enabled) | Add orchestration tests for fail-fast behavior |
| `--no-upload` | Skip slow.pics upload | Functional (skips publish phase) | No change | Existing tests suffice |
| `--write-config` | Write resolved config and exit | Parsed; not implemented | Implement: resolve config + apply config-mapped CLI overrides + write to resolved config path; do not invoke pipeline | Add CLI test (root/config precedence) |
| `--diagnose-paths` | Print path diagnostics JSON and exit | Parsed; not implemented | Implement deterministic JSON schema mapping (pinned below); do not invoke pipeline | Add CLI test (root/config precedence) |
| `--tm-preset/--tm-target/--tm-curve` | Override tonemap config | Functional for pipeline; not persisted by write-config | Ensure write-config writes effective config including these overrides | Add CLI test for write-config persisting mapped keys |
| `--frame-count/--seed/--overlay` | Override analysis/overlay config | Functional for pipeline; not persisted by write-config | Ensure write-config writes effective config including these overrides | Add CLI test for write-config persisting mapped keys |
| `--json` | Machine-readable output | Influences reporter selection; does not print run result JSON | Print pinned JSON success schema; print pinned JSON error schema on `FrameCompareError` | Add CLI tests (success + error) |

## Scope

This plan covers:
- [ ] Complete `preset` subcommands (list/apply/save) in `frame_compare.cli_entry` with deterministic behavior
- [ ] Implement all api-design CLI options, including the missing functional behaviors: `--write-config`, `--diagnose-paths`, `--json`, `--input`, `--no-cache`, `--from-cache-only`, `--no-color`, `--verbose`

This plan does NOT cover:
- The separate checklist item for implementing the ExitCode enum and error-to-exit-code mapping (already exists in `frame_compare.errors` and will be used as-is here)
- Adding new error codes; this slice must only use existing `FrameCompareError` subclasses
- E2E/integration CLI tests (separate checklist item)

## Normative rules (remove ambiguity)

### `--root` / `--config` resolution rules

These rules apply to: `run`, `run --write-config`, `run --diagnose-paths`, `preset apply`, and `preset save`.

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

### Preset directory resolution rule

Presets live under workspace root: `presets_dir = resolved_root / "config" / "presets"`.

### `--diagnose-paths` JSON schema mapping (deterministic; exact keys)

Emit JSON with exactly these keys:

- `root`: string form of `resolved_root`
- `config`: string form of `config_path`
- `input`: string form of `workspace.input_dir` after applying `--input` override
- `output`: string form of `workspace.screenshots_dir`
- `cache`: string form of `workspace.generated_dir`

Determinism: `json.dumps(sort_keys=True, separators=(",", ":"))`.

### `--json` success and error schemas (api-design compatible)

For `run --json` on success, emit JSON with these keys:

- `success` (bool)
- `screenshots_dir` (string or null) ← derived from `RunResult.screenshot_dir`
- `slowpics_url` (string or null)
- `report_path` (string or null)
- `frame_count` (int)
- `clips_processed` (int)
- `duration_seconds` (float)
- `cache_hit` (bool)
- `errors` (list of strings)

On `FrameCompareError`, emit JSON via `frame_compare.errors.format_error_json(error)` and exit via `frame_compare.errors.get_exit_code(error)`.

### JSON purity rule (avoid stdout pollution)

When `--json` is set for `run`, the only stdout output must be the final JSON payload. Any structured logs (e.g., FPS report in json mode) must go to stderr.

Concrete implementation rule for this slice: update `frame_compare.utils.logging.configure_logging(...)` so structlog’s logger factory writes to stderr (not stdout), and call `configure_logging` from CLI before any orchestration work begins.

### `--verbose` and `--quiet` logging level rules

- If `--quiet` is set: logging level is WARNING.
- Else if `--verbose` is set: logging level is DEBUG.
- Else: logging level is INFO.

Logging format rule:
- If `--json` is set: structlog format is JSON.
- Else: structlog format is console.

### `--no-color` concrete behavior

- Progress output: treat `--no-color` as “do not use Rich progress output”; `select_reporter(..., no_color=True)` must return `LogProgressReporter` (unless `quiet=True`, which remains highest precedence).
- Error console output: when `--no-color` is set, error rendering must not emit Rich markup tags (e.g., the literal `[red]...[/red]` text must not appear in stderr).

### `--input` override wiring rule (end-to-end)

- CLI sets `RunRequest.input_dir` from `--input`.
- Orchestration applies it before validating `workspace.input_dir` and before discovering input videos by passing an overrides payload into preflight config loading (equivalent to setting `paths.input_dir` via CLI overrides).

### `--no-cache` / `--from-cache-only` semantics (cached metrics)

Authoritative meaning in this slice:
- “Cached metrics” covers:
  - Analysis metrics cache: `{workspace.cache_dir}/cache.compframes` (analysis spec + implementation)
  - Audio alignment offsets cache: `{workspace.generated_dir}/audio_offsets.toml` (services spec + implementation)
- “Cached metrics” does NOT include the probe snapshot cache (`clip_probe.toml`) in this slice; probe caching remains governed by its own SSOT rules.

#### Mutually exclusive flags

If both `--no-cache` and `--from-cache-only` are set, fail fast with `MetricsCalculationError` and a message indicating the flags are mutually exclusive.

#### `--no-cache`

- Before phase execution begins, delete (or ignore) any existing cached metrics files:
  - `{workspace.cache_dir}/cache.compframes`
  - `{workspace.generated_dir}/audio_offsets.toml`
- Manual overrides (`manual_overrides.toml`) must not be deleted.

#### `--from-cache-only`

Fail fast before phase execution begins unless cached metrics are present and valid:

- Analysis metrics cache requirement (unless `RunRequest.skip_analysis` is True):
  - Compute the expected analysis cache key via `frame_compare.analysis.cache_io.compute_cache_key(...)`.
  - Require `frame_compare.analysis.cache_io.load_cached_metrics(...)` to succeed.
  - If the cache is missing or fingerprint-mismatched: raise `MetricsCalculationError` (exit code 5).
  - If the cache is corrupt: raise `CacheCorruptionError` (exit code 5).
  - If the cache version mismatches: raise `CacheVersionMismatchError` (exit code 5).
- Audio offsets cache requirement (only when `config.audio_alignment.enable` is True and there is at least one comparison clip):
  - Accept an entry as “cached” if either:
    - it exists in manual overrides (`manual_overrides.toml`), or
    - it exists in computed offsets cache (`audio_offsets.toml`).
  - If any required clip pair lacks both entries: raise `AudioAlignmentError` with a message listing missing pairs (exit code 5).

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py`
**Purpose:** Implement preset commands; complete api-design option behaviors (`--write-config`, `--diagnose-paths`, `--json`, global options).

**Functions to implement (spec-anchored):**

- `preset_list() -> None` — list `*.toml` presets from `presets_dir` deterministically; print one name per line
- `preset_apply(name: str) -> None` — load config at `config_path`, apply preset overrides, write updated config back to `config_path`
- `preset_save(name: str) -> None` — load config at `config_path`, save preset into `presets_dir` as `name.toml`
- `run(...) -> None` — implement `--write-config`, `--diagnose-paths`, `--json`, and the pinned global-option behaviors per rules above

**Key implementation notes:**

- `preset list/apply/save` must accept and honor `--root` and `--config` without relying on Typer-wide “true global” refactors.
- `--write-config` and `--diagnose-paths` must guard early and must not invoke `runner.run`.
- `--json` must print only the final JSON payload to stdout (logging must go to stderr per this plan).
- Use `frame_compare.utils.logging.configure_logging(...)` at the start of command execution (before orchestration work) using the pinned rules above.

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

- Extend preflight to accept a nested overrides payload that is applied when loading config before resolving paths and validating the input directory.

### 4. `src/frame_compare/orchestration/coordinator.py`
**Purpose:** Enforce end-to-end semantics for `--input`, `--no-cache`, and `--from-cache-only` without adding external-dependency requirements to unit tests.

**Key implementation notes:**

- Apply `--input` by passing overrides into preflight config loading so discovery uses the overridden directory.
- Implement “cached metrics” semantics (delete / require caches) before phase execution begins using:
  - `frame_compare.analysis.cache_io.compute_cache_key` + `load_cached_metrics`
  - `frame_compare.services.alignment.load_cached_offsets` + `frame_compare.vspreview.load_manual_overrides`
- Raise the exact error types specified in “Normative rules” for cache-only failures (no new errors).

### 5. `src/frame_compare/orchestration/progress.py`
**Purpose:** Make `--no-color` behavior concrete via progress reporter selection.

**Key implementation notes:**

- Extend `select_reporter` to accept a `no_color` boolean and enforce: `no_color=True` ⇒ `LogProgressReporter` (unless `quiet=True`).

### 6. `src/frame_compare/runner.py`
**Purpose:** Ensure progress reporter selection honors `RunRequest.no_color`.

**Key implementation notes:**

- Pass `no_color=request.no_color` into `select_reporter(...)` where reporter is created.

### 7. `src/frame_compare/utils/logging.py`
**Purpose:** Ensure `run --json` stdout remains pure JSON by routing structlog output to stderr.

**Key implementation notes:**

- Update `configure_logging` to configure structlog with a logger factory that writes to stderr.

### 8. `tests/cli/test_cli_commands.py`
**Purpose:** Replace preset stubs with real behavior tests and cover new global/run option behaviors.

**Tests required:**

- `test_preset_list_prints_names_sorted_case_insensitive` — creates `{root}/config/presets/*.toml`, asserts deterministic output lines
- `test_preset_save_respects_root_and_config_writes_preset_file` — uses `--root` and relative `--config`, asserts preset file written under `{root}/config/presets/`
- `test_preset_apply_respects_root_and_config_updates_config_file` — uses `--root` and relative `--config`, asserts config file updated
- `test_run_write_config_respects_root_and_config_and_does_not_invoke_runner` — asserts config path resolution rule and that pipeline is not invoked
- `test_run_diagnose_paths_outputs_pinned_json_schema_and_does_not_invoke_runner` — asserts exact key set + value mapping
- `test_run_json_outputs_pinned_success_schema_and_stdout_is_pure_json` — asserts `result.stdout` parses as JSON and matches pinned schema; allow stderr logs
- `test_run_json_outputs_error_schema_and_exit_code` — runner raises a `FrameCompareError`, assert JSON error payload + exit code
- `test_run_no_color_error_output_has_no_rich_markup` — runner raises a `FrameCompareError` under `--no-color`; assert stderr does not contain Rich markup tags like `[red]`
- `test_run_verbose_calls_configure_logging_debug` — monkeypatch `configure_logging` and assert it is called with DEBUG when `--verbose` is set (and WARNING when `--quiet` is set)

### 9. `tests/orchestration/test_preflight.py`
**Purpose:** Prove `--input` override affects path resolution before directory validation and discovery.

**Tests required:**

- `test_prepare_preflight_overrides_input_dir_before_validation` — sets `paths.input_dir` override, creates videos only there, asserts preflight uses overridden directory

### 10. `tests/orchestration/test_execute_run.py`
**Purpose:** Validate `--no-cache` and `--from-cache-only` “cached metrics” semantics without VS/FFmpeg.

**Tests required:**

- `test_execute_run_no_cache_deletes_metrics_cache_and_offsets_cache` — create cache files, run with `no_cache=True`, assert the files are removed before phases proceed (use monkeypatch to stop before any external work if needed)
- `test_execute_run_from_cache_only_fails_when_metrics_cache_missing` — run with `from_cache_only=True` and missing `cache.compframes`, assert `MetricsCalculationError`
- `test_execute_run_from_cache_only_fails_when_metrics_cache_invalid` — create corrupted cache file, assert `CacheCorruptionError` (and version mismatch maps to `CacheVersionMismatchError`)

### 11. `tests/orchestration/test_progress.py`
**Purpose:** Add concrete coverage for `--no-color` reporter selection semantics.

**Tests required:**

- `test_select_reporter_no_color_returns_log` — `no_color=True` returns `LogProgressReporter` (unless quiet)

## Acceptance Criteria

- [ ] GIVEN presets under `{root}/config/presets/` WHEN `frame-compare preset list --root {root}` runs THEN it prints names deterministically (one per line, case-insensitive lexicographic)
- [ ] GIVEN config at `config_path` WHEN `frame-compare preset save NAME --root {root} --config {config_path}` runs THEN it writes `{root}/config/presets/NAME.toml` deterministically
- [ ] GIVEN preset `{root}/config/presets/NAME.toml` WHEN `frame-compare preset apply NAME --root {root} --config {config_path}` runs THEN it updates `{config_path}` deterministically
- [ ] GIVEN `--write-config` WHEN `frame-compare run --write-config` runs THEN it writes effective config to `config_path` and exits 0 without invoking the pipeline
- [ ] GIVEN `--diagnose-paths` WHEN `frame-compare run --diagnose-paths` runs THEN it prints deterministic JSON with keys `root/config/input/output/cache` and exits 0 without invoking the pipeline
- [ ] GIVEN `--json` WHEN `frame-compare run --json` succeeds or fails THEN stdout is a single JSON payload matching the pinned schema and exit codes are mapped via `get_exit_code`
- [ ] GIVEN `--no-cache` WHEN `frame-compare run --no-cache` runs THEN cached metrics files (`cache.compframes`, `audio_offsets.toml`) are bypassed/cleared per this plan
- [ ] GIVEN `--from-cache-only` WHEN cached metrics are missing/invalid THEN the run fails fast with the pinned error types and exit code 5
- [ ] GIVEN `--no-color` WHEN an error is rendered THEN no Rich markup tags are emitted in stderr

## Verification Commands

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Keep outputs deterministic: stable sorting for presets, stable TOML output via `tomli_w`, stable JSON via sorted keys + fixed separators.
- Do not add network/VapourSynth/FFmpeg requirements to unit tests; for cache-flag tests, only touch filesystem-visible caches (JSON/TOML) and use monkeypatching to avoid external work.
- Do not introduce new error codes; use only existing `FrameCompareError` subclasses pinned in this plan.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

RUN_ID: 2026-02-04__p6-8-3__preset

TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `preset` subcommands + implement all `api-design.md` CLI options

INPUTS:
- .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v3.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md

OUTPUT:
- .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v3.md

STOP CONDITIONS (Hard):
- If verdict != APPROVED or Decision Points Remaining != NONE, Coding Agent must not proceed.
