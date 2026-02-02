#!/usr/bin/env python3
"""
Validate that the FC2 master checklist ordering won't mislead automated orchestration.

Checks (phases >= 1 only):
- Within each '### X.Y' section, once the first unchecked task appears, there must not be a later checked task.
  (This indicates tasks were completed out-of-order OR the checklist order is wrong for reality.)

This is intentionally conservative: if you need to defer a task, move it later in the section or mark it optional.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_PATH = REPO_ROOT / "docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md"


@dataclass(frozen=True)
class Violation:
    section: str
    first_unchecked_line: int
    later_checked_line: int
    later_checked_task: str


def main() -> int:
    text = CHECKLIST_PATH.read_text(encoding="utf-8").splitlines()

    sec_re = re.compile(r"^###\s+(?P<phase>\d+)\.(?P<item>\d+)\s+(?P<title>.*)$")
    cb_re = re.compile(r"^-\s+\[(?P<state>[ xX])\]\s+(?P<task>.*)$")

    cur_key: str | None = None
    cur_phase: int | None = None
    first_unchecked: tuple[int, str] | None = None
    violations: list[Violation] = []

    def flush() -> None:
        nonlocal cur_key, cur_phase, first_unchecked
        cur_key = None
        cur_phase = None
        first_unchecked = None

    for i, line in enumerate(text, start=1):
        m_sec = sec_re.match(line)
        if m_sec:
            flush()
            cur_phase = int(m_sec.group("phase"))
            cur_key = f"{m_sec.group('phase')}.{m_sec.group('item')} {m_sec.group('title').strip()}"
            continue

        if cur_key is None or cur_phase is None or cur_phase < 1:
            continue

        m_cb = cb_re.match(line)
        if not m_cb:
            continue

        checked = m_cb.group("state") != " "
        task = m_cb.group("task").strip()

        if not checked and first_unchecked is None:
            first_unchecked = (i, task)
            continue

        if checked and first_unchecked is not None:
            fu_line, _fu_task = first_unchecked
            violations.append(
                Violation(
                    section=cur_key,
                    first_unchecked_line=fu_line,
                    later_checked_line=i,
                    later_checked_task=task,
                )
            )

    if not violations:
        print("OK: master checklist ordering is monotonic (phases >= 1).")
        return 0

    print(
        "ERROR: master checklist ordering has checked items after an unchecked item (phases >= 1):",
        file=sys.stderr,
    )
    for v in violations:
        print(
            f"- {v.section}: first unchecked at line {v.first_unchecked_line}; "
            f"later checked at line {v.later_checked_line}: {v.later_checked_task}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
