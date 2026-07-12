"""Traceability validation helpers used by repo gates.

This module intentionally keeps its public surface small and testable:
- `extract_refs()` parses markdown-like lines for artifact references in backticks.
- `dedupe_refs()` removes duplicates while preserving "planned" as a distinct state.
- `validate_test()` validates that a referenced test file/function exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_PLANNED_TOKEN = "PLANNED:"


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_TESTS_DIR = REPO_ROOT / "tests"


TraceKind = Literal["test", "module_spec"]


@dataclass(frozen=True, slots=True)
class TraceRef:
    """Single trace reference extracted from an artifact line."""

    kind: TraceKind
    ref: str
    planned: bool
    line_no: int


def extract_refs(lines: list[str]) -> list[TraceRef]:
    """Extract trace references from lines.

    Supported references:
    - Tests: `tests/.../test_*.py` (optionally with `::test_name`)
    - Module specs: `*-module.md`

    Planned behavior:
        The token "PLANNED:" applies to references after it on the same line, and
        is evaluated per code span.
    """

    refs: list[TraceRef] = []
    for idx, line in enumerate(lines, start=1):
        planned_mode = False
        last_end = 0

        for match in _CODE_SPAN_RE.finditer(line):
            between = line[last_end : match.start()]
            if _PLANNED_TOKEN in between:
                planned_mode = True

            raw = match.group(1).strip()
            last_end = match.end()

            # Ignore non-artifact spans and "lists" embedded in a single span.
            if not raw or "," in raw or " " in raw:
                continue

            normalized = raw.replace("\\", "/")
            normalized = re.sub(r"/+", "/", normalized)

            if normalized.startswith("tests/"):
                refs.append(
                    TraceRef(kind="test", ref=normalized, planned=planned_mode, line_no=idx)
                )
                continue

            if normalized.endswith("-module.md"):
                refs.append(
                    TraceRef(kind="module_spec", ref=normalized, planned=planned_mode, line_no=idx)
                )
                continue

    return refs


def dedupe_refs(refs: list[TraceRef]) -> list[TraceRef]:
    """Dedupe by (kind, ref, planned), keeping the lowest line number for each key."""

    by_key: dict[tuple[TraceKind, str, bool], TraceRef] = {}
    for ref in refs:
        key = (ref.kind, ref.ref, ref.planned)
        existing = by_key.get(key)
        if existing is None or ref.line_no < existing.line_no:
            by_key[key] = ref
    return list(by_key.values())


def validate_test(ref: TraceRef) -> tuple[bool, str]:
    """Validate that a referenced test exists.

    For `tests/.../*.py::test_name`, requires an exact `def test_name(` definition
    in the target file.
    """

    if ref.kind != "test":
        return True, f"✓ {ref.ref}"

    file_ref, sep, func_name = ref.ref.partition("::")
    path = _resolve_test_path(file_ref)
    if not path.exists():
        return (
            False,
            f"✗ {ref.ref} NOT FOUND (line {ref.line_no}): file missing in {REPO_TESTS_DIR}",
        )

    if not sep:
        return True, f"✓ {ref.ref}"

    source = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^def\s+{re.escape(func_name)}\s*\(", re.MULTILINE)
    if pattern.search(source) is None:
        return (
            False,
            f"✗ {ref.ref} NOT FOUND (line {ref.line_no}): function {func_name} missing in {path}",
        )

    return True, f"✓ {ref.ref}"


def _resolve_test_path(file_ref: str) -> Path:
    # `file_ref` is expected to start with "tests/" per extract_refs(), but keep
    # this tolerant to direct calls for robustness.
    if file_ref.startswith("tests/"):
        rel = Path(file_ref).relative_to("tests")
        return REPO_TESTS_DIR / rel
    return REPO_TESTS_DIR / file_ref


def main() -> int:
    """No-op CLI placeholder.

    The full repo gate is implemented elsewhere; this script is imported by tests.
    """

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
