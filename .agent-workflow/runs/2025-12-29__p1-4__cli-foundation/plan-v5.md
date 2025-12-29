---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v5
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v4.md
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md
---

# Implementation Plan: CLI Foundation

## Changes Since plan-v4

1. **Complete Signatures:** `run()` and `doctor()` now include full parameter lists with `typer.Option(...)` defaults (no ellipses).

## Context

**Phase:** 1
**Module:** `frame_compare.cli_entry`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
**Dependencies:** Phase 1.1 ✅, Phase 1.2 ✅, Phase 1.3 ✅

## Scope

- [ ] Extend `src/frame_compare/cli_entry.py` with commands: `run`, `wizard`, `doctor`, `preset list|apply|save`
- [ ] Import and use `get_exit_code()` from `frame_compare.errors`
- [ ] Implement `handle_error()`
- [ ] Write CLI unit tests in `tests/cli/`

Out of scope: Full pipeline execution, wizard UI, doctor checks, runner.py, orchestration/.

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

## Public API Signatures (spec-anchored, complete)

**Existing (unchanged, do NOT modify):**

The existing `main()` and `version()` in cli_entry.py are not part of this implementation.

**New (implement per SSOT):**

- `run(root: Path = typer.Option(".", "--root", "-r"), config: Path | None = typer.Option(None, "--config", "-c"), input_dir: Path | None = typer.Option(None, "--input", "-i"), no_cache: bool = typer.Option(False, "--no-cache"), from_cache_only: bool = typer.Option(False, "--from-cache-only"), no_upload: bool = typer.Option(False, "--no-upload"), tm_preset: str | None = typer.Option(None, "--tm-preset"), tm_target: int | None = typer.Option(None, "--tm-target"), tm_curve: str | None = typer.Option(None, "--tm-curve"), frame_count: int | None = typer.Option(None, "--frame-count", "-n"), seed: int | None = typer.Option(None, "--seed"), overlay: str | None = typer.Option(None, "--overlay"), skip_analysis: bool = typer.Option(False, "--skip-analysis"), skip_metadata: bool = typer.Option(False, "--skip-metadata"), skip_dovi: bool = typer.Option(False, "--skip-dovi"), json_output: bool = typer.Option(False, "--json"), no_color: bool = typer.Option(False, "--no-color"), write_config: bool = typer.Option(False, "--write-config"), diagnose_paths: bool = typer.Option(False, "--diagnose-paths"), quiet: bool = typer.Option(False, "--quiet", "-q"), verbose: bool = typer.Option(False, "--verbose", "-v")) -> None`
- `wizard() -> None`
- `doctor(json_output: bool = typer.Option(False, "--json")) -> None`
- `preset_list() -> None`
- `preset_apply(name: str) -> None`
- `preset_save(name: str) -> None`
- `handle_error(error: FrameCompareError) -> int`

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py` (MODIFY)

**Exit Code Source of Truth:**

```python
from frame_compare.errors import get_exit_code, FrameCompareError
```

**Stub Output Contracts:**

| Command | Output (stdout) | Exit |
|---------|-----------------|------|
| `run` (no args) | `"[stub] run: Not yet implemented\n"` | 0 |
| `wizard` | `"[stub] wizard: Not yet implemented\n"` | 0 |
| `doctor` | `"[stub] doctor: Not yet implemented\n"` | 0 |
| `doctor --json` | `{"status": "stub", "checks": []}\n` | 0 |
| `preset list` | `"[stub] preset list: Not yet implemented\n"` | 0 |
| `preset apply <n>` | `"[stub] preset apply: Not yet implemented\n"` | 0 |
| `preset save <n>` | `"[stub] preset save: Not yet implemented\n"` | 0 |

**Typer Sub-App Pattern for Presets:**

```python
preset_app = typer.Typer(name="preset", help="Manage configuration presets.", no_args_is_help=True)
app.add_typer(preset_app, name="preset")
```

### 2. `tests/cli/test_cli_commands.py` (NEW)

**Tests:** `test_app_help_lists_all_commands`, `test_run_help_shows_all_options`, `test_run_stub_executes`, `test_wizard_stub`, `test_doctor_stub_text`, `test_doctor_stub_json`, `test_preset_list_stub`, `test_preset_apply_stub`, `test_preset_save_stub`

**Full SSOT Option Flags for `test_run_help_shows_all_options`:**

```python
REQUIRED_RUN_OPTIONS = ["--root", "-r", "--config", "-c", "--input", "-i", "--no-cache", "--from-cache-only", "--no-upload", "--tm-preset", "--tm-target", "--tm-curve", "--frame-count", "-n", "--seed", "--overlay", "--skip-analysis", "--skip-metadata", "--skip-dovi", "--json", "--no-color", "--write-config", "--diagnose-paths", "--quiet", "-q", "--verbose", "-v"]
```

### 3. `tests/cli/test_exit_codes.py` (NEW)

**SSOT Exception Constructors:**

| Error | Constructor | Exit |
|-------|-------------|------|
| Config | `ConfigNotFoundError(Path("/x"))` | 2 |
| Dependency | `VapourSynthNotFoundError()` | 3 |
| Input | `NoVideosFoundError(Path("/x"), patterns=["*.mkv"])` | 4 |
| Processing | `FrameExtractionError(frame=0, clip=Path("/x"))` | 5 |
| Network | `SlowpicsError("x")` | 6 |
| Internal | `GenericInternalError("x")` | 1 |

### 4. `tests/cli/__init__.py` (NEW)

Empty marker file.

### 5. `docs/DECISIONS.md` (MODIFY)

Record RUN_ID, SSOT edits, exit code source of truth.

### 6. `CHANGELOG.md` (MODIFY)

Under `## [Unreleased]`, add CLI foundation + exit code mapping entry.

## Acceptance Criteria

- [ ] `frame-compare --help` lists: run, wizard, doctor, preset, version
- [ ] `frame-compare run --help` contains all 21 option flags
- [ ] `frame-compare run` outputs stub message, exits 0
- [ ] `frame-compare doctor --json` outputs valid JSON, exits 0
- [ ] `handle_error(ConfigNotFoundError(...))` returns 2
- [ ] `handle_error(SlowpicsError(...))` returns 6

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/cli_entry.py
.venv/bin/ruff check src/frame_compare/cli_entry.py
.venv/bin/pytest -v tests/cli/
.venv/bin/pytest -v tests/e2e/test_cli_version.py
.venv/bin/pyright --warnings
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All exit 0.

## Notes for Coding Agent

1. **Existing stub:** Extend cli_entry.py; do NOT modify `main()` or `version()`.
2. **handle_error per SSOT:**

   ```python
   def handle_error(error: FrameCompareError) -> int:
       console = Console(stderr=True)
       console.print(f"[red]Error[/red] [{error.code}]: {error.context.message}")
       if error.hint:
           console.print(f"[yellow]Hint:[/yellow] {error.hint}")
       return int(get_exit_code(error))
   ```

3. **Rollback:** If Typer behavior diverges from SSOT, STOP and return to Planning.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p1-4__cli-foundation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v5.md
