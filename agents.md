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
## Global Defaults (Always On)
- **Planning protocol = Sequential Thinking**: use Serena’s `think_about_*` tools (or, if unavailable, the fallback Sequential Thinking MCP) to draft a concise plan before proposing diffs. Sequential Thinking is for planning only—once the plan is logged, resume normal Serena analysis without juggling duplicate planners.
- **Docs lookup = context7**: pull short, dated snippets from official sources/best-practice docs for each claim. If unavailable, log the fallback.
- **Search = Serena first**: prefer Serena MCP search tools (`find_symbol`, `find_referencing_symbols`, `search_for_pattern`) for evidence sweeps; fall back to `ripgrep` when Serena is unavailable or insufficient. Respect repo ignores and log the fallback method used.
- **Project orchestration = Serena MCP**: use Serena for structured planning (sequential-thinking tools), symbol-aware code understanding (`get_symbols_overview`, `find_symbol`), and project memory (`write_memory`/`list_memories`) during analysis. Advisors still propose diffs; Codex executes per CODEX.md. If Serena’s sequential-thinking tools are unavailable, fall back to the generic Sequential Thinking MCP before using general bullet outlines.
- **Context lean**: Advisors remind Codex to follow CODEX’s Sequential Thinking Context Management rules (condense `process_thought` output, keep roughly the last 7–10 thoughts in working memory, and lean on MCP history for archives).
- **Metadata accuracy**: Flag hallucinated Sequential Thinking metadata—`files_touched`, `tests_to_run`, `dependencies`, `risk_level`, `confidence_score`, etc. should stay empty/default unless there is real evidence.

## Standard Flow
1) **Evidence sweep (Serena ➜ ripgrep)** → prefer Serena tools (`get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `search_for_pattern`) to enumerate where code/config/tests live. If Serena is unavailable or insufficient for the task, use `ripgrep` and record the fallback used.
2) **Docs check (context7 ➜ MCP)** → start with Context7 (title + link + date). When Context7 lacks the needed source, call the Fetch MCP server via `mcp__fetch__fetch`, constrain `max_length` (default ≤ 20000 chars), and log URL, timestamp, format (HTML/JSON/Markdown/TXT), `start_index`, and chunk count in your response plus `docs/DECISIONS.md`. Only fetch publicly reachable URLs; escalate before touching authenticated or private targets.
3) **Plan (Sequential Thinking)** → Switch Serena to `planning` mode for multi-step tasks, then call Serena’s `think_about_*` tools to capture the Scoping→Review thought loop. Only fall back to the generic Sequential Thinking MCP if Serena’s planner is down; otherwise avoid running two planners in parallel. Produce 3–7 steps, success checks, and rollback notes, then exit planning mode and continue with Serena’s regular analysis tools.
   - Confirm the agent keeps logging Scoping → Research & Spike → Implementation → Testing → Review thoughts and leaves `next_thought_needed=true` until that Review entry is recorded; flag any run that flips it to `false` prematurely.
4) **Proposed diffs** → file-by-file changes + tests (await approval).
5) **Persist** → append decisions to `docs/DECISIONS.md`; update `CHANGELOG.md`. Before adding an entry, run `date -u +%Y-%m-%d` (or equivalent) and stamp the log with that exact value—never extrapolate future dates. When referencing MCP output, cite the URL + timestamp (from that command) and summarize any key snippets directly in the response so reviewers can replay the call without re-fetching.
6) **Verify** → Advisors propose the exact verification commands and expected signals; Codex executes per CODEX.md. Prefer `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, and `.venv/bin/pytest -q` before fallbacks. If the local binary is missing, install dev deps (`uv sync --all-extras --dev`) and document the fix. Only fall back to `uv run`/`npx` when the local command is unavailable, and record any sandbox/cache issues plus mitigations (for example `UV_CACHE_DIR=./.uv_cache`). When you must run `npx pyright --warnings`, request escalated permissions for that command even if prior steps were sandboxed.
7) **Commit subject** → finish every task report with a Conventional Commit-style subject line (e.g., `chore: update packaging excludes`). This is what the user pastes into `git commit -m`, so it must include a type and summary per commitlint rules.
## Repo Invariants (enforced)
- Add/adjust tests with code changes; keep contracts and error boundaries explicit
- Type correctness (no `any` where strict types expected); logging for libs; no `sys.exit` in libs
- Config from ENV/TOML → typed config object
- Avoid N+1; caches documented; input validation and authZ for protected paths

- Serena MCP (analysis-first): use `get_current_config`, `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `search_for_pattern`, `think_about_*`, `list_dir`, `list_memories`, and `read_memory` to collect evidence. Advisors must not use editing tools (`insert_*`, `replace_symbol_body`)—propose diffs instead.
- Sequential Thinking MCP (fallback): use `process_thought`, `generate_summary`, and related tools if Serena’s thinking tools are unavailable.
- Code search (fallback): `ripgrep` when Serena is unavailable; otherwise prefer Serena’s symbol- and pattern-aware queries.
- Docs lookup (**required default: context7/official docs**; fallback: project docs/README with explicit note)
- External context MCP servers — Context7 stays first-line. Use Fetch MCP (`mcp__fetch__fetch`) for live docs and APIs (private-IP blocking + length limits per `/zcaceres/fetch-mcp`, 2025‑11‑10). For structured task decomposition, TaskFlow MCP enforces plan/approval phases and dependency tracking (`/pinkpixel-dev/taskflow-mcp`, 2025‑11‑10). For combined search + fetch, snf-mcp provides DuckDuckGo/Wikipedia search plus rate-limited HTML/Markdown retrieval (`/mseri/snf-mcp`, 2025‑11‑10). Record the server, tool name, key arguments, and cite the resulting snippet (URL + timestamp) every time.
- Planning (**required default: Serena sequential-thinking tools**; fallback: thorough bullet outline)
- Logging/trace insertion (suggest exact file:line; fallback: print/console.log with labels)
Guideline: If a preferred tool is unavailable (local or Cloud), degrade gracefully and state the fallback used.

## Execution Policy
- Advisors provide analysis only. All execution/command runs follow CODEX.md.
- MCP calls count as “analysis actions” but must be logged like commands: cite `source:<url>@<timestamp>` in findings, mention chunking/pagination, and mirror the metadata in `docs/DECISIONS.md`.
- When in doubt, stop and request approval as per CODEX.md.
 - Serena constraints: Advisors may call Serena analysis tools but must not perform editing operations; instead, include a minimal patch diff proposal.
