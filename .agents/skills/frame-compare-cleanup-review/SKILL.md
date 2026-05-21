---
name: frame-compare-cleanup-review
description: Use when the user explicitly asks for frame-compare-cleanup-review, invokes the matching Frame Compare cleanup review workflow, or wants a reusable cleanup/refactor reviewer launcher as a skill.
---

# Frame Compare Cleanup Review

Use this skill to review cleanup/refactor/remediation plans or implementations.

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

- behavioral regressions
- CLI/config/JSON/release contract drift
- import-layer or owner-boundary violations
- filesystem persistence leaks
- runtime integration failures
- missing or insufficient verification
- unrelated changes or stale docs

Say explicitly when no blocking findings are found.

## Output

Use file/line evidence where possible and separate blockers from optional improvements.
