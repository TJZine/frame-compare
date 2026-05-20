---
name: frame-compare-cleanup-loop
description: Use when the user explicitly asks for frame-compare-cleanup-loop, invokes a Frame Compare cleanup controller workflow, or wants a reusable multi-step cleanup/refactor loop as a skill.
---

# Frame Compare Cleanup Loop

Use this skill for high-risk or repeated cleanup/refactor/remediation work that needs planner, implementer, and reviewer loops.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. `docs/current-architecture.md`
4. `docs/current-cli-contract.md`
5. `importlinter.ini`
6. relevant repo-local boundary skills

## Controller Workflow

1. Keep authoritative live state in `update_plan`.
2. Create or load the approved plan using `frame-compare-cleanup-plan`.
3. Request review with `frame-compare-cleanup-review` before implementation when risk is medium or high.
4. Execute one approved unit with `frame-compare-cleanup-implement`.
5. Review the implementation.
6. Adjudicate findings with `review-adjudication`.
7. Repeat until the approved scope closes or a stop-and-replan trigger fires.
8. Use `closeout-verification` for final status.

Do not let the loop become a feature-delivery umbrella; split mixed feature and cleanup work.
