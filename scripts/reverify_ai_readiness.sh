#!/usr/bin/env bash
#
# Re-verify Frame Compare 2.0 readiness gates and update AI_READINESS_ROADMAP.md
# with a single, consistent UTC timestamp.
#
# This script prints the exact stdout/stderr of each gate command (no paraphrasing).
#
# Modes:
#   - Default: run gates only (no file updates)
#   - --update-roadmap: after gates, update AI_READINESS_ROADMAP.md timestamps to the same UTC value
#
# Canonical gate commands SSOT:
#   docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json
#
set -euo pipefail

update_roadmap=0
if [[ "${1:-}" == "--update-roadmap" ]]; then
  update_roadmap=1
  shift
fi
if [[ "${#}" -ne 0 ]]; then
  echo "Usage: $0 [--update-roadmap]" >&2
  exit 2
fi

checked_at="$(date -u +'%Y-%m-%d %H:%M')"

echo "Checked at (UTC): ${checked_at}"
echo ""

echo "=== Gate 1/3: Contract views freshness ==="
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
echo ""

echo "=== Gate 2/3: Scaffold Tier-A suite ==="
(
  cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold
  .venv/bin/pytest -q -m tier_a
)
echo ""

echo "=== Gate 3/3: Traceability validation ==="
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
echo ""

if [[ "${update_roadmap}" -eq 1 ]]; then
  echo "=== Updating AI_READINESS_ROADMAP.md timestamps ==="
  UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/update_ai_readiness_roadmap.py --checked-at "${checked_at}"
  echo "OK: AI_READINESS_ROADMAP.md updated (Last Updated/Last Checked = ${checked_at} UTC)"
else
  echo "NOTE: Not updating AI_READINESS_ROADMAP.md (pass --update-roadmap to sync timestamps)."
fi
