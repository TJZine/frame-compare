---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v4
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v3.md
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v4.md
---

# Implementation Plan: CLI Foundation

## Changes Since plan-v3

1. **Public API Signatures:** Added `main()` and `version()` marked as "(unchanged)".
2. **Typer Defaults Clarified:** Explicit note that all `run` parameters use `typer.Option(...)` with defaults, making all options optional.
3. **Spec Anchors:** Format unchanged but validator passes.

## Context

**Phase:** 1
**Module:** `frame_compare.cli_entry`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
**Dependencies:** Phase 1.1 (Config Module) ✅, Phase 1.2 (Error Handling) ✅, Phase 1.3 (Logging) ✅

## Scope

This plan covers:

- [ ] Extend `src/frame_compare/cli_entry.py` with commands: `run`, `wizard`, `doctor`, `preset list|apply|save`
- [ ] Import and use `ExitCode` + `get_exit_code()` from `frame_compare.errors`
- [ ] Implement `handle_error()` using imported exit code mapping
- [ ] Write CLI unit tests in `tests/cli/`

This plan does NOT cover:

- Full implementation of `run` pipeline execution (Phase 6)
- Full `wizard` interactive UI (Phase 6)
- Full `doctor` dependency checks (Phase 6)
- `runner.py` and `orchestration/` subdirectory (Phase 6)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2.1 Command Structure"
  - Section: "2.2 Exit Codes"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "4. Exit Code Mapping"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md`:
  - Section: "4.1 CLI Layer"

## Public API Signatures (spec-anchored)

**Existing functions (unchanged, do NOT modify):**

The existing `main()` callback and `version()` command in cli_entry.py are NOT part of this implementation. Leave them unchanged.

**New functions (to implement per SSOT Section 2.1):**

All `run` command parameters use `typer.Option(...)` defaults per SSOT, making them **optional**:

- `run(root: Path = typer.Option("."), config: Path | None = typer.Option(None), ...) -> None` — See SSOT for full signature with all 21 optional parameters
- `wizard() -> None`
- `doctor(json_output: bool = typer.Option(False)) -> None`
- `preset_list() -> None`
- `preset_apply(name: str) -> None`
- `preset_save(name: str) -> None`
- `handle_error(error: FrameCompareError) -> int`

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py` (MODIFY)

**Purpose:** Extend existing stub with full Typer CLI commands per spec.

**Exit Code Source of Truth:**

```python
from frame_compare.errors import ExitCode, get_exit_code, FrameCompareError
```

The `handle_error()` function MUST call `get_exit_code(error)` per SSOT.

**Typer Option Defaults (CRITICAL):**

All `run` command parameters MUST use `typer.Option(...)` with defaults exactly as shown in SSOT Section 2.1. This makes all options optional (not required) when invoking the CLI.

**Stub Output Contracts (deterministic):**

| Command | Output (stdout) | Exit |
|---------|-----------------|------|
| `run` (no args) | `"[stub] run: Not yet implemented\n"` | 0 |
| `wizard` | `"[stub] wizard: Not yet implemented\n"` | 0 |
| `doctor` | `"[stub] doctor: Not yet implemented\n"` | 0 |
| `doctor --json` | `{"status": "stub", "checks": []}\n` (valid JSON) | 0 |
| `preset list` | `"[stub] preset list: Not yet implemented\n"` | 0 |
| `preset apply <name>` | `"[stub] preset apply: Not yet implemented\n"` | 0 |
| `preset save <name>` | `"[stub] preset save: Not yet implemented\n"` | 0 |

**Typer Sub-App Pattern for Presets:**

```python
preset_app = typer.Typer(
    name="preset",
    help="Manage configuration presets.",
    no_args_is_help=True,
)
app.add_typer(preset_app, name="preset")

@preset_app.command("list")
def preset_list() -> None: ...
```

### 2. `tests/cli/test_cli_commands.py` (NEW)

**Purpose:** Unit tests for CLI commands using CliRunner.

**Tests required:**

- `test_app_help_lists_all_commands` — `--help` exits 0, output contains `run`, `wizard`, `doctor`, `preset`, `version`
- `test_run_help_shows_all_options` — `run --help` exits 0, output contains ALL SSOT flags (see below)
- `test_run_stub_executes` — `run` (no args) exits 0, stdout equals `"[stub] run: Not yet implemented\n"`
- `test_wizard_stub` — `wizard` exits 0, stdout equals `"[stub] wizard: Not yet implemented\n"`
- `test_doctor_stub_text` — `doctor` exits 0, stdout equals `"[stub] doctor: Not yet implemented\n"`
- `test_doctor_stub_json` — `doctor --json` exits 0, stdout is valid JSON with keys `status`, `checks`
- `test_preset_list_stub` — `preset list` exits 0, stdout equals `"[stub] preset list: Not yet implemented\n"`
- `test_preset_apply_stub` — `preset apply test-name` exits 0, stdout equals `"[stub] preset apply: Not yet implemented\n"`
- `test_preset_save_stub` — `preset save test-name` exits 0, stdout equals `"[stub] preset save: Not yet implemented\n"`

**Full SSOT Option Flags for `test_run_help_shows_all_options`:**

```python
REQUIRED_RUN_OPTIONS = [
    "--root", "-r",
    "--config", "-c",
    "--input", "-i",
    "--no-cache",
    "--from-cache-only",
    "--no-upload",
    "--tm-preset",
    "--tm-target",
    "--tm-curve",
    "--frame-count", "-n",
    "--seed",
    "--overlay",
    "--skip-analysis",
    "--skip-metadata",
    "--skip-dovi",
    "--json",
    "--no-color",
    "--write-config",
    "--diagnose-paths",
    "--quiet", "-q",
    "--verbose", "-v",
]
```

### 3. `tests/cli/test_exit_codes.py` (NEW)

**Purpose:** Test exception-to-exit-code mapping via `handle_error`.

**SSOT-Correct Exception Instances (from errors-module.md):**

| Test | Exception Constructor (SSOT-exact) | Expected Exit Code |
|------|-------------------------------------|-------------------|
| Config error | `ConfigNotFoundError(Path("/nonexistent/config.toml"))` | 2 |
| Dependency error | `VapourSynthNotFoundError()` | 3 |
| Input error | `NoVideosFoundError(Path("/empty"), patterns=["*.mkv"])` | 4 |
| Processing error | `FrameExtractionError(frame=0, clip=Path("/video.mkv"))` | 5 |
| Network error | `SlowpicsError("test error")` | 6 |
| Internal error | `GenericInternalError("test internal error")` | 1 |

**Tests required:**

- `test_handle_error_config_error_returns_2` — passes `ConfigNotFoundError(Path("/nonexistent/config.toml"))`, expects return `2`
- `test_handle_error_dependency_error_returns_3` — passes `VapourSynthNotFoundError()`, expects return `3`
- `test_handle_error_input_error_returns_4` — passes `NoVideosFoundError(Path("/empty"), patterns=["*.mkv"])`, expects return `4`
- `test_handle_error_processing_error_returns_5` — passes `FrameExtractionError(frame=0, clip=Path("/video.mkv"))`, expects return `5`
- `test_handle_error_network_error_returns_6` — passes `SlowpicsError("test error")`, expects return `6`
- `test_handle_error_internal_error_returns_1` — passes `GenericInternalError("test internal error")`, expects return `1`

### 4. `tests/cli/__init__.py` (NEW)

**Purpose:** Empty marker file for test package.

### 5. `docs/DECISIONS.md` (MODIFY)

**Required facts to record:**

- RUN_ID: `2025-12-29__p1-4__cli-foundation`
- SSOT edits: error-handling.md Section 4.1 (use get_exit_code), cli-module.md Section 2.1 (Typer sub-app pattern)
- Exit code source of truth: `frame_compare.errors.ExitCode` + `get_exit_code()`

### 6. `CHANGELOG.md` (MODIFY)

**Entry format:** Under `## [Unreleased]`, add:

```markdown
### Added
- CLI foundation with `run`, `wizard`, `doctor`, and `preset` command stubs
- Exception-to-exit-code mapping using `frame_compare.errors.get_exit_code()`
```

## Acceptance Criteria

- [ ] GIVEN `frame-compare --help` WHEN invoked THEN output lists: `run`, `wizard`, `doctor`, `preset`, `version`
- [ ] GIVEN `frame-compare run --help` WHEN invoked THEN contains all 21 SSOT-defined option flags
- [ ] GIVEN `frame-compare run` WHEN invoked THEN stdout is `"[stub] run: Not yet implemented\n"` and exit 0
- [ ] GIVEN `frame-compare doctor --json` WHEN invoked THEN stdout is valid JSON `{"status": "stub", "checks": []}` and exit 0
- [ ] GIVEN `handle_error(ConfigNotFoundError(Path("/x")))` WHEN called THEN returns `2`
- [ ] GIVEN `handle_error(VapourSynthNotFoundError())` WHEN called THEN returns `3`
- [ ] GIVEN `handle_error(SlowpicsError("x"))` WHEN called THEN returns `6`

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/cli_entry.py
.venv/bin/ruff check src/frame_compare/cli_entry.py
.venv/bin/pytest -v tests/cli/
.venv/bin/pytest -v tests/e2e/test_cli_version.py
.venv/bin/pyright --warnings
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0.

## Notes for Coding Agent

1. **Existing stub:** `cli_entry.py` exists with `app`, `main()`, and `version()`. Do NOT modify these existing functions.

2. **Exit codes:** Import from `frame_compare.errors`:

   ```python
   from frame_compare.errors import ExitCode, get_exit_code, FrameCompareError
   ```

3. **handle_error implementation per SSOT:**

   ```python
   def handle_error(error: FrameCompareError) -> int:
       console = Console(stderr=True)
       console.print(f"[red]Error[/red] [{error.code}]: {error.context.message}")
       if error.hint:
           console.print(f"[yellow]Hint:[/yellow] {error.hint}")
       return int(get_exit_code(error))
   ```

4. **Typer Option Defaults:** Copy the `run` command signature exactly from SSOT Section 2.1, including all `typer.Option(...)` defaults. All options are optional.

5. **Rollback:** If Typer behavior diverges from SSOT or blocks implementation, STOP and return to Planning.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p1-4__cli-foundation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v4.md
