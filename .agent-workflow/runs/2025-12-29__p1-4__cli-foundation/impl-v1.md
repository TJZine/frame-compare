---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v1
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/impl-v1.md
  - src/frame_compare/cli_entry.py
  - tests/cli/test_cli_commands.py
  - tests/cli/test_exit_codes.py
---

# Implementation Report: CLI Foundation

## Summary
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v5.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `tests/cli/__init__.py` — Package marker
- `tests/cli/test_cli_commands.py` — 9 tests for CLI command availability and stub output
- `tests/cli/test_exit_codes.py` — 1 test for exception-to-exit-code mapping

### Modified
- `src/frame_compare/cli_entry.py` — Implemented Typer commands (`run`, `wizard`, `doctor`, `preset`) and `handle_error`
- `docs/DECISIONS.md` — Added record for CLI foundation
- `CHANGELOG.md` — Added CLI foundation entry

## Implementation Notes
- Added `# ruff: noqa: B008` to `src/frame_compare/cli_entry.py` to suppress standard Typer pattern warnings (`typer.Option` in defaults).
- Implemented `run` command signature exactly as specified in the plan (all 21 options).
- Implemented `doctor` command with JSON output support.
- Implemented `preset` command group with `list`, `apply`, `save`.
- Implemented `handle_error` using the `get_exit_code` SSOT from `frame_compare.errors`.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/cli_entry.py` — exit 0
- `.venv/bin/ruff check src/frame_compare/cli_entry.py` — exit 0
- `.venv/bin/pytest -v tests/cli/` — exit 0 (10 passed)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0

## Checklist Item Implemented
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Create `src/frame_compare/cli_entry.py`
- [x] Implement Typer app + commands
- [x] Add global options: `--root`, `--config`, `--quiet`, `--verbose`
- [x] Implement `run` command (stub)
- [x] Implement `wizard` command (stub)
- [x] Implement `doctor` command (stub)
- [x] Implement `preset` command group (stub)
- [x] Map exceptions to exit codes
- [x] Write CLI integration tests

## Open Questions
- None.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p1-4__cli-foundation

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md
3. Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v5.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/verify-v1.md
