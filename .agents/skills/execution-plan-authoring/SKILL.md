---
name: execution-plan-authoring
description: Use when a Frame Compare task needs a durable implementation plan or execution brief that freezes scope, ownership, public contracts, and verification without over-specifying local coding choices.
---

# Execution Plan Authoring

## Overview

Use this skill to write decision-complete Frame Compare plans.

The target is not "make the implementer decide nothing." The target is "leave no unresolved scope, ownership, contract, or verification decision that would make implementation invent policy mid-run."

Use `verification-strategy` before or alongside this skill when the proof surface is unsettled.

## Use This Skill For

- High-risk work under [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
- Durable cross-session work that activates `docs/plans/`
- CLI/config, Docker/runtime, Windows/release, architecture, workflow, or hotspot work
- Handoffs to an implementer where ambiguity would be expensive

## Plan Modes

Choose exactly one:

1. No tracked plan: use `update_plan` only for tiny bounded work.
2. Light execution brief: use for single-session work that still needs scope, seam, files, invariants, verification, and stop conditions.
3. Serious tracked plan: use only when durable handoff memory is needed or the maintainer asks for it.

`docs/plans/` becomes authoritative only when the plan starts with:

```text
Status: Active
Scope: <task scope>
Owner: <person or session>
```

## Planning Target

Freeze decisions that are expensive to get wrong:

- task family and risk tier
- goal and non-goals
- chosen owner seam
- files in scope and out of scope
- public CLI/config/release/import-layer contracts
- invariants to preserve
- verification strategy and commands
- rollback surface
- stop-and-replan triggers

Leave ordinary local coding choices delegated: helper names, local extraction shapes inside the chosen owner, routine control flow, and test helper organization.

## Verification Classification

Every execution surface should classify verification as one of:

- `new regression/contract test required`
- `existing coverage sufficient`
- `broader integration/manual proof required`
- `no new automated test needed`

Then name exact commands and expected outcomes.

## Snippet Policy

Use snippets only when precision materially reduces risk: CLI payload examples, schema shapes, command lines, file paths, or fragile output examples.

Avoid full function bodies or pseudo-code for every future task.

## Stop Conditions

Stop and resolve before freezing the plan when:

- owner seam is undecided
- public CLI/config/release behavior would change implicitly
- import-layer changes are required but not scoped
- verification depth is still open
- Docker or Windows proof is required but no environment path is named
- the plan compensates for uncertainty with excessive pseudo-code

## Output Expectations

For a light execution brief, include scope, seam, files, invariants, verification, and stop conditions.

For a serious tracked plan, follow the runbook's active-plan rules and make the proof surface explicit.

## Common Mistakes

- Promoting routine work into `docs/plans/` without durable handoff need
- Hiding public CLI/config behavior changes in implementation details
- Treating Windows or Docker verification gaps as minor when they are release surfaces
- Writing patch prose instead of execution constraints
