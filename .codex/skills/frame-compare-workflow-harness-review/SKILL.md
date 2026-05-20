---
name: frame-compare-workflow-harness-review
description: Use when the user explicitly asks for frame-compare-workflow-harness-review, invokes the matching Frame Compare workflow review, or wants a reusable review of workflow docs, skills, launchers, or control-plane rules.
---

# Frame Compare Workflow Harness Review

Use this skill to review the repo's agent workflow, runbook, skills, launcher surfaces, and verification policy.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. `.codex/skills/*/SKILL.md`
4. `.codex/skills/*/agents/openai.yaml` when present
5. `.codex/config.toml` and `.codex/agents/*.toml` when delegated roles are in scope
6. `.agents/skills/desloppify/SKILL.md` when code-health workflow policy is in scope
7. `docs/current-architecture.md`
8. `docs/current-cli-contract.md`

## Review Focus

Lead with findings ordered by severity. Prioritize:

- conflicting authority or load-order rules
- skill trigger descriptions that are too broad, too narrow, or stale
- missing verification routing
- launchers pointing at nonexistent docs
- public-surface workflow gaps
- stale paths or source-repo residue
- missing or undefined delegated roles
- instructions that would make agents overwrite user changes or claim unverified work

## Output

Report blockers first with exact files and lines. Then list non-blocking improvements and verification gaps.
