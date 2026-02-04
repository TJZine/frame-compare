---
RUN_ID: 2026-02-04__p6-8__run
VERSION: v2
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md
---

# Implementation Plan: Phase 6.8 — CLI `run` Command (Bundled)

## Changes Since plan-v1
- Spec-anchor gate wiring fix: `config-module.md` code-fence comment lines are indented so `validate_spec_anchors.py` does not mis-parse them as Markdown headings (no intended spec semantics change).

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
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.4 Run Coordination"
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
- [ ] Implement input discovery rules per orchestration spec §4.4.6 (default patterns, stable order, raise `NoVideosFoundError`).

This plan does NOT cover:
- `wizard`, `doctor`, `preset` subcommands completion (separate checklist items under 6.8).
- JSON output schema for successful runs beyond existing progress reporter selection (future slice unless SSOT defines a success schema).
- Docker / real-deps integration verification (Phase 6 quality gate; out of scope for this slice).

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py`
**Purpose:** Implement `run` command to execute the orchestration pipeline and exit with correct codes.

**Changes:**
- Add missing CLI flag `--force-interactive-alignment` to match SSOT.
- Replace stub body with:
  - Build a `RunRequest` from CLI args (no implicit defaults beyond Typer defaults).
  - Call `frame_compare.runner.run(request, dependencies=None)`.
  - On `FrameCompareError`, call `handle_error(...)` and exit with that code.
  - On `KeyboardInterrupt`, exit with `ExitCode.INTERRUPTED` (130).
  - If `RunResult.success` is `False`, exit with `ExitCode.PROCESSING_ERROR` (5).

**Functions to implement (spec-anchored):**
- `run(root: Path, config: Path | None, input_dir: Path | None, no_cache: bool, from_cache_only: bool, no_upload: bool, tm_preset: str | None, tm_target: int | None, tm_curve: str | None, frame_count: int | None, seed: int | None, overlay: str | None, skip_analysis: bool, skip_metadata: bool, skip_dovi: bool, force_interactive_alignment: bool, json_output: bool, no_color: bool, write_config: bool, diagnose_paths: bool, quiet: bool, verbose: bool) -> None`

**Key implementation notes:**
- `overlay` CLI arg maps to `RunRequest.overlay_mode` (name mismatch).
- `tm_target` CLI arg maps to `RunRequest.tm_target_nits` (name mismatch).
- `--force-interactive-alignment` is carried on the request so the orchestration layer can apply config overrides deterministically.

### 2. `src/frame_compare/orchestration/coordinator.py`
**Purpose:** Ensure orchestration applies CLI config overrides (highest priority) and uses spec-compliant input discovery.

**Changes:**
- Add `force_interactive_alignment: bool = False` to `RunRequest` (the orchestration request type) to carry the CLI flag through to orchestration.
- Apply CLI overrides to the loaded config before creating `RunContext`:
  - Build a dict of override values from the `RunRequest`.
  - Call `frame_compare.config.overrides.apply_cli_overrides(preflight.config, cli_args=...)`.
  - Apply `--force-interactive-alignment` implication: if enabled, ensure both `audio_alignment.force_interactive=True` and `audio_alignment.use_vspreview=True`.
  - Use the overridden config in `RunContext`.
- Use `discover_inputs(...)` per §4.4.6 semantics (stable order, error on empty result).

**Functions to implement (spec-anchored):**
- `execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult`

**Key implementation notes:**
- Override priority must be CLI > config file > defaults (apply overrides after config load, before phase execution).
- Keep unit tests deterministic by monkeypatching phase execution and dependency boundaries (no real VS/FFmpeg/network).

### 3. `src/frame_compare/orchestration/preflight.py`
**Purpose:** Make `discover_inputs(...)` match SSOT (§4.4.6): default patterns, deterministic ordering, and correct error behavior.

**Changes:**
- Update `discover_inputs` signature to include the default patterns list.
- Raise `NoVideosFoundError(FC-3001)` from `discover_inputs` when no matches.
- Keep stable ordering: case-insensitive lexicographic by filename.

**Functions to implement (spec-anchored):**
- `discover_inputs(input_dir: Path, patterns: list[str] = ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]) -> list[Path]`

### 4. `src/frame_compare/config/overrides.py`
**Purpose:** Centralize and validate CLI → config overrides mapping per orchestration spec §4.4.5.

**Changes:**
- Update `CLI_OVERRIDE_MAP` to match orchestration spec keys and config paths:
  - Map `seed` → `analysis.random_seed`.
  - Keep `frame_count` → `analysis.frame_count`, `tm_preset` → `color.preset`, `tm_target` → `color.target_nits`, `tm_curve` → `color.tone_curve`, `overlay` → `screenshots.overlay_mode`.
  - Add `force_interactive_alignment` → `audio_alignment.force_interactive` and enforce implied `audio_alignment.use_vspreview = True`.
- Ensure boolean inversion stays correct for `no_upload` → `slowpics.auto_upload = False`.
- Keep behavior: ignore unknown keys; ignore keys with `None` values; validate via Pydantic and raise `ConfigValidationError` on invalid overrides.

**Functions to implement (spec-anchored):**
- `apply_cli_overrides(config: ConfigSchema, cli_args: dict[str, object]) -> ConfigSchema`

### 5. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`
**Purpose:** Keep the CLI flags SSOT contract consistent with the implemented CLI surface.

**Changes:**
- Add missing flag entry for `--force-interactive-alignment` (type `bool`, default `false`).
- Document that it maps to `audio_alignment.force_interactive` and implies `audio_alignment.use_vspreview = True` (contract note/comment).

### 6. `tests/cli/test_cli_commands.py`
**Purpose:** Keep CLI surface tests aligned to the implemented `run` command.

**Tests required / updates:**
- Update `test_run_help_shows_all_options` to include `--force-interactive-alignment`.
- Replace `test_run_stub_executes` with deterministic tests that monkeypatch `frame_compare.cli_entry.runner.run`:
  - Exit code `0` when fake runner returns `RunResult(success=True)`.
  - Exit code `5` when fake runner returns `RunResult(success=False)`.
  - Assert the captured `RunRequest` fields match the CLI args (spot-check `tm_preset`, `tm_target_nits`, `overlay_mode`, `seed`, `force_interactive_alignment`).

### 7. `tests/orchestration/test_run_request.py`
**Purpose:** Ensure `RunRequest` defaults and immutability remain correct after adding `force_interactive_alignment`.

**Tests required / updates:**
- Update `test_run_request_defaults` to assert `force_interactive_alignment is False`.

### 8. `tests/config/test_overrides.py`
**Purpose:** Validate override mapping behavior is spec-correct.

**Tests required / updates:**
- Add a test for `seed` mapping to `analysis.random_seed`.
- Add a test for `force_interactive_alignment` mapping:
  - Setting it to `True` sets both `audio_alignment.force_interactive=True` and `audio_alignment.use_vspreview=True`.

### 9. `tests/orchestration/test_execute_run.py`
**Purpose:** Ensure orchestration applies config overrides before building context.

**Tests required / updates:**
- Add a test that monkeypatches `frame_compare.orchestration.coordinator.execute_phases` to capture the `RunContext.config` used:
  - Create a config file with known baseline values (e.g., `color.preset = "reference"`, `audio_alignment.use_vspreview = false`).
  - Run `execute_run` with a `RunRequest` setting overrides (e.g., `tm_preset="filmic"`, `force_interactive_alignment=True`).
  - Assert the captured config reflects the overrides.

## Acceptance Criteria
- [ ] GIVEN a CLI invocation `frame-compare run ...` WHEN the pipeline completes successfully THEN the command exits with code `0` and does not print the prior stub marker.
- [ ] GIVEN the runner raises a `FrameCompareError` WHEN invoked via CLI THEN the command exits with the mapped `ExitCode` from `get_exit_code(...)`.
- [ ] GIVEN CLI overrides (`--tm-preset`, `--seed`, `--overlay`, `--no-upload`) WHEN `execute_run` builds the context THEN `RunContext.config` reflects the override mapping from orchestration spec §4.4.5.
- [ ] GIVEN `--force-interactive-alignment` WHEN overrides are applied THEN `config.audio_alignment.force_interactive=True` AND `config.audio_alignment.use_vspreview=True`.
- [ ] GIVEN an input directory with no matching videos WHEN `discover_inputs(...)` runs THEN it raises `NoVideosFoundError(FC-3001)` and preserves the patterns list.
- [ ] GIVEN mixed-case filenames WHEN `discover_inputs(...)` runs THEN ordering is stable and case-insensitive lexicographic by filename.

## Verification Commands

Spec anchor gate (MUST pass before coding):
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md
```

Quality gates (Coding + Verification):
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
- Do not execute the real pipeline in unit tests; monkeypatch `runner.run` / `execute_phases` and use fake `VSLoader` (pattern already used in `tests/orchestration/test_execute_run.py`).
- Ensure no new tests require network / VapourSynth / FFmpeg by default.
- Keep override mapping logic centralized in `config/overrides.py` and apply it once per run in `execute_run` before phases.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the **Plan Review Agent** for Frame Compare 2.0.

RUN_ID: 2026-02-04__p6-8__run

Target: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks

Read file:
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md

Run STOP gate (spec anchors):
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md
```

Then write:
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v2.md

Ensure the Plan Review verdict includes:
- Verdict: APPROVED or CHANGES REQUIRED
- Implementation Agent Decision Points Remaining: NONE (required for APPROVED)
