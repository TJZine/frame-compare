---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v2
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v2.md
---

# Implementation Plan: CLI Foundation

## Changes Since plan-v1

1. **SSOT Updated:** Fixed `cli-module.md` Section 2.1 — replaced unsupported `@app.group()` with Typer sub-app pattern (`preset_app = typer.Typer()` + `app.add_typer()`). Removed `def preset() -> None`.
2. **Exit Code Source of Truth:** CLI must import `ExitCode` and `get_exit_code()` from `frame_compare.errors` — not redefine.
3. **Removed `preset() -> None`:** Function signature removed from plan since SSOT no longer defines it.
4. **Deterministic Stub Outputs:** Specified exact stdout text and JSON schema for each stub command.
5. **Fixed `run` No-Args Behavior:** Typer will execute the stub; test updated to expect stub output, not help.
6. **Exit-Code Tests:** Added concrete exception constructors with deterministic arguments.
7. **Spec Anchors:** Added errors-module.md Section 4 for `get_exit_code()` definition.

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

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py` (MODIFY)

**Purpose:** Extend existing stub with full Typer CLI commands per spec.

**Functions to implement (spec-anchored):**

- `run(...) -> None` — per spec Section 2.1 (stub: prints `"[stub] run: Not yet implemented"` to stdout, exits 0)
- `wizard() -> None` — stub: prints `"[stub] wizard: Not yet implemented"` to stdout, exits 0
- `doctor(json_output: bool = False) -> None` — stub: prints text or JSON per format below
- `preset_list() -> None` — stub: prints `"[stub] preset list: Not yet implemented"` to stdout, exits 0
- `preset_apply(name: str) -> None` — stub: prints `"[stub] preset apply: Not yet implemented"` to stdout, exits 0
- `preset_save(name: str) -> None` — stub: prints `"[stub] preset save: Not yet implemented"` to stdout, exits 0
- `handle_error(error: FrameCompareError) -> int` — per error-handling.md Section 4.1

**Exit Code Source of Truth:**

The CLI MUST import and use `ExitCode` and `get_exit_code()` from `frame_compare.errors`:

```python
from frame_compare.errors import ExitCode, get_exit_code, FrameCompareError
```

The `handle_error()` function MUST call `get_exit_code(error)` rather than reimplementing the mapping.

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
- `test_run_help_shows_all_options` — `run --help` exits 0, output contains `--root`, `--config`, `--quiet`, `--verbose`
- `test_run_stub_executes` — `run` (no args) exits 0, stdout equals `"[stub] run: Not yet implemented\n"`
- `test_wizard_stub` — `wizard` exits 0, stdout equals `"[stub] wizard: Not yet implemented\n"`
- `test_doctor_stub_text` — `doctor` exits 0, stdout equals `"[stub] doctor: Not yet implemented\n"`
- `test_doctor_stub_json` — `doctor --json` exits 0, stdout is valid JSON with keys `status`, `checks`
- `test_preset_list_stub` — `preset list` exits 0, stdout equals `"[stub] preset list: Not yet implemented\n"`
- `test_preset_apply_stub` — `preset apply test-name` exits 0, stdout equals `"[stub] preset apply: Not yet implemented\n"`
- `test_preset_save_stub` — `preset save test-name` exits 0, stdout equals `"[stub] preset save: Not yet implemented\n"`

### 3. `tests/cli/test_exit_codes.py` (NEW)

**Purpose:** Test exception-to-exit-code mapping via `handle_error`.

**Concrete Exception Instances (deterministic):**

| Test | Exception Constructor |
|------|----------------------|
| Config error → 2 | `ConfigNotFoundError(path=Path("/nonexistent/config.toml"))` |
| Dependency error → 3 | `VapourSynthNotFoundError()` |
| Input error → 4 | `NoVideosFoundError(input_dir=Path("/empty"), patterns=["*.mkv"])` |
| Processing error → 5 | `FrameExtractionError(frame_num=0, path=Path("/video.mkv"), reason="test")` |
| Network error → 6 | `SlowpicsUploadError(status_code=500, response_text="error")` |
| Internal error → 1 | `InternalError(message="test internal error")` |

**Tests required:**

- `test_handle_error_config_error_returns_2` — passes `ConfigNotFoundError(...)`, expects return value `2`
- `test_handle_error_dependency_error_returns_3` — passes `VapourSynthNotFoundError()`, expects return value `3`
- `test_handle_error_input_error_returns_4` — passes `NoVideosFoundError(...)`, expects return value `4`
- `test_handle_error_processing_error_returns_5` — passes `FrameExtractionError(...)`, expects return value `5`
- `test_handle_error_network_error_returns_6` — passes `SlowpicsUploadError(...)`, expects return value `6`
- `test_handle_error_internal_error_returns_1` — passes `InternalError(...)`, expects return value `1`

### 4. `tests/cli/__init__.py` (NEW)

**Purpose:** Empty marker file for test package.

### 5. `docs/DECISIONS.md` (MODIFY)

**Required facts to record:**

- RUN_ID: `2025-12-29__p1-4__cli-foundation`
- Artifact versions created
- SSOT edits: cli-module.md Section 2.1 (Typer sub-app pattern)
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
- [ ] GIVEN `frame-compare run --help` WHEN invoked THEN contains `--root`, `--config`, `--quiet`, `--verbose`
- [ ] GIVEN `frame-compare run` WHEN invoked THEN stdout is `"[stub] run: Not yet implemented\n"` and exit 0
- [ ] GIVEN `frame-compare wizard` WHEN invoked THEN stdout is `"[stub] wizard: Not yet implemented\n"` and exit 0
- [ ] GIVEN `frame-compare doctor` WHEN invoked THEN stdout is `"[stub] doctor: Not yet implemented\n"` and exit 0
- [ ] GIVEN `frame-compare doctor --json` WHEN invoked THEN stdout is valid JSON `{"status": "stub", "checks": []}` and exit 0
- [ ] GIVEN `frame-compare preset list` WHEN invoked THEN stdout is `"[stub] preset list: Not yet implemented\n"` and exit 0
- [ ] GIVEN `handle_error(ConfigNotFoundError(...))` WHEN called THEN returns `2`
- [ ] GIVEN `handle_error(VapourSynthNotFoundError())` WHEN called THEN returns `3`
- [ ] GIVEN `handle_error(SlowpicsUploadError(...))` WHEN called THEN returns `6`

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

1. **Existing stub:** `cli_entry.py` exists with `app`, `main()`, and `version`. Extend it.

2. **Exit codes:** Import from `frame_compare.errors`:

   ```python
   from frame_compare.errors import ExitCode, get_exit_code, FrameCompareError
   ```

3. **handle_error implementation:**

   ```python
   def handle_error(error: FrameCompareError) -> int:
       console = Console(stderr=True)
       console.print(f"[red]Error[/red] [{error.code}]: {error.context.message}")
       if error.hint:
           console.print(f"[yellow]Hint:[/yellow] {error.hint}")
       return int(get_exit_code(error))
   ```

4. **Rollback:** If Typer behavior diverges from SSOT or blocks implementation, STOP and return to Planning.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p1-4__cli-foundation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v2.md
