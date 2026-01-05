---
RUN_ID: 2025-12-27__p0-4__ci-pipeline
VERSION: v1
TARGET: Phase 0 → Item 0.4 (CI/CD Pipeline)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v1.md
---

# Implementation Plan: CI/CD Pipeline (Phase 0.4)

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
- [x] Verify CI passes on push

This plan does NOT cover:

- Container E2E testing (Phase 0.5)
- Docker build (Phase 0.5)
- Branch protection rules (GitHub UI config, not code)
- Contract/traceability gates (will be added in Phase 1)

## Contract Impact

**Contracts touched:** NO

---

## Rollback / Stop Conditions

> [!CAUTION]
> If any verification command fails, **do not patch around it**. Return to Planning Agent for a plan revision.

**Stop conditions:**

1. Workflow file has YAML syntax errors → Fix before committing
2. CI job fails on push → Diagnose and fix the specific job
3. Any linting/type-check/test jobs that pass locally but fail in CI → Check for environment differences

**Prerequisite checks (before starting):**

- `.github/workflows/` directory exists (it does — contains `pr-title.yml`, `release-please.yml`)
- `pyproject.toml` exists with dev dependencies
- `uv.lock` exists

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

### 2. `CHANGELOG.md` [MODIFY]

**Purpose:** Document CI/CD additions.

**Content to add under `[Unreleased]` → `### Added`:**

```markdown
- **CI/CD Pipeline:** GitHub Actions workflow with Ruff linting, Pyright type checking, and pytest stages.
```

---

### 3. `docs/DECISIONS.md` [MODIFY]

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

- [ ] **AC-1:** GIVEN `.github/workflows/ci.yml` exists WHEN a commit is pushed to `main` THEN the CI workflow triggers
- [ ] **AC-2:** GIVEN the CI workflow runs WHEN `lint` job executes THEN Ruff checks pass (exit 0)
- [ ] **AC-3:** GIVEN the CI workflow runs WHEN `typecheck` job executes THEN Pyright checks pass (exit 0)
- [ ] **AC-4:** GIVEN the CI workflow runs WHEN `test` job executes THEN pytest runs and passes (exit 0)
- [ ] **AC-5:** GIVEN all jobs pass WHEN `ci-pass` job runs THEN it succeeds (exit 0)
- [ ] **AC-6:** GIVEN the workflow file WHEN YAML is validated THEN it has no syntax errors

---

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

**Local verification (before push):**

```bash
# ─── Step 1: Validate YAML syntax ────────────────────────────────────────────
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
# Pass criteria: exit 0 (no Python/YAML errors)

# Alternative if PyYAML not available:
cat .github/workflows/ci.yml | head -5
# Pass criteria: file is readable and looks like valid YAML

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
```

**CI verification (after push):**

```bash
# ─── Step 4: Push and verify CI ──────────────────────────────────────────────
git add .github/workflows/ci.yml CHANGELOG.md docs/DECISIONS.md
git commit -m "ci: add CI workflow with lint, typecheck, and test stages"
git push origin main  # Or push to a branch and open PR

# Pass criteria: GitHub Actions shows all jobs green (lint ✓, typecheck ✓, test ✓, ci-pass ✓)
```

**Overall pass criteria:** All local verification commands exit 0, and CI workflow shows all jobs passing on GitHub.

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

10. **Local YAML validation:** The `python -c "import yaml..."` command requires PyYAML which may not be installed. If unavailable, skip this step — CI will catch YAML errors anyway.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-4__ci-pipeline

## Plan to Review

Read file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-4__ci-pipeline/plan-review-v1.md
