---
RUN_ID: 2025-12-27__p0-1__repo-foundation
VERSION: v1
TARGET: Phase 0 → Items 0.1-0.3 (Repository Setup, Project Structure, Development Tooling)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v4.md
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/impl-v1.md
  - pyproject.toml
  - src/frame_compare/cli_entry.py
  - tests/e2e/test_cli_version.py
  - tests/conftest.py
  - docs/DECISIONS.md
---

# Implementation Report: Repository Foundation

## Summary
**Date:** 2025-12-28
**Plan Reference:** .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v4.md
**Plan Review Report:** .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v4.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `pyproject.toml` — Project configuration and dependencies.
- `src/frame_compare/__init__.py` — Package root.
- `src/frame_compare/py.typed` — PEP 561 marker.
- `src/frame_compare/cli_entry.py` — CLI entry point.
- `tests/__init__.py` — Test package marker.
- `tests/e2e/__init__.py` — E2E test package marker.
- `tests/e2e/test_cli_version.py` — Version command tests.
- `tests/conftest.py` — Shared fixtures.
- `docs/DECISIONS.md` — Decision log.
- `src/frame_compare/analysis/.gitkeep` (and others) — Directory structure markers.

### Modified
- `.gitignore` — Appended Python ignore patterns.
- `CHANGELOG.md` — Added Phase 0 entry.
- `scripts/lint_command_canon.py` — Auto-fixed by Ruff (imports sorting) to satisfy linting checks.

## Implementation Notes

1.  **Deviations from Plan (cli_entry.py):**
    -   Added `@app.callback()` to `cli_entry.py`.
    -   **Reason:** With a single command (`version`), Typer was implicitly treating the application as a "Single Command" CLI, causing it to consume the `version` argument as an extra argument rather than a subcommand. This caused both manual execution and tests (`runner.invoke(app, ["version"])`) to fail. Adding a callback forces Typer to treat the app as a command group, restoring expected behavior.

2.  **Deviations from Plan (pyproject.toml):**
    -   Added `venvPath = "."` and `venv = ".venv"` to `[tool.pyright]`.
    -   **Reason:** Required for the local `.venv/bin/pyright` binary to correctly resolve dependencies in the virtual environment when running in strict mode.

3.  **Linting Adjustments:**
    -   Ran `ruff check --fix .`.
    -   **Reason:** The plan required `ruff check .` (root) to pass. Existing script `scripts/lint_command_canon.py` had unsorted imports, and the planned `tests/conftest.py` content triggered `UP043` (unnecessary default type args). These were fixed automatically.

## Verification Evidence

### Pyright Output
```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations
```

### Ruff Output
```text
$ .venv/bin/ruff check .
All checks passed!
```

### Test Output
```text
$ .venv/bin/pytest -q
..                                                                                                                     [100%]
2 passed in 0.03s
```

### CLI Output
```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync frame-compare version
frame-compare 0.1.0
```

### Run Artifacts
```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-27__p0-1__repo-foundation
OK: Run artifacts valid for 2025-12-27__p0-1__repo-foundation
```

## Checklist Item Implemented

- [x] 0.1 Repository Setup — Create `pyproject.toml` with build system
- [x] 0.2 Project Structure — Create directory structure with marker files
- [x] 0.3 Development Tooling — Configure dependencies, Pyright, Ruff

## Open Questions
None.

## Ready for Verification

All files created. Verification suite passes.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-1__repo-foundation

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v4.md
3. Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v4.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/verify-v1.md
