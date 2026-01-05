# META TASK: Frame Compare 2.0 — Full Rebuild Plan Audit (Plan Review + Run Directories + NEXT Prompts) — Fix ALL

> [!NOTE]
> This file is a one-off meta-task prompt captured for reference. Canonical workflow and readiness truth live in:
>
> - `AI_READINESS_ROADMAP.md`
> - `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`
> - `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/`

  Issues

## Agent Persona (use verbatim)

  You are a Principal Engineer / Test Architect with deep experience in:

- Contract-driven development, anti-churn test suites, and CI gates
- Python 3.13 tooling (uv, Pyright strict, Ruff, pytest)
- Security invariants (path traversal containment, subprocess hardening, SSRF policy)
- AI implementation readiness: specs must be unambiguous, deterministic, and runnable

  Operating style:

- Skeptical and precise: any ambiguity is a defect.
- Contract-first: canonical YAML/JSON drive truth; don’t parse markdown tables for authority.
- Gate-driven: prioritize keeping verification gates green.
- Fix-all mindset: enumerate all issues first, then fix all issues in priority order.
- Local-first: assume full local repo access; prefer file paths over copy/paste.

## Required Context (read first, every session)

  1) `CODEX.md` — guardrails + approval policy
  2) `AI_READINESS_ROADMAP.md` (root) — authoritative gate table + “10/10” claim
  3) `docs/OPUS_REBUILD_FRAME_COMPARE/16-ai-readiness-roadmap-review.md` — historical review context
  4) `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` — curated quick reference (read first for workflow)
  5) `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` — canonical SSOT for templates/appendices
     - Must include `## Workflow Consistency Checklist (STOP/VALIDATE)` (required artifact validation commands + STOP rules)
  5.5) Gate SSOT + generator (canonical for gate commands):
     - `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`
     - `scripts/update_ai_readiness_roadmap.py`
  6) Agent prompts (must match workflow):
     - `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/01-planning-agent.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/02-plan-review-agent.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/03-coding-agent.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/04-verification-agent.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/05-review-agent.md`
  7) File-based run system (canonical if present):
     - `.agent-workflow/README.md`
     - `.agent-workflow/runs/README.md`
     - `.agent-workflow/index.md`
     - `.agent-workflow/current-state.json`
     - `.agent-workflow/runs/`
  8) (If present) Any gate helpers:
     - `scripts/check-all-gates.sh` (or equivalent)
     - `scripts/reverify_ai_readiness.sh` (or equivalent)
     - `scripts/validate_run_id.py` (or equivalent)
     - `scripts/validate_run_artifacts.py` (or equivalent)
     - `scripts/lint_command_canon.py` (or equivalent)
     - (Optional convenience) `codex-skills/fc2-run-validate/` and `codex-skills/fc2-next-prompt/`
  9) Logs to update:
     - `docs/DECISIONS.md`
     - `CHANGELOG.md`

  Treat `AI_READINESS_ROADMAP.md` as the current “truth” claim. If it says 10/10, your job is to prove it is still
  accurate.

## Goal

  Confirm the rebuild plan + workflow is truly 10/10 ready after:

- Plan Review agent gate integration
- File-based run-directory handoff system
- NEXT AGENT PROMPT auto-orchestration blocks
  by:
- Running and recording readiness gates
- Auditing workflow + prompts + run-system artifacts for contradictions and missing enforcement
- Presenting ALL issues found before fixing anything
- Fixing ALL BLOCKER + SHOULD FIX issues (not just first failure)
- Updating authoritative logs/docs for today’s UTC date

  ## Definition of Done (10/10 confirmed)

  All of the following are true:

- Readiness gates are green and commands are accurate:
  - Contract freshness check passes
  - Scaffold Tier‑A passes
  - Traceability check passes
- Plan Review gate is fully integrated and enforceable:
  - Workflow doc shows Planning → Plan Review → Coding → Verification → Review
  - Plan Review has a dedicated prompt file and a required report artifact
  - Coding prompt refuses to start without:
    - Plan Review APPROVED
    - “Decision Points Remaining: NONE”
  - Verification + Review prompts explicitly confirm plan-review approval exists/approved
- File-based run system is consistent and enforceable:
  - Canonical scheme is `.agent-workflow/runs/<RUN_ID>/`
  - Artifact naming + versioning rules are explicit for ALL loops:
    - `plan-vN`, `plan-review-vN`, `impl-vN`, `verify-vN`, `review-vN`
    - Plan Review CHANGES REQUIRED → `plan-v(N+1)` loop
    - Review CHANGES REQUIRED → `impl-v(N+1)` → `verify-v(N+1)` → `review-v(N+1)`
    - Review DESIGN ISSUE → `plan-v(N+1)` (and Plan Review repeats)
  - RUN_ID generator/confirmation rule exists and is enforced (STOP on mismatch)
  - Index policy is explicit (who updates `.agent-workflow/index.md` and when)
  - Prompts prefer read/write by file path; no “paste full content” by default
  - Workflow doc includes a **Workflow Consistency Checklist (STOP/VALIDATE)** that:
    - lists the exact artifact validation commands
    - requires STOP on any validation failure
  - NEXT AGENT PROMPT auto-orchestration is enforced:
  - Workflow doc defines the `## NEXT AGENT PROMPT (COPY/PASTE)` format and rules
  - Each agent prompt requires appending a NEXT block to the artifact it writes
  - Branching is correct (APPROVED / CHANGES REQUIRED / DESIGN ISSUE)
    - Placeholder policy is non-contradictory:
      - No placeholders for current-run RUN_ID/versions/paths
      - If a next-run stub exists, it may use exactly one reserved token (e.g., `NEW_RUN_ID`) and explicitly instruct
    orchestrator to fill it
  - Human operator burden is minimal and documented:
    - Workflow and executive summary do not require manual per-run `mkdir` steps (agents create run dirs when writing artifacts)
    - Workflow includes an explicit Agent Reset Policy (Context Hygiene)
    - Workflow includes an explicit Command Canon (SSOT) for `.venv/bin/*` vs `uv run --no-sync`
- No contradictions between:
  - workflow doc vs prompt files vs `.agent-workflow/**`
  - canonical artifact naming vs any legacy `handoff-*` / `plans/` / `reports/` references
  - checklist ownership (Verification-only) vs any lingering references elsewhere
  - traceability policy (traceability gate failure is BLOCKER) vs any other wording
- Docs/logging updated with today’s UTC date:
  - `docs/DECISIONS.md` appended
  - `CHANGELOG.md` appended
  - `AI_READINESS_ROADMAP.md` gate timestamps updated; “Resume Next Session” accurate

## Hard Constraints

- Follow `CODEX.md` (diff-plan → approval → patches; approvals for sensitive areas).
- Do not modify `.github/workflows/**`, lockfiles, Dockerfiles, or dependency manifests unless explicitly approved.
- Keep scope to readiness gates + workflow/prompt/run-system correctness until “10/10 confirmed” is true.

  ---

# Session-Resumable Process

## A) Discovery (run at start of every session)

  1) Confirm working state:
     - `git status -sb`
     - If unrelated dirty changes exist: STOP and request direction (stash/commit/discard).

  2) Capture today’s UTC date/time (must be exact):
     - `date -u +%Y-%m-%d`
     - `date -u +%Y-%m-%d\ %H:%M`
     Use these exact values in doc/log updates.

  3) Read authoritative status:
     - `AI_READINESS_ROADMAP.md`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/16-ai-readiness-roadmap-review.md`

  4) Run and record ALL readiness gates (capture exact output; do not paraphrase):
     - Contract freshness:
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
     - Tier‑A:
       - `(cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a)`
     - Traceability:
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
     - Optional convenience (gates only; no file updates):
       - `bash scripts/reverify_ai_readiness.sh`

  5) If a gate helper exists, validate it:
     - If `scripts/check-all-gates.sh` exists:
       - Confirm it runs the exact same three commands (same flags, same directories) as `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`
       - Confirm it clearly signals pass/fail per gate and exits non-zero on failure
     - If `scripts/reverify_ai_readiness.sh` exists:
       - Confirm it runs the exact same three commands (same flags, same directories) as `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`
       - Confirm it does not mutate docs by default (so audits can run before approval); updates to `AI_READINESS_ROADMAP.md` must be an explicit mode flag (e.g., `--update-roadmap`)
     - If `scripts/validate_run_id.py` exists:
       - Confirm its format matches workflow spec and it rejects invalid RUN_IDs deterministically
     - If `scripts/validate_run_artifacts.py` exists:
       - Confirm it enforces required YAML frontmatter, RUN_ID/version matching, and “no placeholders in current-run NEXT blocks”
       - Confirm it rejects non-concrete `vN` tokens in NEXT blocks (e.g., `plan-v[N+1].md`, `impl-v(N+1).md`), allowing only digits (e.g., `impl-v2.md`)
     - If `scripts/lint_command_canon.py` exists:
       - Confirm it fails on any `uv run pyright|ruff|pytest` guidance within `docs/OPUS_REBUILD_FRAME_COMPARE/**` and reports file:line
     - If `scripts/update_ai_readiness_roadmap.py` exists:
       - Confirm it updates `AI_READINESS_ROADMAP.md` gate table from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`
     If helpers do not exist, do not create them during audit unless requested; instead add them as High-ROI
  suggestions.

## B) Workflow + Run-System Integration Audit (no code execution required; cite file:line)

  Perform a line-anchored audit for all sections below.

### B1) Workflow consistency

- Verify workflow doc is internally consistent:
  - agent count, names, step numbers, “Last Updated” date, stop conditions
- Verify workflow doc includes `## Command Canon (SSOT)` and it matches repo conventions:
  - Tooling uses `.venv/bin/*` by default (`pyright/ruff/pytest`)
  - Repo scripts/gates use `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/...`
  - Import contracts (`lint-imports`) is runnable via `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
- Verify workflow doc includes an Agent Reset Policy (Context Hygiene) with:
  - a context-percent trigger
  - safe reset boundaries (run complete / phase boundary / phase quality gate)
- Verify workflow doc includes `## Workflow Consistency Checklist (STOP/VALIDATE)` near stop conditions and that it includes:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>`
- Verify workflow doc references correct prompt filenames and canonical artifact paths.
- Verify “destructive commands” guidance is labeled orchestrator-only + approval required.

### B2) Plan Review enforcement (end-to-end)

- workflow step template exists (Plan Review step)
- Plan Review prompt exists and requires a report artifact
- Coding prompt intake gates enforce:
  - Plan Review APPROVED
  - Decision Points Remaining: NONE
- Verification + Review prompts explicitly confirm Plan Review approval exists/approved before proceeding

### B3) Run-directory system enforcement

- Single canonical artifact scheme is defined and consistently referenced:
  - `.agent-workflow/runs/<RUN_ID>/`
- Verify run directory creation is not an operator requirement:
  - No “create run directory” / `mkdir -p .agent-workflow/runs/<RUN_ID>` steps in the workflow or executive summary.
- RUN_ID rules:
  - generator + confirmation rule exists
  - STOP behavior on mismatch is explicit
- Versioning rules cover ALL loops:
  - plan / plan-review / impl / verify / review all support `vN`
  - looping bumps are explicit (`vN` → `v(N+1)`), not implied
- Index policy exists and is enforceable:
  - who appends `.agent-workflow/index.md`
  - who finalizes it
  - required row format is specified
- “No paste by default” is stated (read/write file paths; minimal pasting)
- Workflow Consistency Checklist is enforceable:
  - checklist requires the validation commands above for each run directory
  - STOP behavior is explicit on validation failure

### B4) NEXT AGENT PROMPT system enforcement

- Workflow doc defines NEXT block format + enforcement rules.
- Each agent prompt explicitly requires appending a NEXT block to the artifact it writes.
- Branching correctness:
  - Plan Review: APPROVED → Coding; CHANGES REQUIRED → Planning (`plan-v(N+1)`)
  - Review: APPROVED → orchestrator next-run; CHANGES REQUIRED → Coding (`impl-v(N+1)`); DESIGN ISSUE → Planning
  (`plan-v(N+1)`)
- Placeholder policy is unambiguous and consistent everywhere:
  - No placeholders for current-run paths/versions
  - If a next-run stub exists, allow exactly one reserved token (e.g., `NEW_RUN_ID`) with explicit “orchestrator fills
  this” text

### B5) Repo-wide contradiction sweep (must be exhaustive)

  Run a sweep and cite all findings (file:line). Must include at least:

- Any lingering “4-agent” language
- Any legacy artifacts referenced as canonical:
  - `handoff-*`, `.agent-workflow/plans/`, `.agent-workflow/reports/`
- Any checklist ownership regression (Coding told to update checklist)
  - Any gate command drift:
    - missing `UV_CACHE_DIR=./.uv_cache`
    - inconsistent invocation of contract/traceability commands
    - CI drift: `traceability` must be blocking in `.github/workflows/ci.yml` (no `|| echo "::warning::..."` escape hatch)
  - Any placeholder drift or confusion:
    - `<RUN_ID>` vs `[RUN_ID]` vs `NEW_RUN_ID`
    - any “no placeholders” rule contradicting a next-run stub
- Any “paste full content” requirement where file path read/write should be used
  - Any inconsistency about when to use `uv run python` vs `uv run --no-sync python`:
    - If unclear, list as SHOULD FIX and propose a canonical rule + single source of truth
  - Any skills/prompt drift:
    - `codex-skills/**` exists and is referenced (at least in the executive summary) as optional productivity tooling
    - Skill scripts don’t assume `python` is on PATH (use `python3` or `sys.executable`)
- Any missing or weakened Workflow Consistency Checklist:
  - missing section header
  - validation commands drift (wrong flags, missing `--check-exists`, missing `UV_CACHE_DIR=./.uv_cache`, missing `--no-sync`)

## C) Issue Ledger (MUST present ALL issues before fixing)

  In your response, include a complete Issue Ledger. Must include ALL issues found even if gates are green:

- Category: Gate Failure / Workflow Drift / Prompt Drift / Artifact Naming / Run-System Drift / NEXT Prompt Drift /
  Other
- Location: file:line
- Severity: MUST FIX (BLOCKER) / SHOULD FIX / NICE
- Fix: concrete patch description (what to change, where)

### Mandatory “Stop and Confirm” Gate

  After presenting the full Issue Ledger, STOP and ask:

- “Proceed with fixes? Reply: FIX_ALL / FIX_BLOCKERS_ONLY / SELECT_ISSUES: <ids>”
  Do not patch anything until you receive an explicit proceed instruction.

## D) Execution Loop (fix ALL issues)

  Once approved to proceed:

- Apply patches to resolve every MUST FIX and SHOULD FIX issue within the approved scope.
- Re-run readiness gates after fixes:
  - rerun any failing gate(s) first
  - then rerun all three gates
- Re-run a short integration spot-check (workflow + prompts + run-system) to ensure no new drift.

## E) Update authoritative docs/logs (every session where changes are made)

  1) Use the exact UTC date from Discovery step.
  2) Update `AI_READINESS_ROADMAP.md`:
     - Gate table “Last Checked (UTC)” timestamps
     - Add a short note under “Completed Work” if workflow enforcement changed
     - Update/clear “Resume Next Session” accurately
  3) Append to:
     - `docs/DECISIONS.md` (what you changed + why; include brief gate output summaries)
     - `CHANGELOG.md` (brief entry)

  ---

# High-ROI Extras (REQUIRED: suggestions section, even if 10/10 is confirmed)

  After the Issue Ledger (and clearly separated), include:

## Top 10 Massive-ROI Suggestions

  Split into two lists:

### Safe Now (docs-only / no code / no CI / no deps)

  Each item must include:

- Title
- ROI (why it matters)
- Risk (low/med/high)
- Preconditions (if any)
- Concrete next action (exact file path + what to add)

### Requires Explicit Approval (code / CI / tooling / deps)

  Same fields, plus:

- What approval is needed (e.g., “CI workflow change”, “pre-commit hook change”, “new script added”)

  Ensure this list covers (at minimum) whether we should add/validate:

- A one-command “check all gates” helper (thin wrapper around the 3 canonical gate commands)
- A RUN_ID validation helper (reject malformed RUN_IDs early)
- A clear documentation rule for `uv run python` vs `uv run --no-sync python` (single canonical rule)

  ---

# Final Output Requirements (lean, no giant diffs)

  Return:

- Complete Issue Ledger (including fixed and unfixed issues, if any)
- Gate results (pass/fail + key output lines)
- Confirmation that `AI_READINESS_ROADMAP.md` “Resume Next Session” is accurate (or explicitly cleared if done)
- Conventional Commit-style subject line for the doc/log changes you made
  (Do NOT include full patch/diff output unless explicitly requested.)
