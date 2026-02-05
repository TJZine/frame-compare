# Phase 7 Closeout Report (TEMPLATE)

> Use this template for a **single, human-orchestrated session** to finish Phase 7.
> This is intentionally “verification-first” and minimizes multi-run workflow churn.

## Session Metadata

- Date:
- Repo root:
- Branch:
- Operator:

## Preconditions

- [ ] `git status -sb` is understood (no surprising uncommitted work)
- [ ] Master checklist ordering is valid:
  - Command: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_master_checklist_order.py`
  - Result:

## Phase 7.2 — Quality Assurance

### 7.2.1 Full Gate Suite (Baseline)

Run and record:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check
```

Results:

- Pyright:
- Ruff:
- Pytest:
- Import-linter:
- Contract views `--check`:
- Traceability `--check`:
- API docs `--check`:

### 7.2.2 Coverage > 80%

Run:

```bash
.venv/bin/pytest -q --cov --cov-report=term-missing
```

Result:

- Coverage summary:
- If any test additions were required, list files changed:

### 7.2.3 Fix Any Pyright Errors (If Applicable)

- Status: `PASS` / `N/A`
- Notes:

### 7.2.4 Fix Any Ruff Errors (If Applicable)

- Status: `PASS` / `N/A`
- Notes:

### 7.2.5 Consistent Module-Level Logger Pattern

Target policy (state the chosen repo convention explicitly):
- Convention:
- Examples (files verified):

Audit outcome:
- Status: `PASS` / `PARTIAL` / `NEEDS_FOLLOWUP`
- Notes (only if not PASS):

### 7.2.6 Performance Testing

Minimum requirement for Phase 7: perf instrumentation exists and is exercised by deterministic tests.

Run:

```bash
.venv/bin/pytest -q tests/utils/test_perf.py
```

Result:

- Status: `PASS` / `FAIL`
- Notes:

## Phase 7.3 — Container Finalization

### 7.3.1 Optimize Dockerfile Layers

- Status: `PASS` / `N/A`
- Notes:

### 7.3.2 Docker End-to-End Verification (Real Deps)

Run:

```bash
bash tools/verify_docker_integration.sh
```

Result:
- Status: `PASS` / `FAIL`
- Notes:

### 7.3.3 Publish to ghcr.io (If Applicable)

- Status: `PASS` / `BLOCKED` / `N/A`
- If BLOCKED: specify what credential or environment is required.

## Phase 7 Quality Gate ✓

Only mark these as complete if they are supported by evidence above.

- [ ] All tests pass
- [ ] Coverage > 80%
- [ ] Pyright: 0 errors
- [ ] Ruff: 0 errors
- [ ] Docker image builds and runs
- [ ] Documentation complete

Evidence links (commands or artifact references):

- Tests:
- Coverage:
- Pyright/Ruff:
- Docker:
- Docs:

## Checklist Updates

File:
- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`

Edits made:
- Section 7.2:
- Section 7.3:
- Phase 7 Quality Gate:

## Final Re-Run (Proof)

Re-run these and record final outcomes:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/pytest -q --cov
bash tools/verify_docker_integration.sh
```

Results:

- Pyright:
- Ruff:
- Pytest:
- Coverage:
- Docker verify:

## Notes / Followups

- Any exceptions taken:
- Any remaining unchecked items and why:
