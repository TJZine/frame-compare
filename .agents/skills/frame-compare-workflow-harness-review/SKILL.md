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
3. `docs/current-architecture.md`
4. `docs/current-cli-contract.md`
5. `importlinter.ini`
6. `pyproject.toml`
7. `.agents/skills/*/SKILL.md`
8. `.agents/skills/*/agents/openai.yaml` when present
9. `.codex/config.toml` and `.codex/agents/*.toml` when delegated roles are in scope

## Review Focus

Lead with findings ordered by severity. Prioritize:

- conflicting authority or load-order rules
- skill trigger descriptions that are too broad, too narrow, or stale
- missing verification routing
- launchers pointing at nonexistent docs
- public-surface workflow gaps
- stale paths or source-repo residue
- missing or undefined delegated roles
- missing language-specific workflow coverage for Python, Typer CLI, or pytest changes
- instructions that would make agents overwrite user changes or claim unverified work

## Output

Report blockers first with exact files and lines. Then list non-blocking improvements and verification gaps.
