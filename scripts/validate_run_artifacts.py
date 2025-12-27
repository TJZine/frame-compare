#!/usr/bin/env python3
"""Validate `.agent-workflow/runs/<RUN_ID>/` artifact hygiene.

Checks:
  - RUN_ID format (via the same regex rules as `scripts/validate_run_id.py`)
  - Required YAML frontmatter keys exist and match:
    RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS
  - VERSION matches the `*-vN.md` filename
  - The artifact ends with a `## NEXT AGENT PROMPT (COPY/PASTE)` block
  - Current-run artifacts contain no placeholder tokens inside the NEXT block
    (exception: `NEW_RUN_ID` is allowed only in `review-vN.md` APPROVED next-run stub)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_RUNS_ROOT = PROJECT_ROOT / ".agent-workflow" / "runs"

RUN_ID_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})__(?P<kind>p\d+-\d+(?:-\d+)*|meta)__(?P<slug>[a-z0-9][a-z0-9-]*)$"
)

ARTIFACT_PATTERN = re.compile(r"^(?P<stage>plan|plan-review|impl|verify|review)-v(?P<version>\d+)\.md$")

NEXT_HEADER = "## NEXT AGENT PROMPT (COPY/PASTE)"

FORBIDDEN_PLACEHOLDER_SNIPPETS = (
    "[INSERT ACTUAL RUN_ID]",
    "[actual-run-id]",
    "<RUN_ID>",
    "[RUN_ID]",
    ".agent-workflow/runs/RUN_ID/",
    "[artifact-vN].md",
    "[output-file].md",
    "[Next Agent Name]",
    "[Brief task description]",
)

_NEXT_BLOCK_VERSION_REF = re.compile(
    r"(?P<stage>plan|plan-review|impl|verify|review)-v(?P<token>[^\s/`]+)\.md"
)


@dataclass(frozen=True)
class Frontmatter:
    run_id: str
    version: str
    target: str
    inputs: list[str]
    outputs: list[str]


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_run_id_format(run_id: str) -> None:
    if RUN_ID_PATTERN.match(run_id) is None:
        _fail(
            f"RUN_ID {run_id!r} invalid; expected YYYY-MM-DD__p<phase>-<item>__<slug> or YYYY-MM-DD__meta__<slug>"
        )


def _parse_frontmatter(text: str, path: Path) -> Frontmatter:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        _fail(f"{path}: missing YAML frontmatter (expected starting '---')")

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        _fail(f"{path}: unterminated YAML frontmatter (missing closing '---')")

    raw = lines[1:end_idx]
    current_key: str | None = None
    values: dict[str, str] = {}
    lists: dict[str, list[str]] = {"INPUTS": [], "OUTPUTS": []}

    for line in raw:
        if not line.strip():
            continue
        if re.match(r"^[A-Z_]+:\s*", line):
            key, _, rest = line.partition(":")
            key = key.strip()
            current_key = key
            if key in ("INPUTS", "OUTPUTS"):
                # list starts on following indented lines
                continue
            values[key] = rest.strip()
            continue

        if current_key in ("INPUTS", "OUTPUTS"):
            stripped = line.strip()
            if stripped.startswith("- "):
                lists[current_key].append(stripped.removeprefix("- ").strip())
                continue

    run_id = values.get("RUN_ID")
    version = values.get("VERSION")
    target = values.get("TARGET")
    if not run_id:
        _fail(f"{path}: frontmatter missing RUN_ID")
    if not version:
        _fail(f"{path}: frontmatter missing VERSION")
    if not target:
        _fail(f"{path}: frontmatter missing TARGET")
    if not lists["INPUTS"]:
        _fail(f"{path}: frontmatter missing INPUTS list entries")
    if not lists["OUTPUTS"]:
        _fail(f"{path}: frontmatter missing OUTPUTS list entries")

    return Frontmatter(
        run_id=run_id,
        version=version,
        target=target,
        inputs=lists["INPUTS"],
        outputs=lists["OUTPUTS"],
    )


def _extract_next_block(text: str, path: Path) -> str:
    idx = text.rfind(NEXT_HEADER)
    if idx == -1:
        _fail(f"{path}: missing required '{NEXT_HEADER}' block")
    return text[idx:]


def _validate_next_block_placeholders(next_block: str, *, allow_new_run_id: bool, path: Path) -> None:
    for snippet in FORBIDDEN_PLACEHOLDER_SNIPPETS:
        if snippet in next_block:
            _fail(f"{path}: NEXT block contains placeholder token: {snippet!r}")

    for match in _NEXT_BLOCK_VERSION_REF.finditer(next_block):
        token = match.group("token")
        if not token.isdigit():
            _fail(
                f"{path}: NEXT block contains non-concrete version token in {match.group(0)!r} "
                "(expected digits only, like -v1.md)"
            )

    if "NEW_RUN_ID" in next_block:
        if not allow_new_run_id:
            _fail(f"{path}: NEXT block contains NEW_RUN_ID (only allowed in review artifacts)")

        # Only allow NEW_RUN_ID when it is used as the Review-APPROVED next-run stub.
        required_snippets = (
            "You are the Planning Agent",
            "Write file: .agent-workflow/runs/NEW_RUN_ID/plan-v1.md",
        )
        missing = [snippet for snippet in required_snippets if snippet not in next_block]
        if missing:
            _fail(
                f"{path}: NEXT block contains NEW_RUN_ID but is missing required next-run stub content: "
                + ", ".join(repr(snippet) for snippet in missing)
            )


def validate_artifact(path: Path, run_id: str) -> None:
    match = ARTIFACT_PATTERN.match(path.name)
    if match is None:
        _fail(f"{path}: unexpected filename (expected (plan|plan-review|impl|verify|review)-vN.md)")

    expected_version = f"v{match.group('version')}"
    stage = match.group("stage")
    allow_new_run_id = stage == "review"

    text = path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text, path)

    if fm.run_id != run_id:
        _fail(f"{path}: frontmatter RUN_ID {fm.run_id!r} does not match directory RUN_ID {run_id!r}")
    validate_run_id_format(fm.run_id)

    if fm.version != expected_version:
        _fail(f"{path}: frontmatter VERSION {fm.version!r} does not match filename VERSION {expected_version!r}")

    next_block = _extract_next_block(text, path)
    _validate_next_block_placeholders(next_block, allow_new_run_id=allow_new_run_id, path=path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate run artifacts under .agent-workflow/runs/<RUN_ID>/")
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to .agent-workflow/runs/<RUN_ID>/",
    )
    args = parser.parse_args()

    run_dir: Path = args.run_dir
    if not run_dir.exists() or not run_dir.is_dir():
        _fail(f"Run directory not found: {run_dir}")

    run_id = run_dir.name
    validate_run_id_format(run_id)

    artifacts = sorted([p for p in run_dir.iterdir() if p.is_file() and p.suffix == ".md"])
    if not artifacts:
        _fail(f"{run_dir}: no .md artifacts found")

    had_any_expected = False
    for artifact in artifacts:
        if ARTIFACT_PATTERN.match(artifact.name) is None:
            continue
        had_any_expected = True
        validate_artifact(artifact, run_id)

    if not had_any_expected:
        _fail(f"{run_dir}: no stage artifacts found matching (plan|plan-review|impl|verify|review)-vN.md")

    print(f"OK: Run artifacts valid for {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
