---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v1
TARGET: Meta → Phase 5 Quality Gate Verification
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v1.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
---

# Implementation Plan: Phase 5 Quality Gate Verification

## Context

**Phase:** Meta (Pre-Phase 6 checkpoint)
**Purpose:** Verify all Phase 5 quality gate items pass before proceeding to Phase 6 CLI & Orchestration
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` (lines 404-413)

## Scope

This plan covers:

- [x] Static analysis verification (pyright, ruff, lint-imports)
- [x] Unit test verification for all services
- [x] Contract freshness gates
- [x] Docker integration verification with real dependencies
- [x] Coverage threshold verification
- [x] Master checklist update (if all pass)

This plan does NOT cover:

- Implementing fixes for any failures found (separate runs)
- Phase 6+ implementation

## Contract Impact

**Contracts touched:** NO

## Phase 5 Quality Gate Items (from Master Checklist)

| # | Item | Verification Method |
|---|------|---------------------|
| 1 | Audio alignment calculates offsets | Unit tests in `tests/services/test_alignment.py` |
| 2 | Metadata parses filenames | Unit tests in `tests/services/test_metadata.py` |
| 3 | slow.pics uploads work | Unit tests in `tests/services/test_publishers.py` (mocked network) |
| 4 | HTML report generates | Unit tests in `tests/services/test_report.py` |
| 5 | All services have error recovery | Verify error handling patterns in tests |
| 6 | Docker verification passes | `bash tools/verify_docker_integration.sh` |
| 7 | Test coverage > 80% and ALL tests pass | `pytest --cov` with coverage report |

## Verification Commands

### 1. Spec Anchor Validation (Skip — no plan spec anchors for meta run)

N/A — this is a verification-only meta run.

### 2. Static Analysis

```bash
# Type checking
.venv/bin/pyright --warnings

# Linting
.venv/bin/ruff check .

# Import layering
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors.

### 3. Contract Freshness Gates

```bash
# Contract views freshness
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check

# Traceability
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** Both commands exit 0.

### 4. Full Test Suite with Coverage

```bash
# Run all tests with coverage
.venv/bin/pytest -v --cov=src/frame_compare --cov-report=term-missing --cov-fail-under=80
```

**Pass criteria:**

- Exit 0
- Coverage ≥ 80%
- All tests pass (no failures, no errors)

### 5. Services-Specific Tests (Detailed Verification)

```bash
# Audio alignment
.venv/bin/pytest -v tests/services/test_alignment.py

# Metadata service
.venv/bin/pytest -v tests/services/test_metadata.py

# Publishers
.venv/bin/pytest -v tests/services/test_publishers.py

# Report generator
.venv/bin/pytest -v tests/services/test_report.py
```

**Pass criteria:** Each command exits 0 with all tests passing.

### 6. Docker Integration Verification

```bash
# Real dependencies (VapourSynth, FFmpeg) in Docker
bash tools/verify_docker_integration.sh
```

**Pass criteria:**

- Exit 0
- Zero skipped tests inside Docker container

## Execution Workflow

1. **Run all verification commands** in sequence
2. **Capture output** for each command
3. **Document results** in `verify-v1.md`
4. **If all pass:**
   - Update master checklist Phase 5 Quality Gate items
   - Append run to `.agent-workflow/index.md`
5. **If any fail:**
   - Document failures in `verify-v1.md`
   - Create targeted fix runs before proceeding

## Acceptance Criteria

- [ ] GIVEN pyright run WHEN checking all source files THEN exit 0 with no errors
- [ ] GIVEN ruff run WHEN checking all source files THEN exit 0 with no errors
- [ ] GIVEN lint-imports run WHEN checking import contracts THEN exit 0
- [ ] GIVEN contract freshness check WHEN running both gates THEN both exit 0
- [ ] GIVEN pytest with coverage WHEN running full suite THEN coverage ≥ 80% and all tests pass
- [ ] GIVEN Docker integration script WHEN running with real deps THEN zero skips and exit 0
- [ ] GIVEN all gates pass WHEN updating master checklist THEN all Phase 5 Quality Gate items marked complete

## Notes for Verification Agent

- This is a **meta verification run** — no code changes expected
- If any check fails, document the exact failure in `verify-v1.md` and escalate
- Do NOT attempt to fix failures in this run — create separate targeted fix runs
- Update master checklist ONLY if ALL verification commands pass

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Plan to Verify

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md

## Your Task

Execute all verification commands from the plan. Document results. If all pass, update master checklist.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
