---
name: frame-compare-cleanup-plan
description: Use when the user explicitly asks for frame-compare-cleanup-plan, invokes the matching Frame Compare cleanup planning workflow, or wants a reusable cleanup/refactor plan launcher as a skill.
---

# Frame Compare Cleanup Plan

Use this skill for cleanup/refactor/remediation planning in Frame Compare.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. `docs/current-architecture.md`
4. `docs/current-cli-contract.md` when CLI/config/public behavior may be affected
5. `importlinter.ini`
6. relevant repo-local boundary skills

## Workflow

1. Classify the task as cleanup/refactor/remediation and choose the runbook risk tier.
2. Use `verification-strategy` to lock the proof surface.
3. Use `execution-plan-authoring` to decide whether the plan stays in `update_plan`, becomes a light execution brief, or activates `docs/plans/`.
4. Preserve public CLI/config/release behavior unless the task explicitly changes it.
5. Name exact owner files, files out of scope, invariants, verification commands, rollback surface, and stop-and-replan triggers.

## Output

Return a plan or handoff that is ready for review or implementation. For durable tracked plans, follow the runbook's `Status: Active` metadata rule.
