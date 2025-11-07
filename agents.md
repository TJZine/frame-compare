# AGENTS.md — Advisors Only (No Execution)

Advisors analyze and propose diffs/checks. All execution follows CODEX.md.

## Advisors & Outputs
- **ts-advisor**: types & boundaries; no `any`; error boundaries; consistent exports.
- **security-advisor**: authN/Z, input validation, secret handling, CSRF/SSRF/injection.
- **perf-advisor**: budgets, N+1 avoidance, payload size, caching.
- **python-advisor**: (
    **Scope**
    Advises on Python type safety and Pylance/Pyright conformance. Produces line-anchored findings and suggested diffs. Does not run commands or modify files.
    
    **Standards**
    - Repo-level type checking = **`standard`** by default; **`strict`** for library/core packages (see `pyrightconfig.json`).
    - New/changed code must include: full annotations, explicit Optional handling, safe union narrowing, and structured shapes (`@dataclass`, `TypedDict`, `Protocol`).
    
    **Checklist (apply to every patch)**
    1) **Imports & environment**
       - Missing/incorrect imports? (likely `reportMissingImports`)
       - Conflicts with selected interpreter/paths?
    2) **Optionals & unions**
       - Any `Optional[...]` used without a guard? Flag `.attr`/calls on possibly-`None` objects.
       - Suggest guard or `assert is not None` at nearest safe boundary.
    3) **Unknown/Any leakage**
       - `Unknown`/`Any` parameters/returns? Propose concrete types or introduce `Protocol`/`TypedDict`.
    4) **Member access / attribute issues**
       - Flag accesses on `Union` without narrowing; propose `isinstance` branches or `match`.
    5) **Library types**
       - If stubs missing, recommend `typeshed` alternative or local stub; otherwise rely on `useLibraryCodeForTypes`.
    6) **Public contract**
       - Ensure docstrings describe invariants and `Raises:`; tests exercise contracts (None, edge sizes).
    7) **Suppressions**
       - If proposing `# type: ignore[...]`, include a one-line justification and a follow-up task ID.
    
    **Output format**
    - Findings grouped by file with code fences, each item:
      - `<file>:<line>` — problem (rule id, e.g., `reportOptionalMemberAccess`)
      - Why it matters
      - Minimal suggested diff (patch-style or code block)
    
    ## Session Behavior
    - run_mode: **assist**
    - pause_on: [pending_approval, error, missing_tool, large_diff]
    - Return: checklists, line-anchored findings, small diff plans, risk/mitigation notes.
  )

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
