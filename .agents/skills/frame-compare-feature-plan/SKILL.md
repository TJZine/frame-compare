---
name: frame-compare-feature-plan
description: Use when the user explicitly asks for frame-compare-feature-plan, invokes the matching Frame Compare feature planning workflow, or wants a reusable feature/change plan launcher as a skill.
---

# Frame Compare Feature Plan

Use this skill for feature, behavior, CLI, output, runtime, or release-path planning.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. `docs/current-architecture.md`
4. `docs/current-cli-contract.md` when CLI/config/public behavior may change
5. relevant repo-local boundary skills

## Workflow

1. Confirm the product behavior or stop and ask for the missing invariant.
2. Classify risk using the runbook.
3. Identify public surfaces: CLI/config/JSON/report/release/import-level behavior.
4. Use `verification-strategy` to lock proof.
5. Use `execution-plan-authoring` for light or tracked planning.
6. Include docs updates when authority surfaces change.

## Output

Return an implementation-ready plan with goal, non-goals, owner seam, files, invariants, verification, and stop conditions.
