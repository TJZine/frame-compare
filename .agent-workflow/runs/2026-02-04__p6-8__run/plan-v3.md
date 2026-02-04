---
RUN_ID: 2026-02-04__p6-8__run
VERSION: v3
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md
---

# Implementation Plan: Phase 6.8 — CLI `run` Command (Bundled)

## Changes Since plan-v2
- Added SSOT/spec doc updates to prevent drift (per plan-review-v2 Concrete Edit #1):
  - `cli-module.md` §3.1: `RunRequest.force_interactive_alignment`
  - `config-module.md` §4.1: `CLI_OVERRIDE_MAP` uses `seed` and includes `force_interactive_alignment` mapping + required implication note
  - `orchestration-module.md` §4.4.1 and §4.4.6: `RunRequest.force_interactive_alignment` and ruff-safe `discover_inputs(...)` signature
- Removed implementation decision points by making input discovery ruff-safe (no mutable default list) and fully specifying new tests (names + key assertions).

## Context
**Phase:** 6
**Module:** CLI + Orchestration + Config
**Spec Reference:**
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
**Dependencies:** `frame_compare.runner.run(...)` and `frame_compare.orchestration.coordinator.execute_run(...)` already exist.

## Contract Impact
**Contracts touched:** YES

Canonical files:
- docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml

Derived outputs (do not hand-edit):
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md
- docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py

Regeneration:
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`

Freshness gate:
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`

Traceability gate:
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2. CLI Entry Point"
  - Section: "2.1 Command Structure"
  - Section: "3. Runner"
  - Section: "3.1 Types"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.4 Run Coordination"
  - Section: "4.4.1 Request Types"
  - Section: "4.4.3 Execute Function"
  - Section: "4.4.5 CLI Flags → Config Overrides Mapping"
  - Section: "4.4.6 Input Discovery Rules"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`:
  - Section: "4. CLI Overrides"
  - Section: "4.1 Override Mapping"
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md`:
  - Section: "2.4 Run Command Options"
  - Section: "2.5 Exit Codes"

## Scope
This plan covers:
- [ ] Complete `frame-compare run` implementation (replace stub) per CLI module spec: build `RunRequest`, call runner, map errors to exit codes.
- [ ] Implement CLI flag → config override mapping per orchestration spec §4.4.5 (including `--force-interactive-alignment` semantics).
- [ ] Implement input discovery rules per orchestration spec §4.4.6 (stable order; raise `NoVideosFoundError(FC-3001)` on empty).

This plan does NOT cover:
- `wizard`, `doctor`, `preset` subcommands completion (separate checklist items under 6.8).
- Docker / real-deps integration verification (Phase 6 quality gate; out of scope for this slice).

## Files to Create/Modify

### SSOT/spec updates (already applied in this planning iteration; do not re-edit unless Plan Review requests changes)

1) `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
- Add `RunRequest.force_interactive_alignment: bool = False` and document the implication on `audio_alignment.use_vspreview`.

2) `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`
- Update `CLI_OVERRIDE_MAP` keys to match CLI names (`seed`, not `random_seed`) and add `force_interactive_alignment` mapping + required implication note.

3) `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
- Add `RunRequest.force_interactive_alignment: bool = False` in §4.4.1.
- Make `discover_inputs(...)` ruff-safe in §4.4.6 by using `patterns: list[str] | None = None` and defining defaults inside the function.

### Implementation files

#### 1. `src/frame_compare/cli_entry.py`
**Purpose:** Implement `run` command to execute the pipeline and exit with correct codes.

**Changes:**
- Add missing CLI flag `--force-interactive-alignment`.
- Replace stub body with:
  - Build a `RunRequest` from CLI args (no implicit defaults beyond Typer defaults).
  - Call the runner entrypoint.
  - On `FrameCompareError`, map to exit code via `handle_error(...)` and exit.
  - On `KeyboardInterrupt`, exit with code 130.
  - If `RunResult.success` is `False`, exit with code 5.

**Functions to implement (spec-anchored):**
- `run(root: Path, config: Path | None, input_dir: Path | None, no_cache: bool, from_cache_only: bool, no_upload: bool, tm_preset: str | None, tm_target: int | None, tm_curve: str | None, frame_count: int | None, seed: int | None, overlay: str | None, skip_analysis: bool, skip_metadata: bool, skip_dovi: bool, force_interactive_alignment: bool, json_output: bool, no_color: bool, write_config: bool, diagnose_paths: bool, quiet: bool, verbose: bool) -> None`

**Key implementation notes:**
- Map `tm_target` CLI arg to `RunRequest.tm_target_nits`.
- Map `overlay` CLI arg to `RunRequest.overlay_mode`.
- Preserve existing `handle_error(...)` formatting/exit mapping behavior.

#### 2. `src/frame_compare/orchestration/coordinator.py`
**Purpose:** Apply CLI config overrides and ensure discover-inputs behavior matches SSOT.

**Changes:**
- Add `force_interactive_alignment: bool = False` to `RunRequest`.
- Apply CLI overrides to the loaded config before building `RunContext`:
  - Build `cli_args` dict from `RunRequest` values (`tm_preset`, `tm_target_nits`, `tm_curve`, `frame_count`, `seed`, `overlay_mode`, `no_upload`, `force_interactive_alignment`).
  - Apply with `apply_cli_overrides(...)`.
  - Ensure the `force_interactive_alignment=True` implication is applied (force_interactive + use_vspreview).
- Use `discover_inputs(...)` as the single source for “empty directory” behavior (no duplicate empty checks after calling it).

**Functions to implement (spec-anchored):**
- `execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult`

#### 3. `src/frame_compare/orchestration/preflight.py`
**Purpose:** Implement input discovery rules per §4.4.6 with deterministic ordering and correct error behavior.

**Ruff-safe strategy (normative):**
- `discover_inputs` takes `patterns: list[str] | None = None` and sets `effective_patterns` to the module constant when `patterns is None`.

**Changes:**
- Update signature per SSOT (patterns optional, default inside).
- Raise `NoVideosFoundError(FC-3001)` from `discover_inputs(...)` when empty, passing the effective patterns list.
- Keep stable ordering: case-insensitive lexicographic by filename.

**Functions to implement (spec-anchored):**
- `discover_inputs(input_dir: Path, patterns: list[str] | None = None) -> list[Path]`

#### 4. `src/frame_compare/config/overrides.py`
**Purpose:** Centralize and validate CLI → config overrides mapping per orchestration spec §4.4.5.

**Changes:**
- Update `CLI_OVERRIDE_MAP` to match §4.4.5 keys/paths:
  - Use `seed` → `analysis.random_seed` (do not use `random_seed` as the CLI key).
  - Add `force_interactive_alignment` → `audio_alignment.force_interactive`.
- Implement the required implication:
  - If `force_interactive_alignment` is enabled, also set `audio_alignment.use_vspreview = True`.
- Keep boolean inversion for `no_upload` → `slowpics.auto_upload = False`.

**Functions to implement (spec-anchored):**
- `apply_cli_overrides(config: ConfigSchema, cli_args: dict[str, object]) -> ConfigSchema`

#### 5. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`
**Purpose:** Keep the CLI flags SSOT contract consistent with the implemented CLI surface.

**Changes:**
- Add missing flag entry for `--force-interactive-alignment` (type `bool`, default `false`).
- Document that it maps to `audio_alignment.force_interactive` and implies `audio_alignment.use_vspreview = True` (contract note/comment).

## Tests to Update/Add (exact names + key assertions)

### 1) `tests/orchestration/test_preflight.py`
- Add `test_discover_inputs_empty_raises_no_videos_found_error_preserves_patterns`
  - Arrange: create empty `input_dir` (exists but contains no matching files).
  - Act: call `discover_inputs(input_dir)` (no explicit patterns).
  - Assert:
    - Raises `NoVideosFoundError`
    - `error.code == "FC-3001"`
    - Assert `error.path == input_dir.resolve()`
    - `error.patterns == ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]`

### 2) `tests/config/test_overrides.py`
- Add `test_apply_cli_overrides_seed_maps_to_analysis_random_seed`
  - Given default config and CLI args `{"seed": 123}`
  - Assert `new_config.analysis.random_seed == 123`
- Add `test_apply_cli_overrides_force_interactive_alignment_sets_force_and_use_vspreview`
  - Given default config and CLI args `{"force_interactive_alignment": True}`
  - Assert `new_config.audio_alignment.force_interactive is True`
  - Assert `new_config.audio_alignment.use_vspreview is True`

### 3) `tests/orchestration/test_execute_run.py`
- Add `test_execute_run_applies_cli_overrides_before_phase_execution`
  - Arrange: config TOML sets `audio_alignment.use_vspreview = false` and `report.enable = false` to avoid optional work.
  - Monkeypatch `coordinator.execute_phases` to capture `RunContext.config` from the first call and then return without running real phases.
  - Act: call `execute_run` with `RunRequest(tm_preset="filmic", force_interactive_alignment=True, skip_analysis=True, skip_metadata=True, skip_dovi=True, no_upload=True)`.
  - Assert captured config:
    - `config.color.preset == "filmic"`
    - `config.audio_alignment.force_interactive is True`
    - `config.audio_alignment.use_vspreview is True`

### 4) `tests/orchestration/test_run_request.py`
- Update `test_run_request_defaults`
  - Assert `request.force_interactive_alignment is False`

### 5) `tests/cli/test_cli_commands.py`
- Update `test_run_help_shows_all_options`
  - Add `--force-interactive-alignment` to the required option list.
- Replace `test_run_stub_executes` with:
  - `test_run_exits_zero_when_runner_returns_success`
    - Monkeypatch `frame_compare.cli_entry.runner.run` to return `RunResult(success=True)`.
    - Assert `exit_code == 0`.
  - `test_run_exits_processing_error_when_runner_returns_unsuccessful`
    - Monkeypatch `frame_compare.cli_entry.runner.run` to return `RunResult(success=False)`.
    - Assert `exit_code == 5`.

## Acceptance Criteria
- [ ] GIVEN a CLI invocation `frame-compare run ...` WHEN the pipeline completes successfully THEN the command exits with code `0` and does not print the prior stub marker.
- [ ] GIVEN the runner raises a `FrameCompareError` WHEN invoked via CLI THEN the command exits with the mapped `ExitCode` from `get_exit_code(...)`.
- [ ] GIVEN CLI overrides (`--tm-preset`, `--seed`, `--overlay`, `--no-upload`) WHEN `execute_run` builds the context THEN `RunContext.config` reflects the override mapping from orchestration spec §4.4.5.
- [ ] GIVEN `--force-interactive-alignment` WHEN overrides are applied THEN `config.audio_alignment.force_interactive=True` AND `config.audio_alignment.use_vspreview=True`.
- [ ] GIVEN an input directory with no matching videos WHEN `discover_inputs(...)` runs THEN it raises `NoVideosFoundError(FC-3001)` and preserves the effective patterns list.
- [ ] GIVEN mixed-case filenames WHEN `discover_inputs(...)` runs THEN ordering is stable and case-insensitive lexicographic by filename.

## Verification Commands

Spec anchor gate (MUST pass before coding):
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md
```

Quality gates:
```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors (Pyright warnings are treated as failures via `--warnings`).

## Notes for Coding Agent
- Keep unit tests hermetic: no network, no real VapourSynth, no FFmpeg.
- Prefer monkeypatching `runner.run` for CLI tests and `execute_phases` for orchestration tests to avoid heavy work.
- Apply CLI overrides exactly once per run in `execute_run(...)`, before any phase execution.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the **Plan Review Agent** for Frame Compare 2.0.

RUN_ID: 2026-02-04__p6-8__run

Target: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks

Read file:
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md

Run STOP gate (spec anchors):
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md
```

Then write:
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v3.md

Ensure the Plan Review verdict includes:
- Verdict: APPROVED or CHANGES REQUIRED
- Implementation Agent Decision Points Remaining: NONE (required for APPROVED)
