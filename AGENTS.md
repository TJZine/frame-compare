# AGENTS.md

Short entrypoint map for local coding agents.

Use the relevant section of [docs/ENGINEERING_RUNBOOK.md](docs/ENGINEERING_RUNBOOK.md)
for risk, verification, planning, or handoff decisions. Load deeper context only when
the task needs it:

- ownership, hotspots, runtime flow, or layering: [docs/current-architecture.md](docs/current-architecture.md)
- CLI, config, JSON, reports, or other public behavior: [docs/current-cli-contract.md](docs/current-cli-contract.md)
- import direction: [importlinter.ini](importlinter.ini)
- dependencies, packaging, or tool configuration: [pyproject.toml](pyproject.toml)

Always-on defaults:

- Task-specific user instructions take precedence over skill workflow guidance.
  Honor explicit requests to review a proposal before editing; apply the runbook's
  escalation rules within the scope the user has authorized.
- Bootstrap with `uv sync --group dev --extra vsview --frozen` if `.venv/bin/*` is missing.
- Use Codanna for unknown owners, callers, and impact when available; confirm
  important results in source and use `rg`/direct reads for exact queries.
- Use the smallest matching repo-local skill set. Prefer one process skill plus only
  the boundary skills required by the changed surface.
- Read relevant authority sections first; expand to callers, adjacent contracts, or
  the full document when the evidence leaves a material question unresolved.
- Keep code-health scanner state and optional local code-health skills untracked; do not add a repo-local `desloppify` skill unless the task explicitly targets desloppify workflow and the maintainer approves tracking it.
- Keep Antigravity rules in `.agents/rules/general-guidelines.md` as a thin shim over this entrypoint and the runbook, not a second workflow.
- Use the repo command canon from the runbook.
- Let the runbook own public-surface and `docs/plans/` activation policy.
- Default to one agent. Delegate only independent read-heavy work or an approved,
  disjoint implementation unit; do not add planner/reviewer passes by habit.
- Complete authorized work through verification and repair of failures caused by
  the change. Resolve routine uncertainty from source; use the runbook's escalation
  boundaries for consequential decisions that remain unresolved.
- Before claiming completion, run risk-matched verification, inspect the diff, and
  preserve unrelated user changes.
- Prove features with real-CLI E2E tests in `tests/e2e/` on generated media, leaving checked artifacts; run the media tier through Docker.
- Keep one owner per user-visible behavior; follow production value flow before calling an assertion internal.
- Keep isolated tests only for `owner`, `edge`, `failure`, `contract`, `network`, `security` or `platform`; internal assertions never justify retention.
- Apply R1 to test-only production code and R2 to failure outcomes for program-written data; preserve distinct external-input and security cases.
- List failure modes first; prove bug regressions fail on pre-fix code once at the highest reproducing seam.
- Load `python-test-design` before writing, changing or reviewing tests.

Where to look next:

- Workflow, risk tiers, verification, handoff: [docs/ENGINEERING_RUNBOOK.md](docs/ENGINEERING_RUNBOOK.md)
- Runtime flow, boundaries, hotspots: [docs/current-architecture.md](docs/current-architecture.md)
- CLI command, flag, and persistence contract: [docs/current-cli-contract.md](docs/current-cli-contract.md)
- Repo-local workflow and boundary skills: [.agents/skills/](.agents/skills/)
- Antigravity rule shim: [.agents/rules/general-guidelines.md](.agents/rules/general-guidelines.md)
- Historical exceptions and decisions: [docs/DECISIONS.md](docs/DECISIONS.md)

<!-- desloppify-begin -->
# desloppify

Use the installed `desloppify` skill/tool only when explicitly requested to run a
code-health scan, produce a health score, or create a cleanup plan. Keep scanner
state untracked; do not add a repo-local `desloppify` skill unless the task
explicitly targets that workflow and maintainer approval for tracking it is
recorded. Follow the repo command canon and workflow policy in
`docs/ENGINEERING_RUNBOOK.md`.
<!-- desloppify-end -->
