# Claude Code runtime map

`AGENTS.md` and the documents it points to are the shared authority. This file only maps Codex runtime terms to Claude Code; it adds no workflow policy.

- Skills: canonical bodies live in `.agents/skills/<name>/SKILL.md`. Each `.claude/skills/<name>/SKILL.md` is a thin discovery entry that loads the canonical file; edit the canonical file, not the entry. If you change a canonical skill's `name` or `description`, update the matching entry too.
- Roles: `explorer`, `reviewer`, `docs_researcher`, `planner`, `worker`, `worker_luna`, `monitor` are Claude subagents with the same names in `.claude/agents/`. `.codex/config.toml` and `.codex/agents/*.toml` (OpenAI models, sandbox modes) configure Codex only. For Claude, the agent file sets model, effort, and tools; role semantics stay as the repository describes them. `worker` is the stronger implementer (Opus); `worker_luna` is the cost-efficient bounded implementer (Sonnet).
- Delegation depth: subagents cannot spawn subagents (Codex `max_depth = 1`). Treat six concurrent agents as a ceiling, not a target.
- Codex `update_plan` corresponds to Claude's task list.
