---
RUN_ID: 2026-02-04__p6-8__run
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks
INPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v4.md
OUTPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-04__p6-8__run/impl-v1.md
  - /Users/tristan/Software/frame-compare/docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md
  - /Users/tristan/Software/frame-compare/docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md
  - /Users/tristan/Software/frame-compare/docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md
  - /Users/tristan/Software/frame-compare/docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
  - /Users/tristan/Software/frame-compare/docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py
---

## Summary
- Implemented `frame-compare run` to build `RunRequest`, execute the runner, and return spec-compliant exit codes.
- Applied CLI override mapping and input discovery per SSOT, including `force_interactive_alignment` implications.
- Added/updated tests for CLI request mapping, overrides, and input discovery.
- Regenerated contract-derived views after updating `cli_flags.yaml`.
- Traceability gate fails because `tests/cli/test_cli_commands.py::test_run_stub_executes` is referenced but removed per plan; resolving requires updating traceability references (out of current plan scope).

## Commands & Results
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md`
  - OK
- `.venv/bin/pyright --warnings`
  - FAIL: type error in `src/frame_compare/orchestration/coordinator.py` (fixed)
- `.venv/bin/pyright --warnings`
  - OK
- `.venv/bin/ruff check .`
  - OK
- `.venv/bin/pytest -q`
  - OK (3 tests skipped: VapourSynth mocked)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
  - OK
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
  - FAIL: stale derived outputs
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
  - WROTE: cli-flags-canonical.md, error-codes.md, config-reference.md, dependency-graph.md, scaffold/src/frame_compare/cli/_generated.py
- `.venv/bin/pyright --warnings`
  - OK
- `.venv/bin/ruff check .`
  - OK
- `.venv/bin/pytest -q`
  - OK (3 tests skipped: VapourSynth mocked)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
  - OK
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
  - OK
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
  - FAIL: missing `tests/cli/test_cli_commands.py::test_run_stub_executes`
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
  - FAIL: missing `tests/cli/test_cli_commands.py::test_run_stub_executes`

## Changes
- Implemented `run` command and added `--force-interactive-alignment` option in `src/frame_compare/cli_entry.py`.
- Applied CLI overrides in `src/frame_compare/orchestration/coordinator.py` and added `RunRequest.force_interactive_alignment`.
- Updated input discovery behavior in `src/frame_compare/orchestration/preflight.py`.
- Updated CLI override mapping in `src/frame_compare/config/overrides.py`.
- Updated CLI flags contract in `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml` and regenerated derived views.
- Added/updated tests in:
  - `tests/cli/test_cli_commands.py`
  - `tests/config/test_overrides.py`
  - `tests/orchestration/test_execute_run.py`
  - `tests/orchestration/test_preflight.py`
  - `tests/orchestration/test_run_request.py`

## Tests
- `.venv/bin/pyright --warnings` (pass)
- `.venv/bin/ruff check .` (pass)
- `.venv/bin/pytest -q` (pass; 3 skipped: VapourSynth mocked)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` (pass)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` (pass)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check` (fail: missing test reference)

## NEXT AGENT PROMPT (COPY/PASTE)
You are the Verification Agent for Frame Compare 2.0.

RUN_ID: 2026-02-04__p6-8__run

Target: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks

Read files:
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md
- .agent-workflow/runs/2026-02-04__p6-8__run/impl-v1.md

Required gates:
```
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

Notes:
- Traceability gate currently fails due to missing `tests/cli/test_cli_commands.py::test_run_stub_executes` reference.
