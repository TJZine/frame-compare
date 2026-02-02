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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / ".agent-workflow" / "runs"
INDEX_PATH = REPO_ROOT / ".agent-workflow" / "index.md"
CHECKLIST_PATH = REPO_ROOT / "docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md"
NEXT_ACTION_SCRIPT = REPO_ROOT / "codex-skills/fc2-collab-autopilot/scripts/next_fc2_action.py"


PLAN_STAGE = "plan"
PLAN_REVIEW_STAGE = "plan-review"
IMPL_STAGE = "impl"
VERIFY_STAGE = "verify"
REVIEW_STAGE = "review"


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
            {out or '<empty>'}

            stderr:
            {err or '<empty>'}
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
    _run(
        [
            "uv",
            "run",
            "--no-sync",
            "python",
            "scripts/validate_run_artifacts.py",
            str(RUNS_DIR / run_id),
        ],
        cwd=REPO_ROOT,
        env=env,
        dry_run=dry_run,
    )


def _validate_spec_anchors(plan_path: Path, *, dry_run: bool) -> None:
    env = {"UV_CACHE_DIR": "./.uv_cache"}
    _run(
        ["uv", "run", "--no-sync", "python", "scripts/validate_spec_anchors.py", str(plan_path)],
        cwd=REPO_ROOT,
        env=env,
        dry_run=dry_run,
    )


def _run_quality_gates(*, dry_run: bool) -> None:
    env = {"UV_CACHE_DIR": "./.uv_cache"}
    commands: list[list[str]] = [
        [".venv/bin/pyright", "--warnings"],
        [".venv/bin/ruff", "check", "."],
        [".venv/bin/pytest", "-q"],
        ["uv", "run", "--no-sync", "lint-imports", "--config", "importlinter.ini"],
        ["uv", "run", "--no-sync", "python", "scripts/generate_contract_views.py", "--check"],
        ["uv", "run", "--no-sync", "python", "scripts/validate_traceability.py", "--check"],
    ]

    for cmd in commands:
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


def _parse_plan_review_gate(plan_review_path: Path) -> tuple[str | None, str | None]:
    verdict: str | None = None
    dp: str | None = None
    for raw in _read_text(plan_review_path).splitlines():
        m_v = re.fullmatch(r"##\s+Verdict:\s+([A-Z_]+)\s*", raw.strip())
        if m_v:
            verdict = m_v.group(1)
        if "Implementation Agent Decision Points Remaining:" in raw:
            _, _, rest = raw.partition(":")
            dp = rest.strip() or None
    return verdict, dp


def _parse_review_verdict(review_path: Path) -> str | None:
    for raw in _read_text(review_path).splitlines():
        m = re.fullmatch(r"##\s+Verdict:\s+([A-Z_]+)\s*", raw.strip())
        if m:
            return m.group(1)
    return None


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
        raise RuntimeError(f"Could not parse verdict from {latest_review}")

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
    run_id: str, *, plan_path: Path, prev_plan: Path | None, prev_plan_review: Path | None
) -> str:
    extra_inputs = ""
    if prev_plan is not None and prev_plan_review is not None:
        extra_inputs = textwrap.dedent(
            f"""
            ## Prior Iteration Inputs (Plan Revision)
            - Previous plan: {prev_plan}
            - Previous plan review: {prev_plan_review}
            """
        ).strip()

    return textwrap.dedent(
        f"""
        You are the Planning Agent for Frame Compare 2.0.

        You MUST follow FC2 STOP rules and templates from:
        - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
        - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

        ## RUN_ID
        {run_id}

        ## Target
        {action_target_line(run_id)}

        ## Allowed Writes (Hard)
        - {plan_path}

        ## Disallowed Writes (Hard)
        - .agent-workflow/index.md
        - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
        - Any code under src/ or tests/

        ## Your Task
        Write the plan artifact at {plan_path}.
        - Use the canonical YAML frontmatter header and required sections.
        - Include concrete file list and verification commands.
        - End with a correct NEXT block for the Plan Review Agent (with concrete version numbers).

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
        - Run the local quality gates listed in AGENTS.md before finishing.
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
        2. If gates pass, update checklist and append index row with PENDING_REVIEW.
        3. Perform review and write {review_path} with final verdict.
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
            raise RuntimeError(f"Index row still PENDING_REVIEW for {run_id}")
        if "[review](" not in line:
            raise RuntimeError(f"Index row missing review link for {run_id}")
        return
    raise RuntimeError(f"Index row not found for {run_id}")


def _find_latest_review_path(run_id: str) -> Path | None:
    return _latest_stage_path(run_id, REVIEW_STAGE)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="FC-2.0 autopilot controller (local Codex sessions)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands; do not invoke Codex or validators."
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
    args = parser.parse_args(argv)

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
        raise RuntimeError(f"Unexpected action payload: {action.action}")

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
            _planning_prompt(run_id, plan_path=plan_path, prev_plan=None, prev_plan_review=None),
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

    # Planning <-> Plan Review loop.
    approved_plan_version: int | None = None
    for _ in range(args.max_plan_revisions):
        plan_v = _next_version(run_dir, PLAN_STAGE)
        plan_path = _artifact_path(run_id, PLAN_STAGE, plan_v)
        prev_plan = _artifact_path(run_id, PLAN_STAGE, plan_v - 1) if plan_v > 1 else None
        prev_pr = _artifact_path(run_id, PLAN_REVIEW_STAGE, plan_v - 1) if plan_v > 1 else None

        _codex_exec(
            "fc2_planning",
            _planning_prompt(
                run_id,
                plan_path=plan_path,
                prev_plan=prev_plan if prev_plan and prev_plan.exists() else None,
                prev_plan_review=prev_pr if prev_pr and prev_pr.exists() else None,
            ),
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            if not plan_path.exists():
                raise RuntimeError(f"Planning did not produce {plan_path}")
            _validate_run_artifacts(run_id, dry_run=args.dry_run)
            _validate_spec_anchors(plan_path, dry_run=args.dry_run)

        plan_review_path = _artifact_path(run_id, PLAN_REVIEW_STAGE, plan_v)
        prev_plan_review = (
            _artifact_path(run_id, PLAN_REVIEW_STAGE, plan_v - 1) if plan_v > 1 else None
        )
        _codex_exec(
            "fc2_plan_review",
            _plan_review_prompt(
                run_id,
                plan_path=plan_path,
                plan_review_path=plan_review_path,
                prev_plan_review=prev_plan_review
                if prev_plan_review and prev_plan_review.exists()
                else None,
            ),
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            if not plan_review_path.exists():
                raise RuntimeError(f"Plan Review did not produce {plan_review_path}")
            _validate_run_artifacts(run_id, dry_run=args.dry_run)
            verdict, dp = _parse_plan_review_gate(plan_review_path)
            if verdict == "APPROVED" and dp == "NONE":
                approved_plan_version = plan_v
                break

    if approved_plan_version is None:
        raise RuntimeError(
            "Plan did not reach APPROVED + Decision Points Remaining = NONE within iteration cap."
        )

    plan_path = _artifact_path(run_id, PLAN_STAGE, approved_plan_version)
    plan_review_path = _artifact_path(run_id, PLAN_REVIEW_STAGE, approved_plan_version)

    # Coding + verify/review cycles.
    last_gate_failure: str | None = None
    for _ in range(args.max_review_revisions):
        impl_v = _next_version(run_dir, IMPL_STAGE)
        impl_path = _artifact_path(run_id, IMPL_STAGE, impl_v)
        _codex_exec(
            "fc2_coding",
            _coding_prompt(
                run_id, plan_path=plan_path, plan_review_path=plan_review_path, impl_path=impl_path
            )
            + ("\n\n## Previous Gate Failure\n" + last_gate_failure if last_gate_failure else ""),
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            if not impl_path.exists():
                raise RuntimeError(f"Coding did not produce {impl_path}")
            _validate_run_artifacts(run_id, dry_run=args.dry_run)
            try:
                _run_quality_gates(dry_run=args.dry_run)
            except GateFailure as e:
                last_gate_failure = e.format_for_prompt()
                print(f"GATES FAILED after coding for {run_id}; retrying coding in next revision.")
                continue

        verify_path = _artifact_path(run_id, VERIFY_STAGE, impl_v)
        review_path = _artifact_path(run_id, REVIEW_STAGE, impl_v)

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
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            _validate_run_artifacts(run_id, dry_run=args.dry_run)
            try:
                _run_quality_gates(dry_run=args.dry_run)
            except GateFailure as e:
                last_gate_failure = e.format_for_prompt()
                print(
                    f"GATES FAILED after verify/review for {run_id}; retrying coding in next revision."
                )
                continue
            _ensure_index_finalized(run_id)

            latest_review = _find_latest_review_path(run_id)
            if latest_review is None:
                raise RuntimeError("Review artifact missing after verify+review.")
            verdict = _parse_review_verdict(latest_review)
            if verdict == "APPROVED":
                print(f"RUN COMPLETE: {run_id} (APPROVED)")
                return 0
            if verdict == "CHANGES_REQUIRED":
                print(f"Review verdict CHANGES_REQUIRED for {run_id}; continuing revision cycle.")
                last_gate_failure = None
                continue
            if verdict == "DESIGN_ISSUE":
                raise RuntimeError(
                    f"Review verdict DESIGN_ISSUE for {run_id}; return to Planning/Plan Review."
                )

        # Dry-run: do a single cycle.
        break

    raise RuntimeError("Exceeded max review revision cycles without reaching APPROVED.")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
