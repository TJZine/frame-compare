---
name: large-task-orchestration
description: "Explicit controller workflow for very large Frame Compare features, refactors, migrations, or remediation programs that require multiple bounded subagents; do not use for routine work or a single delegated unit."
disable-model-invocation: true
---

# large-task-orchestration (Claude Code entry)

Canonical skill: [`.agents/skills/large-task-orchestration/SKILL.md`](../../../.agents/skills/large-task-orchestration/SKILL.md), shared with Codex.
This file is only the Claude Code discovery entry. Do not copy the skill body here.

Before acting, read `.agents/skills/large-task-orchestration/SKILL.md` from the repository root in full and follow it as this skill's instructions.
Resolve its relative links from `.agents/skills/large-task-orchestration/`.

Claude Code runtime: keep live state in Claude's task list where the skill says `update_plan`. Dispatch the named roles as the Claude subagents of the same names in `.claude/agents/`. They cannot spawn further agents, which enforces `max_depth = 1`. Treat `max_threads = 6` as the parallelism ceiling.
