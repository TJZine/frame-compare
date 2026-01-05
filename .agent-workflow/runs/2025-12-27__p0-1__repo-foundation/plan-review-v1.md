---
RUN_ID: 2025-12-27__p0-1__repo-foundation
VERSION: v1
TARGET: Phase 0 → Items 0.1-0.3 (Repository Setup, Project Structure, Development Tooling)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v1.md
---

# Plan Review Report: Repository Foundation (Phase 0.1-0.3)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-27
**Plan Reference:** .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Scope is explicitly Phase 0.1–0.3 with a clear out-of-scope list. |
| 2 | Dependencies | PASS | External tools/libraries are listed; no internal module dependencies for this slice. |
| 3 | File List | FAIL | Missing required run documentation updates (`CHANGELOG.md`, `docs/DECISIONS.md`) per repo workflow; file list must be complete and explicit for this run. |
| 4 | Contract Impact | PASS | Explicitly “NO”; no regen gates required. |
| 5 | Types Complete | PASS | All provided Python stubs include concrete signatures and avoid `Any`. |
| 6 | Tests Complete | FAIL | Plan relies on “empty suite OK” but does not define any tests for the only implemented behavior (`frame-compare version`); requires at least one deterministic test with exact name + assertions. |
| 7 | Verification Complete | FAIL | Verification commands deviate from `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` Command Canon (SSOT) and omit required run-directory hygiene validators. |
| 8 | Decision-Minimizing | PASS | File contents are exact; conditional `.gitignore` append rules are sufficiently constrained. |
| 9 | Determinism Defined | N/A | No randomness in this slice. |

## Additional Quality Checks

- Error Codes: OK (no new errors in scope)
- Failure Modes: Issue — plan should define what happens if required tooling is missing (e.g., `uv` unavailable / Python < 3.13): stop with a clear failure and return to Planning.
- Derived Outputs: OK (no derived contract artifacts)
- Rollback Guidance: Issue — missing explicit “stop/rollback” guidance if any gate fails (return to Planning rather than ad-hoc changes).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. What exact entries to add (or files to create) for `CHANGELOG.md` and `docs/DECISIONS.md` for this run.
2. Whether to add a smoke test for the `version` CLI command; if so, exact file path/name and assertions.
3. Which exact command variants to run to comply with the Command Canon (SSOT), including use of `--frozen`, `-q`, and the run-artifact validators.

## Concrete Edits Required (for plan-v2.md)

1. **Add required run documentation outputs**
   - Section: `Files to Create/Modify`
   - Problem: Plan omits required run “persist” artifacts (repo workflow requires a changelog + decisions log per run).
   - Required Change: Add these files with exact content:
     - `CHANGELOG.md` [NEW] — include an “Unreleased” section and an entry describing Phase 0 foundation scaffolding/tooling.
     - `docs/DECISIONS.md` [NEW] — include a dated entry (use UTC date at implementation time) capturing key decisions (Python 3.13 requirement, toolchain choices, strict type checking, dependency baselines).

2. **Add at least one deterministic test for implemented behavior**
   - Section: `Files to Create/Modify` + `Acceptance Criteria`
   - Problem: Plan adds a CLI command (`version`) but provides no tests (violates “Test-complete” requirement for this plan-review gate).
   - Required Change: Specify one test file with exact name and assertions, for example:
     - `tests/e2e/test_cli_version.py` [NEW]
       - Uses `typer.testing.CliRunner()` to invoke `frame_compare.cli_entry:app` with args `["version"]`
       - Asserts `exit_code == 0`
       - Asserts output equals exactly `frame-compare 0.1.0` (including trailing newline handling rules explicitly)

3. **Align verification commands with Command Canon (SSOT) and include run-directory hygiene validators**
   - Section: `Verification Commands`
   - Problem: Uses `uv sync --group dev` (missing `--frozen`), uses `.venv/bin/pytest` without `-q`, and omits required validators from `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`.
   - Required Change: Update verification to:
     - Bootstrap: `uv sync --group dev --frozen`
     - Tooling: `.venv/bin/pyright --warnings`, `.venv/bin/ruff check .`, `.venv/bin/pytest -q`
     - Run-artifact hygiene:
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-27__p0-1__repo-foundation`
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-27__p0-1__repo-foundation`
     - CLI check: prefer `UV_CACHE_DIR=./.uv_cache uv run --no-sync frame-compare version`
     - Pass criteria must be explicit per-command (exit 0, and for `version` exact stdout match).

4. **Add explicit stop/rollback guidance**
   - Section: Add a `Rollback / Stop Conditions` section
   - Problem: Plan lacks an explicit instruction to stop and return to Planning if any gate fails or if repo state differs materially from assumptions.
   - Required Change: Add a short section stating: if any verification command fails, do not patch around it; return to Planning for a plan revision.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-1__repo-foundation

## Revision Required
Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v1.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v1.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v2.md
