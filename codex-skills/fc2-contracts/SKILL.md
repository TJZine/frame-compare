---
name: fc2-contracts
description: Use when changing FC-2.0 canonical contracts (docs/OPUS_REBUILD_FRAME_COMPARE/contracts/*) and regenerating/verifying derived views and traceability without manual drift.
---

# FC-2.0 Contracts Skill

## SSOT

- Canonical contracts only: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`
- Gate commands SSOT: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`

## Contract Change Loop (deterministic)

1. Edit canonical contract(s).
2. Regenerate derived views:
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
3. Verify gates:
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
4. If docs are involved, ensure you did **not** edit generated derived files by hand.

## When in doubt

Read `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` first (curated quick reference).
For full Contract-First Loop + Command Canon details: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`.
