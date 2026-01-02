---
name: fc2-readiness-audit
description: Use when auditing or refreshing Frame Compare 2.0 AI readiness (run the three readiness gates, verify workflow/prompt/run-system consistency, and update AI_READINESS_ROADMAP.md plus docs/DECISIONS.md and CHANGELOG.md with the current UTC timestamp).
---

# FC-2.0 Readiness Audit Skill

## Canonical Sources (SSOT)

- `AI_READINESS_ROADMAP.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` (read first — curated quick reference)
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` (canonical SSOT for templates/appendices)
- `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`
- `scripts/update_ai_readiness_roadmap.py`

## Required Gates (run + record exact output)

- Contract views freshness:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
- Scaffold Tier‑A:
  - `(cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a)`
- Traceability validation:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`

## Timestamp Discipline

- Capture UTC timestamp once:
  - `date -u +%Y-%m-%d`
  - `date -u +%Y-%m-%d\ %H:%M`
- Use that value everywhere you update readiness timestamps.

## Roadmap Sync

- Update `AI_READINESS_ROADMAP.md` gate table timestamps via:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/update_ai_readiness_roadmap.py --checked-at "<YYYY-MM-DD HH:MM>"`
- Ensure “Resume Next Session” reflects the same “last checked” timestamp.

## Logging

- Append a short entry to:
  - `docs/DECISIONS.md`
  - `CHANGELOG.md`
