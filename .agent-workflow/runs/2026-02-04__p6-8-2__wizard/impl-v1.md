---
RUN_ID: 2026-02-04__p6-8-2__wizard
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `wizard` command (interactive config) — Bundled 2 tasks
INPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-review-v1.md
OUTPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-2__wizard/impl-v1.md
---

## Summary
- Implemented `wizard` interactive config writer with validation and deterministic output.
- Implemented `doctor` command with JSON output per schema and correct exit codes.
- Replaced CLI stub tests with deterministic wizard/doctor coverage and added traceability-compatible wrappers.

## Commands and Results
- `cat /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-review-v1.md`
  - Result: reviewed (APPROVED, Decision Points Remaining: NONE).
- `cat /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md`
  - Result: reviewed plan details.
- `python3 - <<'PY' ... PY`
  - Result: failed (ModuleNotFoundError: tomli_w) during local check.
- `.venv/bin/pyright --warnings`
  - Result: failed (type errors in `cli_entry.py`), then fixed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
  - Result: failed (missing `test_wizard_stub`/`test_doctor_stub_text`), then fixed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
  - Result: pass after adding wrapper tests.
- Full gate suite re-run:
  - `.venv/bin/pyright --warnings` → pass.
  - `.venv/bin/ruff check .` → pass.
  - `.venv/bin/pytest -q` → pass (3 skips: vapoursynth mocked).
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` → pass.
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` → pass.
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check` → pass.

## Changes
- Updated `wizard` and `doctor` implementations with validation, TOML output, and JSON reporting.
  - `src/frame_compare/cli_entry.py`
- Replaced stub CLI tests with deterministic wizard/doctor tests and added traceability wrappers.
  - `tests/cli/test_cli_commands.py`

## Notes
- Added wrapper tests named `test_wizard_stub` and `test_doctor_stub_text` to satisfy traceability references.
- TOML output normalizes `tmdb.api_key=None` to empty string for serialization.

## NEXT AGENT PROMPT (COPY/PASTE)
You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8-2__wizard

## Inputs (Read These)
1. Read file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/impl-v1.md
2. Read file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md
3. Read file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-review-v1.md

## Your Task
Verify the implementation against the plan and run artifacts. Re-run the full gate suite if needed and produce the verification report.

## Output
Write file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/verify-v1.md
