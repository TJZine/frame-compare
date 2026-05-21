---
name: frame-compare-feature-review
description: Use when the user explicitly asks for frame-compare-feature-review, invokes the matching Frame Compare feature review workflow, or wants a reusable feature/change reviewer launcher as a skill.
---

# Frame Compare Feature Review

Use this skill to review feature/change plans or implementations.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. reviewed plan, diff, or artifact
4. `docs/current-architecture.md`
5. `docs/current-cli-contract.md` when public behavior is involved
6. relevant repo-local boundary skills

## Review Focus

Lead with findings ordered by severity. Prioritize:

- user-visible behavior bugs
- CLI/config/JSON/report/release contract drift
- missing docs updates for authority surfaces
- import-layer and owner-boundary issues
- runtime integration or packaging regressions
- weak verification or missing tests

Say explicitly when no blocking findings are found.
