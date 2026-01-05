---
RUN_ID: 2025-12-27__p0-4__ci-pipeline
VERSION: v2
TARGET: Phase 0 → Item 0.4 (CI/CD Pipeline)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v1.md
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v2.md
---

# Implementation Plan: CI/CD Pipeline (Phase 0.4)

> **Revision:** v2 — Addresses FAIL items from plan-review-v1.md (git prerequisite, deterministic YAML validation, explicit PR-based CI trigger)

## Context

**Phase:** 0 — Foundation
**Module:** N/A (infrastructure)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` (Phase 0.4 section)
**Dependencies:** Phase 0.1-0.3 complete (pyproject.toml, src/frame_compare/, tests/ exist)

## Scope

This plan covers:

- [x] Create `.github/workflows/ci.yml` with:
  - [x] Lint stage (Ruff)
  - [x] Type check stage (Pyright)
  - [x] Test stage (pytest)
  - [x] Python 3.13 matrix
- [x] Verify CI passes on pull request

This plan does NOT cover:

- Container E2E testing (Phase 0.5)
- Docker build (Phase 0.5)
- Branch protection rules (GitHub UI config, not code)
- Contract/traceability gates (will be added in Phase 1)
- Direct push to `main` (orchestrator action only, not part of this plan)

## Contract Impact

**Contracts touched:** NO

---

## Rollback / Stop Conditions

> [!CAUTION]
> If any verification command fails, **do not patch around it**. Return to Planning Agent for a plan revision.

**Stop conditions:**

1. CI job fails on PR → Diagnose and fix the specific job locally, then push fixes
2. YAML syntax error detected by CI → Fix file structure locally, push again
3. Any linting/type-check/test jobs that pass locally but fail in CI → Check for environment differences

**Prerequisite checks (before starting):**

- `git --version` must succeed (git must be installed)
- `uv --version` must succeed (uv must be installed)
- `.github/workflows/` directory exists (it does — contains `pr-title.yml`, `release-please.yml`)
- `pyproject.toml` exists with dev dependencies
- `uv.lock` exists

If prerequisites fail, **STOP** and escalate to orchestrator.

---

## Files to Create/Modify

### 1. `.github/workflows/ci.yml` [NEW]

**Purpose:** Main CI workflow for linting, type checking, and testing on every push and PR.

**Content (exact):**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

env:
  UV_CACHE_DIR: .uv_cache
  PYTHON_VERSION: "3.13"

jobs:
  lint:
    name: Lint (Ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: uv sync --group dev --frozen

      - name: Run Ruff
        run: uv run --no-sync ruff check .

  typecheck:
    name: Type Check (Pyright)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: uv sync --group dev --frozen

      - name: Run Pyright
        run: uv run --no-sync pyright --warnings

  test:
    name: Test (pytest)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: uv sync --group dev --frozen

      - name: Run pytest
        run: uv run --no-sync pytest -q

  # All jobs must pass for PR merge
  ci-pass:
    name: CI Pass
    runs-on: ubuntu-latest
    needs: [lint, typecheck, test]
    if: always()
    steps:
      - name: Check all jobs passed
        run: |
          if [[ "${{ needs.lint.result }}" != "success" ]] || \
             [[ "${{ needs.typecheck.result }}" != "success" ]] || \
             [[ "${{ needs.test.result }}" != "success" ]]; then
            echo "One or more CI jobs failed"
            exit 1
          fi
          echo "All CI jobs passed"
```

---

### 2. `pyproject.toml` [MODIFY]

**Purpose:** Add `pyyaml` to dev dependencies for local YAML syntax validation.

**Change:** In the `[dependency-groups]` section, add `pyyaml>=6.0` to the `dev` list:

```toml
[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-mock>=3.14.0",
    "pytest-cov>=6.0.0",
    "pyright>=1.1.390",
    "ruff>=0.8.0",
    "respx>=0.22.0",
    "pyyaml>=6.0",
]
```

**Note:** After modifying `pyproject.toml`, run `uv sync --group dev` to update `uv.lock`.

---

### 3. `CHANGELOG.md` [MODIFY]

**Purpose:** Document CI/CD additions.

**Content to add under `[Unreleased]` → `### Added`:**

```markdown
- **CI/CD Pipeline:** GitHub Actions workflow with Ruff linting, Pyright type checking, and pytest stages.
```

---

### 4. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Document CI/CD decisions.

**Content to append (new section):**

> [!IMPORTANT]
> Before writing, run `date -u +%Y-%m-%d` and use that value to replace `<UTC_DATE>` in the heading below.

```markdown
---

## <UTC_DATE> — Phase 0.4 CI/CD Decisions

### CI Runner: ubuntu-latest

**Context:** Need a CI environment for Python 3.13 testing.

**Decision:** Use `ubuntu-latest` for all CI jobs.

**Rationale:**
- Most common CI environment
- Good Python 3.13 support
- Fast job startup

---

### Package Manager in CI: uv

**Context:** Need reproducible dependency installation in CI.

**Decision:** Use `uv` with `--frozen` flag in CI.

**Rationale:**
- Same tooling as local development
- Lockfile ensures reproducibility
- Fast installs via caching

---

### CI Job Structure: Parallel Independent Jobs

**Context:** Need efficient CI while maintaining clear failure signals.

**Decision:** Run lint, typecheck, and test as parallel independent jobs with a final aggregation job.

**Rationale:**
- Parallel execution reduces total CI time
- Independent failures are immediately visible
- `ci-pass` job provides single status check for branch protection
```

---

## Acceptance Criteria

- [ ] **AC-1:** GIVEN `.github/workflows/ci.yml` exists WHEN a PR is opened targeting `main` THEN the CI workflow triggers (evidenced by a GitHub Actions run appearing)
- [ ] **AC-2:** GIVEN the CI workflow runs WHEN `lint` job executes THEN Ruff checks pass (exit 0, green check)
- [ ] **AC-3:** GIVEN the CI workflow runs WHEN `typecheck` job executes THEN Pyright checks pass (exit 0, green check)
- [ ] **AC-4:** GIVEN the CI workflow runs WHEN `test` job executes THEN pytest runs and passes (exit 0, green check)
- [ ] **AC-5:** GIVEN all jobs pass WHEN `ci-pass` job runs THEN it succeeds (green check)
- [ ] **AC-6:** GIVEN the workflow file WHEN CI attempts to parse it THEN no YAML syntax errors occur (CI run is created successfully)

---

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

**Single deterministic flow (execute in order):**

```bash
# ─── Step 0: Prerequisites ───────────────────────────────────────────────────
git --version
# Pass criteria: exit 0

uv --version
# Pass criteria: exit 0

# Verify workflow directory exists
ls .github/workflows/
# Pass criteria: shows existing workflow files (pr-title.yml, release-please.yml)

# ─── Step 1a: Sync dependencies (after pyproject.toml change) ────────────────
uv sync --group dev
# Pass criteria: exit 0, uv.lock updated

git add uv.lock
uv sync --group dev --frozen
# Pass criteria: exit 0

git diff --exit-code -- uv.lock
# Pass criteria: exit 0 (lockfile stable)

# ─── Step 1b: Validate YAML syntax (mandatory) ───────────────────────────────
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
# Pass criteria: exit 0 (no exception = valid YAML syntax)

# ─── Step 2: Verify local tools still pass ───────────────────────────────────
.venv/bin/ruff check .
# Pass criteria: exit 0

.venv/bin/pyright --warnings
# Pass criteria: exit 0

.venv/bin/pytest -q
# Pass criteria: exit 0

# ─── Step 3: Run-artifact hygiene validators ─────────────────────────────────
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-27__p0-4__ci-pipeline
# Pass criteria: exit 0

UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline
# Pass criteria: exit 0

# ─── Step 4: Create branch and push ──────────────────────────────────────────
git checkout -b ci/add-ci-workflow
# Pass criteria: exit 0

git add .github/workflows/ci.yml CHANGELOG.md docs/DECISIONS.md
git commit -m "ci: add CI workflow with lint, typecheck, and test stages"
# Pass criteria: exit 0

git push origin ci/add-ci-workflow
# Pass criteria: exit 0

# ─── Step 5: Open PR and verify CI ───────────────────────────────────────────
# Open a PR from ci/add-ci-workflow → main via GitHub UI or CLI:
gh pr create --title "ci: add CI workflow" --body "Adds lint, typecheck, test CI jobs" --base main
# Pass criteria: PR is created

# Wait for CI to complete and verify:
# - GitHub Actions shows a run was triggered (AC-6: no YAML syntax errors)
# - lint job: green check (AC-2)
# - typecheck job: green check (AC-3)
# - test job: green check (AC-4)
# - ci-pass job: green check (AC-5)

# ─── Step 6: Merge (orchestrator action) ─────────────────────────────────────
# NOTE: Merge is an orchestrator action, not part of Coding Agent scope.
# Once all checks pass, orchestrator merges the PR.
```

**Overall pass criteria:** All local verification commands exit 0, PR is created, and GitHub Actions shows all 4 jobs green (lint ✓, typecheck ✓, test ✓, ci-pass ✓).

---

## Notes for Coding Agent

1. **Use exact content:** The workflow YAML content is exact — copy it verbatim.

2. **YAML indentation:** YAML is indentation-sensitive. Ensure 2-space indentation throughout.

3. **uv action:** Uses `astral-sh/setup-uv@v4` which is the official uv GitHub Action.

4. **Python version:** Uses `uv python install` to install Python 3.13 via uv's Python management.

5. **Frozen installs:** CI uses `--frozen` to ensure lockfile is respected. If lockfile is out of date, CI will fail (by design).

6. **Cache directory:** `UV_CACHE_DIR` is set as an env var to ensure consistent caching behavior.

7. **ci-pass job:** This aggregation job allows branch protection rules to require a single "CI Pass" status check rather than listing each individual job.

8. **No E2E or Docker:** E2E tests requiring Docker are out of scope for this run (Phase 0.5).

9. **CHANGELOG/DECISIONS updates:** Follow same patterns as previous run — append to existing sections.

10. **Mandatory YAML validation:** Local YAML syntax validation uses `pyyaml` (added to dev deps). Run `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` — must exit 0.

11. **Branch name:** Use exactly `ci/add-ci-workflow` for the feature branch.

12. **PR-based verification:** Do NOT push directly to `main`. Create a PR to trigger the `pull_request` event and verify CI.

13. **gh CLI:** If `gh` CLI is not installed, create the PR via GitHub web UI instead. The key is that a PR targeting `main` is opened to trigger CI.

14. **Merge is out of scope:** The Coding Agent does not merge the PR. Once CI is green, the orchestrator or Verification Agent handles merge.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-4__ci-pipeline

## Plan to Review

Read file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-review-v2.md
