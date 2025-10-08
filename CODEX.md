# CODEX.md — Project Guardrails

## Execution & Approvals
- Default: **diff-plan → approval → patches**. Advisors never execute.
- Autonomous changes allowed (no approval) **only if all are true**:
  - <= 100 changed lines total, no file moves/renames, no dependency/secret/CI changes,
  - confined to current feature scope (paths listed in the feature’s GUIDE.md),
  - adds/updates tests for the touched code, and all tests still pass.
- **Always require approval** if touching:
  - `.github/workflows/**`, `package.json`/`requirements.txt`, lockfiles, `Dockerfile`,
  - `migrations/**`, `*.sql`, infra/terraform, secrets, CI/CD settings,
  - public API contracts, auth/security logic, cross-feature refactors, file moves/renames.
  - executing tests or test related commands

## Advisory Flow
- Use ripgrep to search when possible.
- Advisors must follow AGENTS.md §Standard Flow before implementation.

## Sandbox & Network
- Local sandbox: `workspace-write`; no network unless explicitly approved. (If Cloud: follow environment defaults.)  
- Print commands before running; never run package scripts or migrations without approval. :contentReference[oaicite:9]{index=9}

## Structure-Change Policy
- No renames/moves or project reorg without a **Structure-Change micro-plan** (impact, rollback, test plan).

## Tests & Quality Gates
- Each code change must add/adjust **unit/integration** tests to satisfy acceptance criteria.
- **Security**: validate inputs, enforce authZ, avoid secret leakage; run `/deep-review` before merge.

## CI & Workflows
- Any change affecting tests/tooling must update `.github/workflows/**` (matrix, caches, coverage, path filters).
- Treat edits under `.github/workflows/**` as approval-required; provide a CI diff plan + verification steps.

## Visibility & Summaries
- For each task, output: proposed diff plan → patches → test results → summary of changes, risks, and follow-ups.

