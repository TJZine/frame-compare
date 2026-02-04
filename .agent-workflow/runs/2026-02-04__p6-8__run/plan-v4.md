---
RUN_ID: 2026-02-04__p6-8__run
VERSION: v4
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md
---

# Implementation Plan: Phase 6.8 — CLI `run` Command (Bundled)

## Changes Since plan-v3
- Made orchestration `cli_args` override dict keying explicit (must match `CLI_OVERRIDE_MAP` keys, not `RunRequest` field names).
- Extended tests to lock in CLI→`RunRequest` name-mismatch mappings and orchestration override application for `tm_target_nits`, `overlay_mode`, and `no_upload` inversion.

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

### 1. `src/frame_compare/cli_entry.py`
**Purpose:** Implement the `run` command to execute the pipeline and exit with correct codes.

**Changes:**
- Add missing CLI flag `--force-interactive-alignment`.
- Replace stub body with:
  - Build a `RunRequest` from CLI args (no implicit defaults beyond Typer defaults).
  - Call `frame_compare.runner.run(request, dependencies=None)`.
  - On `FrameCompareError`, map to exit code via `handle_error(...)` and exit.
  - On `KeyboardInterrupt`, exit with code 130.
  - If `RunResult.success` is `False`, exit with code 5.

**Functions to implement (spec-anchored):**
- `run(root: Path, config: Path | None, input_dir: Path | None, no_cache: bool, from_cache_only: bool, no_upload: bool, tm_preset: str | None, tm_target: int | None, tm_curve: str | None, frame_count: int | None, seed: int | None, overlay: str | None, skip_analysis: bool, skip_metadata: bool, skip_dovi: bool, force_interactive_alignment: bool, json_output: bool, no_color: bool, write_config: bool, diagnose_paths: bool, quiet: bool, verbose: bool) -> None`

**Key implementation notes:**
- Map `tm_target` CLI arg to `RunRequest.tm_target_nits`.
- Map `overlay` CLI arg to `RunRequest.overlay_mode`.

### 2. `src/frame_compare/orchestration/coordinator.py`
**Purpose:** Apply CLI config overrides deterministically and ensure discover-inputs behavior matches SSOT.

**Rationale (normative):**
`apply_cli_overrides(...)` consumes dict keys matching `CLI_OVERRIDE_MAP` / §4.4.5, which are *not* identical to `RunRequest` field names (e.g., `tm_target` vs `tm_target_nits`, `overlay` vs `overlay_mode`).

**Changes:**
- Add `force_interactive_alignment: bool = False` to `RunRequest`.
- Apply CLI overrides to loaded config before building `RunContext` using this exact key mapping:

```python
cli_args = {
    "tm_preset": request.tm_preset,
    "tm_target": request.tm_target_nits,
    "tm_curve": request.tm_curve,
    "frame_count": request.frame_count,
    "seed": request.seed,
    "overlay": request.overlay_mode,
    "no_upload": request.no_upload,
    "force_interactive_alignment": request.force_interactive_alignment,
}
config = apply_cli_overrides(preflight.config, cli_args=cli_args)
```

- Ensure `force_interactive_alignment=True` implies both:
  - `config.audio_alignment.force_interactive = True`
  - `config.audio_alignment.use_vspreview = True`
- Use `discover_inputs(...)` as the single source for “empty directory” behavior (no duplicate emptiness check after calling it).

**Functions to implement (spec-anchored):**
- `execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult`

### 3. `src/frame_compare/orchestration/preflight.py`
**Purpose:** Implement input discovery rules per §4.4.6 with deterministic ordering and correct error behavior.

**Ruff-safe strategy (normative):**
`discover_inputs` takes `patterns: list[str] | None = None` and uses the module default patterns when `None`.

**Changes:**
- Update signature per SSOT.
- Raise `NoVideosFoundError(FC-3001)` from `discover_inputs(...)` when empty, including the effective patterns list on the error.
- Keep stable ordering: case-insensitive lexicographic by filename.

**Functions to implement (spec-anchored):**
- `discover_inputs(input_dir: Path, patterns: list[str] | None = None) -> list[Path]`

### 4. `src/frame_compare/config/overrides.py`
**Purpose:** Centralize and validate CLI → config overrides mapping per §4.4.5.

**Changes:**
- Update `CLI_OVERRIDE_MAP` to match §4.4.5 keys/paths:
  - Use `seed` → `analysis.random_seed`.
  - Add `force_interactive_alignment` → `audio_alignment.force_interactive`.
- Implement required implication:
  - If `force_interactive_alignment` is enabled, also set `audio_alignment.use_vspreview = True`.
- Keep boolean inversion for `no_upload` → `slowpics.auto_upload = False`.

**Functions to implement (spec-anchored):**
- `apply_cli_overrides(config: ConfigSchema, cli_args: dict[str, object]) -> ConfigSchema`

### 5. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`
**Purpose:** Keep CLI flags contract consistent with implemented CLI surface.

**Changes:**
- Add missing flag entry for `--force-interactive-alignment` (type `bool`, default `false`).
- Note that it maps to `audio_alignment.force_interactive` and implies `audio_alignment.use_vspreview = True`.

## Tests to Update/Add (exact names + key assertions)

### 1) `tests/orchestration/test_preflight.py`
- Add `test_discover_inputs_empty_raises_no_videos_found_error_preserves_patterns`
  - Arrange: empty existing `input_dir`.
  - Act: call `discover_inputs(input_dir)` with patterns omitted.
  - Assert:
    - Raises `NoVideosFoundError`
    - `error.code == "FC-3001"`
    - Assert `error.path == input_dir.resolve()`
    - `error.patterns == ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]`

### 2) `tests/config/test_overrides.py`
- Add `test_apply_cli_overrides_seed_maps_to_analysis_random_seed`
  - Given CLI args `{"seed": 123}` → assert `new_config.analysis.random_seed == 123`
- Add `test_apply_cli_overrides_force_interactive_alignment_sets_force_and_use_vspreview`
  - Given CLI args `{"force_interactive_alignment": True}` → assert:
    - `new_config.audio_alignment.force_interactive is True`
    - `new_config.audio_alignment.use_vspreview is True`

### 3) `tests/orchestration/test_execute_run.py`
- Add `test_execute_run_applies_cli_overrides_before_phase_execution`
  - Arrange:
    - Config TOML sets `audio_alignment.use_vspreview = false` and `report.enable = false`.
    - Monkeypatch `coordinator.execute_phases` to capture `RunContext.config` from the first call, then return immediately.
  - Act: call `execute_run` with a request that sets:
    - `tm_preset="filmic"`
    - `tm_target_nits=203`
    - `overlay_mode="diagnostic"`
    - `seed=123`
    - `no_upload=True`
    - `force_interactive_alignment=True`
    - `skip_analysis=True`, `skip_metadata=True`, `skip_dovi=True`
  - Assert captured config:
    - `config.color.preset == "filmic"`
    - `config.color.target_nits == 203`
    - `config.screenshots.overlay_mode == "diagnostic"`
    - `config.analysis.random_seed == 123`
    - `config.slowpics.auto_upload is False`
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
- Add `test_run_builds_run_request_from_cli_args`
  - Monkeypatch `frame_compare.cli_entry.runner.run` to capture the incoming `RunRequest` and return `RunResult(success=True)`.
  - Invoke `frame-compare run` with (at minimum): `--tm-target 203 --overlay diagnostic --force-interactive-alignment`.
  - Assert captured request fields:
    - `request.tm_target_nits == 203`
    - `request.overlay_mode == "diagnostic"`
    - `request.force_interactive_alignment is True`

## Acceptance Criteria
- [ ] GIVEN `frame-compare run` completes successfully WHEN invoked THEN it exits `0` and does not print the prior stub marker.
- [ ] GIVEN the runner raises a `FrameCompareError` WHEN invoked via CLI THEN it exits with the mapped exit code from `get_exit_code(...)`.
- [ ] GIVEN `--tm-target`, `--overlay`, `--seed`, and `--no-upload` WHEN `execute_run` builds `RunContext` THEN `RunContext.config` reflects §4.4.5 override mapping (including `no_upload` inversion).
- [ ] GIVEN `--force-interactive-alignment` WHEN overrides are applied THEN both `audio_alignment.force_interactive=True` AND `audio_alignment.use_vspreview=True`.
- [ ] GIVEN an empty input directory WHEN `discover_inputs(...)` runs THEN it raises `NoVideosFoundError(FC-3001)` and preserves the effective patterns list.

## Verification Commands

Spec anchor gate (MUST pass before coding):
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md
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
- In CLI tests, capture `RunRequest` by monkeypatching `frame_compare.cli_entry.runner.run`.
- In orchestration tests, capture the config used for context building by monkeypatching `execute_phases`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the **Plan Review Agent** for Frame Compare 2.0.

RUN_ID: 2026-02-04__p6-8__run

Target: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks

Read file:
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md

Run STOP gate (spec anchors):
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md
```

Then write:
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v4.md

Ensure the Plan Review verdict includes:
- Verdict: APPROVED or CHANGES REQUIRED
- Implementation Agent Decision Points Remaining: NONE (required for APPROVED)
