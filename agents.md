# AGENTS.md — Advisors Only (No Execution)

Advisors analyze and propose diffs/checks; they never execute tools or run commands. All execution follows CODEX.md.

## Advisors & Outputs
- **ts-advisor**: types & boundaries; no `any`; error boundaries; consistent exports.
- **security-advisor**: authN/Z, input validation, secret handling, CSRF/SSRF/injection.
- **perf-advisor**: budgets, N+1 avoidance, payload size, caching.
*(Add db/api/dir advisors per feature when needed.)*

## Session Behavior
- run_mode: **assist**
- pause_on: [pending_approval, error, missing_tool, large_diff]
- Return: checklists, line-anchored findings, small diff plans, risk/mitigation notes.

## Standard Flow
1) **Evidence sweep** (ripgrep) → where code/config/tests live.
2) **Docs check** (context7) → short official snippets (title+link+date).
3) **Plan** → 3–7 steps, success checks, rollback notes.
4) **Proposed diffs** → file-by-file changes + tests (await approval).
5) **Persist** → append decisions to `docs/DECISIONS.md`; update `CHANGELOG.md`.
6) **Verify** → targeted checks; concise summary.
## Repo Invariants (enforced)
- Add/adjust tests with code changes; keep contracts and error boundaries explicit
- Type correctness (no `any` where strict types expected); logging for libs; no `sys.exit` in libs
- Config from ENV/TOML → typed config object
- Avoid N+1; caches documented; input validation and authZ for protected paths

## Tooling Registry (Capabilities)
- Code search (preferred: ripgrep; fallback: IDE/LSP search)
- Docs lookup (preferred: context7/official docs; fallback: project docs/README)
- Planning (structured chain-of-thought tool; fallback: outline using bullets)
- Logging/trace insertion (suggest exact file:line; fallback: print/console.log with labels)
Guideline: If a preferred tool is unavailable (local or Cloud), degrade gracefully and state the fallback used.

## Execution Policy
- Advisors provide analysis only. All execution/command runs follow CODEX.md.
- When in doubt, stop and request approval as per CODEX.md.