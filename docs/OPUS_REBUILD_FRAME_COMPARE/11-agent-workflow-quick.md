# Frame Compare 2.0 — Agent Workflow Quick Reference

> **Version:** 1.0
> **Last Updated:** 2026-01-02
> **Purpose:** Curated, token-efficient entry point for agents — read this first

---

## 1. What Is SSOT

**Canonical SSOT:** `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` remains the single source of truth for the full multi-agent workflow, templates, and appendices.

**This document** is a curated operational subset for quick agent onboarding.

> [!IMPORTANT]
> If this quick doc conflicts with the canonical doc, **the canonical doc wins**.

> [!IMPORTANT]
> If you need to change workflow rules, update the canonical doc first, then refresh this quick reference.

---

## 2. Contract-First Loop (When Contracts Change)

**Canonical contracts location:** `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`

Derived docs and codegen are **never edited by hand**.

### When any canonical contract changes

1. **Edit** the canonical file in `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`
2. **Regenerate** derived views:

   ```bash
   UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py
   ```

3. **Verify freshness** before handoff:

   ```bash
   UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
   UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
   ```

4. **Proceed** only after checks pass

---

## 3. Run Artifact Rules

### RUN_ID Format

```
RUN_ID = YYYY-MM-DD__p<phase>-<item>__<short_slug>
```

For meta runs (non-checklist / maintenance tasks):

```
RUN_ID = YYYY-MM-DD__meta__<short_slug>
```

**Examples:**

- `2025-12-25__p1-1-1__config-module`
- `2025-12-26__meta__ai-readiness-audit`

### Run Directory Layout

```
.agent-workflow/runs/<RUN_ID>/
├── plan-v1.md
├── plan-v2.md         (if revision required)
├── plan-review-v1.md
├── plan-review-v2.md  (if revision required)
├── impl-v1.md
├── impl-v2.md         (if review requires changes)
├── verify-v1.md
├── verify-v2.md       (if re-verification required)
├── review-v1.md
└── review-v2.md       (if re-review required)
```

### Versioning Rules

1. **Start at `v1`** for all artifacts
2. **If Plan Review requires changes:** Planning Agent emits `plan-v(N+1).md`, Plan Review Agent emits `plan-review-v(N+1).md`
3. **If Review requires changes:** Coding Agent emits `impl-v(N+1).md`, Verification emits `verify-v(N+1).md`, Review emits `review-v(N+1).md`
4. **If Review identifies DESIGN ISSUE:** Return to Planning + Plan Review for `plan-v(N+1).md`
5. **Artifact versions are explicit** — no “latest”, no guessing; the orchestrator provides exact `vN` to read/write

### NEXT AGENT PROMPT Block (Required)

> [!IMPORTANT]
> Every artifact file must end with a `## NEXT AGENT PROMPT (COPY/PASTE)` block.

- Fully resolved for the current run — no placeholders except `NEW_RUN_ID` in Review Agent's APPROVED next-run stub
- Specifies: next agent role, `RUN_ID`, exact file paths (INPUTS/OUTPUT)

### Artifact Header (Required)

Every run artifact file must begin with the canonical YAML frontmatter header (`RUN_ID`, `VERSION`, `TARGET`, `INPUTS`, `OUTPUTS`).

### Run-Directory Hygiene (Required)

After writing or updating any artifact under `.agent-workflow/runs/<RUN_ID>/`, run the validators listed in **Command Canon** below. If any fail: **STOP**.

---

## 4. STOP Conditions

> [!CAUTION]
> These conditions apply to **all agents**. Violation requires immediate escalation.

| Condition | Action |
|-----------|--------|
| Required input artifact file is missing | **STOP** — escalate to orchestrator |
| Plan Review verdict is not APPROVED | **Coding Agent must not run** |
| Plan Review shows Decision Points Remaining ≠ NONE | **Coding Agent must not run** |
| RUN_ID mismatch detected | **STOP** — escalate immediately |
| Any verification gate fails | **Verification must not advance** |

---

## 5. Command Canon

### Quality Gates (use local `.venv/bin/*`)

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

If `.venv/bin/*` is unavailable, bootstrap once (offline-friendly): `uv sync --group dev --frozen`.

### Repo Scripts / Generators (use `uv run --no-sync`)

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py [--check]
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/<RUN_ID>/plan-v<N>.md
```

### Import-Linter Gate

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Import contract SSOT:** `importlinter.ini` in repo root.

### Docker Verification Gate (Real External Deps)

When a plan requires real external deps (VapourSynth + FFmpeg):

```bash
bash tools/verify_docker_integration.sh
```

**Expectation:** Zero skips inside Docker. Any skip = failure.

---

## 6. Mechanical Auto-Fix Mode (Summary)

Allows Plan Review Agent to apply **semantics-preserving** fixes without another Planning round.

**When Allowed (all must be true):**

- No SSOT/spec/contract changes required to approve
- Remaining issues are mechanical only (formatting, artifact wiring, missing workflow-required verification lines)

**Allowed fixes:**

- Plan formatting for validators (`validate_spec_anchors.py`)
- Artifact wiring (NEXT prompt paths/versions, frontmatter)
- Adding workflow-required verification commands that don't change scope

**Disallowed:**

- Any change to runtime behavior, public API, algorithms, error mapping, or file layout
- Any SSOT/spec/contract edits

**Must produce:** New `plan-v(N+1).md` with `## Changes Since plan-vN` section.

---

## 7. SSOT Decision Audit (Summary)

**When required:** If the Planning Agent updated SSOT/specs during the Plan Review loop.

**What to check:**

1. Read updated SSOT sections (exact headings)
2. Validate changes are:
   - Implementable (no undefined names, no contradictions)
   - Best-practice aligned (typed errors at module boundaries, deterministic output rules, unit tests don't require external binaries by default, import layering respected)
3. If unsound, return **CHANGES REQUIRED** with specific SSOT edits required

**Plan Review Report must include:** `SSOT Update Audit: OK` or `SSOT Update Audit: Issue` with concrete required edits.

---

## 8. Where to Find Templates

> **Templates and appendices are NOT duplicated here.**
>
> Refer to the canonical doc for full templates:
>
> - **Plan template:** `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → Template 1
> - **Plan Review template:** `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → Template 1.5
> - **Implementation Report template:** `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → Template 2
> - **Verification Handoff template:** `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → Template 3
> - **Review Report template:** `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → Template 4
> - **NEXT AGENT PROMPT examples:** Each agent-prompt file in `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/`
>
> **Orchestrator workflow steps:** Canonical doc → "Human Orchestrator Protocol" section.

---

## 9. Quick Doc Verification

To validate this quick doc contains all required sections (drift check):

```bash
python3 scripts/validate_workflow_quick.py
```

**Pass criteria:** Exit code 0 with "All required content present" message.
