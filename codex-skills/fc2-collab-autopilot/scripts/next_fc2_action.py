#!/usr/bin/env python3
"""
FC-2.0 helper: determine the next action (resume run vs start next checklist slice),
and propose a RUN_ID for the next slice.

This script is intentionally conservative:
- It never edits files.
- It does not try to infer "done" from the index (the checklist is authoritative for completion).
- It will surface PENDING_REVIEW / CHANGES_REQUIRED runs first so you don't start new work while a run is open.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKLIST_PATH = REPO_ROOT / "docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md"
INDEX_PATH = REPO_ROOT / ".agent-workflow/index.md"
RUNS_DIR = REPO_ROOT / ".agent-workflow/runs"


@dataclasses.dataclass(frozen=True)
class IndexRow:
    run_id: str
    target_item: str | None  # e.g. "6.7"
    verdict: str


@dataclasses.dataclass(frozen=True)
class ChecklistSection:
    phase: int
    item: int
    title: str
    first_unchecked_task: str | None
    first_unchecked_nonoptional_task: str | None

    @property
    def item_key(self) -> str:
        return f"{self.phase}.{self.item}"

    @property
    def preferred_unchecked_task(self) -> str | None:
        # This is intentionally "non-optional only" by default. Callers that want
        # to include optional tasks should set `first_unchecked_nonoptional_task`
        # accordingly (see `--include-optional` handling).
        return self.first_unchecked_nonoptional_task


def _iter_lines(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8") as f:
        yield from f


def parse_index_rows(path: Path) -> list[IndexRow]:
    """
    Parse `.agent-workflow/index.md` rows.

    Expected shape (markdown table):
    | RUN_ID | Target | Date | Verdict | Artifacts |
    """

    rows: list[IndexRow] = []

    for raw in _iter_lines(path):
        line = raw.rstrip("\n")
        if not line.startswith("|"):
            continue

        # Skip header separator rows.
        if "---" in line:
            continue

        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 6:
            continue

        run_id = cols[1]
        target = cols[2]
        verdict = cols[4]

        if not run_id or run_id == "RUN_ID":
            continue

        m_item = re.search(r"\bItem\s+(\d+\.\d+)\b", target)
        rows.append(
            IndexRow(
                run_id=run_id, target_item=m_item.group(1) if m_item else None, verdict=verdict
            )
        )

    return rows


def is_optional_task(task_text: str) -> bool:
    t = task_text.lower()
    return "(optional" in t or t.startswith("optional:")


def parse_checklist_sections(path: Path) -> list[ChecklistSection]:
    """
    Parse checklist sections of the form:
    ### 6.7 Runner & Phase Orchestration
    ... checkbox lines ...
    """

    header_re = re.compile(r"^###\s+(\d+)\.(\d+)\s+(.*)$")
    checkbox_re = re.compile(r"^-\s+\[(?P<state>[ xX])\]\s+(?P<task>.*)$")

    sections: list[ChecklistSection] = []
    cur_phase: int | None = None
    cur_item: int | None = None
    cur_title: str | None = None
    cur_first_unchecked: str | None = None
    cur_first_unchecked_nonopt: str | None = None

    def flush() -> None:
        nonlocal cur_phase, cur_item, cur_title, cur_first_unchecked, cur_first_unchecked_nonopt
        if cur_phase is None or cur_item is None or cur_title is None:
            return
        sections.append(
            ChecklistSection(
                phase=cur_phase,
                item=cur_item,
                title=cur_title,
                first_unchecked_task=cur_first_unchecked,
                first_unchecked_nonoptional_task=cur_first_unchecked_nonopt,
            )
        )
        cur_phase = None
        cur_item = None
        cur_title = None
        cur_first_unchecked = None
        cur_first_unchecked_nonopt = None

    for raw in _iter_lines(path):
        line = raw.rstrip("\n")

        m_header = header_re.match(line)
        if m_header:
            flush()
            cur_phase = int(m_header.group(1))
            cur_item = int(m_header.group(2))
            cur_title = m_header.group(3).strip()
            continue

        if cur_phase is None:
            continue

        m_cb = checkbox_re.match(line)
        if not m_cb:
            continue

        if m_cb.group("state") == " ":
            task = m_cb.group("task").strip()
            if cur_first_unchecked is None:
                cur_first_unchecked = task
            if cur_first_unchecked_nonopt is None and not is_optional_task(task):
                cur_first_unchecked_nonopt = task

    flush()
    return sections


def find_latest_review(run_id: str) -> Path | None:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        return None

    best: tuple[int, Path] | None = None
    for p in run_dir.iterdir():
        m = re.fullmatch(r"review-v(\d+)\.md", p.name)
        if not m:
            continue
        v = int(m.group(1))
        if best is None or v > best[0]:
            best = (v, p)
    return best[1] if best is not None else None


def parse_review_verdict(review_path: Path) -> str | None:
    verdict_re = re.compile(r"^##\s+Verdict:\s+([A-Z_]+)\s*$")
    for raw in _iter_lines(review_path):
        m = verdict_re.match(raw.rstrip("\n"))
        if m:
            return m.group(1)
    return None


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "task"


def derive_slug(task_text: str) -> str:
    """
    Derive a short RUN_ID slug from a checklist task string.

    Preference order:
    - a referenced `.py` filename (runner.py -> runner)
    - a referenced path basename
    - a filtered word-based slug
    """

    backticked = re.findall(r"`([^`]+)`", task_text)
    for token in backticked:
        base = os.path.basename(token)
        if base.endswith(".py"):
            return _slugify(base[:-3])
        if base:
            return _slugify(base)[:48]

    stop = {
        "create",
        "implement",
        "complete",
        "write",
        "update",
        "wire",
        "verify",
        "add",
        "run",
        "tests",
        "test",
        "unit",
        "integration",
        "per",
        "spec",
        "and",
        "or",
        "the",
        "a",
        "an",
        "to",
        "for",
        "of",
        "in",
        "at",
    }
    words = [w for w in re.split(r"\s+", re.sub(r"[`.,:;()]", " ", task_text)) if w]
    picked: list[str] = []
    for w in words:
        wl = w.lower()
        if wl in stop:
            continue
        picked.append(wl)
        if len(picked) >= 5:
            break

    return _slugify("-".join(picked))[:48]


def next_slice_number(phase: int, item: int, runs_dir: Path) -> int | None:
    """
    If this checklist item is already being split into sub-slices (pX-Y-N),
    return the next N. Otherwise return None (meaning use unsliced pX-Y).
    """

    # Match both run dirs and any other possible names; be strict enough to avoid false positives.
    sliced = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}__p{phase}-{item}-(\d+)__")
    unsliced = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}__p{phase}-{item}__")

    max_n: int | None = None
    seen_unsliced = False

    if not runs_dir.exists():
        return None

    for entry in runs_dir.iterdir():
        name = entry.name
        m_s = sliced.match(name)
        if m_s:
            n = int(m_s.group(1))
            max_n = n if max_n is None else max(max_n, n)
            continue
        if unsliced.match(name):
            seen_unsliced = True

    if max_n is not None:
        return max_n + 1

    # If an unsliced run already exists, future runs should use slices to avoid collisions.
    if seen_unsliced:
        # Treat the unsliced run as the implicit "slice 1" and start at 2.
        return 2

    return None


def propose_run_id(phase: int, item: int, task_text: str, runs_dir: Path) -> str:
    today = dt.date.today().isoformat()
    slug = derive_slug(task_text)
    next_slice = next_slice_number(phase=phase, item=item, runs_dir=runs_dir)
    if next_slice is None:
        return f"{today}__p{phase}-{item}__{slug}"
    return f"{today}__p{phase}-{item}-{next_slice}__{slug}"


def find_next_section(sections: Iterable[ChecklistSection]) -> ChecklistSection | None:
    for s in sections:
        if s.preferred_unchecked_task is not None:
            return s
    return None


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    include_phase0 = "--include-phase0" in argv
    min_phase = 0 if include_phase0 else 1
    include_optional = "--include-optional" in argv

    if not CHECKLIST_PATH.exists():
        raise FileNotFoundError(f"Missing checklist: {CHECKLIST_PATH}")
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Missing index: {INDEX_PATH}")

    index_rows = parse_index_rows(INDEX_PATH)

    pending = [r for r in index_rows if r.verdict == "PENDING_REVIEW"]
    if pending:
        chosen = pending[-1]
        latest_review = find_latest_review(chosen.run_id)
        if latest_review is not None:
            verdict = parse_review_verdict(latest_review)
            payload = {
                "action": "repair_stale_pending_review",
                "run_id": chosen.run_id,
                "latest_review": str(latest_review),
                "latest_review_verdict": verdict,
                "hint": "Index shows PENDING_REVIEW but a review artifact exists. Repair the index row (add review link + final verdict) before starting new work.",
            }
        else:
            payload = {
                "action": "resume_pending_review",
                "run_id": chosen.run_id,
                "hint": "Run the Review role for this RUN_ID; do not start a new run.",
            }
        if as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"ACTION: {payload['action']}\nRUN_ID: {chosen.run_id}")
            if payload["action"] == "repair_stale_pending_review":
                print(f"REVIEW: {payload['latest_review']}")
                if payload.get("latest_review_verdict"):
                    print(f"VERDICT: {payload['latest_review_verdict']}")
        return 0

    changes_required = [r for r in index_rows if r.verdict == "CHANGES_REQUIRED"]
    if changes_required:
        chosen = changes_required[-1]
        payload = {
            "action": "resume_changes_required",
            "run_id": chosen.run_id,
            "hint": "Resume this RUN_ID (apply review changes -> verify -> review). Do not start a new run.",
        }
        if as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"ACTION: resume_changes_required\nRUN_ID: {chosen.run_id}")
        return 0

    design_issue = [r for r in index_rows if r.verdict == "DESIGN_ISSUE"]
    if design_issue:
        chosen = design_issue[-1]
        payload = {
            "action": "stop_design_issue",
            "run_id": chosen.run_id,
            "hint": "Latest run ended with DESIGN_ISSUE. Return to Planning/Plan Review for that run before new work.",
        }
        if as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"ACTION: stop_design_issue\nRUN_ID: {chosen.run_id}")
        return 2

    raw_sections = [s for s in parse_checklist_sections(CHECKLIST_PATH) if s.phase >= min_phase]
    sections: list[ChecklistSection] = []
    for s in raw_sections:
        if include_optional:
            sections.append(
                ChecklistSection(
                    phase=s.phase,
                    item=s.item,
                    title=s.title,
                    first_unchecked_task=s.first_unchecked_task,
                    first_unchecked_nonoptional_task=s.first_unchecked_task,
                )
            )
        else:
            sections.append(s)
    next_section = find_next_section(sections)
    if next_section is None:
        payload = {"action": "done", "hint": "No unchecked checklist sections found."}
        if as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("ACTION: done\nHINT: No unchecked checklist sections found.")
        return 0

    next_task = next_section.preferred_unchecked_task
    assert next_task is not None
    run_id = propose_run_id(
        phase=next_section.phase,
        item=next_section.item,
        task_text=next_task,
        runs_dir=RUNS_DIR,
    )

    payload = {
        "action": "start_new_run",
        "run_id": run_id,
        "target": f"Phase {next_section.phase} → Item {next_section.item_key}",
        "checklist_section_title": next_section.title,
        "first_unchecked_task": next_task,
        "paths": {
            "checklist": str(CHECKLIST_PATH),
            "index": str(INDEX_PATH),
            "runs_dir": str(RUNS_DIR),
        },
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"ACTION: start_new_run\nRUN_ID: {run_id}")
        print(f"TARGET: Phase {next_section.phase} → Item {next_section.item_key}")
        print(f"SECTION: {next_section.title}")
        print(f"NEXT_TASK: {next_section.first_unchecked_task}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
