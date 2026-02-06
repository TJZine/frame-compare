# AGENTS.md — Frame Compare 2.0 Agent Guide (Token-Efficient)

This file is consumed by “IDE agents” (e.g., antigravity / Opus) as high-signal project constraints.
Keep it short and actionable; do not reprint SSOT specs or workflow templates here.

## SSOT Pointers (Read These, Don’t Re-Invent)

- Guardrails + approvals: `CODEX.md`
- Canonical multi-agent workflow + templates (SSOT): `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`
- Workflow quick reference (preferred first read): `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md`
- Canonical contracts (SSOT): `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`
- Import layering SSOT: `importlinter.ini`
- Tooling config SSOT: `pyproject.toml` (`[tool.pyright]`, `[tool.ruff]`, pytest markers)

## Codex Collab Setup (Repo Defaults)

- Codex team config: `.codex/config.toml` (includes FC-2.0 role profiles for per-agent model + reasoning effort)
- Codex skills: `.codex/skills/` (symlinks into `codex-skills/` for compatibility)
- Subagent autopilot: `fc2-collab-autopilot` (run FC-2.0 end-to-end with local subagents + strict STOP gates)
- Full automation entrypoint: `python3 scripts/fc2_autopilot.py`

## STOP Conditions (Hard)

- Required input artifact missing → STOP (do not guess versions or “latest”).
- Plan Review verdict ≠ `APPROVED` or Decision Points Remaining ≠ `NONE` → STOP (Coding must not proceed).
- Plan/spec anchor validation fails → STOP and fix wiring:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/<RUN_ID>/plan-vN.md`
- Contract freshness gate fails → STOP and regenerate via script (never hand-edit derived views):
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`

## Command Canon (Use These Exact Commands)

Bootstrap (if `.venv/bin/*` missing):

```bash
uv sync --group dev --frozen
```

Quality gates:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Contract + traceability gates:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

## Python Constraints (Project-Wide)

- Type checking: Pyright = `standard` repo-wide (see `pyproject.toml` / `pyrightconfig.json`).
- No implicit `Any`: all new/changed functions have full parameter + return annotations.
- Explicit `Optional[...]` handling: guard/early-return/assert at the nearest safe boundary.
- Union narrowing required: use `isinstance(...)` / guards; no unchecked member access.
- Prefer explicit shapes: `@dataclass`, `TypedDict`, `Protocol` over loose dicts/tuples.
- No `sys.exit()` in library code (CLI may map errors to exit codes).
- Determinism: stable sorting, stable JSON output, seeded randomness (when applicable).
- Public functions include docstrings describing invariants and `Raises:` (where relevant).

## Tests & External Dependencies

- Default unit tests must not require network, VapourSynth, or FFmpeg.
- Use pytest markers for opt-in tests (see `pyproject.toml` markers such as `vs_required`, `integration`, `network`).
- If a test would invoke external tools, stub/mock at the module boundary or gate behind a marker.

## Run Artifacts (Workflow Summary)

- All run artifacts live under `.agent-workflow/runs/<RUN_ID>/` (see SSOT workflow docs for exact templates).
- Artifact versions are explicit; never guess `vN`.
- Every artifact ends with `## NEXT AGENT PROMPT (COPY/PASTE)` containing concrete RUN_ID + versions.
- Ownership:
  - Coding Agent: code/tests + `impl-vN.md` only
  - Verification Agent: gates + checklist/index + `verify-vN.md` only
  - Review Agent: `review-vN.md` + final index verdict only

## Workflow Exceptions (Documented, Narrow)

- Verification may apply **Ruff-only** mechanical auto-fixes (`ruff check --fix` + `ruff format`, no `--unsafe-fixes`)
  when Ruff is the only failing gate, limited to run-touched failing files, and must emit `impl-v(N+1).md`
  documenting the mechanical edits.
- Coding must run the full local gate suite before handoff to avoid verification churn (see Coding Agent prompt).

## Codanna + Sequential‑Thinking Workflow (Detailed; Used by IDE Agents)

This section is intentionally detailed because some IDE agents do not read `CODEX.md`.

### Sequential Thinking Context Management

- Plan of record lives in the run artifacts (`.agent-workflow/runs/<RUN_ID>/plan-vN.md` + `plan-review-vN.md`).
  Use Sequential‑Thinking MCP to capture structured thoughts across Scoping → Research & Spike → Implementation →
  Testing → Review.
- Before making non-trivial changes in shared/public code, use Codanna for impact framing:
  - Start with `semantic_search_with_context` to locate the right symbols and context.
  - Then run `analyze_impact` on the relevant `symbol_id` to enumerate callers, type usage, and composition.
- When calling `process_thought`, include `thought_number`, `total_thoughts`, and `next_thought_needed` when known.
  If any are omitted, the server will infer sensible defaults; do not retry just to backfill fields. Do not pass
  arbitrary extra fields; if the bridge requires a wrapper, use `kwargs` or `legacy_kwargs` with JSON only.
- When calling `process_thought` or `generate_summary`, only echo a condensed digest in chat (stage, immediate next
  steps, blockers/alerts). Never dump raw JSON payloads back to the user; the MCP log preserves them.
- Archive or truncate aged thoughts once they are logged—keep roughly the last 7–10 items in active memory (expand
  temporarily if needed) and rely on the MCP server for historical retrieval instead of reprinting prior entries.
- Prefer the lighter summary path (short synopsis rather than full analytics) whenever detailed telemetry is not
  needed for the current decision; escalate to verbose output only for debugging or reviewer requests.
- Note in task reports when you have rotated context so reviewers know why earlier thoughts are omitted.
- When filling metadata (`files_touched`, `tests_to_run`, `dependencies`, `risk_level`, `confidence_score`, etc.),
  provide real values or leave the schema defaults/empty lists; never fabricate filenames/tests/risk signals.
- Keep logging thoughts for each stage in that sequence—do not skip a phase unless you explicitly state why it does
  not apply.
- Set `next_thought_needed=false` only when you’re done (or when explicitly stopping early—state why). If omitted, the
  server assumes more thoughts are needed.

### MCP Call Logging (Always)

- Every Context7, Codanna, or Fetch MCP invocation must log tool name, URL (if applicable), format, `max_length`,
  `start_index`, chunk count, latency, and summarize the returned snippet (or quote the relevant portion) directly in
  your response or run artifact.

### Codanna Workflow

- **Roles**
  - **Codanna** provides discovery/context via semantic search, symbol lookups, and impact analysis.
  - **Sequential‑Thinking MCP** records structured thoughts; keep entries short (stage + metadata) and obey
    `guidance.recommendedNextThoughtNeeded`.
  - The run plan artifact (`plan-vN.md`) is the authoritative plan of record; do not treat ST as the planning store.
- **Tool priority (Codanna)**
  - **Tier 1 (code)**: `semantic_search_with_context`, `analyze_impact` (default limit=5, threshold≈0.5, no `lang`
    unless noise is high; raise limit to 8–10 for ambiguity).
  - **Tier 1 (docs)**: `search_documents` when document collections are indexed (filter by collection/path when
    possible).
  - **Tier 2**: `find_symbol`, `get_calls`, `find_callers` to confirm call chains and disambiguate symbols.
  - **Tier 3**: `search_symbols`, `semantic_search_docs` for broader sweeps once Tier 1/2 context is captured.
- **Accuracy-first defaults**
  - **Discovery:** start with `semantic_search_with_context`, summarize key findings, prefer symbol_id chaining, and
    run `analyze_impact symbol_id:<ID>` before touching public/shared/cross-cutting code; widen the search scope (lower
    threshold, raise limit) when context feels insufficient.
  - **Docs search:** use `search_documents` for indexed docs; re-index or enable the file watcher if results look
    stale.
  - **Docs-heavy tasks (plans/schemas/specs/roadmaps):** avoid single “kitchen‑sink” queries. Split into multiple small
    `search_documents` calls (4–8 keywords, `limit` 3–5, `collection="docs"`). If timeouts or coverage gaps persist,
    fall back to `ripgrep` for exhaustive sweeps, then return to Codanna for targeted chunks.
  - **Plan:** keep `update_plan` aligned with Codanna’s findings; add verification and rollback steps for high-risk
    workstreams.
  - **Thoughts:** include `stage`, `files_touched`, `dependencies`, `tests_to_run`, and `risk_level` when you have real
    evidence; omit unknowns and let defaults stand. Use stage aliases (e.g., “Planning” → Implementation) and keep
    `next_thought_needed=true` until tests succeed and a Review thought is recorded.
  - **Verification:** cross-check impacted files from Codanna’s results against the actual diff and document how
    tests/rollbacks cover high-risk areas; when context is unclear, prefer broader discovery over assumptions.
- **Workflow**
  1. **Discovery (Codanna)** – run Tier 1 queries with the defaults above; use `search_documents` for indexed docs,
     chain into `analyze_impact`, and use Tier 2 lookups to trace usages; capture symbol_ids and summarize
     implications.
  2. **Plan (Artifact)** – update the plan by writing a new `plan-v(N+1).md` that links to Codanna context and lists
     verification/rollback actions when risk warrants it.
  3. **Thoughts (ST)** – log concise `process_thought` entries with known metadata; if fields are omitted, the server
     infers defaults; do not retry just to backfill. Stop when `guidance.recommendedNextThoughtNeeded` becomes false
     after Review.
  4. **Validate/Review** – run targeted tests, record outcomes, and conclude with a Review thought before closing.
