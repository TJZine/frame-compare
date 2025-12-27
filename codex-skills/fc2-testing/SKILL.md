---
name: fc2-testing
description: Use when adding or refactoring tests for Frame Compare to keep them deterministic, low-churn, and aligned with the workflow gates (pytest/pyright/ruff/import contracts/traceability).
---

# FC-2.0 Testing Skill

## Principles

- Deterministic by default (seeded randomness, stable ordering).
- Anti-churn: prefer narrow unit tests, contract-based assertions, and stable fixtures.
- Match verification evidence expectations in run artifacts.

## Quick verification (Command Canon)

- Tooling (preferred):
  - `.venv/bin/pyright --warnings`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pytest -q`
- Import contracts:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
- Contract/traceability gates:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
