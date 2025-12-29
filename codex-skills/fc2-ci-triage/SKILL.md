---
name: fc2-ci-triage
description: Use when a Frame Compare 2.0 CI run fails and you need a deterministic local reproduction and minimal fix plan using the Command Canon (prefer .venv/bin for tooling; uv run --no-sync for repo scripts/gates).
---

# FC-2.0 CI Triage Skill

## Canonical References

- `CODEX.md` (approvals + command preferences)
- `.github/workflows/ci.yml` (actual CI command lines)
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**

## Triage Workflow (minimal churn)

1. Identify which CI step failed (pyright / ruff / pytest / lint-imports / contract views / traceability).
2. Reproduce locally with the closest command:
   - Tooling (preferred):
     - `.venv/bin/pyright --warnings`
     - `.venv/bin/ruff check .`
     - `.venv/bin/pytest -q`
   - Import contracts (CI installs import-linter explicitly):
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
   - Repo-script gates:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
   - Plan artifact hygiene (if a plan was revised in this run):
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/<RUN_ID>/plan-vN.md`
3. Create a fix plan that changes only what the failing command requires (no drive-by refactors).
4. Re-run:
   - the failing command first
   - then the full verification suite if you touched code

## Reporting Template (what to produce)

- Failed CI step name + exact command
- Local reproduction command + exact output
- Minimal patch plan (files + rationale)
- Verification reruns (expected: exit 0)
