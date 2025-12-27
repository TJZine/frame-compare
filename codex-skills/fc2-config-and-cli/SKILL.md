---
name: fc2-config-and-cli
description: Use when changing config schema, config templates, or CLI flags so contracts, docs generation, and precedence rules stay aligned and validated.
---

# FC-2.0 Config + CLI Skill

## SSOT and generators

- Config schema SSOT: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/config_schema.json`
- CLI flags SSOT: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`
- Derived views generator: `scripts/generate_contract_views.py`
- Config docs generator (CI): `tools/gen_config_docs.py`

## Required checks after changes

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
- CI config docs check equivalent:
  - `uv run --no-sync python tools/gen_config_docs.py --check docs/_generated/config_tables.md`

## Guardrails

- Don’t edit generated derived views by hand.
- Keep config precedence deterministic; tests should lock the precedence behavior.
