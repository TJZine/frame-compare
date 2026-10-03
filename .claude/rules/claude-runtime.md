# Claude Code runtime map

Root `CLAUDE.md` imports `AGENTS.md`; `.agents/project.md` supplies repository facts.
Shared skills are installed once per host. Do not recreate repository-local copies
or wrappers for the retired workflow names.

Host configuration owns model/effort choices, permissions, and available tools.
Use the shared workflow's delegation criteria with the capabilities actually
available; a Codex role name or TOML key does not configure Claude.

Independent investigation, verification, and implementation can run in parallel.
Parallel writers need isolated worktrees or explicit disjoint shared-tree ownership,
one Git/integration owner, and stable test state. Serialize dependent work and real
shared-resource conflicts. Claude's task list can hold the controller's live plan.

Codanna is optional. Its absence does not prevent source inspection with direct
reads and search. Preserve the configured tool permissions; do not claim that an
unavailable host capability was exercised.
