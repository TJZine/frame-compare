---
RUN_ID: 2026-02-02__p6-7-8__runner
VERSION: v7
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Create `src/frame_compare/runner.py` at package root (see `cli-module.md` §1.2)
INPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v2.md
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v2.md
OUTPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-02__p6-7-8__runner/impl-v7.md
---

# Implementation Report: runner.py Package-Root Scaffold

## Summary
- No code changes in this attempt.
- All required gates passed.

## Verification

- `.venv/bin/pyright --warnings`
  - Result: `0 errors, 0 warnings, 0 informations`
- `.venv/bin/ruff check .`
  - Result: `All checks passed!`
- `.venv/bin/pytest -q`
  - Result: `395 passed, 2 skipped`
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
  - Result: `Contracts: 2 kept, 0 broken.`
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
  - Result: `OK: All derived files are up-to-date`
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
  - Result: `✅ All traceability references valid`

## NEXT AGENT PROMPT (COPY/PASTE)
You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-8__runner

## Files to Review
- `.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v2.md`
- `.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v2.md`
- `.agent-workflow/runs/2026-02-02__p6-7-8__runner/impl-v7.md`

## Verification Tasks
1. Confirm the implementation matches the plan exactly (no extra scope).
2. Verify `importlinter.ini` layering includes `frame_compare.runner` immediately after `frame_compare.cli_entry`.
3. Verify `src/frame_compare/runner.py` re-exports `RunRequest`, `RunResult`, `RunDependencies` and exposes `run(...)` that raises `NotImplementedError` with the exact scaffold message.
4. Verify `tests/test_runner_import_smoke.py` contains the two required smoke tests and the regex match for the scaffold message.
5. Re-run the full verification command suite and confirm exit code 0:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

## Output
Write verification report to:
`.agent-workflow/runs/2026-02-02__p6-7-8__runner/verify-v7.md`
