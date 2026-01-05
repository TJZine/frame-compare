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

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs/OPUS_REBUILD_FRAME_COMPARE"
TRACEABILITY_PATH = DOCS_ROOT / "02-requirements/requirements-traceability.md"
MODULE_SPECS_DIR = DOCS_ROOT / "05-implementation/module-specs"
SCAFFOLD_TESTS_DIR = DOCS_ROOT / "scaffold/tests"
REPO_TESTS_DIR = PROJECT_ROOT / "tests"

# Regex patterns per §1.2 and §1.3 of the fix plan
CODE_SPAN_PATTERN = re.compile(r"`([^`]+)`")
MODULE_SPEC_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-module\.md$")
TEST_PATH_PATTERN = re.compile(r"^tests/[a-zA-Z0-9_/\-]+\.py(?:::test_[a-zA-Z0-9_]+)?$")


@dataclass
class TraceRef:
    """A reference extracted from the traceability matrix."""

    kind: Literal["module_spec", "test"]
    ref: str
    planned: bool
    line_no: int


def extract_refs(lines: list[str]) -> list[TraceRef]:
    """Extract structured references from traceability markdown lines.

    Per §1.2: Only inline code spans (backticks) are considered.
    Per §1.3: Classification rules for module_spec vs test.
    Per §1.4: PLANNED policy based on text before code span.
    """
    refs: list[TraceRef] = []

    for line_no, line in enumerate(lines, start=1):
        # Find all code spans in this line
        for match in CODE_SPAN_PATTERN.finditer(line):
            # §1.2: Normalization - strip whitespace and normalize path separators
            span_content = match.group(1).strip()
            span_start = match.start()

            # Text before this code span (for PLANNED detection)
            text_before = line[:span_start]
            is_planned = "PLANNED:" in text_before

            # Classify the reference
            if MODULE_SPEC_PATTERN.match(span_content):
                refs.append(
                    TraceRef(
                        kind="module_spec",
                        ref=span_content,
                        planned=False,  # Planned not meaningful for module specs
                        line_no=line_no,
                    )
                )
            else:
                # §1.2: Normalization applies to test refs (after whitespace strip).
                # We implement it before matching TEST_PATH_PATTERN so Windows-style
                # refs like "tests\\x\\y.py" become "tests/x/y.py".
                normalized = span_content
                if "\\\\" in normalized:
                    normalized = normalized.replace("\\\\", "/")
                if normalized.startswith("tests\\"):
                    normalized = normalized.replace("\\", "/")

                if TEST_PATH_PATTERN.match(normalized):
                    refs.append(
                        TraceRef(
                            kind="test",
                            ref=normalized,
                            planned=is_planned,
                            line_no=line_no,
                        )
                    )
            # Everything else is ignored per §1.3.3

    return refs


def dedupe_refs(refs: list[TraceRef]) -> list[TraceRef]:
    """Deduplicate refs per §1.2.

    - Key is (kind, ref, planned).
    - If duplicates occur, keep the lowest line_no for reporting.
    """
    best: dict[tuple[str, str, bool], TraceRef] = {}
    for ref in refs:
        key = (ref.kind, ref.ref, ref.planned)
        existing = best.get(key)
        if existing is None or ref.line_no < existing.line_no:
            best[key] = ref
    return list(best.values())


def validate_module_spec(ref: TraceRef) -> tuple[bool, str]:
    """Check if module spec file exists."""
    path = MODULE_SPECS_DIR / ref.ref
    if path.exists():
        return True, f"✓ {ref.ref}"
    # §2.7: Error format for module spec missing
    return False, f"✗ {ref.ref} NOT FOUND (line {ref.line_no}): expected {path}"


def _parse_test_ref(ref_str: str) -> tuple[str, str | None]:
    """Parse a test reference into (file_path, test_func_or_none).

    Examples:
        "tests/vs/test_loader.py" -> ("tests/vs/test_loader.py", None)
        "tests/cli/test_cli_commands.py::test_run_stub_executes"
            -> ("tests/cli/test_cli_commands.py", "test_run_stub_executes")
    """
    if "::" in ref_str:
        parts = ref_str.split("::", 1)
        return parts[0], parts[1]
    return ref_str, None


def _check_test_function_exists(file_path: Path, test_func: str) -> bool:
    """Check if a specific test function exists in a file.

    Per §1.5: Uses regex `rf"(?m)^\\s*def\\s+{re.escape(test_func)}\\s*\\("`
    to match exact function definition.
    """
    if not file_path.exists():
        return False

    content = file_path.read_text()
    pattern = rf"(?m)^\s*def\s+{re.escape(test_func)}\s*\("
    return bool(re.search(pattern, content))


def validate_test(ref: TraceRef) -> tuple[bool, str]:
    """Validate a test file or test function reference.

    Per §1.4: Planned vs implemented policy.
    Per §1.5: File vs function validation.
    """
    file_path_str, test_func = _parse_test_ref(ref.ref)

    # Remove leading "tests/" to get relative path for scaffold lookup
    relative_to_tests = file_path_str[len("tests/") :]

    # Candidate paths
    real_path = REPO_TESTS_DIR / relative_to_tests
    scaffold_path = SCAFFOLD_TESTS_DIR / relative_to_tests

    # Determine which paths to check per §1.4
    if ref.planned:
        # PLANNED: check scaffold first, then real
        check_paths = [(scaffold_path, "scaffold"), (real_path, "real")]
    else:
        # Implemented: check only real tests
        check_paths = [(real_path, "real")]

    # Find a matching file
    found_path: Path | None = None
    found_source: str | None = None
    checked_locations: list[str] = []

    for path, source in check_paths:
        checked_locations.append(str(path))
        if path.exists():
            found_path = path
            found_source = source
            break

    if found_path is None:
        # §2.7: Error format for test file missing
        locations = ", ".join(checked_locations)
        return False, f"✗ {ref.ref} NOT FOUND (line {ref.line_no}): checked {locations}"

    # If no test function specified, file existence is sufficient
    if test_func is None:
        return True, f"✓ {ref.ref} ({found_source})"

    # Check for specific test function per §1.5
    if _check_test_function_exists(found_path, test_func):
        return True, f"✓ {ref.ref} ({found_source})"

    # §2.7: Error format for test function missing
    return (
        False,
        f"✗ {ref.ref} NOT FOUND (line {ref.line_no}): function {test_func} missing in {found_path}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate traceability references")
    parser.add_argument("--check", action="store_true", help="CI mode: exit 1 if invalid")
    _ = parser.parse_args()

    if not TRACEABILITY_PATH.exists():
        print(f"ERROR: Traceability file not found: {TRACEABILITY_PATH}")
        return 1

    lines = TRACEABILITY_PATH.read_text().splitlines()
    all_refs = dedupe_refs(extract_refs(lines))

    module_refs = sorted(
        (r for r in all_refs if r.kind == "module_spec"),
        key=lambda r: (r.ref, r.planned),
    )
    test_refs = sorted(
        (r for r in all_refs if r.kind == "test"),
        key=lambda r: (r.ref, r.planned),
    )

    errors: list[str] = []

    print("Validating module spec references...")
    for ref in module_refs:
        valid, msg = validate_module_spec(ref)
        print(f"  {msg}")
        if not valid:
            errors.append(msg)

    print("\nValidating test references...")
    for ref in test_refs:
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
