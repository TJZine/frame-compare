# CODEX.md — Project Guardrails

## Execution & Approvals
- Default: **diff-plan → approval → patches**. Advisors never execute.
- **Always-allowed checks (no extra approval)** — assume permission is granted:
  - `.venv/bin/pyright --warnings` (fallbacks: `uv run pyright --warnings`, `npx pyright --warnings`)
  - `.venv/bin/ruff check` (fallbacks: `ruff check`, `uv run ruff check`)
  - `.venv/bin/pytest -q` (unit/integration only; see Test Guardrails)
- Autonomous changes allowed (no approval) **only if all are true**:
  - <= 300 changed lines total, no file moves/renames, no dependency/secret/CI changes,
  - confined to current feature scope (paths listed in the feature’s GUIDE.md),
  - adds/updates tests for the touched code, and all tests still pass.
- **Always require approval** if touching:
  - `.github/workflows/**`, `package.json`/`requirements.txt`, lockfiles, `Dockerfile`,
  - `migrations/**`, `*.sql`, infra/terraform, secrets, CI/CD settings,
  - public API contracts, auth/security logic, cross-feature refactors, file moves/renames.
  - executing tests that require network, external services, or non-ephemeral resources

## Global Defaults (Enforced)
1) **Planning = Sequential Thinking** (generate a stepwise plan before patches).
2) **Docs = context7 first** (cite official/best-practice; record date). If unavailable, log fallback.
3) **Search = ripgrep first** (respect repo ignores). If unavailable, log fallback.
4) **Verify** = run pyright/ruff/pytest
5) **Output**: populate PR “Decision Minute” fields before proposing patches.
6) **Commit Title**: every task response must include a Conventional Commit-style subject (for example, `feat: …`, `chore: …`) that can be copied directly into `git commit -m`. State it explicitly before the summary so users running commit hooks don’t have to invent one.

## Always-Allowed Commands (details)
Print each command before execution and capture exit code + duration. These checks may read/write their standard caches (`.venv/**`, `.uv_cache/**`, `~/.cache/uv/**`). If a host sandbox blocks `~/.cache/uv`, set `UV_CACHE_DIR=./.uv_cache` (already gitignored) and rerun the command.

```bash
# Primary (repo-local virtualenv)
.venv/bin/pyright --warnings
.venv/bin/ruff check
.venv/bin/pytest -q

# Fallbacks (auto-detected if the above fail)
uv run pyright --warnings
npx pyright --warnings
ruff check
pytest -q
```

### Test Guardrails (for always-allowed pytest)
- **No external services**: skip DB/services unless ephemeral/mocked.
- **Filesystem scope**: writes must stay under repo temp dirs (pytest tmp_path). Fail closed if outside.


## Advisory Flow
- **Use ripgrep** for the evidence sweep and any searching (fallback must be logged).
- **Follow AGENTS.md §Standard Flow**; planning must use sequential thinking.

## Type Safety & Pylance/Pyright Quality Gates

**Policy**
- Type checking level: **Pyright/Pylance = `standard`** across the repo.
  - For library/core packages, raise to **`strict`** (via `pyrightconfig.json` executionEnvironments).
- All new/modified Python code MUST:
  - Include full type hints on function params/returns (no implicit `Any`).
  - Handle `Optional[...]` explicitly (early return, guard, or `assert x is not None`).
  - Narrow unions via `isinstance`/guards (no unchecked attribute access).
  - Avoid dynamic attributes; prefer `@dataclass`/`TypedDict`/`Protocol` for shape.
  - Keep public APIs stable; document invariants in docstrings.

**Gates (pre-merge)**
1) **Diff plan** → approval → **patch** (no auto-exec).
2) Before asking to merge, the assistant MUST:
   - Propose running: `npx pyright --warnings` (or equivalent) and wait for approval.
   - Report **zero errors** and **<= N warnings** (N defaults to 10; justify any above).
   - If errors occur, propose minimal diffs to fix them and re-check.
3) **Suppressions policy**
   - `# type: ignore[...]` allowed only with a one-line justification above and a follow-up ticket.
   - Prefer stubs/`TypedDict`/`Protocol` over blanket `Any`.
4) **Config is source of truth**: the repo’s `pyrightconfig.json` (or `[tool.pyright]`) governs analysis; do not override via editor-only settings.

**Reviewer checklist (assistant must confirm)**
- No new `Any` leaks, unknown members, or unchecked Optional access.
- Library calls typed (stubs present or `useLibraryCodeForTypes` suffices).
- Tests cover the typed contract (positive + None/edge cases).

## Sandbox & Network
- Local sandbox: `workspace-write` except for testing; **no network** unless explicitly approved (If Cloud: follow environment defaults).
- Always print commands before running; never run package scripts or migrations without approval.
- Tool caches required by the approved checks (`.venv/**`, `.uv_cache/**`, `~/.cache/uv/**`) are allowed. If a host blocks `~/.cache/uv`, set `UV_CACHE_DIR=./.uv_cache` and rerun.
- **Checks exception:** pyright/ruff/pytest (under Test Guardrails) may run without extra approval as long as they respect the guardrails above.

## Local Toolchain Expectations
- Bootstrap the virtualenv via `uv sync --all-extras --dev` (preferred) or `python -m venv .venv && .venv/bin/pip install -e .[dev]` so `.venv/bin/pyright`, Ruff, and Pytest are always available offline.
- Activate `.venv` (or prefix commands with `.venv/bin/`) before running checks to ensure everyone uses the same binaries.
- When falling back to `uv run`, set `UV_CACHE_DIR` to a workspace path (for example `./.uv_cache`) if the default cache path is sandboxed.


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
