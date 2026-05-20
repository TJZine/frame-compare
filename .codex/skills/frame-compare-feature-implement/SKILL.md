---
name: frame-compare-feature-implement
description: Use when the user explicitly asks for frame-compare-feature-implement, invokes the matching Frame Compare feature implementation workflow, or wants a reusable feature/change implementer launcher as a skill.
---

# Frame Compare Feature Implement

Use this skill to implement an approved feature/change plan.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. active plan or execution brief
4. `docs/current-architecture.md`
5. `docs/current-cli-contract.md` when public behavior is involved
6. relevant repo-local boundary skills

## Workflow

1. Confirm product behavior, public surfaces, and verification are decided.
2. Keep `update_plan` current.
3. Implement the smallest coherent approved unit.
4. Update authority docs in the same pass when CLI/config/release/workflow/architecture behavior changes.
5. Stop and re-plan if public behavior, owner seams, or verification diverge.
6. Run targeted proof plus the runbook-required gate.
7. Use `closeout-verification`.

## Output

Report changed files, verification evidence, public contract/doc updates, and remaining risks.
