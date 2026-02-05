---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v1
TARGET: Phase 7 → Item 7.1 (Bundled) — Documentation — Complete README.md with usage examples — Bundled 4 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v5.md
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v5.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/impl-v1.md
---

## Summary

- Expanded user-facing `README.md` with Docker-first usage examples for `wizard`, `doctor`, and `run`.
- Added deterministic API documentation generation via `scripts/generate_api_docs.py` (AST-only; no imports).
- Generated `docs/api.md` and added unit tests for the generator.
- Added/normalized short Google-style docstrings for exported public configuration and render types.

## Changes

- MODIFY: `README.md`
- MODIFY: `CHANGELOG.md`
- CREATE: `scripts/generate_api_docs.py`
- CREATE (generated): `docs/api.md`
- CREATE: `tests/test_generate_api_docs.py`
- MODIFY (docstrings):
  - `src/frame_compare/config/schema.py`
  - `src/frame_compare/render/types.py`

## Commands & Results

- `.venv/bin/pyright --warnings` — PASS (0 errors).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/pytest -q` — PASS.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — PASS.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — PASS.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check` — PASS.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check` — PASS.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Target

Phase 7 → Item 7.1 (Bundled) — Documentation (README + CHANGELOG + docstrings + API docs generator)

## Files To Read

- .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v5.md
- .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v5.md
- .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/impl-v1.md

## Your Task

Run the full gate suite and record results. If all gates pass, write `verify-v1.md`, update the checklist and index,
then complete review with `review-v1.md` and finalize the index row.

## Output

- Write file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/verify-v1.md
- Write file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/review-v1.md
