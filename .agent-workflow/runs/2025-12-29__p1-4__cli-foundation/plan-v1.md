---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v1
TARGET: Phase 1 → Item 1.4
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v1.md
---

# Implementation Plan: CLI Foundation

## Context

**Phase:** 1
**Module:** `frame_compare.cli_entry` + `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
**Dependencies:** Phase 1.1 (Config Module) ✅, Phase 1.2 (Error Handling) ✅, Phase 1.3 (Logging) ✅

## Scope

This plan covers:

- [x] Create `src/frame_compare/cli_entry.py` — extend existing stub with commands
- [ ] Implement Typer app + commands
- [ ] Add global options: `--root`, `--config`, `--quiet`, `--verbose`
- [ ] Implement `run` command (stub)
- [ ] Implement `wizard` command (stub)
- [ ] Implement `doctor` command (stub)
- [ ] Implement `preset` command group (stub)
- [ ] Map exceptions to exit codes
- [ ] Write CLI integration tests

This plan does NOT cover:

- Full implementation of `run` pipeline execution (Phase 6)
- Full `wizard` interactive UI (Phase 6)
- Full `doctor` dependency checks (Phase 6)
- `runner.py` and `orchestration/` subdirectory (Phase 6)
- Progress reporter implementations (already exist in utils)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2.1 Command Structure" (contains Typer command templates with full signatures)
  - Section: "2.2 Exit Codes" (contains ExitCode enum definition)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md`:
  - Section: "4.1 CLI Layer" (contains handle_error function template)
  - Section: "7. Exit Code Reference" (contains exit code mapping table)

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py` (MODIFY)

**Purpose:** Extend existing stub with full Typer CLI commands per spec.

**Implementation approach:**

The Coding Agent MUST follow the code templates in the Spec Anchors verbatim:

- `ExitCode(IntEnum)` enum from spec Section 2.2
- Command decorators and option definitions from spec Section 2.1
- `handle_error` function from error-handling.md Section 4.1

All commands except `version` are stubs that print "Not yet implemented" and exit 0.

**Functions to implement (spec-anchored):**

- `run(...) -> None` — Execute comparison pipeline (stub: prints message and exits 0)
- `wizard() -> None` — Interactive configuration setup (stub: prints message and exits 0)
- `doctor(json_output: bool) -> None` — Check system dependencies (stub: prints message or JSON and exits 0)
- `preset() -> None` — Command group container
- `preset_list() -> None` — List available presets (stub)
- `preset_apply(name: str) -> None` — Apply a preset (stub)
- `preset_save(name: str) -> None` — Save current config as preset (stub)
- `handle_error(error: FrameCompareError) -> int` — Map exception to exit code and display message

**CLI Options for `run` command (stub placeholders):**

All options defined in spec Section 2.1:

- `--root`/`-r`, `--config`/`-c`, `--input`/`-i`, `--no-cache`, `--from-cache-only`
- `--no-upload`, `--tm-preset`, `--tm-target`, `--tm-curve`, `--frame-count`/`-n`
- `--seed`, `--overlay`, `--skip-analysis`, `--skip-metadata`, `--skip-dovi`
- `--json`, `--no-color`, `--write-config`, `--diagnose-paths`, `--quiet`/`-q`, `--verbose`/`-v`

### 2. `tests/cli/test_cli_commands.py` (NEW)

**Purpose:** Unit tests for CLI commands using CliRunner.

**Tests required:**

- `test_run_help_shows_all_options` — `run --help` exits 0 and shows documented options
- `test_run_no_args_shows_help` — `run` with no args shows help (via Typer)
- `test_wizard_stub_exits_zero` — `wizard` exits 0 with stub message
- `test_doctor_stub_exits_zero` — `doctor` exits 0 with stub message
- `test_doctor_json_flag_accepted` — `doctor --json` exits 0
- `test_preset_list_stub` — `preset list` exits 0 with stub message
- `test_preset_apply_stub` — `preset apply test` exits 0 with stub message
- `test_preset_save_stub` — `preset save test` exits 0 with stub message

### 3. `tests/cli/test_exit_codes.py` (NEW)

**Purpose:** Test exception-to-exit-code mapping via `handle_error`.

**Tests required:**

- `test_handle_error_config_error_returns_2` — ConfigError maps to exit 2
- `test_handle_error_dependency_error_returns_3` — DependencyError maps to exit 3
- `test_handle_error_input_error_returns_4` — InputError maps to exit 4
- `test_handle_error_processing_error_returns_5` — ProcessingError maps to exit 5
- `test_handle_error_network_error_returns_6` — NetworkError maps to exit 6
- `test_handle_error_internal_error_returns_1` — InternalError maps to exit 1

### 4. `tests/cli/__init__.py` (NEW)

**Purpose:** Empty marker file for test package.

### 5. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-29__p1-4__cli-foundation`
- Artifact versions: plan-v1, plan-review-vN, impl-vN, verify-vN, review-vN
- Scope: CLI foundation with stub commands (no full implementation)
- SSOT edits: none
- Out-of-scope: runner.py, orchestration/, full command implementations

### 6. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for CLI foundation.

**Entry format:** Under `## [Unreleased]`, add:

```markdown
### Added
- CLI foundation with `run`, `wizard`, `doctor`, and `preset` command stubs
- Exit code mapping from exception types (FC-xxxx errors to exit codes 1-6)
```

## Acceptance Criteria

- [ ] GIVEN the CLI app WHEN `frame-compare --help` is invoked THEN all commands are listed (run, wizard, doctor, preset, version)
- [ ] GIVEN the CLI app WHEN `frame-compare run --help` is invoked THEN all options from spec are shown
- [ ] GIVEN the CLI app WHEN `frame-compare run` is invoked without required config THEN stub message is displayed and exit code is 0 (stub behavior)
- [ ] GIVEN the CLI app WHEN `frame-compare wizard` is invoked THEN stub message is shown and exit code is 0
- [ ] GIVEN the CLI app WHEN `frame-compare doctor` is invoked THEN stub message is shown and exit code is 0
- [ ] GIVEN the CLI app WHEN `frame-compare doctor --json` is invoked THEN stub JSON is output and exit code is 0
- [ ] GIVEN the CLI app WHEN `frame-compare preset list` is invoked THEN stub message is shown and exit code is 0
- [ ] GIVEN a ConfigError exception WHEN `handle_error` is called THEN exit code 2 is returned
- [ ] GIVEN a DependencyError exception WHEN `handle_error` is called THEN exit code 3 is returned
- [ ] GIVEN a NetworkError exception WHEN `handle_error` is called THEN exit code 6 is returned

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Type checking
.venv/bin/pyright --warnings src/frame_compare/cli_entry.py

# Linting
.venv/bin/ruff check src/frame_compare/cli_entry.py

# Unit tests
.venv/bin/pytest -v tests/cli/

# Existing e2e test still passes
.venv/bin/pytest -v tests/e2e/test_cli_version.py

# Full project type check (no regressions)
.venv/bin/pyright --warnings

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Existing stub:** `cli_entry.py` already exists with `app` and `version` command. Extend it, don't replace.

2. **Stub behavior:** All commands except `version` should print "Not yet implemented" message and exit 0. The `run` command should still define all CLI options per spec (they just won't be used yet).

3. **ExitCode enum:** Define as `IntEnum` to enable `raise typer.Exit(code=ExitCode.CONFIG_ERROR)`.

4. **handle_error function:** Must import from `frame_compare.errors` and map exception types to exit codes per spec. Use `rich.console.Console(stderr=True)` for error output.

5. **Typer patterns:**
   - Use `@app.command()` for top-level commands
   - Use `preset_app = typer.Typer()` + `app.add_typer(preset_app, name="preset")` for subcommands
   - Use `typer.Option(...)` with proper type hints

6. **Test fixtures:** Use `typer.testing.CliRunner` for all CLI tests. No mocking needed for stub commands.

7. **Import order:** The CLI must not import heavy modules at module level. Use local imports inside command functions where needed.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p1-4__cli-foundation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v1.md
