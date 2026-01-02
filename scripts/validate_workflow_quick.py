#!/usr/bin/env python3
"""Validate that 11-agent-workflow-quick.md contains all required sections.

This is a drift-check to ensure the curated quick doc stays complete and accurate.
Runs with stdlib only; no external dependencies required.

Usage:
    python3 scripts/validate_workflow_quick.py

Exit codes:
    0 - All required content present
    1 - Missing required content (details printed to stderr)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple


class Check(NamedTuple):
    """A required string or pattern to find in the quick doc."""

    name: str
    pattern: str  # regex pattern
    description: str


# Required checks — each must match at least once in the quick doc
REQUIRED_CHECKS: list[Check] = [
    # 1. Canonical SSOT rule + "canonical wins"
    Check(
        name="canonical_ssot_rule",
        pattern=r"11-agent-workflow\.md.*SSOT|SSOT.*11-agent-workflow\.md",
        description="Canonical SSOT declaration (11-agent-workflow.md is SSOT)",
    ),
    Check(
        name="canonical_wins",
        pattern=r"canonical.*wins|canonical\s+doc\s+wins",
        description="'Canonical wins' conflict resolution rule",
    ),
    # 2. Contract-first loop commands
    Check(
        name="generate_contract_views_check",
        pattern=r"generate_contract_views\.py.*--check",
        description="Contract freshness check command (generate_contract_views.py --check)",
    ),
    Check(
        name="validate_traceability_check",
        pattern=r"validate_traceability\.py.*--check",
        description="Traceability check command (validate_traceability.py --check)",
    ),
    # 3. RUN_ID format + run directory layout + NEXT prompt requirement
    Check(
        name="run_id_format",
        pattern=r"RUN_ID\s*=\s*YYYY-MM-DD",
        description="RUN_ID format specification",
    ),
    Check(
        name="run_directory_layout",
        pattern=r"\.agent-workflow/runs/<RUN_ID>/|plan-v.*\.md.*impl-v.*\.md",
        description="Run directory layout",
    ),
    Check(
        name="next_prompt_requirement",
        pattern=r"NEXT AGENT PROMPT.*\(COPY/PASTE\)|NEXT.*block.*required",
        description="NEXT AGENT PROMPT block requirement",
    ),
    # 4. STOP conditions
    Check(
        name="stop_plan_review_not_approved",
        pattern=r"Plan Review.*not.*APPROVED.*Coding|Coding.*must not run",
        description="STOP condition: Plan Review not approved",
    ),
    Check(
        name="stop_run_id_mismatch",
        pattern=r"RUN_ID mismatch.*STOP|STOP.*RUN_ID mismatch",
        description="STOP condition: RUN_ID mismatch",
    ),
    Check(
        name="stop_verification_gate_fails",
        pattern=r"verification.*gate.*fails.*STOP|Verification must not advance",
        description="STOP condition: verification gate fails",
    ),
    # 5. Command canon
    Check(
        name="cmd_pyright",
        pattern=r"\.venv/bin/pyright",
        description="Command canon: .venv/bin/pyright",
    ),
    Check(
        name="cmd_ruff",
        pattern=r"\.venv/bin/ruff",
        description="Command canon: .venv/bin/ruff",
    ),
    Check(
        name="cmd_pytest",
        pattern=r"\.venv/bin/pytest",
        description="Command canon: .venv/bin/pytest",
    ),
    Check(
        name="cmd_lint_imports",
        pattern=r"lint-imports|lint_imports",
        description="Command canon: lint-imports",
    ),
    Check(
        name="cmd_docker_verify",
        pattern=r"bash\s+tools/verify_docker_integration\.sh|verify_docker_integration\.sh",
        description="Command canon: Docker verification script",
    ),
    Check(
        name="docker_zero_skips",
        pattern=r"zero\s+skip|Zero\s+skip|0\s+skip",
        description="Docker verification: zero skips expectation",
    ),
    # 6. Mechanical Auto-Fix summary
    Check(
        name="mechanical_autofix",
        pattern=r"Mechanical Auto-Fix|mechanical.*auto.*fix",
        description="Mechanical Auto-Fix Mode summary",
    ),
    # 7. SSOT Decision Audit summary
    Check(
        name="ssot_decision_audit",
        pattern=r"SSOT Decision Audit|SSOT.*audit",
        description="SSOT Decision Audit summary",
    ),
    # 8. Templates pointer to canonical doc
    Check(
        name="templates_pointer",
        pattern=r"template.*canonical|canonical.*template|11-agent-workflow\.md.*template|template.*11-agent-workflow\.md",
        description="Pointer to canonical doc for templates",
    ),
]


def validate_quick_doc(quick_doc_path: Path) -> list[Check]:
    """Validate the quick doc contains all required content.

    Returns:
        List of failed checks (empty if all pass).
    """
    if not quick_doc_path.exists():
        print(f"ERROR: Quick doc not found: {quick_doc_path}", file=sys.stderr)
        sys.exit(1)

    content = quick_doc_path.read_text(encoding="utf-8")
    failed: list[Check] = []

    for check in REQUIRED_CHECKS:
        if not re.search(check.pattern, content, re.IGNORECASE | re.MULTILINE):
            failed.append(check)

    return failed


def main() -> int:
    """Run validation and report results."""
    # Find repo root (where this script lives is under scripts/)
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    quick_doc = repo_root / "docs" / "OPUS_REBUILD_FRAME_COMPARE" / "11-agent-workflow-quick.md"

    print(f"Validating: {quick_doc}")
    failed = validate_quick_doc(quick_doc)

    if not failed:
        print("✅ All required content present in quick doc")
        return 0

    print("\n❌ Missing required content:", file=sys.stderr)
    for check in failed:
        print(f"  - {check.name}: {check.description}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
