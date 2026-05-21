---
trigger: always_on
---

# Antigravity Rules

Antigravity reads repo rules from `.agents/rules/`. Treat this file as a thin
entrypoint shim only; it must not become a second runbook.

## Read Order

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. `docs/current-architecture.md`
4. `docs/current-cli-contract.md`
5. `importlinter.ini`
6. `pyproject.toml`

## Authority

- `AGENTS.md` owns the short entrypoint map.
- `docs/ENGINEERING_RUNBOOK.md` owns workflow, risk tiers, verification, planning,
  review, handoff, and production-quality guardrails.
- `docs/current-architecture.md` owns current module boundaries, runtime flow,
  hotspots, and same-pass architecture doc freshness triggers.
- `docs/current-cli-contract.md` owns current CLI command, flag, exit, stream,
  JSON, config persistence, and report-open behavior.
- `importlinter.ini` owns import-layer direction.
- `pyproject.toml` owns local Python tooling policy and pytest markers.
- `docs/plans/**` is reference-only unless the file starts with `Status: Active`.
- `.agents/rules/general-guidelines.md` is Antigravity routing material only. If it
  conflicts with the files above, follow those files and update this shim.

## Skill Locations

- Use repo-local workflow and boundary skills under `.agents/skills/` when their
  trigger descriptions match the task.
- Keep code-health scanner state and optional local code-health skills untracked;
  do not add a repo-local `desloppify` skill unless the task explicitly targets
  desloppify workflow and the maintainer approves tracking it.
- Do not use `.agent/skills/` for Frame Compare workflow skills. If Antigravity
  discovers a local `.agent/skills/` folder, treat it as stale local state and do
  not copy it into the repo without an explicit maintainer decision.

## Verification

Use the command canon and verification routing in `docs/ENGINEERING_RUNBOOK.md`.
Do not claim commands passed unless they were observed in this workspace.
