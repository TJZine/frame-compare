#!/usr/bin/env bash
# Check all readiness gates for Frame Compare 2.0
#
# Usage: ./scripts/check-all-gates.sh
#
# Exit codes:
#   0: All gates passed
#   1: One or more gates failed

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Contract Freshness ===${NC}"
if UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check; then
    echo -e "${GREEN}✓ Contract freshness passed${NC}"
else
    echo -e "${RED}✗ Contract freshness FAILED${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}=== Scaffold Tier-A ===${NC}"
if (cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a); then
    echo -e "${GREEN}✓ Scaffold Tier-A passed${NC}"
else
    echo -e "${RED}✗ Scaffold Tier-A FAILED${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}=== Traceability ===${NC}"
if UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check; then
    echo -e "${GREEN}✓ Traceability passed${NC}"
else
    echo -e "${RED}✗ Traceability FAILED${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ All gates passed${NC}"
