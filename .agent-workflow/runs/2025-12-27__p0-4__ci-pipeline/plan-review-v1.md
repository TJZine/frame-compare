---
RUN_ID: 2025-12-27__p0-4__ci-pipeline
VERSION: v1
TARGET: Phase 0 → Item 0.4 (CI/CD Pipeline)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-review-v1.md
---

# Plan Review Report: CI/CD Pipeline (Phase 0.4)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-28
**Plan Reference:** .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 0.4) with clear out-of-scope items. |
| 2 | Dependencies | FAIL | Local verification requires `git` and (optionally) `PyYAML`, but prerequisites do not declare either as required tooling/deps. |
| 3 | File List | PASS | File list is explicit (workflow + CHANGELOG + DECISIONS). |
| 4 | Contract Impact | PASS | Explicit “NO”; no contract gates required. |
| 5 | Types Complete | PASS | N/A for YAML/docs changes; no typed APIs introduced. |
| 6 | Tests Complete | PASS | No new tests required for this slice; plan explicitly runs `.venv/bin/pytest -q` as part of verification. |
| 7 | Verification Complete | FAIL | Verification includes conditional/optional steps (“skip if PyYAML not available”) and the CI verification step is ambiguous about how CI is triggered (workflow only triggers on `push` to `main` and `pull_request` targeting `main`). |
| 8 | Decision-Minimizing | FAIL | Implementation agent must decide how to validate YAML without PyYAML and whether to push to `main` vs open a PR (and how to trigger CI deterministically). |
| 9 | Determinism Defined | N/A | No randomness. |

## Additional Quality Checks

- Error Codes: OK (no new errors)
- Failure Modes: Issue — “PyYAML missing” path says “skip”; must be replaced with a deterministic check path.
- Derived Outputs: OK (none)
- Rollback Guidance: OK (stop conditions present)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Whether/how to validate YAML syntax locally without adding new dependencies.
2. Whether to verify CI by pushing to `main` or by opening a PR, and the exact trigger path consistent with the workflow `on:` config.

## Concrete Edits Required (for plan-v2.md)

1. **Make local YAML verification deterministic (no optional “skip”)**
   - Section: `Verification Commands`, `Acceptance Criteria` (AC-6)
   - Problem: `python -c "import yaml ..."` depends on PyYAML which is not guaranteed installed; the plan allows skipping, violating “verification-complete”.
   - Required Change (pick ONE and specify it as the only path; no alternatives):
     - Option A (recommended, no new deps): Remove local YAML-parse validation and redefine AC-6 as: “CI workflow triggers successfully (no YAML syntax errors), evidenced by a GitHub Actions run being created.” Local step becomes a simple file existence/readability check only (deterministic).
     - Option B (adds deps): Add `pyyaml>=6.0` to the dev dependency group in `pyproject.toml` (this requires explicitly listing the `pyproject.toml` modification in this plan’s file list).

2. **Make CI trigger/verification unambiguous and safe**
   - Section: `CI verification (after push)` + `Acceptance Criteria` (AC-1)
   - Problem: Plan suggests pushing to `main` or “push to a branch and open PR”, but `push` triggers only for `main`; branch pushes alone will not trigger CI.
   - Required Change: Specify the exact verification flow:
     - Create a branch (exact name), push it, open a PR targeting `main` to trigger `pull_request`, and verify checks are green.
     - Remove/forbid “push directly to main” in the plan (treat as out-of-scope / orchestrator-only action).

3. **Declare required tooling for verification**
   - Section: `Prerequisite checks (before starting)` + `Verification Commands`
   - Problem: Verification uses `git` commands but prerequisites do not require `git`.
   - Required Change: Add `git --version` to prerequisites (and keep `uv.lock` precondition as-is).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-4__ci-pipeline

## Revision Required
Read file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-review-v1.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v1.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v2.md

