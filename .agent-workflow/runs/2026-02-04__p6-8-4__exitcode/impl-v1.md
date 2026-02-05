---
RUN_ID: 2026-02-04__p6-8-4__exitcode
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Implement `ExitCode` enum per spec §3.2 — Bundled 3 tasks
INPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-review-v1.md
OUTPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-4__exitcode/impl-v1.md
---

## Summary
- Mapped exit codes by error code prefix and removed CLI magic numbers.
- Extended CLI/test coverage for generic error mapping and interrupts.

## Changes
- Updated `ExitCode` mapping to use `FC-` category prefixes in `src/frame_compare/errors.py`.
- Normalized CLI exit codes and expanded `handle_error` behavior in `src/frame_compare/cli_entry.py`.
- Added error-mapping and CLI exit-code tests in `tests/test_errors.py`, `tests/cli/test_cli_commands.py`, and `tests/cli/test_exit_codes.py`.

## Commands & Results
- `.venv/bin/pyright --warnings` — 0 errors, 0 warnings.
- `.venv/bin/ruff check .` — All checks passed.
- `.venv/bin/pytest -q` — All tests passed (3 skipped: vapoursynth mocked).
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — Contracts kept.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — Up-to-date.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check` — All references valid.

## NEXT AGENT PROMPT (COPY/PASTE)
You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8-4__exitcode

## Target
Phase 6 → Item 6.8 (Bundled) — CLI Commands — Implement `ExitCode` enum per spec §3.2 — Bundled 3 tasks

## Input Artifacts
- Read file: .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/impl-v1.md

## Your Task
Verify the implementation by running the required gates and reviewing the implementation report for completeness.

## Output
- Write file: .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/verify-v1.md
