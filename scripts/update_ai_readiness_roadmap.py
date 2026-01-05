#!/usr/bin/env python3
"""Update `AI_READINESS_ROADMAP.md` readiness gate table from a JSON SSOT.

This script does NOT run the gates. It keeps the table's commands (and optionally timestamps)
in sync with `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_GATES_PATH = (
    PROJECT_ROOT / "docs" / "OPUS_REBUILD_FRAME_COMPARE" / "contracts" / "readiness_gates.json"
)
ROADMAP_PATH = PROJECT_ROOT / "AI_READINESS_ROADMAP.md"

BEGIN_MARKER = "<!-- BEGIN GENERATED:readiness-gates -->"
END_MARKER = "<!-- END GENERATED:readiness-gates -->"


@dataclass(frozen=True)
class ReadinessGate:
    gate_id: str
    name: str
    cwd: str
    command: str

    def display_command(self) -> str:
        if self.cwd == ".":
            return self.command
        return f"(cd {self.cwd} && {self.command})"


def _parse_checked_at(checked_at: str | None) -> str:
    if checked_at is None:
        now = datetime.now(UTC)
        return now.strftime("%Y-%m-%d %H:%M")
    try:
        datetime.strptime(checked_at, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise SystemExit(
            f"Invalid --checked-at {checked_at!r}; expected 'YYYY-MM-DD HH:MM' (UTC)."
        ) from exc
    return checked_at


def load_gates(path: Path) -> list[ReadinessGate]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_gates = data.get("gates")
    if not isinstance(raw_gates, list):
        raise SystemExit(f"Invalid gates file: {path} (missing 'gates' list)")

    gates: list[ReadinessGate] = []
    for raw_gate in raw_gates:
        if not isinstance(raw_gate, dict):
            raise SystemExit(f"Invalid gates file: {path} (gate is not an object)")
        gate_id = raw_gate.get("id")
        name = raw_gate.get("name")
        cwd = raw_gate.get("cwd")
        command = raw_gate.get("command")
        if not isinstance(gate_id, str) or not gate_id:
            raise SystemExit(f"Invalid gates file: {path} (gate missing string 'id')")
        if not isinstance(name, str) or not name:
            raise SystemExit(f"Invalid gates file: {path} (gate {gate_id} missing string 'name')")
        if not isinstance(cwd, str) or not cwd:
            raise SystemExit(f"Invalid gates file: {path} (gate {gate_id} missing string 'cwd')")
        if not isinstance(command, str) or not command:
            raise SystemExit(
                f"Invalid gates file: {path} (gate {gate_id} missing string 'command')"
            )
        gates.append(ReadinessGate(gate_id=gate_id, name=name, cwd=cwd, command=command))

    return gates


def _extract_existing_statuses(table_lines: list[str]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for line in table_lines:
        if not line.strip().startswith("|"):
            continue
        # | Gate | Command | Status | Last Checked (UTC) |
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) != 4:
            continue
        gate_name, _cmd, status, _checked = parts
        if gate_name == "Gate":
            continue
        statuses[gate_name] = status
    return statuses


def render_table(gates: list[ReadinessGate], *, checked_at: str, existing_block: str | None) -> str:
    existing_statuses: dict[str, str] = {}
    if existing_block is not None:
        existing_statuses = _extract_existing_statuses(existing_block.splitlines())

    lines: list[str] = []
    lines.append("| Gate | Command | Status | Last Checked (UTC) |")
    lines.append("|:-----|:--------|:------:|:-------------------|")
    for gate in gates:
        status = existing_statuses.get(gate.name, "✅")
        lines.append(f"| {gate.name} | `{gate.display_command()}` | {status} | {checked_at} |")
    return "\n".join(lines) + "\n"


def _extract_marked_block(content: str) -> str:
    start = content.find(BEGIN_MARKER)
    end = content.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(
            f"Missing or malformed markers in {ROADMAP_PATH}: add {BEGIN_MARKER} and {END_MARKER}."
        )

    after_start = start + len(BEGIN_MARKER)
    return content[after_start:end].strip("\n")


def _replace_marked_block(content: str, replacement: str) -> str:
    start = content.find(BEGIN_MARKER)
    end = content.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(
            f"Missing or malformed markers in {ROADMAP_PATH}: add {BEGIN_MARKER} and {END_MARKER}."
        )

    after_start = start + len(BEGIN_MARKER)
    return content[:after_start] + "\n" + replacement + content[end:]


def _update_last_updated_line(content: str, checked_at: str) -> str:
    pattern = re.compile(r"^> \*\*Last Updated:\*\* .+ UTC\s*$", re.MULTILINE)
    repl = f"> **Last Updated:** {checked_at} UTC"
    if not pattern.search(content):
        raise SystemExit(f"Could not find 'Last Updated' line in {ROADMAP_PATH}")
    return pattern.sub(repl, content, count=1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update AI_READINESS_ROADMAP.md readiness gates table from readiness_gates.json"
    )
    parser.add_argument(
        "--gates",
        type=Path,
        default=DEFAULT_GATES_PATH,
        help="Path to readiness_gates.json (default: contracts/readiness_gates.json)",
    )
    parser.add_argument(
        "--checked-at",
        help="UTC timestamp to set for all gates: 'YYYY-MM-DD HH:MM' (default: now)",
    )
    args = parser.parse_args()

    checked_at = _parse_checked_at(args.checked_at)
    gates = load_gates(args.gates)

    content = ROADMAP_PATH.read_text(encoding="utf-8")
    content = _update_last_updated_line(content, checked_at)
    existing_block = _extract_marked_block(content)
    content = _replace_marked_block(
        content, render_table(gates, checked_at=checked_at, existing_block=existing_block)
    )
    ROADMAP_PATH.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
