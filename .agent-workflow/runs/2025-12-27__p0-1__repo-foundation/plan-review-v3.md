---
RUN_ID: 2025-12-27__p0-1__repo-foundation
VERSION: v3
TARGET: Phase 0 → Items 0.1-0.3 (Repository Setup, Project Structure, Development Tooling)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v3.md
---

# Plan Review Report: Repository Foundation (Phase 0.1-0.3)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-28
**Plan Reference:** .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Scope is explicitly Phase 0.1–0.3 with a clear out-of-scope list. |
| 2 | Dependencies | FAIL | Verification requires `git` but it is not listed as a prerequisite/tool dependency; additionally, `uv sync --group dev` implies dependency-groups support but `pyproject.toml` uses `project.optional-dependencies` instead. |
| 3 | File List | PASS | File list is explicit and now includes `uv.lock` as generated output. |
| 4 | Contract Impact | PASS | Explicit “NO”; no contract regen gates required. |
| 5 | Types Complete | PASS | Public signatures are concrete and typed; no `Any` introduced. |
| 6 | Tests Complete | PASS | Exact test file and assertions for `version` are specified (deterministic). |
| 7 | Verification Complete | FAIL | Lockfile stability check is not valid: `git status --porcelain uv.lock` cannot detect lockfile changes when `uv.lock` is untracked; pass criteria also doesn’t handle reruns where `uv.lock` is already committed (empty output). |
| 8 | Decision-Minimizing | FAIL | Coding Agent must decide how to make `uv sync --group dev` actually install dev deps (dependency groups vs extras) and how to robustly validate lockfile stability. |
| 9 | Determinism Defined | N/A | No randomness in this slice. |

## Additional Quality Checks

- Error Codes: OK (no new errors in scope)
- Failure Modes: OK (stop conditions are explicit)
- Derived Outputs: Issue — `uv.lock` is correctly treated as generated, but verification must treat it as tracked to validate stability.
- Rollback Guidance: OK

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Whether to implement dev dependencies as dependency groups or extras (must match `uv sync --group dev`).
2. How to validate `uv.lock` stability without relying on an untracked-file status check.

## Concrete Edits Required (for plan-v4.md)

1. **Make `uv sync --group dev` compatible with `pyproject.toml`**
   - Section: `pyproject.toml` content + `Verification Commands` + `Acceptance Criteria`
   - Problem: `uv sync --group dev` expects a `dev` dependency group, but the plan defines dev deps under `[project.optional-dependencies] dev = [...]` (extras).
   - Required Change: Replace the extras-based dev list with a dependency group. Specify the exact TOML change:
     - Remove the entire `[project.optional-dependencies]` table.
     - Add:
       ```toml
       [dependency-groups]
       dev = [
           "pytest>=8.3.0",
           "pytest-mock>=3.14.0",
           "pytest-cov>=6.0.0",
           "pyright>=1.1.390",
           "ruff>=0.8.0",
           "respx>=0.22.0",
       ]
       ```
     - Keep verification commands using `uv sync --group dev` / `--frozen` unchanged afterward.

2. **Add explicit Git prerequisites and deterministic init**
   - Section: `Prerequisite checks` + `Verification Commands`
   - Problem: Verification uses `git` but prerequisites only mention `uv` and `python`.
   - Required Change: Add `git --version` as a prerequisite and add `git init` as an explicit Step 0 command (safe/idempotent) so subsequent git-based checks always run.

3. **Replace the lockfile stability check with a tracked-file diff check**
   - Section: `Verification Commands` + `Acceptance Criteria`
   - Problem: Current check cannot detect changes to an untracked `uv.lock` and does not define rerun behavior.
   - Required Change: Specify one exact check sequence (no conditionals):
     1) `uv sync --group dev`
     2) `git add uv.lock`
     3) `uv sync --group dev --frozen`
     4) `git diff --exit-code -- uv.lock`
        - Pass criteria: exit 0 (no diff). This works whether `uv.lock` is new, staged, or already committed.
     - Update AC-2 accordingly (use `git diff --exit-code -- uv.lock` rather than `git status` semantics).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-1__repo-foundation

## Revision Required
Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v3.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v3.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v4.md
