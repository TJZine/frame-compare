# CODEX.md — Project Guardrails

## Execution & Approvals

- Default: **diff-plan → approval → patches**. Advisors never execute.
- **Always-allowed checks (no extra approval)** — assume permission is granted:
  - `.venv/bin/pyright --warnings` (must run first; only fall back to `uv run pyright --warnings` or `npx pyright --warnings` if the local binary is unavailable. When using the `npx` fallback, request escalated permissions for that command.)
  - `.venv/bin/ruff check` (fallbacks: `ruff check`, `uv run ruff check`)
  - `.venv/bin/pytest -q` (unit/integration only; see Test Guardrails)
  - Read-only repo inspection: `rg` (preferred), `sed`, `nl`, `head`, `tail` for ≤250 line chunks
  - Codanna MCP discovery/analysis calls: `semantic_search_docs`, `search_documents`, `semantic_search_with_context`, `find_symbol`, `get_calls`, `find_callers`, `analyze_impact` (Codanna is discovery/context-only; editing still follows the diff-plan → approval flow)
- Autonomous changes allowed (no approval) **only if all are true**:
  - <= 300 changed lines total, no file moves/renames, no dependency/secret/CI changes,
  - confined to current feature scope (paths listed in the feature’s GUIDE.md),
  - adds/updates tests for the touched code, and all tests still pass.
- **MCP tools**: Context7 and Fetch MCP calls against public URLs with `max_length ≤ 20000` (≈20 KB) and recorded metadata (URL, timestamp, format, chunk count) are pre-approved. Any authenticated target, pagination burst (>5 sequential chunks), or private-network URL still requires explicit approval before execution.
- **Always require approval** if touching:
  - `.github/workflows/**`, `package.json`/`requirements.txt`, lockfiles, `Dockerfile`,
  - `migrations/**`, `*.sql`, infra/terraform, secrets, CI/CD settings,
  - public API contracts, auth/security logic, cross-feature refactors, file moves/renames.
  - executing tests that require network, external services, or non-ephemeral resources

### Sequential Thinking Context Management

- Plan of record lives in Codex via `update_plan`. Use Sequential‑Thinking MCP to capture structured thoughts across
  Scoping → Research & Spike → Implementation → Testing → Review.
- Before Codanna analysis, call `codanna_prompt` to frame impact/call‑graph questions and risks.
- When calling `process_thought`, include `thought_number`, `total_thoughts`, and `next_thought_needed` when known.
  If any are omitted, the server will infer sensible defaults; do not retry just to backfill fields. Do not pass
  arbitrary extra fields; if the bridge requires a wrapper, use `kwargs` or `legacy_kwargs` with JSON only.
- When calling `process_thought` or `generate_summary`, only echo a condensed digest in chat (stage, immediate next
  steps, blockers/alerts). Never dump the raw JSON payloads back to the user; the MCP log already preserves them.
- Archive or truncate aged thoughts once they are logged—keep roughly the last 7–10 items in active memory (expand
  temporarily if needed) and rely on the MCP server for historical retrieval instead of reprinting prior entries.
- Prefer the lighter summary path (short synopsis rather than full analytics) whenever detailed telemetry is not
  needed for the current decision; escalate to the verbose output only for debugging or reviewer requests.
- Note in task reports when you have rotated context (e.g., “older Sequential Thinking context archived per
  guidelines”) so reviewers know why earlier thoughts are omitted.
- When filling metadata (`files_touched`, `tests_to_run`, `dependencies`, `risk_level`, `confidence_score`, etc.),
  provide real values or leave the schema defaults/empty lists; never fabricate filenames, tests, or risk signals just
  to satisfy the shape.
- Keep logging thoughts for each stage in that sequence—do not skip a phase unless you explicitly state why it does
  not apply.
- Set `next_thought_needed=false` only when you’re done (or when explicitly stopping early—state why). If omitted, the
  server assumes more thoughts are needed.

## Global Defaults (Enforced)

1) **Planning = Codex plan + ST thoughts**
   - Use Codex `update_plan` for the authoritative plan.
   - Use Sequential‑Thinking MCP to log concise thoughts per stage (not as the plan store).
2) **Docs = context7 first** (cite official/best-practice; record date). If unavailable, log fallback.
3) **Search = Codanna first** (prefer Codanna MCP’s semantic/symbol search; use `search_documents` for indexed docs; fall back to ripgrep; respect repo ignores; log fallback).
4) **Discovery/Context = Codanna MCP** (use `semantic_search_docs`/`semantic_search_with_context` to shortlist; `search_documents` for indexed docs; `find_symbol`/`get_calls`/`find_callers` for precision; `analyze_impact` before risky changes). Codanna is not an editor.
5) **Verify** = run `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `.venv/bin/pytest -q` (only fall back to `uv run`/`npx`/system binaries after attempting `uv sync --group dev --frozen` to install the local venv; any `npx pyright --warnings` fallback must be executed with escalated permissions enabled). The `npm test`/Husky hook path now invokes `tools/run_pytest.mjs`, which sets `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` by default; export `FC_SKIP_PYTEST_DISABLE=1` on machines (e.g., Windows) that must keep plugin autoloading enabled.
6) **Output**: populate PR “Decision Minute” fields before proposing patches.
7) **Commit Title**: every task response must include a Conventional Commit-style subject (for example, `feat: …`, `chore: …`) that can be copied directly into `git commit -m`. State it explicitly before the summary so users running commit hooks don’t have to invent one.
8) **Log Dates Accurately**: when updating `docs/DECISIONS.md`, `CHANGELOG.md`, or similar logs, run `date -u +%Y-%m-%d` and use that exact stamp—do not future-date entries.

## Always-Allowed Commands (details)

Print each command before execution and capture exit code + duration. These checks may read/write their standard caches (`.venv/**`, `.uv_cache/**`, `~/.cache/uv/**`). If a host sandbox blocks `~/.cache/uv`, set `UV_CACHE_DIR=./.uv_cache` (already gitignored) and rerun the command.

```bash
# Primary (repo-local virtualenv)
.venv/bin/pyright --warnings
.venv/bin/ruff check
.venv/bin/pytest -q

# Fallbacks (auto-detected if the above fail)
uv run pyright --warnings
# Request escalated permissions when running this fallback:
npx pyright --warnings
ruff check
pytest -q
```

## Test Guardrails

- No network or external services during tests by default.
- Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for reproducible local and CI runs.
- Tests must not write outside the workspace; prefer tmp dirs/fixtures.
- Randomized tests must set deterministic seeds and assert invariants, not incidental state.
- Mark slow/integration suites; don’t run them under the always-allowed quick path.
- Log any environment toggles used (e.g., `-p no:vsengine`) in DECISIONS with rationale.

### Always-logged MCP calls

- Every Context7, Codanna, or Fetch MCP invocation must log tool name, URL (if applicable), format, `max_length`, `start_index`, chunk count, latency, and summarize the returned snippet (or quote the relevant portion) directly in your response.
- Respect server-side caps: Fetch MCP already enforces private-IP blocking and length filtering (`/zcaceres/fetch-mcp`, 2025‑11‑10); document any override (`DEFAULT_LIMIT`, pagination strategy) when you use it.
- When using broader MCP servers (e.g., TaskFlow MCP for workflow planning or snf-mcp for DuckDuckGo/Wikipedia search), include the server ID and describe the resulting artifacts so reviewers can replay the call.

## Escalation Playbook

1. If an allowed command/tool fails because of sandbox, missing permissions, or blocked cache paths, immediately rerun it with `with_escalated_permissions=true` and a one-sentence justification (e.g., “Need unsandboxed pyright to read node_modules”).
2. If the rerun still fails, capture the full stderr/exit code in your response and note the mitigation attempted (cache dir override, `uv sync`, etc.).
3. Never abandon a required check silently—either secure approval, provide the failure log, or propose an alternative verification path (e.g., `uv run pyright`) before moving on.

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
   - Propose running: `.venv/bin/pyright --warnings` first; only if the local binary fails or is missing should you fall back to `npx pyright --warnings`, and that fallback must be issued with escalated permissions requested up front.
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
- MCP fetch/context7 calls are permitted without extra approval because the servers enforce private-IP blocking, HTTP status validation, and chunked length limits (per `/zcaceres/fetch-mcp`, 2025‑11‑10). Still log URLs/timestamps and stop if a request would hit authenticated resources or violate robots/security policies.
- **Checks exception:** pyright/ruff/pytest (under Test Guardrails) may run without extra approval as long as they respect the guardrails above.

## Local Toolchain Expectations

- Bootstrap the virtualenv via `uv sync --group dev --frozen` (preferred; matches CI). If using pip, install the project editable plus dev tools explicitly (pip does not install uv dependency groups): `python -m venv .venv && .venv/bin/pip install -e . && .venv/bin/pip install pytest pytest-cov ruff pyright`.
- Activate `.venv` (or prefix commands with `.venv/bin/`) before running checks to ensure everyone uses the same binaries.
- When falling back to `uv run`, set `UV_CACHE_DIR` to a workspace path (for example `./.uv_cache`) if the default cache path is sandboxed.

## Structure-Change Policy

- No renames/moves or project reorg without a **Structure-Change micro-plan** (impact, rollback, test plan).

## Tests & Quality Gates

- Each code change must add/adjust **unit/integration** tests to satisfy acceptance criteria.
- If acceptance criteria require **real external deps** (VapourSynth + FFmpeg), run `bash tools/verify_docker_integration.sh` and require **zero skips** as part of verification.
- **Security**: validate inputs, enforce authZ, avoid secret leakage; run `/deep-review` before merge.

## CI & Workflows

- Any change affecting tests/tooling must update `.github/workflows/**` (matrix, caches, coverage, path filters).
- Treat edits under `.github/workflows/**` as approval-required; provide a CI diff plan + verification steps.

## Visibility & Summaries

- For each task, output: proposed diff plan → patches → test results → summary of changes, risks, and follow-ups.

## Codanna + Sequential‑Thinking workflow

- **Roles**
  - **Codanna** provides discovery/context via semantic search, symbol lookups, and impact analysis.
  - **Sequential‑Thinking MCP** records structured thoughts; keep entries short (stage + metadata) and obey `guidance.recommendedNextThoughtNeeded`.
  - **Codex `update_plan`** is the authoritative plan of record; do not treat ST as the planning store.
- **MCP transport (v0.8.4+)**: use HTTP transport (`/mcp`, client type `http`) instead of SSE.
- **Tool priority (Codanna)**
  - **Tier 1 (code)**: `semantic_search_with_context`, `analyze_impact` (default limit=5, threshold≈0.5, no `lang` unless noise is high; raise limit to 8–10 for ambiguity).
  - **Tier 1 (docs)**: `search_documents` when document collections are indexed (filter by collection/path when possible).
  - **Tier 2**: `find_symbol`, `get_calls`, `find_callers` to confirm call chains and disambiguate symbols.
  - **Tier 3**: `search_symbols`, `semantic_search_docs` for broader sweeps once Tier 1/2 context is captured.
- **Accuracy-first defaults**
  - **Discovery:** start with `semantic_search_with_context`, summarize key findings, prefer symbol_id chaining, and run `analyze_impact symbol_id:<ID>` before touching public/shared/cross-cutting code; widen the search scope (lower threshold, raise limit) when context feels insufficient.
  - **Docs search:** use `search_documents` for indexed docs; re-index or enable the file watcher if results look stale.
  - **Docs-heavy tasks (plans/schemas/specs/roadmaps):** avoid single “kitchen‑sink” queries. Split into multiple small `search_documents` calls (4–8 keywords, `limit` 3–5, `collection="docs"`). If timeouts or coverage gaps persist, fall back to `ripgrep` for exhaustive sweeps, then return to Codanna for targeted chunks.
  - **Plan:** keep `update_plan` aligned with Codanna’s findings; add verification and rollback steps for high-risk workstreams.
  - **Thoughts:** include `stage`, `files_touched`, `dependencies`, `tests_to_run`, and `risk_level` when you have real
    evidence; omit unknowns and let defaults stand. Use stage aliases (e.g., “Planning” → Implementation) and
    string inputs; keep `next_thought_needed=true` until tests succeed and a Review thought is recorded, then honor
    `guidance.recommendedNextThoughtNeeded` (or omit the flag to keep the loop open).
  - **Verification:** cross-check Codanna’s impacted files against the diff, ensure tests cover each high-risk area, and prefer expanding discovery scope rather than omitting context.
- **Workflow**
  1. **Discovery (Codanna)** – run Tier 1 queries with the defaults above; use `search_documents` for indexed docs, chain into `analyze_impact`, and use Tier 2 lookups to trace usages; capture symbol_ids and summarize implications.
  2. **Plan (Codex)** – update steps via `update_plan`, linking to Codanna context and listing verification/rollback actions when risk warrants it.
  3. **Thoughts (ST)** – log concise `process_thought` entries with known metadata; if any required fields are missing,
     the server infers defaults, so do not issue retries. Stop when `guidance.recommendedNextThoughtNeeded` becomes
     false after Review.
  4. **Validate/Review** – run the targeted tests, record outcomes, and conclude with a Review thought before closing.
- **ST usage guidance**
  - Keep payloads brief but complete; stage aliases and stringified metadata are accepted.
  - Respect `guidance.recommendedNextThoughtNeeded`; stop issuing follow-up thoughts when it flips to false after Review.
- **Verification guidance**
  - Cross-check impacted files from Codanna’s results against the actual diff and document how tests/rollbacks cover high-risk areas.
  - When context is unclear, prefer broader discovery (lower threshold or higher limit) over making assumptions.
