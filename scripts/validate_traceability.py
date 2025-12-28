#!/usr/bin/env python3
"""Validate requirements-traceability.md references exist.

Checks that all file and test references in the traceability matrix
point to actual files/tests in the codebase.

Usage:
    UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py          # Validate
    UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check  # CI check (exit 1 if invalid)

Fallback:
    python scripts/validate_traceability.py          # Validate
    python scripts/validate_traceability.py --check  # CI check (exit 1 if invalid)

Exit codes:
    0: All references valid
    1: Missing references found
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs/OPUS_REBUILD_FRAME_COMPARE"
TRACEABILITY_PATH = DOCS_ROOT / "02-requirements/requirements-traceability.md"
MODULE_SPECS_DIR = DOCS_ROOT / "05-implementation/module-specs"
SCAFFOLD_TESTS_DIR = DOCS_ROOT / "scaffold/tests"


def extract_module_refs(content: str) -> list[str]:
    """Extract module-spec.md references from markdown tables."""
    # Match patterns like "config-module.md" or "vs-module.md"
    pattern = r"([a-z]+-module\.md)"
    return list(set(re.findall(pattern, content)))


def extract_test_refs(content: str) -> list[str]:
    """Extract test_* function references from markdown tables."""
    # Match patterns like "test_screenshots_only" or "test_config_validation"
    pattern = r"(test_[a-z_0-9]+)"
    return list(set(re.findall(pattern, content)))


def validate_module_spec(filename: str) -> tuple[bool, str]:
    """Check if module spec file exists."""
    path = MODULE_SPECS_DIR / filename
    if path.exists():
        return True, f"✓ {filename}"
    return False, f"✗ {filename} NOT FOUND at {path}"


def validate_test(test_name: str) -> tuple[bool, str]:
    """Check if test function exists in scaffold tests."""
    for test_file in SCAFFOLD_TESTS_DIR.rglob("test_*.py"):
        content = test_file.read_text()
        if f"def {test_name}" in content:
            return True, f"✓ {test_name} found in {test_file.name}"
    return False, f"✗ {test_name} NOT FOUND in scaffold tests"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate traceability references")
    parser.add_argument("--check", action="store_true", help="CI mode: exit 1 if invalid")
    _ = parser.parse_args()

    if not TRACEABILITY_PATH.exists():
        print(f"ERROR: Traceability file not found: {TRACEABILITY_PATH}")
        return 1

    content = TRACEABILITY_PATH.read_text()

    # Extract and validate references
    errors = []

    print("Validating module spec references...")
    for ref in extract_module_refs(content):
        valid, msg = validate_module_spec(ref)
        print(f"  {msg}")
        if not valid:
            errors.append(msg)

    print("\nValidating test references...")
    for ref in extract_test_refs(content):
        valid, msg = validate_test(ref)
        print(f"  {msg}")
        if not valid:
            errors.append(msg)

    if errors:
        print(f"\n❌ Traceability validation FAILED: {len(errors)} missing references")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("\n✅ All traceability references valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
