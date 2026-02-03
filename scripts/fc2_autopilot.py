#!/usr/bin/env python3
"""
FC-2.0 Autopilot (local).

This is a thin controller that shells out to separate local Codex CLI sessions (profiles)
to run the standard FC-2.0 workflow end-to-end:

- Select next action (resume pending vs start new)
- Planning <-> Plan Review loop until APPROVED + Decision Points Remaining = NONE
- Coding
- Verification + Review (optionally in a single session)

It enforces FC2 STOP gates by validating artifact hygiene and parsing plan-review/review verdicts.

Design constraints:
- No network required.
- Deterministic version selection (no "latest" in prompts; controller computes exact vN).
- Conservative: stops early rather than guessing.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from contextlib import suppress
from pathlib import Path

from fc2_autopilot_engine import (
    ROLE_CODING,
    ROLE_PLAN_REVIEW,
    ROLE_PLANNING,
    ROLE_POLICY,
    ROLE_VERIFY_REVIEW,
    AppServerEngine,
    AutopilotEngine,
    AutopilotStopError,
    ExecEngine,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / ".agent-workflow" / "runs"
INDEX_PATH = REPO_ROOT / ".agent-workflow" / "index.md"
CHECKLIST_PATH = REPO_ROOT / "docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md"
NEXT_ACTION_SCRIPT = REPO_ROOT / "codex-skills/fc2-collab-autopilot/scripts/next_fc2_action.py"
LOCK_PATH = REPO_ROOT / ".agent-workflow" / ".autopilot.lock"


PLAN_STAGE = "plan"
PLAN_REVIEW_STAGE = "plan-review"
IMPL_STAGE = "impl"
VERIFY_STAGE = "verify"
REVIEW_STAGE = "review"

QUALITY_GATES_COMMANDS: list[list[str]] = [
    [".venv/bin/pyright", "--warnings"],
    [".venv/bin/ruff", "check", "."],
    [".venv/bin/pytest", "-q"],
    ["uv", "run", "--no-sync", "lint-imports", "--config", "importlinter.ini"],
    ["uv", "run", "--no-sync", "python", "scripts/generate_contract_views.py", "--check"],
    ["uv", "run", "--no-sync", "python", "scripts/validate_traceability.py", "--check"],
]


@dataclasses.dataclass(frozen=True)
class RunAction:
    action: str
    run_id: str
    hint: str | None
    target: str | None = None
    checklist_section_title: str | None = None
    first_unchecked_task: str | None = None
    latest_review: str | None = None
    latest_review_verdict: str | None = None


@dataclasses.dataclass(frozen=True)
class ChecklistTask:
    text: str
    checked: bool
    optional: bool


@dataclasses.dataclass(frozen=True)
class ChecklistSection:
    phase: int
    item: int
    title: str
    tasks: list[ChecklistTask]

    @property
    def item_key(self) -> str:
        return f"{self.phase}.{self.item}"


@dataclasses.dataclass(frozen=True)
class BundleSelection:
    section_title: str
    tasks: list[str]
    phase: int | None = None
    item: int | None = None
    phase_label: str | None = None
    is_quality_gate: bool = False


@dataclasses.dataclass(frozen=True)
class GateFailure(Exception):
    command: list[str]
    stdout: str
    stderr: str

    def format_for_prompt(self) -> str:
        cmd = " ".join(_shlex_quote(a) for a in self.command)
        out = (self.stdout or "").strip()
        err = (self.stderr or "").strip()
        return textwrap.dedent(
            f"""
            Gate command failed:
            {cmd}

            stdout:
            {out or "<empty>"}

            stderr:
            {err or "<empty>"}
            """
        ).strip()


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    if dry_run:
        joined = " ".join(_shlex_quote(a) for a in argv)
        print(f"[dry-run] {joined}")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=merged_env,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def _shlex_quote(s: str) -> str:
    # Minimal shell quoting for logging.
    if re.fullmatch(r"[A-Za-z0-9_./:=+-]+", s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _is_optional_task(task_text: str) -> bool:
    t = task_text.lower()
    return "(optional" in t or t.startswith("optional:")


def _parse_checklist_sections(path: Path) -> list[ChecklistSection]:
    header_re = re.compile(r"^###\s+(\d+)\.(\d+)\s+(.*)$")
    checkbox_re = re.compile(r"^-\s+\[(?P<state>[ xX])\]\s+(?P<task>.*)$")

    sections: list[ChecklistSection] = []
    cur_phase: int | None = None
    cur_item: int | None = None
    cur_title: str | None = None
    cur_tasks: list[ChecklistTask] = []

    def flush() -> None:
        nonlocal cur_phase, cur_item, cur_title, cur_tasks
        if cur_phase is None or cur_item is None or cur_title is None:
            return
        sections.append(
            ChecklistSection(
                phase=cur_phase,
                item=cur_item,
                title=cur_title,
                tasks=cur_tasks,
            )
        )
        cur_phase = None
        cur_item = None
        cur_title = None
        cur_tasks = []

    for raw in _read_text(path).splitlines():
        m_header = header_re.match(raw)
        if m_header:
            flush()
            cur_phase = int(m_header.group(1))
            cur_item = int(m_header.group(2))
            cur_title = m_header.group(3).strip()
            continue

        if cur_phase is None:
            continue

        m_cb = checkbox_re.match(raw)
        if not m_cb:
            continue

        checked = m_cb.group("state") in ("x", "X")
        task_text = m_cb.group("task").strip()
        cur_tasks.append(
            ChecklistTask(
                text=task_text,
                checked=checked,
                optional=_is_optional_task(task_text),
            )
        )

    flush()
    return sections


def _parse_bundle_prefix(prefix: str) -> tuple[int, int]:
    if "." not in prefix:
        raise AutopilotStopError(
            f"STOP: invalid --bundle-prefix {prefix!r}; expected format like '7.1'."
        )
    phase_text, item_text = prefix.split(".", 1)
    if not phase_text.isdigit() or not item_text.isdigit():
        raise AutopilotStopError(
            f"STOP: invalid --bundle-prefix {prefix!r}; expected numeric format like '7.1'."
        )
    return int(phase_text), int(item_text)


@dataclasses.dataclass(frozen=True)
class NamedSection:
    header: str
    tasks: list[ChecklistTask]


def _parse_named_sections(path: Path) -> list[NamedSection]:
    header_re = re.compile(r"^###\s+(.*)$")
    checkbox_re = re.compile(r"^-\s+\[(?P<state>[ xX])\]\s+(?P<task>.*)$")

    sections: list[NamedSection] = []
    current_header: str | None = None
    current_tasks: list[ChecklistTask] = []

    def flush() -> None:
        nonlocal current_header, current_tasks
        if current_header is None:
            return
        sections.append(NamedSection(header=current_header, tasks=current_tasks))
        current_header = None
        current_tasks = []

    for raw in _read_text(path).splitlines():
        m_header = header_re.match(raw)
        if m_header:
            flush()
            current_header = m_header.group(1).strip()
            continue

        if current_header is None:
            continue

        m_cb = checkbox_re.match(raw)
        if not m_cb:
            continue

        checked = m_cb.group("state") in ("x", "X")
        task_text = m_cb.group("task").strip()
        current_tasks.append(
            ChecklistTask(
                text=task_text,
                checked=checked,
                optional=_is_optional_task(task_text),
            )
        )

    flush()
    return sections


def _parse_phase_label_from_title(title: str) -> str | None:
    match = re.match(r"^Phase\s+(\d+(?:\.\d+)?)\b", title)
    if not match:
        return None
    return match.group(1)


def _parse_numeric_section_from_header(header: str) -> tuple[int, int] | None:
    match = re.match(r"^(?P<phase>\d+)\.(?P<item>\d+)\s+", header)
    if not match:
        return None
    return int(match.group("phase")), int(match.group("item"))


def _select_bundle_by_prefix(
    *,
    prefix: str,
    count: int,
    include_optional: bool,
) -> BundleSelection:
    phase, item = _parse_bundle_prefix(prefix)
    sections = _parse_checklist_sections(CHECKLIST_PATH)
    section = next((s for s in sections if s.phase == phase and s.item == item), None)
    if section is None:
        raise AutopilotStopError(f"STOP: no checklist section found for prefix {prefix!r}.")

    candidates = [
        t.text for t in section.tasks if not t.checked and (include_optional or not t.optional)
    ]
    if count == 0:
        count = len(candidates)
    if count < 2:
        raise AutopilotStopError("STOP: --bundle-count must be at least 2 for bundling.")
    if len(candidates) < count:
        raise AutopilotStopError(
            "STOP: not enough unchecked tasks to satisfy bundle request "
            f"({len(candidates)} available, {count} requested) for {prefix}."
        )
    return BundleSelection(
        section_title=section.title,
        tasks=candidates[:count],
        phase=phase,
        item=item,
        phase_label=str(phase),
        is_quality_gate=False,
    )


def _select_bundle_by_title(
    *,
    title: str,
    count: int,
    include_optional: bool,
) -> BundleSelection:
    sections = _parse_named_sections(CHECKLIST_PATH)
    section = next((s for s in sections if s.header == title), None)
    if section is None:
        raise AutopilotStopError(f"STOP: no checklist section found titled {title!r}.")
    candidates = [
        t.text for t in section.tasks if not t.checked and (include_optional or not t.optional)
    ]
    if count == 0:
        count = len(candidates)
    if count < 2:
        raise AutopilotStopError("STOP: --bundle-count must be at least 2 for bundling.")
    if len(candidates) < count:
        raise AutopilotStopError(
            "STOP: not enough unchecked tasks to satisfy bundle request "
            f"({len(candidates)} available, {count} requested) for {title!r}."
        )
    numeric = _parse_numeric_section_from_header(title)
    phase_label = _parse_phase_label_from_title(title)
    is_quality_gate = "Quality Gate" in title
    return BundleSelection(
        section_title=title,
        tasks=candidates[:count],
        phase=numeric[0] if numeric else None,
        item=numeric[1] if numeric else None,
        phase_label=phase_label,
        is_quality_gate=is_quality_gate,
    )


def _select_bundle_by_items(
    *,
    items: list[str],
    include_optional: bool,
) -> BundleSelection:
    if len(items) < 2:
        raise AutopilotStopError("STOP: --bundle-items must include at least 2 tasks.")
    sections = _parse_named_sections(CHECKLIST_PATH)
    lookup: list[tuple[NamedSection, ChecklistTask]] = []
    for s in sections:
        for t in s.tasks:
            lookup.append((s, t))

    selected: list[tuple[NamedSection, ChecklistTask]] = []
    for item_text in items:
        matches = [(s, t) for s, t in lookup if t.text == item_text]
        if not matches:
            raise AutopilotStopError(f"STOP: bundle item not found in checklist: {item_text!r}")
        if len(matches) > 1:
            raise AutopilotStopError(
                f"STOP: bundle item is ambiguous (appears multiple times): {item_text!r}"
            )
        section, task = matches[0]
        if task.checked:
            raise AutopilotStopError(
                f"STOP: bundle item already checked in checklist: {item_text!r}"
            )
        if task.optional and not include_optional:
            raise AutopilotStopError(
                "STOP: bundle item is marked optional but --include-optional not set: "
                f"{item_text!r}"
            )
        selected.append((section, task))

    section_headers = {s.header for s, _ in selected}
    if len(section_headers) != 1:
        raise AutopilotStopError(
            "STOP: bundled items span multiple checklist sections; bundle must stay within "
            "a single section (e.g., 7.1)."
        )

    section = selected[0][0]
    ordered = [t.text for t in section.tasks if any(t.text == sel[1].text for sel in selected)]
    numeric = _parse_numeric_section_from_header(section.header)
    phase_label = _parse_phase_label_from_title(section.header)
    is_quality_gate = "Quality Gate" in section.header
    return BundleSelection(
        section_title=section.header,
        tasks=ordered,
        phase=numeric[0] if numeric else None,
        item=numeric[1] if numeric else None,
        phase_label=phase_label,
        is_quality_gate=is_quality_gate,
    )


def _find_latest_version(run_dir: Path, stage: str) -> int | None:
    best: int | None = None
    pat = re.compile(rf"^{re.escape(stage)}-v(\d+)\.md$")
    if not run_dir.exists():
        return None
    for p in run_dir.iterdir():
        m = pat.match(p.name)
        if not m:
            continue
        v = int(m.group(1))
        best = v if best is None else max(best, v)
    return best


def _next_version(run_dir: Path, stage: str) -> int:
    latest = _find_latest_version(run_dir, stage)
    return 1 if latest is None else latest + 1


def _artifact_path(run_id: str, stage: str, version: int) -> Path:
    return RUNS_DIR / run_id / f"{stage}-v{version}.md"


def _validate_run_artifacts(run_id: str, *, dry_run: bool) -> None:
    env = {"UV_CACHE_DIR": "./.uv_cache"}
    cmd = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "scripts/validate_run_artifacts.py",
        str(RUNS_DIR / run_id),
    ]
    if dry_run:
        _run(cmd, cwd=REPO_ROOT, env=env, dry_run=True)
        return
    try:
        _run(cmd, cwd=REPO_ROOT, env=env, capture=True, dry_run=False)
    except subprocess.CalledProcessError as e:
        raise GateFailure(command=cmd, stdout=e.stdout or "", stderr=e.stderr or "") from e


def _validate_spec_anchors(plan_path: Path, *, dry_run: bool) -> None:
    env = {"UV_CACHE_DIR": "./.uv_cache"}
    cmd = ["uv", "run", "--no-sync", "python", "scripts/validate_spec_anchors.py", str(plan_path)]
    if dry_run:
        _run(cmd, cwd=REPO_ROOT, env=env, dry_run=True)
        return
    try:
        _run(cmd, cwd=REPO_ROOT, env=env, capture=True, dry_run=False)
    except subprocess.CalledProcessError as e:
        raise GateFailure(command=cmd, stdout=e.stdout or "", stderr=e.stderr or "") from e


def _run_quality_gates(*, dry_run: bool) -> None:
    env = {"UV_CACHE_DIR": "./.uv_cache"}
    for cmd in QUALITY_GATES_COMMANDS:
        if dry_run:
            _run(cmd, cwd=REPO_ROOT, env=env, dry_run=True)
            continue
        try:
            proc = _run(cmd, cwd=REPO_ROOT, env=env, capture=True, dry_run=False)
        except subprocess.CalledProcessError as e:
            raise GateFailure(command=cmd, stdout=e.stdout or "", stderr=e.stderr or "") from e
        # Some tools (notably pyright) can emit to stderr on success in some environments;
        # we intentionally do not treat non-empty stderr as failure here.
        _ = proc


def _format_quality_gates_for_prompt() -> str:
    lines: list[str] = []
    for cmd in QUALITY_GATES_COMMANDS:
        rendered = " ".join(_shlex_quote(a) for a in cmd)
        if cmd[:2] == ["uv", "run"]:
            rendered = f"UV_CACHE_DIR=./.uv_cache {rendered}"
        lines.append(rendered)
    # Use a fenced block so we don't accidentally create confusing nested bullets.
    return "```bash\n" + "\n".join(lines) + "\n```"


def _parse_plan_review_gate(plan_review_path: Path) -> tuple[str | None, str | None]:
    verdict: str | None = None
    dp: str | None = None
    for raw in _read_text(plan_review_path).splitlines():
        stripped = raw.strip()
        m_v = re.match(r"##\s+Verdict:\s+([A-Z_]+)", stripped)
        if m_v:
            verdict = m_v.group(1)
        if "Implementation Agent Decision Points Remaining:" in raw:
            _, _, rest = raw.partition(":")
            dp = _normalize_decision_points(rest)
    return verdict, dp


def _parse_review_verdict(review_path: Path) -> str | None:
    for raw in _read_text(review_path).splitlines():
        m = re.fullmatch(r"##\s+Verdict:\s+([A-Z_]+)\s*", raw.strip())
        if m:
            return m.group(1)
    return None


def _normalize_decision_points(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    # Strip common markdown emphasis/backticks and trailing punctuation.
    value = re.sub(r"[`*_]", "", value)
    value = value.strip().rstrip(".").strip()
    if not value:
        return None
    return value.upper()


def _extract_spec_anchor_paths(plan_path: Path) -> list[Path]:
    header = "## Spec Anchors (SSOT)"
    lines = _read_text(plan_path).splitlines()
    try:
        start_idx = lines.index(header)
    except ValueError:
        return []

    anchor_lines: list[str] = []
    for line in lines[start_idx + 1 :]:
        if line.startswith("## "):
            break
        anchor_lines.append(line.rstrip("\n"))

    paths: list[Path] = []
    for raw_line in anchor_lines:
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if not line.lstrip().startswith("- "):
            continue
        indent = len(line) - len(line.lstrip())
        if indent != 0:
            continue
        body = line.lstrip()[2:].strip()
        if body.startswith("`") and "`" in body[1:]:
            body = body.split("`", 2)[1]
        body = body.removesuffix(":").strip()
        if not body:
            continue
        path = (REPO_ROOT / body).resolve()
        paths.append(path)

    return paths


_ARTIFACT_ERROR_RE = re.compile(r"ERROR:\s+(?P<path>[^:]+):")
_STALE_CONTRACT_RE = re.compile(r"^STALE:\s+(?P<path>.+?)\s+differs from generated$", re.MULTILINE)


def _extract_artifact_error_path(stderr: str, *, run_dir: Path) -> Path | None:
    match = _ARTIFACT_ERROR_RE.search(stderr)
    if not match:
        return None
    candidate = Path(match.group("path"))
    try:
        candidate = candidate.resolve()
    except FileNotFoundError:
        return None
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        return None
    if candidate.suffix != ".md":
        return None
    return candidate


def _extract_stale_contract_paths(stdout: str) -> list[Path]:
    paths: list[Path] = []
    for match in _STALE_CONTRACT_RE.finditer(stdout):
        raw = match.group("path").strip()
        if not raw:
            continue
        path = (REPO_ROOT / raw).resolve()
        if path.exists():
            paths.append(path)
    return paths


def _latest_stage_path(run_id: str, stage: str) -> Path | None:
    run_dir = RUNS_DIR / run_id
    latest = _find_latest_version(run_dir, stage)
    if latest is None:
        return None
    p = _artifact_path(run_id, stage, latest)
    return p if p.exists() else None


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "task"


def _derive_slug(task_text: str) -> str:
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


def _next_slice_number(phase: int, item: int, runs_dir: Path) -> int | None:
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
    if seen_unsliced:
        return 2
    return None


def _propose_run_id(phase: int, item: int, task_text: str, runs_dir: Path) -> str:
    today = time.strftime("%Y-%m-%d", time.localtime())
    slug = _derive_slug(task_text)
    next_slice = _next_slice_number(phase=phase, item=item, runs_dir=runs_dir)
    if next_slice is None:
        return f"{today}__p{phase}-{item}__{slug}"
    return f"{today}__p{phase}-{item}-{next_slice}__{slug}"


def _propose_bundle_run_id(selection: BundleSelection) -> str:
    today = time.strftime("%Y-%m-%d", time.localtime())
    if selection.is_quality_gate:
        if selection.phase_label:
            slug = f"p{selection.phase_label}-quality-gate".replace(".", "-")
        else:
            slug = _slugify(selection.section_title)
        return f"{today}__meta__{slug}"
    if selection.phase is not None and selection.item is not None:
        return _propose_run_id(
            phase=selection.phase,
            item=selection.item,
            task_text=selection.tasks[0],
            runs_dir=RUNS_DIR,
        )
    slug = _slugify(selection.section_title)
    return f"{today}__meta__{slug}"


def _load_next_action(*, include_phase0: bool, include_optional: bool, dry_run: bool) -> RunAction:
    args = ["python3", str(NEXT_ACTION_SCRIPT), "--json"]
    if include_phase0:
        args.append("--include-phase0")
    if include_optional:
        args.append("--include-optional")
    # This command is read-only and safe; run it even in --dry-run so users can
    # see what would happen without actually invoking Codex.
    proc = _run(args, cwd=REPO_ROOT, capture=True, dry_run=False)
    payload = json.loads(proc.stdout)
    return RunAction(
        action=payload["action"],
        run_id=payload.get("run_id", ""),
        hint=payload.get("hint"),
        target=payload.get("target"),
        checklist_section_title=payload.get("checklist_section_title"),
        first_unchecked_task=payload.get("first_unchecked_task"),
        latest_review=payload.get("latest_review"),
        latest_review_verdict=payload.get("latest_review_verdict"),
    )


def _repair_stale_pending_review(run_id: str, latest_review: Path, *, dry_run: bool) -> None:
    """
    Deterministic repair: if index row is PENDING_REVIEW but a review artifact exists, finalize it.
    """

    verdict = _parse_review_verdict(latest_review)
    if verdict is None:
        raise AutopilotStopError(f"STOP: could not parse verdict from {latest_review}")

    rel_review = latest_review.relative_to(REPO_ROOT)

    lines = _read_text(INDEX_PATH).splitlines(keepends=True)
    new_lines: list[str] = []
    changed = False

    for line in lines:
        if not line.startswith(f"| {run_id} "):
            new_lines.append(line)
            continue

        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 6:
            new_lines.append(line)
            continue

        if cols[4] != "PENDING_REVIEW":
            new_lines.append(line)
            continue

        artifact_col = cols[5]
        if "[review](" not in artifact_col:
            artifact_col = artifact_col.rstrip()
            artifact_col = artifact_col + f" / [review](runs/{run_id}/{rel_review.name})"

        cols[4] = verdict
        cols[5] = artifact_col
        rebuilt = "| " + " | ".join(cols[1:-1]) + " |\n"
        new_lines.append(rebuilt)
        changed = True

    if not changed:
        return

    if dry_run:
        print(f"[dry-run] would update {INDEX_PATH} for RUN_ID={run_id} -> {verdict}")
        return

    _write_text(INDEX_PATH, "".join(new_lines))


def _codex_exec(profile: str, message: str, *, dry_run: bool) -> None:
    _run(
        ["codex", "exec", "--profile", profile, "-C", str(REPO_ROOT), message],
        cwd=REPO_ROOT,
        dry_run=dry_run,
    )


def _planning_prompt(
    run_id: str,
    *,
    plan_path: Path,
    prev_plan: Path | None,
    prev_plan_review: Path | None,
    extra_allowed_writes: list[Path] | None,
    allow_spec_edits: bool,
) -> str:
    allowed_writes: list[str] = [f"- {plan_path}"]
    if extra_allowed_writes:
        for path in extra_allowed_writes:
            allowed_writes.append(f"- {path}")

    spec_guidance = ""
    if allow_spec_edits:
        spec_guidance = textwrap.dedent(
            """
            ## Spec Fix Guidance (Use Only If Needed)
            The previous plan failed spec-anchor validation. You MAY edit the anchored spec files listed
            in Allowed Writes to resolve missing headings/signatures. Keep changes minimal, align with the
            original intent, and follow best practices. If a spec change is not required, do not edit specs.
            """
        ).strip()

    extra_inputs = ""
    if prev_plan is not None or prev_plan_review is not None:
        prev_lines: list[str] = []
        if prev_plan is not None:
            prev_lines.append(f"- Previous plan: {prev_plan}")
        if prev_plan_review is not None:
            prev_lines.append(f"- Previous plan review: {prev_plan_review}")
        extra_inputs = textwrap.dedent(
            f"""
            ## Prior Iteration Inputs (Plan Revision)
            {"\n".join(prev_lines)}
            """
        ).strip()

    bundle_section = _bundle_prompt_section(run_id)

    return textwrap.dedent(
        f"""
        Treat this prompt as complete and authoritative. Do not rely on any prior thread/session context.

        You are the Planning Agent for Frame Compare 2.0.

        You MUST follow FC2 STOP rules and templates from:
        - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
        - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

        ## RUN_ID
        {run_id}

        ## Target
        {action_target_line(run_id)}

        ## Allowed Writes (Hard)
        {"\n".join(allowed_writes)}

        ## Disallowed Writes (Hard)
        - .agent-workflow/index.md
        - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
        - Any code under src/ or tests/

        {spec_guidance}
        {bundle_section}

        ## Your Task
        Write the plan artifact at {plan_path}.
        - Use the canonical YAML frontmatter header and required sections.
        - Include concrete file list and verification commands.
        - End with a correct NEXT block for the Plan Review Agent (with concrete version numbers).
        - IMPORTANT: `scripts/validate_spec_anchors.py` treats any bullet of the form `- `...`` as a planned
          signature if the backticked text contains parentheses. Use that exact bullet+backtick pattern ONLY
          for real callable signatures in the plan's "Functions to implement" section.
          Do NOT use backticked bullets for decorators (e.g. `@dataclass(...)`) or test assertions
          (e.g. `request.root == Path(\"x\")`); put those in plain text or fenced code blocks instead.

        {extra_inputs}
        """
    ).strip()


def _plan_review_prompt(
    run_id: str, *, plan_path: Path, plan_review_path: Path, prev_plan_review: Path | None
) -> str:
    extra_inputs = ""
    if prev_plan_review is not None:
        extra_inputs = f"\n## Prior Plan Review\n- {prev_plan_review}\n"
    bundle_section = _bundle_prompt_section(run_id)
    return textwrap.dedent(
        f"""
        Treat this prompt as complete and authoritative. Do not rely on any prior thread/session context.

        You are the Plan Review Agent for Frame Compare 2.0.

        You MUST follow FC2 STOP rules and templates from:
        - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
        - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

        ## RUN_ID
        {run_id}

        ## Target
        {action_target_line(run_id)}

        ## Files To Read
        - {plan_path}
        {extra_inputs.strip()}

        ## Allowed Writes (Hard)
        - {plan_review_path}

        ## Disallowed Writes (Hard)
        - Any other files

        {bundle_section}

        ## Your Task
        Review the plan. If and only if it is ready, set:
        - \"## Verdict: APPROVED\"
        - \"Implementation Agent Decision Points Remaining: NONE\"

        Otherwise, set verdict to CHANGES_REQUIRED and list the exact required edits.

        End with a correct NEXT block for the Coding Agent, pointing to the intended impl-v1.md path for this run.
        """
    ).strip()


def _coding_prompt(
    run_id: str,
    *,
    plan_path: Path,
    plan_review_path: Path,
    impl_path: Path,
    extra_allowed_writes: list[Path] | None = None,
    repair_note: str | None = None,
) -> str:
    allowed_writes: list[str] = [
        "- Code and tests required by the plan",
        f"- {impl_path}",
    ]
    if extra_allowed_writes:
        for path in extra_allowed_writes:
            allowed_writes.append(f"- {path}")

    repair_guidance = ""
    if repair_note:
        repair_guidance = textwrap.dedent(
            f"""
            ## Artifact Repair (Autopilot)
            {repair_note}
            """
        ).strip()

    bundle_section = _bundle_prompt_section(run_id)

    return textwrap.dedent(
        f"""
        Treat this prompt as complete and authoritative. Do not rely on any prior thread/session context.

        You are the Coding Agent for Frame Compare 2.0.

        ## RUN_ID
        {run_id}

        ## Target
        {action_target_line(run_id)}

        ## Preconditions (Hard STOP)
        - Read {plan_review_path} and confirm it is APPROVED and Decision Points Remaining is NONE.

        ## Files To Read
        - {plan_path}
        - {plan_review_path}

        ## Allowed Writes (Hard)
        {"\n".join(allowed_writes)}

        ## Disallowed Writes (Hard)
        - .agent-workflow/index.md
        - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md

        {bundle_section}

        ## Your Task
        Implement EXACTLY what the plan specifies.
        - Start by writing {impl_path} with correct YAML frontmatter and a placeholder section for commands/results.
          Update the file as you run commands so the artifact always exists on disk.
        - The impl artifact MUST include YAML frontmatter with an `INPUTS` list that includes at least:
          - {plan_path}
          - {plan_review_path}
          - {impl_path} (as an OUTPUT entry)
        - Use this exact frontmatter shape (update VERSION as needed):
        ```yaml
        ---
        RUN_ID: {run_id}
        VERSION: v1
        TARGET: {action_target_line(run_id)}
        INPUTS:
          - {plan_path}
          - {plan_review_path}
        OUTPUTS:
          - {impl_path}
        ---
        ```
        - You MUST run the full local quality gates below and ensure they all pass before finishing:
        {_format_quality_gates_for_prompt()}
        - If any gate fails, fix the issue and re-run the failing gate(s) until they pass.
          Then re-run the full gate suite to confirm all gates are green before finishing.
          Do not stop after a failing gate without attempting to fix it.
        - If `generate_contract_views.py --check` reports STALE outputs, run:
          `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
          to regenerate, then re-run the full gate suite. Include any regenerated files in OUTPUTS.
        - For any additional `uv run` commands, prefix with `UV_CACHE_DIR=./.uv_cache` to avoid sandbox approval prompts.
        - Do NOT request scope expansion or permission to edit files outside Allowed Writes.
          If a gate fails in an out-of-scope file, record the failure in {impl_path} and stop after re-running the gate
          to confirm it still fails.
        - Always include the required "## NEXT AGENT PROMPT (COPY/PASTE)" block at the end of {impl_path}
          with concrete RUN_ID + version values (no placeholders like `TBD`).
        - Record commands + outcomes in {impl_path}.
        - End {impl_path} with a correct NEXT block for Verification.

        {repair_guidance}
        """
    ).strip()


def _verify_review_prompt(
    run_id: str,
    *,
    plan_path: Path,
    plan_review_path: Path,
    impl_path: Path,
    verify_path: Path,
    review_path: Path,
) -> str:
    bundle_section = _bundle_prompt_section(run_id)
    return textwrap.dedent(
        f"""
        Treat this prompt as complete and authoritative. Do not rely on any prior thread/session context.

        You are the Verification + Review Agent for Frame Compare 2.0.

        ## RUN_ID
        {run_id}

        ## Target
        {action_target_line(run_id)}

        ## Files To Read
        - {plan_path}
        - {plan_review_path}
        - {impl_path}

        ## Required Outputs (Hard)
        1. Write verification report: {verify_path}
        2. Update checklist: {CHECKLIST_PATH}
        3. Append index row (PENDING_REVIEW) after verification: {INDEX_PATH}
        4. Write review report: {review_path}
        5. Finalize the same index row with final verdict + review link: {INDEX_PATH}
        6. Ensure {review_path} ends with the required "## NEXT AGENT PROMPT (COPY/PASTE)" block.
        7. Ensure {verify_path} ends with the required "## NEXT AGENT PROMPT (COPY/PASTE)" block for Review.

        ## Allowed Writes
        - {verify_path}
        - {review_path}
        - {CHECKLIST_PATH}
        - {INDEX_PATH}

        ## Disallowed
        - Do not change code/tests. If any gate fails, STOP and report it in {verify_path}.
          The controller will route back to Coding for fixes.

        {bundle_section}

        ## Your Task (Order is Mandatory)
        1. Run the full gate suite (pyright/ruff/pytest/import-linter/contracts/traceability) and record results in {verify_path}.
           - For any `uv run` command, prefix with `UV_CACHE_DIR=./.uv_cache` to avoid sandbox approval prompts.
        2. If gates pass, update checklist and append index row with PENDING_REVIEW.
        3. Perform review and write {review_path} with final verdict. Include the required NEXT block at the end.
        4. Ensure {verify_path} includes a Review NEXT block before finishing.
        5. Finalize index row (replace PENDING_REVIEW with final verdict and add review link).
        6. If this is a bundled run, mark ALL bundled checklist items complete.
        """
    ).strip()


_RUN_ID_TARGET_CACHE: dict[str, str] = {}
_RUN_ID_BUNDLE_TASKS: dict[str, list[str]] = {}


def action_target_line(run_id: str) -> str:
    # The controller populates this cache for the active run (best-effort).
    return _RUN_ID_TARGET_CACHE.get(run_id, "<unknown; controller did not provide target context>")


def _bundle_prompt_section(run_id: str) -> str:
    tasks = _RUN_ID_BUNDLE_TASKS.get(run_id)
    if not tasks:
        return ""
    lines = "\n".join(f"- {task}" for task in tasks)
    return textwrap.dedent(
        f"""
        ## Bundled Checklist Items (Complete All)
        {lines}
        """
    ).strip()


def _ensure_index_finalized(run_id: str) -> None:
    text = _read_text(INDEX_PATH)
    for line in text.splitlines():
        if not line.startswith(f"| {run_id} "):
            continue
        if "| PENDING_REVIEW |" in line:
            raise AutopilotStopError(f"STOP: index row still PENDING_REVIEW for {run_id}")
        if "[review](" not in line:
            raise AutopilotStopError(f"STOP: index row missing review link for {run_id}")
        return
    raise AutopilotStopError(f"STOP: index row not found for {run_id}")


def _find_latest_review_path(run_id: str) -> Path | None:
    return _latest_stage_path(run_id, REVIEW_STAGE)


@dataclasses.dataclass(frozen=True)
class AutopilotLock:
    path: Path
    fd: int

    def release(self) -> None:
        with suppress(OSError):
            os.close(self.fd)
        with suppress(OSError):
            self.path.unlink()


def _acquire_autopilot_lock(path: Path) -> AutopilotLock:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise AutopilotStopError(f"STOP: autopilot lock already held at {path}") from exc
    payload = f"pid={os.getpid()} started={int(time.time())}\n"
    os.write(fd, payload.encode("utf-8"))
    return AutopilotLock(path=path, fd=fd)


def _run_turn(engine: AutopilotEngine, *, role: str, message: str) -> None:
    policy = ROLE_POLICY[role]
    engine.run_turn(role=role, message=message, model=policy.model, effort=policy.effort)


def _resume_from_artifacts(run_id: str, *, run_dir: Path) -> int | None:
    latest_pr = _find_latest_version(run_dir, PLAN_REVIEW_STAGE)
    if latest_pr is None:
        return None
    plan_review_path = _artifact_path(run_id, PLAN_REVIEW_STAGE, latest_pr)
    if not plan_review_path.exists():
        return None
    verdict, dp = _parse_plan_review_gate(plan_review_path)
    print(
        "Resume check: latest plan review "
        f"{plan_review_path} verdict={verdict or '<missing>'} dp={dp or '<missing>'}"
    )
    if verdict != "APPROVED" or dp != "NONE":
        return None
    plan_path = _artifact_path(run_id, PLAN_STAGE, latest_pr)
    if not plan_path.exists():
        return None
    print(f"Resume: using approved plan review {plan_review_path} with plan {plan_path}")
    return latest_pr


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="FC-2.0 autopilot controller (local Codex sessions)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands; do not invoke Codex or validators."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not prompt to confirm the proposed RUN_ID (useful for unattended automation).",
    )
    parser.add_argument(
        "--include-phase0", action="store_true", help="Allow Phase 0 checklist selection."
    )
    parser.add_argument(
        "--include-optional", action="store_true", help="Allow optional-only task selection."
    )
    parser.add_argument(
        "--bundle-prefix",
        type=str,
        help="Bundle multiple unchecked checklist tasks within a section (e.g., '7.1').",
    )
    parser.add_argument(
        "--bundle-count",
        type=int,
        default=0,
        help="Number of tasks to include when using --bundle-prefix (must be >=2).",
    )
    parser.add_argument(
        "--bundle-items",
        type=str,
        help="Explicit checklist task texts to bundle, separated by '|'.",
    )
    parser.add_argument(
        "--bundle-title",
        type=str,
        help="Bundle tasks under an exact checklist header title (e.g., 'Phase 6 Quality Gate ✓').",
    )
    parser.add_argument(
        "--max-plan-revisions", type=int, default=4, help="Max plan<->plan-review iterations."
    )
    parser.add_argument(
        "--max-review-revisions", type=int, default=2, help="Max code review revision cycles."
    )
    parser.add_argument(
        "--max-coding-revisions",
        type=int,
        default=4,
        help="Max coding retries before a verify/review cycle begins.",
    )
    parser.add_argument(
        "--engine",
        choices=["exec", "app-server"],
        default="exec",
        help="Execution engine to use (exec or app-server).",
    )
    parser.add_argument(
        "--allow-planning-spec-edits",
        action="store_true",
        default=True,
        help="Allow Planning to edit spec anchors and SSOT spec files when spec validation fails.",
    )
    parser.add_argument(
        "--no-allow-planning-spec-edits",
        action="store_false",
        dest="allow_planning_spec_edits",
        help="Disable Planning edits to spec anchors/SSOT files.",
    )
    parser.add_argument(
        "--resume-from-artifacts",
        action="store_true",
        default=True,
        help="Resume from the latest approved plan review when possible.",
    )
    parser.add_argument(
        "--no-resume-from-artifacts",
        action="store_false",
        dest="resume_from_artifacts",
        help="Disable resume-from-artifacts behavior (always start from Planning).",
    )
    args = parser.parse_args(argv)

    # Fail fast if the checklist ordering would mislead automated selection.
    try:
        _run(
            ["python3", "scripts/validate_master_checklist_order.py"],
            cwd=REPO_ROOT,
            dry_run=False,
        )
    except subprocess.CalledProcessError as exc:
        raise AutopilotStopError("STOP: master checklist order validation failed.") from exc

    if not args.dry_run:
        # Keep derived contract views fresh before starting automation to avoid unrelated gate failures mid-run.
        # If stale, regenerate deterministically via the canonical script.
        env = {"UV_CACHE_DIR": "./.uv_cache"}
        try:
            _run(
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "scripts/generate_contract_views.py",
                    "--check",
                ],
                cwd=REPO_ROOT,
                env=env,
                capture=True,
                dry_run=False,
            )
        except subprocess.CalledProcessError:
            _run(
                ["uv", "run", "--no-sync", "python", "scripts/generate_contract_views.py"],
                cwd=REPO_ROOT,
                env=env,
                dry_run=False,
            )
            try:
                _run(
                    [
                        "uv",
                        "run",
                        "--no-sync",
                        "python",
                        "scripts/generate_contract_views.py",
                        "--check",
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    dry_run=False,
                )
            except subprocess.CalledProcessError as exc:
                raise AutopilotStopError(
                    "STOP: contract view generation check failed after regeneration."
                ) from exc

        # Traceability failures are not safe to auto-fix here; stop early if broken.
        try:
            _run(
                ["uv", "run", "--no-sync", "python", "scripts/validate_traceability.py", "--check"],
                cwd=REPO_ROOT,
                env=env,
                dry_run=False,
            )
        except subprocess.CalledProcessError as exc:
            raise AutopilotStopError("STOP: traceability validation failed.") from exc

    action = _load_next_action(
        include_phase0=args.include_phase0,
        include_optional=args.include_optional,
        dry_run=args.dry_run,
    )

    bundle_mode_flags = [
        flag for flag in [args.bundle_prefix, args.bundle_items, args.bundle_title] if flag
    ]
    if len(bundle_mode_flags) > 1:
        raise AutopilotStopError(
            "STOP: use only one of --bundle-prefix, --bundle-items, or --bundle-title at a time."
        )

    if action.action == "dry_run":
        print("ACTION: dry_run (no next-action available)")
        return 0

    if action.action == "done":
        if args.bundle_prefix or args.bundle_items:
            raise AutopilotStopError("STOP: checklist appears complete; bundling cannot proceed.")
        print("No work to do (checklist appears complete).")
        return 0

    if action.action == "stop_design_issue":
        print(f"STOP: latest run has DESIGN_ISSUE: {action.run_id}")
        return 2

    if action.action == "repair_stale_pending_review":
        assert action.latest_review is not None
        latest_review_path = Path(action.latest_review)
        _repair_stale_pending_review(action.run_id, latest_review_path, dry_run=args.dry_run)
        # After repair, rerun selection in a real invocation.
        print(f"Repaired stale PENDING_REVIEW row for {action.run_id}. Re-run autopilot.")
        return 0

    bundle_selection: BundleSelection | None = None
    if args.bundle_prefix:
        if action.action == "resume_unindexed_run":
            raise AutopilotStopError(
                "STOP: bundling requested, but an unindexed in-progress run exists. "
                "Resolve or remove the in-progress run before bundling."
            )
        bundle_selection = _select_bundle_by_prefix(
            prefix=args.bundle_prefix,
            count=args.bundle_count,
            include_optional=args.include_optional,
        )
    elif args.bundle_items:
        if action.action == "resume_unindexed_run":
            raise AutopilotStopError(
                "STOP: bundling requested, but an unindexed in-progress run exists. "
                "Resolve or remove the in-progress run before bundling."
            )
        items = [item.strip() for item in args.bundle_items.split("|") if item.strip()]
        bundle_selection = _select_bundle_by_items(
            items=items,
            include_optional=args.include_optional,
        )
    elif args.bundle_title:
        if action.action == "resume_unindexed_run":
            raise AutopilotStopError(
                "STOP: bundling requested, but an unindexed in-progress run exists. "
                "Resolve or remove the in-progress run before bundling."
            )
        bundle_selection = _select_bundle_by_title(
            title=args.bundle_title,
            count=args.bundle_count,
            include_optional=args.include_optional,
        )

    if bundle_selection is not None:
        run_id = _propose_bundle_run_id(bundle_selection)
        if bundle_selection.phase is not None and bundle_selection.item is not None:
            target = (
                f"Phase {bundle_selection.phase} → Item "
                f"{bundle_selection.phase}.{bundle_selection.item} (Bundled)"
            )
        else:
            target = f"{bundle_selection.section_title} (Bundled)"
        action = RunAction(
            action="start_new_run",
            run_id=run_id,
            hint="bundle",
            target=target,
            checklist_section_title=bundle_selection.section_title,
            first_unchecked_task=bundle_selection.tasks[0],
        )

    run_id = action.run_id
    if not run_id:
        raise AutopilotStopError(f"STOP: unexpected action payload: {action.action}")

    if not args.dry_run and not args.yes:
        target = action.target or "<unknown target>"
        section = action.checklist_section_title or "<unknown section>"
        task = action.first_unchecked_task or "<unknown task>"
        print("Proposed next run:")
        print(f"- RUN_ID: {run_id}")
        print(f"- Target: {target}")
        print(f"- Section: {section}")
        print(f"- First task: {task}")
        if bundle_selection is not None:
            for bundle_task in bundle_selection.tasks:
                print(f"- Bundled task: {bundle_task}")
        expected = f"CONFIRM RUN_ID: {run_id}"
        response = input(f"\nType exactly: {expected}\n> ").strip()
        if response != expected:
            print("STOP: RUN_ID not confirmed.")
            return 2

    run_dir = RUNS_DIR / run_id
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        if action.target or action.checklist_section_title or action.first_unchecked_task:
            parts = [
                p
                for p in [
                    action.target,
                    action.checklist_section_title,
                    action.first_unchecked_task,
                ]
                if p
            ]
            _RUN_ID_TARGET_CACHE[run_id] = " — ".join(parts)
        if bundle_selection is not None:
            _RUN_ID_BUNDLE_TASKS[run_id] = bundle_selection.tasks
            if run_id in _RUN_ID_TARGET_CACHE:
                _RUN_ID_TARGET_CACHE[run_id] = (
                    _RUN_ID_TARGET_CACHE[run_id] + f" — Bundled {len(bundle_selection.tasks)} tasks"
                )
        # In dry-run mode we don't have artifacts to parse, so just show the
        # intended v1 command sequence and exit.
        plan_path = _artifact_path(run_id, PLAN_STAGE, 1)
        plan_review_path = _artifact_path(run_id, PLAN_REVIEW_STAGE, 1)
        impl_path = _artifact_path(run_id, IMPL_STAGE, 1)
        verify_path = _artifact_path(run_id, VERIFY_STAGE, 1)
        review_path = _artifact_path(run_id, REVIEW_STAGE, 1)

        _codex_exec(
            "fc2_planning",
            _planning_prompt(
                run_id,
                plan_path=plan_path,
                prev_plan=None,
                prev_plan_review=None,
                extra_allowed_writes=None,
                allow_spec_edits=False,
            ),
            dry_run=True,
        )
        _codex_exec(
            "fc2_plan_review",
            _plan_review_prompt(
                run_id,
                plan_path=plan_path,
                plan_review_path=plan_review_path,
                prev_plan_review=None,
            ),
            dry_run=True,
        )
        _codex_exec(
            "fc2_coding",
            _coding_prompt(
                run_id, plan_path=plan_path, plan_review_path=plan_review_path, impl_path=impl_path
            ),
            dry_run=True,
        )
        _codex_exec(
            "fc2_verify_review",
            _verify_review_prompt(
                run_id,
                plan_path=plan_path,
                plan_review_path=plan_review_path,
                impl_path=impl_path,
                verify_path=verify_path,
                review_path=review_path,
            ),
            dry_run=True,
        )
        return 0

    if action.target or action.checklist_section_title or action.first_unchecked_task:
        parts = [
            p
            for p in [action.target, action.checklist_section_title, action.first_unchecked_task]
            if p
        ]
        _RUN_ID_TARGET_CACHE[run_id] = " — ".join(parts)
    if bundle_selection is not None:
        _RUN_ID_BUNDLE_TASKS[run_id] = bundle_selection.tasks
        if run_id in _RUN_ID_TARGET_CACHE:
            _RUN_ID_TARGET_CACHE[run_id] = (
                _RUN_ID_TARGET_CACHE[run_id] + f" — Bundled {len(bundle_selection.tasks)} tasks"
            )

    engine: AutopilotEngine | None = None
    lock: AutopilotLock | None = None
    try:
        if args.engine == "app-server":
            lock = _acquire_autopilot_lock(LOCK_PATH)
            engine = AppServerEngine(
                repo_root=REPO_ROOT,
                run_id=run_id,
                run_dir=run_dir,
                event_log_path=run_dir / "appserver-events.jsonl",
                threads_path=run_dir / "appserver_threads.json",
                config_path=run_dir / "appserver-config.json",
            )
        else:
            engine = ExecEngine(repo_root=REPO_ROOT)

        approved_plan_version: int | None = None
        if args.resume_from_artifacts and not args.dry_run:
            latest_review = _find_latest_review_path(run_id)
            if latest_review is not None:
                verdict = _parse_review_verdict(latest_review)
                if verdict == "APPROVED":
                    print(f"RUN COMPLETE: {run_id} (APPROVED)")
                    return 0
                if verdict == "DESIGN_ISSUE":
                    raise AutopilotStopError(
                        f"STOP: review verdict DESIGN_ISSUE for {run_id}; return to Planning/Plan Review."
                    )
            approved_plan_version = _resume_from_artifacts(run_id, run_dir=run_dir)

        # Planning <-> Plan Review loop.
        if approved_plan_version is None:
            last_plan_gate_failure: str | None = None
            last_plan_spec_paths: list[Path] = []
            allow_spec_edits_next: bool = False
            for _ in range(args.max_plan_revisions):
                plan_v = _next_version(run_dir, PLAN_STAGE)
                plan_path = _artifact_path(run_id, PLAN_STAGE, plan_v)
                prev_plan = _artifact_path(run_id, PLAN_STAGE, plan_v - 1) if plan_v > 1 else None
                prev_pr = (
                    _artifact_path(run_id, PLAN_REVIEW_STAGE, plan_v - 1) if plan_v > 1 else None
                )

                _run_turn(
                    engine,
                    role=ROLE_PLANNING,
                    message=_planning_prompt(
                        run_id,
                        plan_path=plan_path,
                        prev_plan=prev_plan if prev_plan and prev_plan.exists() else None,
                        prev_plan_review=prev_pr if prev_pr and prev_pr.exists() else None,
                        extra_allowed_writes=last_plan_spec_paths
                        if allow_spec_edits_next
                        else None,
                        allow_spec_edits=allow_spec_edits_next,
                    )
                    + (
                        "\n\n## Previous Gate Failure (Autopilot)\n" + last_plan_gate_failure
                        if last_plan_gate_failure
                        else ""
                    ),
                )

                if not args.dry_run:
                    if not plan_path.exists():
                        raise AutopilotStopError(f"STOP: planning did not produce {plan_path}")
                    try:
                        _validate_run_artifacts(run_id, dry_run=args.dry_run)
                        _validate_spec_anchors(plan_path, dry_run=args.dry_run)
                    except GateFailure as e:
                        # This is an expected STOP gate for invalid plan wiring (anchors/templates).
                        last_plan_gate_failure = e.format_for_prompt()
                        allow_spec_edits_next = False
                        last_plan_spec_paths = []
                        if args.allow_planning_spec_edits and any(
                            "validate_spec_anchors.py" in part for part in e.command
                        ):
                            allow_spec_edits_next = True
                            last_plan_spec_paths = _extract_spec_anchor_paths(plan_path)
                        print(
                            f"PLAN VALIDATION FAILED for {run_id}; retrying planning in next revision."
                        )
                        print(last_plan_gate_failure)
                        continue

                plan_review_path = _artifact_path(run_id, PLAN_REVIEW_STAGE, plan_v)
                prev_plan_review = (
                    _artifact_path(run_id, PLAN_REVIEW_STAGE, plan_v - 1) if plan_v > 1 else None
                )
                _run_turn(
                    engine,
                    role=ROLE_PLAN_REVIEW,
                    message=_plan_review_prompt(
                        run_id,
                        plan_path=plan_path,
                        plan_review_path=plan_review_path,
                        prev_plan_review=prev_plan_review
                        if prev_plan_review and prev_plan_review.exists()
                        else None,
                    ),
                )

                if not args.dry_run:
                    if not plan_review_path.exists():
                        raise AutopilotStopError(
                            f"STOP: plan review did not produce {plan_review_path}"
                        )
                    try:
                        _validate_run_artifacts(run_id, dry_run=args.dry_run)
                    except GateFailure as e:
                        last_plan_gate_failure = e.format_for_prompt()
                        allow_spec_edits_next = False
                        last_plan_spec_paths = []
                        print(
                            "PLAN REVIEW ARTIFACT VALIDATION FAILED for "
                            f"{run_id}; retrying planning in next revision."
                        )
                        print(last_plan_gate_failure)
                        continue
                    verdict, dp = _parse_plan_review_gate(plan_review_path)
                    print(
                        "Plan Review parsed: verdict="
                        f"{verdict or '<missing>'} dp={dp or '<missing>'} "
                        f"(from {plan_review_path})"
                    )
                    if verdict == "APPROVED" and dp == "NONE":
                        approved_plan_version = plan_v
                        break

            if approved_plan_version is None:
                raise AutopilotStopError(
                    "STOP: plan did not reach APPROVED + Decision Points Remaining = NONE "
                    "within iteration cap."
                )

        plan_path = _artifact_path(run_id, PLAN_STAGE, approved_plan_version)
        plan_review_path = _artifact_path(run_id, PLAN_REVIEW_STAGE, approved_plan_version)

        # Coding + verify/review cycles.
        last_gate_failure: str | None = None
        for _ in range(args.max_review_revisions):
            coding_attempts = 0
            impl_v: int | None = None
            impl_path: Path | None = None
            extra_coding_writes: list[Path] = []
            repair_note: str | None = None

            while True:
                if coding_attempts >= args.max_coding_revisions:
                    raise AutopilotStopError(
                        "STOP: exceeded max coding revision cycles without producing a "
                        "valid impl artifact."
                    )
                coding_attempts += 1
                impl_v = _next_version(run_dir, IMPL_STAGE)
                impl_path = _artifact_path(run_id, IMPL_STAGE, impl_v)

                _run_turn(
                    engine,
                    role=ROLE_CODING,
                    message=_coding_prompt(
                        run_id,
                        plan_path=plan_path,
                        plan_review_path=plan_review_path,
                        impl_path=impl_path,
                        extra_allowed_writes=extra_coding_writes if extra_coding_writes else None,
                        repair_note=repair_note,
                    )
                    + (
                        "\n\n## Previous Gate Failure (Autopilot)\n" + last_gate_failure
                        if last_gate_failure
                        else ""
                    ),
                )

                if not args.dry_run:
                    if not impl_path.exists():
                        last_gate_failure = (
                            "STOP: coding did not produce the required impl artifact. "
                            f"You MUST write {impl_path} with correct frontmatter and a NEXT block."
                        )
                        print(last_gate_failure)
                        continue
                    try:
                        _validate_run_artifacts(run_id, dry_run=args.dry_run)
                        extra_coding_writes = []
                        repair_note = None
                    except GateFailure as e:
                        last_gate_failure = e.format_for_prompt()
                        artifact_path = _extract_artifact_error_path(e.stderr, run_dir=run_dir)
                        if artifact_path and artifact_path != impl_path:
                            if artifact_path not in extra_coding_writes:
                                extra_coding_writes.append(artifact_path)
                            rel_path = artifact_path.relative_to(REPO_ROOT)
                            repair_note = (
                                "The run artifact validator failed due to an older artifact. "
                                "You are allowed to edit the following file to repair its YAML "
                                "frontmatter / NEXT block without changing substantive content:\n"
                                f"- {rel_path}\n"
                                "Fix the missing frontmatter entries (RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS) "
                                "or required NEXT block as needed, then re-run the gates."
                            )
                        print(
                            f"IMPL ARTIFACT VALIDATION FAILED for {run_id}; "
                            "retrying coding in next revision."
                        )
                        print(last_gate_failure)
                        continue
                    try:
                        _run_quality_gates(dry_run=args.dry_run)
                    except GateFailure as e:
                        last_gate_failure = e.format_for_prompt()
                        if e.command[:5] == [
                            "uv",
                            "run",
                            "--no-sync",
                            "python",
                            "scripts/generate_contract_views.py",
                        ]:
                            stale_paths = _extract_stale_contract_paths(e.stdout or "")
                            if stale_paths:
                                for path in stale_paths:
                                    if path not in extra_coding_writes:
                                        extra_coding_writes.append(path)
                                rel_paths = "\n".join(
                                    f"- {path.relative_to(REPO_ROOT)}" for path in stale_paths
                                )
                                repair_note = (
                                    "Contract view check reported stale generated files. "
                                    "Run the regeneration command:\n"
                                    "  UV_CACHE_DIR=./.uv_cache uv run --no-sync python "
                                    "scripts/generate_contract_views.py\n"
                                    "Then re-run the full gate suite. The following files are allowed to update "
                                    "as generated outputs; include them in OUTPUTS:\n"
                                    f"{rel_paths}"
                                )
                        print(
                            f"GATES FAILED after coding for {run_id}; retrying coding in next revision."
                        )
                        print(last_gate_failure)
                        continue

                break

            assert impl_v is not None
            assert impl_path is not None

            verify_path = _artifact_path(run_id, VERIFY_STAGE, impl_v)
            review_path = _artifact_path(run_id, REVIEW_STAGE, impl_v)

            _run_turn(
                engine,
                role=ROLE_VERIFY_REVIEW,
                message=_verify_review_prompt(
                    run_id,
                    plan_path=plan_path,
                    plan_review_path=plan_review_path,
                    impl_path=impl_path,
                    verify_path=verify_path,
                    review_path=review_path,
                ),
            )

            if not args.dry_run:
                try:
                    _validate_run_artifacts(run_id, dry_run=args.dry_run)
                except GateFailure as e:
                    raise AutopilotStopError(
                        "STOP: verify/review wrote invalid run artifacts; rerun verify/review "
                        "for this impl revision.\n\n" + e.format_for_prompt()
                    ) from e
                try:
                    _run_quality_gates(dry_run=args.dry_run)
                except GateFailure as e:
                    last_gate_failure = e.format_for_prompt()
                    print(
                        f"GATES FAILED after verify/review for {run_id}; retrying coding in next revision."
                    )
                    print(last_gate_failure)
                    continue
                _ensure_index_finalized(run_id)

                latest_review = _find_latest_review_path(run_id)
                if latest_review is None:
                    raise AutopilotStopError("STOP: review artifact missing after verify+review.")
                verdict = _parse_review_verdict(latest_review)
                if verdict == "APPROVED":
                    print(f"RUN COMPLETE: {run_id} (APPROVED)")
                    return 0
                if verdict == "CHANGES_REQUIRED":
                    print(
                        f"Review verdict CHANGES_REQUIRED for {run_id}; continuing revision cycle."
                    )
                    last_gate_failure = None
                    continue
                if verdict == "DESIGN_ISSUE":
                    raise AutopilotStopError(
                        f"STOP: review verdict DESIGN_ISSUE for {run_id}; return to Planning/Plan Review."
                    )

            # Dry-run: do a single cycle.
            break

        raise AutopilotStopError(
            "STOP: exceeded max review revision cycles without reaching APPROVED."
        )
    finally:
        if engine is not None:
            engine.close()
        if lock is not None:
            lock.release()


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except AutopilotStopError as exc:
        print(str(exc))
        raise SystemExit(2) from None
