# AGENTS.md

Short entrypoint map for local coding agents.

Read in this order:

1. [docs/ENGINEERING_RUNBOOK.md](docs/ENGINEERING_RUNBOOK.md)
2. [docs/current-architecture.md](docs/current-architecture.md)
3. [docs/current-cli-contract.md](docs/current-cli-contract.md)
4. [importlinter.ini](importlinter.ini)
5. [pyproject.toml](pyproject.toml)

Always-on defaults:

- Bootstrap with `uv sync --group dev --frozen` if `.venv/bin/*` is missing.
- Use the repo command canon from the runbook.
- Let the runbook own public-surface and `docs/plans/` activation policy.

Where to look next:

- Workflow, risk tiers, verification, handoff: [docs/ENGINEERING_RUNBOOK.md](docs/ENGINEERING_RUNBOOK.md)
- Runtime flow, boundaries, hotspots: [docs/current-architecture.md](docs/current-architecture.md)
- CLI command, flag, and persistence contract: [docs/current-cli-contract.md](docs/current-cli-contract.md)
- Historical exceptions and decisions: [docs/DECISIONS.md](docs/DECISIONS.md)
