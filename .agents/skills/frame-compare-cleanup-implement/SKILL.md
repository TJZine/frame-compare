---
name: frame-compare-cleanup-implement
description: Use when the user explicitly asks for frame-compare-cleanup-implement, invokes the matching Frame Compare cleanup implementation workflow, or wants a reusable cleanup/refactor implementer launcher as a skill.
---

# Frame Compare Cleanup Implement

Use this skill to implement an approved cleanup/refactor/remediation plan.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. active plan or execution brief
4. `docs/current-architecture.md`
5. `docs/current-cli-contract.md` when public behavior is involved
6. relevant repo-local boundary skills

## Workflow

1. Confirm the plan is approved and execution-grade.
2. Keep `update_plan` as the authoritative live state.
3. Implement one bounded unit at a time.
4. Preserve public CLI/config/release behavior unless the plan explicitly changes it.
5. Stop and re-plan if the owner seam, verification depth, or public contract differs from the plan.
6. Run the verification named by the plan and the runbook-required gate.
7. Use `closeout-verification` before claiming completion.

## Output

Report changed files, verification run, unresolved risks, and whether review is still needed.
