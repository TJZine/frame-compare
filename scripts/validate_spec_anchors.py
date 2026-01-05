#!/usr/bin/env python3
"""Validate `## Spec Anchors (SSOT)` and signature coverage in a plan artifact.

This script is intentionally lightweight and stdlib-only. It is designed as a
deterministic STOP gate before implementation: the plan must point to concrete
SSOT spec sections, and the planned public function names must be discoverable
in the anchored sections.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

SPEC_ANCHORS_HEADER = "## Spec Anchors (SSOT)"

_MD_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")
_BULLET = re.compile(r"^(?P<indent>\s*)-\s+(?P<body>.+?)\s*$")

_SECTION_LINE = re.compile(
    r"^Section:\s*(?P<body>.+?)\s*$",
    flags=re.IGNORECASE,
)

_SIGNATURE_BULLET = re.compile(r"^\s*-\s+`(?P<sig>[^`]+)`(?:\s+—|\s+-|\s+–|$)")


@dataclass(frozen=True)
class SpecAnchor:
    path: Path
    headings: tuple[str, ...]


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        _fail(f"failed to read {path}: {exc}")
        raise  # unreachable


def _extract_section_heading(section_body: str) -> str:
    text = section_body.strip()
    for open_quote, close_quote in (('"', '"'), ("“", "”"), ("'", "'")):
        if open_quote not in text:
            continue
        remainder = text.split(open_quote, 1)[1]
        if close_quote not in remainder:
            continue
        return remainder.split(close_quote, 1)[0].strip()
    return text.strip("“”\"'")


def _extract_spec_anchors(plan_text: str, *, plan_path: Path) -> list[SpecAnchor]:
    lines = plan_text.splitlines()
    try:
        start_idx = lines.index(SPEC_ANCHORS_HEADER)
    except ValueError:
        _fail(f"{plan_path}: missing required {SPEC_ANCHORS_HEADER!r} section")
        raise  # unreachable

    # Collect until the next H2 heading (## ...) after Spec Anchors.
    anchors_lines: list[str] = []
    for line in lines[start_idx + 1 :]:
        if line.startswith("## "):
            break
        anchors_lines.append(line.rstrip("\n"))

    anchors: list[SpecAnchor] = []
    current_path: Path | None = None
    current_headings: list[str] = []

    for raw_line in anchors_lines:
        line = raw_line.rstrip()
        if not line.strip():
            continue

        bullet = _BULLET.match(line)
        if not bullet:
            continue

        indent = len(bullet.group("indent"))
        body = bullet.group("body")

        # Top-level anchor bullet: `path/to/spec.md`:
        if indent == 0:
            if current_path is not None:
                anchors.append(SpecAnchor(current_path, tuple(current_headings)))
            current_headings = []

            path_text = body
            # Prefer backticked path.
            if path_text.startswith("`") and "`" in path_text[1:]:
                path_text = path_text.split("`", 2)[1]
            # Trim trailing colon.
            path_text = path_text.removesuffix(":").strip()
            if not path_text:
                current_path = None
                continue
            current_path = (PROJECT_ROOT / path_text).resolve()
            continue

        # Nested bullet: Section: "Heading"
        if current_path is None:
            continue

        section = _SECTION_LINE.match(body)
        if section:
            raw_heading = _extract_section_heading(section.group("body"))
            if raw_heading:
                current_headings.append(raw_heading)

    if current_path is not None:
        anchors.append(SpecAnchor(current_path, tuple(current_headings)))

    if not anchors:
        _fail(f"{plan_path}: {SPEC_ANCHORS_HEADER!r} contains no spec file anchors")

    for anchor in anchors:
        if not anchor.headings:
            _fail(f"{plan_path}: spec anchor {anchor.path} has no Section entries")

    return anchors


def _find_heading_spans(md_text: str) -> dict[str, tuple[int, int]]:
    """Return normalized heading -> (start_line_idx, end_line_idx_exclusive)."""
    lines = md_text.splitlines()

    headings: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        m = _MD_HEADING.match(line)
        if not m:
            continue
        level = len(m.group("hashes"))
        title = m.group("title").strip()
        headings.append((i, level, title))

    spans: dict[str, tuple[int, int]] = {}
    for idx, (line_idx, level, title) in enumerate(headings):
        end = len(lines)
        for next_line_idx, next_level, _ in headings[idx + 1 :]:
            if next_level <= level:
                end = next_line_idx
                break
        spans[_normalize_heading(title)] = (line_idx, end)

    return spans


def _extract_function_signatures(plan_text: str) -> list[str]:
    sigs: list[str] = []
    for line in plan_text.splitlines():
        m = _SIGNATURE_BULLET.match(line)
        if not m:
            continue
        sig = m.group("sig").strip()
        if "(" not in sig or ")" not in sig:
            continue
        sigs.append(sig)
    return sigs


def _signature_name(signature: str) -> str:
    return signature.split("(", 1)[0].strip()


def validate_plan(plan_path: Path) -> None:
    plan_text = _read_text(plan_path)
    anchors = _extract_spec_anchors(plan_text, plan_path=plan_path)

    anchored_texts: list[str] = []
    for anchor in anchors:
        if not anchor.path.exists():
            _fail(f"{plan_path}: spec file does not exist: {anchor.path}")
        md_text = _read_text(anchor.path)
        spans = _find_heading_spans(md_text)

        lines = md_text.splitlines()
        for heading in anchor.headings:
            key = _normalize_heading(heading)
            if key not in spans:
                _fail(f"{plan_path}: missing heading {heading!r} in {anchor.path}")
            start, end = spans[key]
            anchored_texts.append("\n".join(lines[start:end]))

    signatures = _extract_function_signatures(plan_text)
    if not signatures:
        _fail(
            f"{plan_path}: no function signatures found; expected bullets like "
            "`function_name(arg: Type) -> ReturnType` under 'Functions to implement'"
        )

    anchored_blob = "\n\n".join(anchored_texts)
    missing: list[str] = []
    for sig in signatures:
        name = _signature_name(sig)
        # Accept either a Python def or any mention of the call form in the anchored section.
        if re.search(rf"\bdef\s+{re.escape(name)}\b", anchored_blob):
            continue
        if re.search(rf"\b{re.escape(name)}\s*\(", anchored_blob):
            continue
        missing.append(sig)

    if missing:
        joined = ", ".join(missing)
        _fail(
            f"{plan_path}: function signatures not found in anchored SSOT sections: {joined}. "
            "Fix by updating the referenced SSOT spec section(s) (or the Spec Anchors) before proceeding."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that a plan includes Spec Anchors and that planned function names are present in the anchored SSOT sections."
    )
    parser.add_argument(
        "plan_path",
        type=Path,
        help="Path to a .agent-workflow/runs/<RUN_ID>/plan-vN.md file",
    )
    args = parser.parse_args()

    plan_path: Path = args.plan_path
    if not plan_path.is_file():
        _fail(f"plan file not found: {plan_path}")
    validate_plan(plan_path)
    print(f"OK: Spec Anchors valid for {plan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
