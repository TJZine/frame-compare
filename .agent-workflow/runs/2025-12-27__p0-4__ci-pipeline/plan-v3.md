---
RUN_ID: 2025-12-27__p0-4__ci-pipeline
VERSION: v3
TARGET: Phase 0 → Item 0.4 (CI/CD Pipeline)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v2.md
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v3.md
---

# Implementation Plan: CI/CD Pipeline (Phase 0.4)

> **Revision:** v3 — Addresses FAIL items from plan-review-v2.md (uv.lock as output, pyyaml idempotency, .venv prerequisite, PR creation as orchestrator action)

## Context

**Phase:** 0 — Foundation
**Module:** N/A (infrastructure)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` (Phase 0.4 section)
**Dependencies:** Phase 0.1-0.3 complete (pyproject.toml, src/frame_compare/, tests/, .venv/ exist)

## Scope

This plan covers:

- [x] Create `.github/workflows/ci.yml` with:
  - [x] Lint stage (Ruff)
  - [x] Type check stage (Pyright)
  - [x] Test stage (pytest)
  - [x] Python 3.13 matrix
- [x] Push branch for CI verification (orchestrator opens PR)

This plan does NOT cover:

- Container E2E testing (Phase 0.5)
- Docker build (Phase 0.5)
- Branch protection rules (GitHub UI config, not code)
- Contract/traceability gates (will be added in Phase 1)
- Direct push to `main` (orchestrator action only)
- PR creation and merge (orchestrator actions only)

## Contract Impact

**Contracts touched:** NO

---

## Rollback / Stop Conditions

> [!CAUTION]
> If any verification command fails, **do not patch around it**. Return to Planning Agent for a plan revision.

**Stop conditions:**

1. YAML syntax validation fails → Fix workflow file locally
2. CI job fails on PR → Diagnose and fix the specific job locally, then push fixes
3. Any linting/type-check/test jobs that pass locally but fail in CI → Check for environment differences

**Prerequisite checks (before starting):**

- `git --version` must succeed (git must be installed)
- `uv --version` must succeed (uv must be installed)
- `.venv/` directory must exist (run `uv sync --group dev` if missing)
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

**Idempotency rule:** Ensure exactly one `"pyyaml>=6.0"` entry exists in `[dependency-groups].dev`. If already present at `>=6.0` or higher, do not modify. Do not duplicate the entry.

**Change:** In the `[dependency-groups]` section, add `"pyyaml>=6.0"` to the `dev` list (if not already present):

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

---

### 3. `uv.lock` [MODIFY | GENERATED]

**Purpose:** Updated lockfile reflecting the new `pyyaml` dependency.

**Content:** Generated by `uv sync --group dev`. Do not edit by hand. Commit the resulting change.

---

### 4. `CHANGELOG.md` [MODIFY]

**Purpose:** Document CI/CD additions.

**Content to add under `[Unreleased]` → `### Added`:**

```markdown
- **CI/CD Pipeline:** GitHub Actions workflow with Ruff linting, Pyright type checking, and pytest stages.
```

---

### 5. `docs/DECISIONS.md` [MODIFY]

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
- [ ] **AC-6:** GIVEN the workflow file WHEN `.venv/bin/python -c "import yaml; yaml.safe_load(...)"` is run THEN exit 0 (valid YAML syntax)
- [ ] **AC-7:** GIVEN `uv.lock` is updated WHEN `uv sync --group dev --frozen` is run THEN exit 0 and `git diff --exit-code -- uv.lock` passes

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

# Verify .venv exists (required for YAML validation)
ls .venv/bin/python
# Pass criteria: exit 0, file exists

# Verify workflow directory exists
ls .github/workflows/
# Pass criteria: shows existing workflow files (pr-title.yml, release-please.yml)

# ─── Step 1: Sync dependencies (after pyproject.toml change) ─────────────────
uv sync --group dev
# Pass criteria: exit 0, uv.lock updated

git add uv.lock
uv sync --group dev --frozen
# Pass criteria: exit 0

git diff --exit-code -- uv.lock
# Pass criteria: exit 0 (lockfile stable)

# ─── Step 2: Validate YAML syntax (mandatory) ────────────────────────────────
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
# Pass criteria: exit 0 (no exception = valid YAML syntax)

# ─── Step 3: Verify local tools still pass ───────────────────────────────────
.venv/bin/ruff check .
# Pass criteria: exit 0

.venv/bin/pyright --warnings
# Pass criteria: exit 0

.venv/bin/pytest -q
# Pass criteria: exit 0

# ─── Step 4: Run-artifact hygiene validators ─────────────────────────────────
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-27__p0-4__ci-pipeline
# Pass criteria: exit 0

UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline
# Pass criteria: exit 0

# ─── Step 5: Create branch and push ──────────────────────────────────────────
git checkout -b ci/add-ci-workflow
# Pass criteria: exit 0

git add .github/workflows/ci.yml pyproject.toml uv.lock CHANGELOG.md docs/DECISIONS.md
git commit -m "ci: add CI workflow with lint, typecheck, and test stages"
# Pass criteria: exit 0

git push origin ci/add-ci-workflow
# Pass criteria: exit 0

# ─── Step 6: (ORCHESTRATOR ACTION) Open PR and verify CI ────────────────────
# NOTE: PR creation is an orchestrator action, not Coding Agent scope.
# Orchestrator opens PR from ci/add-ci-workflow → main via GitHub UI.
# Orchestrator verifies all 4 jobs green (lint ✓, typecheck ✓, test ✓, ci-pass ✓).

# ─── Step 7: (ORCHESTRATOR ACTION) Merge ─────────────────────────────────────
# NOTE: Merge is an orchestrator action, not Coding Agent scope.
# Once all checks pass, orchestrator merges the PR.
```

**Overall pass criteria for Coding Agent:** All local verification commands (Steps 0-5) exit 0. Branch is pushed.

**Orchestrator verification:** PR is created, GitHub Actions shows all 4 jobs green.

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

12. **pyproject.toml idempotency:** Before adding `pyyaml>=6.0`, check if it already exists. If present, do not duplicate. If present at a compatible version (>=6.0), do not modify.

13. **uv.lock is a modified output:** The lockfile will be updated by `uv sync --group dev`. Stage and commit it.

14. **PR creation is orchestrator scope:** The Coding Agent does NOT create the PR. Push the branch and stop. The orchestrator opens the PR via GitHub UI.

15. **.venv prerequisite:** The `.venv/` directory must exist before YAML validation. If missing, run `uv sync --group dev` first (this is part of Step 1).

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-4__ci-pipeline

## Plan to Review

Read file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-review-v3.md
