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


def _latest_stage_path(run_id: str, stage: str) -> Path | None:
    run_dir = RUNS_DIR / run_id
    latest = _find_latest_version(run_dir, stage)
    if latest is None:
        return None
    p = _artifact_path(run_id, stage, latest)
    return p if p.exists() else None


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

        ## Your Task
        Review the plan. If and only if it is ready, set:
        - \"## Verdict: APPROVED\"
        - \"Implementation Agent Decision Points Remaining: NONE\"

        Otherwise, set verdict to CHANGES_REQUIRED and list the exact required edits.

        End with a correct NEXT block for the Coding Agent, pointing to the intended impl-v1.md path for this run.
        """
    ).strip()


def _coding_prompt(run_id: str, *, plan_path: Path, plan_review_path: Path, impl_path: Path) -> str:
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
        - Code and tests required by the plan
        - {impl_path}

        ## Disallowed Writes (Hard)
        - .agent-workflow/index.md
        - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md

        ## Your Task
        Implement EXACTLY what the plan specifies.
        - You MUST run the full local quality gates below and ensure they all pass before finishing:
        {_format_quality_gates_for_prompt()}
        - For any additional `uv run` commands, prefix with `UV_CACHE_DIR=./.uv_cache` to avoid sandbox approval prompts.
        - Hard rule: Do NOT write the "## NEXT AGENT PROMPT (COPY/PASTE)" block until all gates pass.
        - Record commands + outcomes in {impl_path}.
        - End {impl_path} with a correct NEXT block for Verification.
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

        ## Allowed Writes
        - {verify_path}
        - {review_path}
        - {CHECKLIST_PATH}
        - {INDEX_PATH}

        ## Disallowed
        - Do not change code/tests. If any gate fails, STOP and report it in {verify_path}.
          The controller will route back to Coding for fixes.

        ## Your Task (Order is Mandatory)
        1. Run the full gate suite (pyright/ruff/pytest/import-linter/contracts/traceability) and record results in {verify_path}.
           - For any `uv run` command, prefix with `UV_CACHE_DIR=./.uv_cache` to avoid sandbox approval prompts.
        2. If gates pass, update checklist and append index row with PENDING_REVIEW.
        3. Perform review and write {review_path} with final verdict. Include the required NEXT block at the end.
        4. Finalize index row (replace PENDING_REVIEW with final verdict and add review link).
        """
    ).strip()


_RUN_ID_TARGET_CACHE: dict[str, str] = {}


def action_target_line(run_id: str) -> str:
    # The controller populates this cache for the active run (best-effort).
    return _RUN_ID_TARGET_CACHE.get(run_id, "<unknown; controller did not provide target context>")


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
        "--max-plan-revisions", type=int, default=4, help="Max plan<->plan-review iterations."
    )
    parser.add_argument(
        "--max-review-revisions", type=int, default=2, help="Max code review revision cycles."
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

    if action.action == "dry_run":
        print("ACTION: dry_run (no next-action available)")
        return 0

    if action.action == "done":
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
                )
                + (
                    "\n\n## Previous Gate Failure (Autopilot)\n" + last_gate_failure
                    if last_gate_failure
                    else ""
                ),
            )

            if not args.dry_run:
                if not impl_path.exists():
                    raise AutopilotStopError(f"STOP: coding did not produce {impl_path}")
                try:
                    _validate_run_artifacts(run_id, dry_run=args.dry_run)
                except GateFailure as e:
                    last_gate_failure = e.format_for_prompt()
                    print(
                        f"IMPL ARTIFACT VALIDATION FAILED for {run_id}; retrying coding in next revision."
                    )
                    print(last_gate_failure)
                    continue
                try:
                    _run_quality_gates(dry_run=args.dry_run)
                except GateFailure as e:
                    last_gate_failure = e.format_for_prompt()
                    print(
                        f"GATES FAILED after coding for {run_id}; retrying coding in next revision."
                    )
                    print(last_gate_failure)
                    continue

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
