# Frame Compare 2.0 — Multi-Agent Implementation Workflow

> **Version:** 2.0  
> **Last Updated:** 2025-12-27  
> **Purpose:** Orchestrate 5 AI agents with human oversight for systematic project implementation

---

## Overview

This document defines a **5-agent sequential workflow** with human orchestration for implementing Frame Compare 2.0. Each agent has a specific model and role, with explicit handoff points for human review.

```text
┌───────────────────────────────────────────────────────────────────────────────┐
│                           HUMAN ORCHESTRATOR (You)                            │
│   Initiates phases • Reviews outputs • Approves transitions • Manages flow    │
└───────────────────────────────────────────────────────────────────────────────┘
                                      │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 1. PLANNING     │     │ 2. PLAN REVIEW  │     │ 3. CODING       │
│    AGENT        │ ──▶ │    AGENT        │ ──▶ │    AGENT        │
│                 │     │                 │     │                 │
│ Claude Opus 4.5 │     │ GPT 5.2 High    │     │ Gemini 3.0      │
│                 │     │                 │     │                 │
│ • Read specs    │     │ • Validate plan │     │ • Write code    │
│ • Create plan   │     │ • Check quality │     │ • Write tests   │
│ • Define scope  │     │ • APPROVE/REJECT│     │ • Run linters   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                              ┌─────────────────┐     ┌─────────────────┐
                              │ 5. REVIEW       │     │ 4. VERIFY       │
                              │    AGENT        │ ◀── │    AGENT        │
                              │                 │     │                 │
                              │ GPT 5.2 High    │     │ Claude Opus 4.5 │
                              │                 │     │                 │
                              │ • Final verify  │     │ • Check work    │
                              │ • Quality gate  │     │ • Fill docs     │
                              │ • Approve/Reject│     │ • Create handoff│
                              └─────────────────┘     └─────────────────┘
                                      │
         ┌────────────────────────────┘
         ▼
┌─────────────────┐
│ Next Phase      │ ──▶ Back to Planning Agent
└─────────────────┘
```

---

## Contract-First Loop (When Contracts Change)

> **Canonical SSOT:** `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` only.
> Derived docs and codegen are **never edited by hand**.
>
> **Readiness gate commands SSOT:** `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json` (sync `AI_READINESS_ROADMAP.md` via `scripts/update_ai_readiness_roadmap.py`).

When any canonical contract (YAML/JSON in `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`) changes:

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

4. **Proceed** with implementation only after checks pass

> [!NOTE]
> **CI Status:** Traceability validation is a **blocking** CI gate. Treat it as must-pass locally before handoff.

---

## Command Canon (SSOT)

This repo uses a **two-lane** command convention to avoid `uv run` sync surprises and keep commands deterministic:

1. **Repo scripts (validators / generators)** — always run with `uv run --no-sync`:
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py [--check]`
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>`
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>`

2. **Tooling (pyright / ruff / pytest)** — prefer local `.venv/bin/*`:
   - `.venv/bin/pyright --warnings`
   - `.venv/bin/ruff check .`
   - `.venv/bin/pytest -q`

**Import contracts (`lint-imports`)**: CI installs `import-linter` explicitly; run it via:
`UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`

If `.venv/bin/*` is unavailable, bootstrap once (offline-friendly):
`uv sync --group dev --frozen` and then use `UV_CACHE_DIR=./.uv_cache uv run <tool> ...` as the fallback.

### Optional Gate Helper

For convenience, you may run `scripts/check-all-gates.sh` to execute the **three readiness gates** locally. The SSOT is still `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`.

---

## Run Directory Convention

> **Single Source of Truth:** All agent artifacts for a checklist item run are stored in a single versioned directory.

### RUN_ID Format

Each run uses a unique `RUN_ID` slug:

```
RUN_ID = YYYY-MM-DD__p<phase>-<item>__<short_slug>
```

For meta runs (non-checklist / maintenance tasks):

```
RUN_ID = YYYY-MM-DD__meta__<short_slug>
```

**Examples:**

- `2025-12-25__p1-1-1__config-module`
- `2025-12-26__p2-3__frame-extraction`
- `2025-12-25__p0-1__error-types`
- `2025-12-26__meta__ai-readiness-audit`

**Validation (required):**

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>
```

If either command fails: **STOP** and fix the run directory artifacts before proceeding.

### Run Directory Layout

All artifacts are stored under `.agent-workflow/runs/<RUN_ID>/`:

```
.agent-workflow/runs/<RUN_ID>/
├── plan-v1.md
├── plan-v2.md         (if revision required)
├── plan-review-v1.md
├── plan-review-v2.md  (if revision required)
├── impl-v1.md
├── impl-v2.md         (if review/verification requires changes)
├── verify-v1.md
├── verify-v2.md        (if re-verification required)
├── review-v1.md
└── review-v2.md        (if re-review required)
```

### Versioning Rules

1. **Start at `v1`** for all artifacts.
2. **If Plan Review requires changes:**
   - Planning Agent emits `plan-v(N+1).md`
   - Plan Review Agent emits `plan-review-v(N+1).md`
   - Repeat until Plan Review verdict is APPROVED and Decision Points Remaining is NONE
3. **If Review requires changes (CHANGES_REQUIRED):**
   - Coding Agent emits `impl-v(N+1).md`
   - Verification Agent emits `verify-v(N+1).md`
   - Review Agent emits `review-v(N+1).md`
4. **If Review identifies a design issue (DESIGN_ISSUE):**
   - Return to Planning + Plan Review for `plan-v(N+1).md` and `plan-review-v(N+1).md` (then Coding/Verification/Review repeat)
5. **Cross-artifact references must name exact inputs:**
   - `impl-vN.md` must state which `plan-vM.md` + `plan-review-vM.md` it implemented
   - `verify-vN.md` must state which `impl-vK.md` it verified
   - `review-vN.md` must state which `verify-vK.md` it reviewed

### Required Artifact Headers

**Every artifact file must begin with this YAML frontmatter:**

```yaml
---
RUN_ID: YYYY-MM-DD__p<phase>-<item>__<short_slug>
VERSION: vN
TARGET: Phase X → Item Y
INPUTS:
  - .agent-workflow/runs/<RUN_ID>/plan-vN.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/[module]-module.md
OUTPUTS:
  - .agent-workflow/runs/<RUN_ID>/plan-review-vN.md
---
```

### RUN_ID Generator Rule

> [!IMPORTANT]
> This rule eliminates RUN_ID naming drift and ensures consistency.

**If orchestrator provides RUN_ID:**

- Agents must use it **verbatim**

**If RUN_ID is not provided:**

1. **Planning Agent proposes** a RUN_ID in the **first 5 lines** of its response
2. **Planning Agent waits** for orchestrator confirmation before writing files
3. **Orchestrator confirms** by replying: `CONFIRM RUN_ID: <RUN_ID>`
4. **Only then** does Planning Agent write `.agent-workflow/runs/<RUN_ID>/plan-v<N>.md` (use `v1` for a new run)

**Drift detection:** If an agent detects an artifact under a different RUN_ID than the currently confirmed one, it must **STOP and escalate** immediately.

---

## NEXT AGENT PROMPT Blocks (Auto-Orchestration)

> [!IMPORTANT]
> Every artifact file written during a run MUST end with a `## NEXT AGENT PROMPT (COPY/PASTE)` block.

### Purpose

The NEXT AGENT PROMPT block enables "follow-the-breadcrumbs" orchestration. The orchestrator's default action is to:

1. Open the latest artifact file
2. Copy the NEXT AGENT PROMPT block at the end
3. Paste it unchanged into the next agent

### Rules

1. **Every artifact file MUST end** with a `## NEXT AGENT PROMPT (COPY/PASTE)` section
2. **Fully resolved (current run)** — No placeholders for the current run’s RUN_ID/version numbers/paths. Exception: the Review Agent’s **APPROVED** branch may include a *next-run stub* using exactly one placeholder token `NEW_RUN_ID` that the orchestrator fills in.
3. **Plain text prompt** — Ready to copy/paste directly into the next agent
4. **Specifies:**
   - The next agent role/name
   - The confirmed `RUN_ID`
   - Exact file paths to read (INPUTS)
   - Exact file path to write (OUTPUT)
   - Any preconditions (e.g., "Verdict must be APPROVED")
5. **Branches on verdict** — When an artifact has conditional outcomes (APPROVED vs CHANGES REQUIRED vs DESIGN ISSUE), include the appropriate NEXT block for each branch

> [!NOTE]
> Templates in this document and the agent prompt files show placeholders for readability. Artifact files written under `.agent-workflow/runs/<RUN_ID>/` must replace placeholders per Rule 2.

### Block Format

```markdown
## NEXT AGENT PROMPT (COPY/PASTE)

You are the [Next Agent Name] for Frame Compare 2.0.

## RUN_ID
[actual-run-id]

## Files to Read
1. Read file: .agent-workflow/runs/[actual-run-id]/[artifact-vN].md
2. Read file: [other required files]

## Your Task
[Brief task description]

## Output
Write file: .agent-workflow/runs/[actual-run-id]/[output-file].md
```

### Branching Example (for Review Agent)

```markdown
## NEXT AGENT PROMPT (COPY/PASTE)

### If Verdict is APPROVED:
[Prompt for next checklist item or commit instructions]

### If Verdict is CHANGES REQUIRED:
You are the Coding Agent...
Write file: .agent-workflow/runs/<RUN_ID>/impl-v(N+1).md

### If Verdict is DESIGN ISSUE:
You are the Planning Agent...
Write file: .agent-workflow/runs/<RUN_ID>/plan-v(N+1).md
```

---

## Global Stop Conditions

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

## Workflow Consistency Checklist (STOP/VALIDATE)

> [!IMPORTANT]
> Treat any failed item below as a **STOP** condition. Do not “patch around” workflow drift.

### Required Artifact Validations (Run-Directory Hygiene)

After writing or updating any artifact under `.agent-workflow/runs/<RUN_ID>/`, validate:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>
```

If either command fails: **STOP** and fix the artifact(s) before advancing to the next agent.

### Cross-Agent Preconditions (No-Guessing)

- **RUN_ID must be confirmed** and used verbatim everywhere. Any mismatch: **STOP**.
- **Artifact versions must be explicit** (`vN` provided by orchestrator). No “latest”, no guessing.
- **Plan Review gate is mandatory** before Coding:
  - `.agent-workflow/runs/<RUN_ID>/plan-review-vN.md` exists
  - `Verdict: APPROVED`
  - `Implementation Agent Decision Points Remaining: NONE`
  If any are missing: **STOP** (return to Planning/Plan Review loop).

### Gate Discipline (Do Not Advance on Red)

- If any verification gate fails: **STOP** and loop (Coding → Verification) until green.
- If contracts change, the contract loop is mandatory; do not manually edit derived outputs.

## Agent Definitions

### Agent 1: Planning Agent 🗺️

| Property | Value |
|----------|-------|
| **Model** | Claude Opus 4.5 |
| **Persona** | Senior Technical Architect with deep understanding of the Frame Compare domain |
| **Context Window** | Large — can ingest full module specs |

**Role:** Interpret blueprints, decompose work into actionable implementation plans, define acceptance criteria.

**Responsibilities:**

1. Read and internalize the relevant specification documents
2. Create a focused, scoped implementation plan for one phase item
3. Define **exact** acceptance criteria and test requirements
4. Identify dependencies and potential blockers
5. Produce the Implementation Plan handoff document

**Documents to Read (in order):**

1. `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` — Find the next uncompleted item
2. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/<target>.md` — Full module specification
3. `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` — Verify build order
4. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Error patterns to follow
5. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` — Testing requirements

**Output:** `.agent-workflow/runs/<RUN_ID>/plan-vN.md` (see Template 1 below)

---

### Agent 2: Plan Review Agent ✓

| Property | Value |
|----------|-------|
| **Model** | GPT 5.2 High |
| **Persona** | Principal Engineer / Test Architect (contract-first, anti-churn) |
| **Strength** | Thorough validation, catches ambiguity, ensures implementation-readiness |

**Role:** Validate that the Planning Agent's implementation plan is complete, unambiguous, and ready for implementation. This agent does **NOT** write code.

**Responsibilities:**

1. Review the implementation plan against the 9-point quality checklist
2. Verify all files, types, tests, and verification commands are specified
3. Ensure no decision points remain for the Coding Agent
4. Produce a Plan Review Report with APPROVED or CHANGES REQUIRED verdict

**Documents to Read (in order):**

1. `.agent-workflow/runs/<RUN_ID>/plan-vN.md` — The plan being reviewed
2. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/<target>.md` — Module specification for cross-reference
3. `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` (this file) — Contract-First Loop requirements
4. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` — Canonical contracts if touched by the plan

**Mandatory Checklist (all must PASS for APPROVED):**

| # | Check | Criteria |
|---|-------|----------|
| 1 | Scope | Exactly one checklist item; clear out-of-scope |
| 2 | Dependencies | All imports, layers, prior modules identified |
| 3 | File List | Complete and minimal; no ambiguous references |
| 4 | Contract Impact | YES/NO section present; regen commands if YES |
| 5 | Types Complete | All public function signatures with full types |
| 6 | Tests Complete | Exact test names, assertions, negative cases |
| 7 | Verification Complete | Exact commands and pass criteria |
| 8 | Decision-Minimizing | No algorithm/layout/naming left to Coding Agent |
| 9 | Determinism Defined | Seeds, sorting, stability requirements (if applicable) |

**Output:** `.agent-workflow/runs/<RUN_ID>/plan-review-vN.md` (see Template 1.5 below)

---

### When Plan Review is Mandatory

> [!IMPORTANT]
> **Plan Review is mandatory** for all implementation work. There is no bypass.

The Plan Review gate exists to ensure the Coding Agent (Gemini) can implement without making any design decisions. Skipping this gate defeats the purpose of the contract-first workflow.

**Policy:** Never bypass. Every plan must pass Plan Review before implementation begins.

---

### Agent 3: Coding Agent 💻

| Property | Value |
|----------|-------|
| **Model** | Gemini 3.0 |
| **Persona** | Senior Python Developer specializing in CLI tools and type-safe Python |
| **Strength** | Fast code generation, good at following explicit instructions |

**Role:** Execute the implementation plan precisely, writing production-quality code with tests.

**Responsibilities:**

1. Follow the implementation plan **exactly** — no additions, no omissions
2. Write clean, type-safe Python code (Pyright strict)
3. Write tests alongside implementation (TDD preferred)
4. Run verification commands after each file
5. Document code with docstrings
6. Do **not** update the master checklist (Verification Agent owns checklist edits)

**Quality Requirements (must pass before handoff):**

```bash
.venv/bin/pyright --warnings src/frame_compare/<module>/  # 0 errors
.venv/bin/ruff check src/frame_compare/<module>/  # 0 errors
.venv/bin/pytest -v tests/<module>/  # All pass
```

**Output:**

- Implemented source files in `src/frame_compare/`
- Test files in `tests/`
- `.agent-workflow/runs/<RUN_ID>/impl-vN.md` (implementation report; see Template 2 below)

---

### Agent 4: Verification Agent ✓

| Property | Value |
|----------|-------|
| **Model** | Claude Opus 4.5 |
| **Persona** | Staff Engineer focused on documentation, quality, and process compliance |
| **Strength** | Thorough checking, good at creating structured documents |

**Role:** Validate the Coding Agent's work, ensure all documentation is complete, and prepare the handoff for review.

**Responsibilities:**

1. **Code Review Light** — Verify implementation matches the plan
2. **Doc Completion** — Ensure all docstrings, type hints, and comments are present
3. **Checklist Update** — Mark completed items in `10-agent-master-checklist.md`
4. **Handoff Creation** — Create the comprehensive handoff for Review Agent
5. **Run Full Verification Suite:**

   ```bash
   .venv/bin/pyright --warnings  # Full project
   .venv/bin/ruff check .
   .venv/bin/pytest --cov
   UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini  # Import contract check
   
   # Contract and traceability gates (must pass before PR)
   UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
   UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
   ```

**Output:** `.agent-workflow/runs/<RUN_ID>/verify-vN.md` (verification handoff; see Template 3 below)

---

### Agent 5: Review Agent 🔍

| Property | Value |
|----------|-------|
| **Model** | GPT 5.2 High |
| **Persona** | Principal Engineer / Security-conscious code reviewer |
| **Strength** | Fresh perspective, good at finding edge cases and security issues |

**Role:** Final quality gate before phase completion. Verify correctness, security, and spec compliance.

**Responsibilities:**

1. Review all code changes against module specification
2. Verify all acceptance criteria from the Implementation Plan are met
3. Check for security issues (path traversal, injection, etc.)
4. Verify error handling follows patterns
5. Run final test suite verification
6. **Verdict:** APPROVED, CHANGES_REQUIRED, or DESIGN_ISSUE

**Review Checklist:**

- [ ] Code follows module specification exactly
- [ ] All acceptance criteria met
- [ ] Pyright strict passes
- [ ] Ruff passes (no linting errors)
- [ ] Tests pass and cover critical paths
- [ ] Error handling follows FC-xxxx patterns
- [ ] No security vulnerabilities
- [ ] Docstrings present on all public APIs

**Output:** `.agent-workflow/runs/<RUN_ID>/review-vN.md` (review report; see Template 4 below)

## Human Orchestrator Protocol

This section provides the **concrete step-by-step workflow** for you (the human orchestrator) to follow. Each step includes exactly what to do, what to check, and when to proceed.

### Orchestrator Minimal Prompts

> [!TIP]
> Each agent only needs these minimal inputs from you. Everything else is derived from artifact files.

| Agent | Required Inputs |
|-------|----------------|
| **Planning** | Optional target override + RUN_ID (or confirm proposed RUN_ID). If no target provided, Planning picks the next unchecked checklist item. |
| **Plan Review** | RUN_ID (to locate `plan-vN.md`) |
| **Coding** | RUN_ID (reads plan + plan-review from run directory) |
| **Verification** | RUN_ID (reads impl from run directory) |
| **Review** | RUN_ID (reads verify from run directory) |

### Agent Reset Policy (Context Hygiene)

To keep the human role minimal (“confirm + paste NEXT”), use predictable reset points:

- Keep one persistent thread per agent role; normally paste only the NEXT block from the latest artifact.
- Restart a role thread (re-send its system prompt) when remaining context is **<30%** (or **<40%** for smaller models), or if the agent violates STOP rules / invents paths or versions.
- Safe reset boundaries:
  - After each run completes (Review verdict written)
  - At phase boundaries (`## Phase N` in the master checklist)
  - Before/after each `### Phase N Quality Gate ✓` checkpoint

### Session Setup (Once Per Day)

```bash
# 1. Ensure clean working state
cd <repo-root>
git status  # Should be clean or stash changes
# Optional (network): update your branch from remote if desired.
# git pull origin main

# 2. Check current progress
cat docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md | head -100

# 3. Check run index
cat .agent-workflow/index.md

# 4. Verify tools are working
.venv/bin/pyright --version
.venv/bin/ruff --version
.venv/bin/pytest --version
```

---

### Step-by-Step Orchestration Workflow

#### STEP 1: Identify Next Task + Create RUN_ID

You can run STEP 1 in either mode:

- **Minimal mode (recommended):** tell the Planning Agent to pick the next unchecked item and propose a RUN_ID; you only confirm the RUN_ID.
- **Directed mode:** you pick the checklist item and create the RUN_ID up-front.

Directed mode steps:

1. Open `10-agent-master-checklist.md`
2. Find the first `[ ]` uncompleted item
3. Note the **Phase** and **Item Name**
4. **Create RUN_ID** using format: `YYYY-MM-DD__p<phase>-<item>__<short_slug>`
5. Create a session note:

   ```text
   Session: 2025-12-25
   RUN_ID: 2025-12-25__p1-1-1__config-module
   Target: Phase 1 → Item 1.1
   Status: Starting
   ```

---

#### STEP 2: Run Planning Agent (Claude Opus 4.5)

**Prompt Template to Use:**

```markdown
You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>
(Alternatively: Planning Agent will propose RUN_ID if not provided)

## Target
If not specified, pick the next unchecked item from `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`.

If specified:
- Phase: [X]
- Item: [Item Name from checklist]

## Context Files to Read
1. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`
2. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`

After selecting the target item, read the relevant spec(s):
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/[module]-module.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` (if needed)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` (if needed)

## Your Task
1. Read the specification thoroughly
2. Create a detailed Implementation Plan including:
   - Exact files to create/modify
   - Complete type definitions
   - Function signatures with docstrings
   - Specific test cases with exact names
   - Exact acceptance criteria
   - Exact verification commands
3. Write file: `.agent-workflow/runs/<RUN_ID>/plan-vN.md`
   - Use `v1` for a new run; if revising after Plan Review, write `plan-v(N+1).md`
   - If RUN_ID was not confirmed, do not write files until the orchestrator replies `CONFIRM RUN_ID: <RUN_ID>`

## Constraints
- One checklist item only
- NO code implementation (that's for Coding Agent)
- Be extremely specific - the next agent follows literally
- Do not print full file contents; confirm path and summarize
```

**Quality Checkpoint ✅**

Before proceeding, verify:

- [ ] Plan written to `.agent-workflow/runs/<RUN_ID>/plan-vN.md` (correct `vN` for this iteration)
- [ ] Required headers present (RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS)
- [ ] Clear scope — exactly one checklist item
- [ ] File list is complete and specific
- [ ] Type definitions are full Python code
- [ ] Acceptance criteria are testable (GIVEN/WHEN/THEN)
- [ ] Dependencies identified (what must exist first)
- [ ] Contract Impact section present with YES/NO

**If NOT satisfied:** Re-run Planning Agent with clarifications.

---

#### STEP 3: Run Plan Review Agent (GPT 5.2 High)

**Prompt Template to Use:**

```markdown
You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Plan to Review
Read file: `.agent-workflow/runs/<RUN_ID>/plan-vN.md`
(Use the highest available `vN` for this RUN_ID; start with `v1`.)

## Context Files to Read (if needed)
1. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/[module]-module.md`
2. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`
3. Read files in: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` (if plan touches contracts)

## Your Task
Validate the plan is implementation-ready using the 9-point checklist:

| # | Check | Criteria |
|---|-------|----------|
| 1 | Scope | Exactly one checklist item; clear out-of-scope |
| 2 | Dependencies | All imports, layers, prior modules identified |
| 3 | File List | Complete and minimal; no ambiguous references |
| 4 | Contract Impact | YES/NO section present; regen commands if YES |
| 5 | Types Complete | All public function signatures with full types |
| 6 | Tests Complete | Exact test names, assertions, negative cases |
| 7 | Verification Complete | Exact commands and pass criteria |
| 8 | Decision-Minimizing | No algorithm/layout/naming left to Coding Agent |
| 9 | Determinism Defined | Seeds, sorting, stability requirements (if applicable) |

## Output
Write file: `.agent-workflow/runs/<RUN_ID>/plan-review-vN.md` with:
- Required headers (RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS)
- VERDICT: APPROVED or CHANGES REQUIRED
- Checklist table with PASS/FAIL for each item
- Concrete edits required (if changes needed) specifying changes for `plan-v(N+1).md`
- "Implementation Agent Decision Points Remaining: NONE" (must be NONE to approve)

Do not print full file contents; confirm path and summarize.
```

**Quality Checkpoint ✅**

Before proceeding, verify:

- [ ] Report written to `.agent-workflow/runs/<RUN_ID>/plan-review-vN.md`
- [ ] Required headers present (RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS)
- [ ] Verdict is APPROVED
- [ ] All 9 checklist items show PASS
- [ ] "Implementation Agent Decision Points Remaining: NONE" is confirmed

**If CHANGES REQUIRED:**

- Return to STEP 2 (Planning Agent) with the specific edits
- Planning Agent writes `plan-v(N+1).md`, Plan Review Agent writes `plan-review-v(N+1).md`

---

#### STEP 4: Run Coding Agent (Gemini 3.0)

**Prompt Template to Use:**

> **Version placeholders:** In the templates below, use `M` for the approved plan/plan-review version (`plan-vM.md`, `plan-review-vM.md`) and `N` for the current stage artifact version (`impl-vN.md`, `verify-vN.md`, `review-vN.md`).

```markdown
You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Precondition (verify before starting)
Read file: `.agent-workflow/runs/<RUN_ID>/plan-review-v<M>.md`
Confirm: Verdict is APPROVED and Decision Points Remaining is NONE.
If not approved, STOP and escalate.

## Files to Read
1. Read file: `.agent-workflow/runs/<RUN_ID>/plan-v<M>.md` (the approved plan)
2. Read file: `.agent-workflow/runs/<RUN_ID>/plan-review-v<M>.md` (must be APPROVED)

## Your Task
1. Implement EXACTLY what is specified in the plan — nothing more, nothing less
2. Only modify files explicitly listed in the plan
3. For each file:
   - Create the file with specified types/functions
   - Add proper docstrings
   - Write the corresponding test file
		   - Run verification:
		     ```bash
		     .venv/bin/pyright --warnings src/frame_compare/<module>/
		     .venv/bin/ruff check src/frame_compare/<module>/
		     .venv/bin/pytest -v tests/<module>/
		     ```
4. Write file: `.agent-workflow/runs/<RUN_ID>/impl-vN.md` with:
   - Required headers (RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS)
   - Exact paths changed
   - Actual command outputs (paste verification evidence)
   - References to plan and plan-review file paths used

Do not print full file contents in responses; confirm paths and summarize.

## Constraints
- Follow the plan EXACTLY
- Do NOT add extra features or "improvements"
- Do NOT update the master checklist (that's Verification Agent's job)
- If plan is ambiguous, STOP and escalate
```

**Quality Checkpoint ✅**

After Coding Agent completes:

- [ ] Report written to `.agent-workflow/runs/<RUN_ID>/impl-vN.md`
- [ ] Required headers present
- [ ] All files listed in plan were created
- [ ] No extra files were created
- [ ] Verification evidence pasted in report

**Manual Verification:**

```bash
git status  # See what changed
.venv/bin/pyright --warnings src/frame_compare/<module>/
.venv/bin/pytest -v tests/<module>/
```

**If verification fails:** Return to Coding Agent with error output.

---

#### STEP 5: Run Verification Agent (Claude Opus 4.5)

**Prompt Template to Use:**

```markdown
You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Files to Read
1. Read file: `.agent-workflow/runs/<RUN_ID>/impl-vN.md` (the latest implementation report)
2. Read file: `.agent-workflow/runs/<RUN_ID>/plan-v<M>.md` (original plan)
3. Read file: `.agent-workflow/runs/<RUN_ID>/plan-review-v<M>.md` (must be APPROVED)

## Precondition
Confirm Plan Review Report shows `Verdict: APPROVED`. If not, STOP.

## Your Task
1. **Review Implementation:**
   - Does code match the plan exactly?
   - Were only listed files modified?
   - Are all docstrings complete?
   - Are all type hints present?

2. **Run Full Verification:**
   ```bash
   .venv/bin/pyright --warnings
   .venv/bin/ruff check .
   .venv/bin/pytest --cov
	   UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
   
   # Contract and traceability gates
   UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
   UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
   ```

3. **Update Checklist:**
   Mark completed items in `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`

4. **Update Run Index:**
   Append a `PENDING_REVIEW` row to `.agent-workflow/index.md` with:
   - RUN_ID, target, date, verdict (`PENDING_REVIEW`)
   - Links to artifacts that exist at this stage: `plan`, `plan-review`, `impl`, `verify`
   - (Review Agent will later replace `PENDING_REVIEW` with final verdict and add the `review` link)

5. **Write Verification Report:**
   Write file: `.agent-workflow/runs/<RUN_ID>/verify-vN.md` with:
   - Required headers (RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS)
   - Verification command outputs
   - Plan compliance summary
   - Any issues found

Do not print full file contents; confirm paths and summarize.

```

**Quality Checkpoint ✅**

Before proceeding to Review:
- [ ] Report written to `.agent-workflow/runs/<RUN_ID>/verify-vN.md`
- [ ] Required headers present
- [ ] All verification commands pass
- [ ] Master checklist updated
- [ ] `.agent-workflow/index.md` updated

**Manual Check:**
```bash
.venv/bin/pyright --warnings  # 0 errors
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini  # No violations
```

---

#### STEP 6: Run Review Agent (GPT 5.2 High)

**Prompt Template to Use:**

```markdown
You are the Review Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Files to Read
1. Read file: `.agent-workflow/runs/<RUN_ID>/verify-vN.md` (verification handoff)
2. Read file: `.agent-workflow/runs/<RUN_ID>/plan-v<M>.md` (the plan)
3. Read file: `.agent-workflow/runs/<RUN_ID>/impl-vN.md` (implementation report)
4. Read file: `.agent-workflow/runs/<RUN_ID>/plan-review-v<M>.md` (must be APPROVED)

## Preconditions
- Confirm Plan Review Report exists and shows `Verdict: APPROVED`
- Confirm Verification Report includes all gate outputs

## Your Task
Perform final quality review:

0. **Finalize Run Index:** Update `.agent-workflow/index.md` for this RUN_ID:
   - Replace `PENDING_REVIEW` with final verdict
   - Add/update the `review-vN.md` link
1. **Spec Compliance:** Does implementation match specification exactly?
2. **Acceptance Criteria:** Are all criteria from the plan met?
3. **Security Check:** Path traversal protected? No shell=True? No injection?
4. **Error Handling:** Uses FC-xxxx error codes correctly?
5. **Test Coverage:** Critical paths covered?

## Output
Write file: `.agent-workflow/runs/<RUN_ID>/review-vN.md` with:
- Required headers (RUN_ID, VERSION, TARGET, INPUTS, OUTPUTS)
- VERDICT: APPROVED | CHANGES_REQUIRED | DESIGN_ISSUE
- Checklist results
- Summary of findings
- Specific action items (if not APPROVED)

Update: `.agent-workflow/index.md` row for this RUN_ID with the final verdict and `review` link.

Do not print full file contents; confirm paths and summarize.
```

**Quality Checkpoint ✅**

Based on Review Agent verdict:

| Verdict | Action |
|---------|--------|
| **APPROVED** | Proceed to STEP 7 (Commit) |
| **CHANGES_REQUIRED** | Return to STEP 4 (Coding Agent) with issues |
| **DESIGN_ISSUE** | Return to STEP 2 (Planning Agent) with feedback |

---

#### STEP 7: Commit and Proceed

```bash
# 1. Final verification
.venv/bin/pyright --warnings
.venv/bin/pytest -q

# 2. Commit with conventional commit format
git add -A
git commit -m "feat(<module>): implement <item name>" \
  -m "Run: <RUN_ID>" \
  -m "Closes Phase X Item Y"

# 3. Update your session note
Session: 2025-12-25
RUN_ID: <RUN_ID>
Target: Phase X → Item Y
Status: COMPLETED ✅
```

**Return to Step 1** for the next checklist item.

---

### Handling Issues

| Issue | Resolution |
|-------|------------|
| Plan not approved by Plan Review | Return to Planning Agent with specific edits from plan-review report |
| Coding Agent adds extra code | Delete extra, or re-run with stricter prompt |
| Verification fails | Return to Coding Agent with error |
| Review finds bugs | Return to Coding Agent with specific fixes |
| Review finds design issue | Return to Planning Agent for revised plan |
| Agent hits context limit | Split the task - do half now, half next iteration |
| You're unsure about agent output | Re-run with more specific questions |

---

### Session Tracking Template

Keep a simple log for each session:

```markdown
# Frame Compare 2.0 Implementation Log

## Session: 2025-12-19

### Completed
- [x] Phase 0 - errors.py (took 2 iterations)
- [x] Phase 0 - utils/result.py

### In Progress
- [ ] Phase 0 - utils/logging.py

### Issues Encountered
- Gemini added an extra helper function - removed manually

### Notes
- Planning Agent prompts need to be more specific about exact function signatures
```

---

## Workflow Process

> **Note:** All paths below use the run directory convention. Legacy locations (`.agent-workflow/plans/`, `.agent-workflow/reports/`) are removed; do not use them.

### Phase 1: Planning

```text
PLANNING AGENT (Opus 4.5) receives:
  - Target checklist item from Human Orchestrator
  - RUN_ID (provided or confirmed after proposal)

PLANNING AGENT produces:
  - .agent-workflow/runs/<RUN_ID>/plan-vN.md
  - Scoped to exactly ONE checklist item
```

### Phase 2: Plan Review

```text
PLAN REVIEW AGENT (GPT 5.2 High) receives:
  - RUN_ID to locate plan
  - Reads: .agent-workflow/runs/<RUN_ID>/plan-vN.md

PLAN REVIEW AGENT produces:
  - .agent-workflow/runs/<RUN_ID>/plan-review-vN.md
  - Verdict: APPROVED or CHANGES REQUIRED
```

### Phase 3: Implementation

```text
CODING AGENT (Gemini 3.0) receives:
  - RUN_ID to locate artifacts
  - Reads: .agent-workflow/runs/<RUN_ID>/plan-vN.md (APPROVED)
  - Reads: .agent-workflow/runs/<RUN_ID>/plan-review-vN.md (must be APPROVED)

CODING AGENT produces:
  - Source code files
  - Test files  
  - .agent-workflow/runs/<RUN_ID>/impl-vN.md
```

### Phase 4: Verification

```text
VERIFICATION AGENT (Opus 4.5) receives:
  - RUN_ID to locate artifacts
  - Reads: .agent-workflow/runs/<RUN_ID>/impl-vN.md
  - Reads: .agent-workflow/runs/<RUN_ID>/plan-vN.md
  - Reads: .agent-workflow/runs/<RUN_ID>/plan-review-vN.md

VERIFICATION AGENT produces:
  - Updated master checklist: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - Updated run index: .agent-workflow/index.md
  - .agent-workflow/runs/<RUN_ID>/verify-vN.md
```

### Phase 5: Review

```text
REVIEW AGENT (GPT 5.2 High) receives:
  - RUN_ID to locate artifacts
  - Reads: .agent-workflow/runs/<RUN_ID>/verify-vN.md
  - Reads: .agent-workflow/runs/<RUN_ID>/plan-vN.md
  - Reads: .agent-workflow/runs/<RUN_ID>/plan-review-vN.md

REVIEW AGENT produces:
  - .agent-workflow/runs/<RUN_ID>/review-vN.md with VERDICT
```

---

## Error Recovery Protocols

### Scenario 1: Specification Ambiguity

**When:** Coding Agent encounters unclear or conflicting requirements in the module spec.

**Protocol:**

1. **PAUSE** — Do not guess or make assumptions
2. **Document** — Note the ambiguity in the Implementation Report with:
   - What is unclear
   - What options exist
   - What clarification is needed
3. **Escalate** — Return to Planning Agent with a CLARIFICATION_NEEDED status
4. **Wait** — Planning Agent resolves ambiguity and updates the Implementation Plan

```text
AMBIGUITY FOUND:
  Coding Agent pauses → Documents issue → Planning Agent clarifies → Continue
```

### Scenario 2: Critical Bug Found in Review

**When:** Review Agent finds a fundamental bug that breaks core functionality.

**Protocol:**

1. **Classify** — Determine if bug is:
   - **Isolated:** Affects single function/file → Coding Agent fixes
   - **Systemic:** Affects multiple components → Reset to last known-good state
2. **Reset** — For systemic bugs (**Human Orchestrator only; explicit approval required; prefer non-destructive actions**):

   ```bash
   git status
   git stash push -u -m "wip: <RUN_ID> (pre-reset)"
   git checkout --detach <last-green-commit>
   ```

3. **Re-implement** — Coding Agent implements ONLY the failing functionality
4. **Micro-review** — Review Agent verifies just the fix before full review

```text
CRITICAL BUG:
  Review Agent identifies → Classify scope → Reset if systemic → Fix → Micro-review
```

### Scenario 3: Scope Creep Detection

**When:** Actual implementation effort exceeds 2x the estimated scope.

**Protocol:**

1. **Stop** — When effort metric (files, LOC, time) exceeds 2x estimate
2. **Report** — Document what's complete and what remains
3. **Re-scope** — Planning Agent breaks remaining work into smaller chunks
4. **Checkpoint** — Commit completed work before continuing

```text
SCOPE EXCEEDED:
  Stop → Commit completed → Planning Agent re-scopes → Continue in chunks
```

### Scenario 4: Missing Dependency

**When:** Implementation cannot proceed because a required module/type doesn't exist.

**Protocol:**

1. **Document** — Add `BLOCKED: [dependency]` to checklist
2. **Escalate** — Notify Planning Agent of blocker
3. **Pivot** — Switch to parallel-safe work if available
4. **Resume** — Continue blocked work once dependency is complete

```text
DEPENDENCY BLOCKED:
  Document → Notify → Work on parallel items → Resume when unblocked
```

### Scenario 5: CI Pipeline Failure

**When:** Automated tests or type checks fail in CI after a commit.

**Protocol:**

1. **Analyze** — Read CI logs to identify failure cause:
   - Type error → Pyright fix needed
   - Test failure → Identify failing test
   - Lint error → Ruff/formatter fix needed
2. **Local Reproduce** — Run failing command locally:

		   ```bash
		   .venv/bin/pyright --warnings src/
		   .venv/bin/pytest -x tests/
		   .venv/bin/ruff check src/
		   ```

3. **Fix** — Apply minimal fix targeting only the failure
4. **Verify** — Run full verification suite locally before pushing:

		   ```bash
		   .venv/bin/pyright --warnings src/ && .venv/bin/pytest tests/ && .venv/bin/ruff check src/
		   ```

```text
CI FAILURE:
  Read logs → Reproduce locally → Fix → Verify locally → Push
```

### Scenario 6: Environment Setup Issues

**When:** Agent cannot run commands due to missing tools, permissions, or configuration.

**Protocol:**

1. **Diagnose** — Identify root cause:
   - Tool not found → Check PATH and installation
   - Permission denied → Check file/directory permissions
   - Config missing → Check for required env vars or config files
2. **Escalate** — If environment is fundamentally broken:
   - Document exact error message
   - Return to orchestrator with ENVIRONMENT_BLOCKED status
   - Do not attempt workarounds that could pollute the environment
3. **Use DevContainer** — For reproducibility issues, recommend:

   ```bash
   # Open in DevContainer for guaranteed environment
   code --folder-uri "vscode-remote://dev-container+..."
   ```

4. **Document** — Add environment requirements to README if missing

```text
ENVIRONMENT BLOCKED:
  Diagnose → Document → Escalate to orchestrator → Recommend DevContainer
```

---

## Handoff Templates

### Template 1: Implementation Plan (Planning → Coding)

```markdown
# Implementation Plan: [Feature Name]

## Context
**Phase:** [Phase number]
**Module:** [Module name]
**Spec Reference:** [Link to module spec]
**Dependencies:** [What must exist first]

## Contract Impact
**Contracts touched:** YES / NO

If YES:
- **Canonical files:** [list under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`]
- **Regeneration:** `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py`
- **Freshness gate:** `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
- **Traceability gate:** `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`

## Scope
This plan covers:
- [ ] [Specific item 1]
- [ ] [Specific item 2]
- [ ] [Specific item 3]

This plan does NOT cover:
- [Out of scope item]

## Files to Create/Modify

### 1. `src/frame_compare/[module]/[file].py`
**Purpose:** [What this file does]

**Types to define:**
- `TypeName` — [Description]

**Functions to implement:**
```python
def function_name(arg: Type) -> ReturnType:
    """
    [Docstring]
    
    Algorithm:
    1. [Step 1]
    2. [Step 2]
    """
```

**Key implementation notes:**

- [Important detail]

### 2. `tests/[module]/test_[file].py`

**Tests required:**

- `test_[scenario]` — [What it tests]
- `test_[scenario]` — [What it tests]

## Acceptance Criteria

- [ ] GIVEN [context] WHEN [action] THEN [result]
- [ ] GIVEN [context] WHEN [action] THEN [result]

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/[module]
.venv/bin/ruff check src/frame_compare/[module]
.venv/bin/pytest -v tests/[module]
```

## Notes for Coding Agent

- [Any gotchas or tips]

```

---

### Template 1.5: Plan Review Report (Plan Review → Coding)

```markdown
# Plan Review Report: [Feature Name]

## Verdict: [APPROVED / CHANGES REQUIRED]

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** YYYY-MM-DD
**Plan Reference:** .agent-workflow/runs/<RUN_ID>/plan-vN.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS/FAIL | [Details if FAIL] |
| 2 | Dependencies | PASS/FAIL | |
| 3 | File List | PASS/FAIL | |
| 4 | Contract Impact | PASS/FAIL | |
| 5 | Types Complete | PASS/FAIL | |
| 6 | Tests Complete | PASS/FAIL | |
| 7 | Verification Complete | PASS/FAIL | |
| 8 | Decision-Minimizing | PASS/FAIL | |
| 9 | Determinism Defined | PASS/FAIL | N/A if not applicable |

## Additional Quality Checks

- Error Codes: [OK / Issue description]
- Failure Modes: [OK / Issue description]
- Derived Outputs: [OK / Issue description]
- Rollback Guidance: [OK / Issue description]

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NONE

[If not NONE, list any remaining decision points — must be NONE to approve]

## Concrete Edits Required (if CHANGES REQUIRED)

1. **[Issue Title]**
   - Section: [Which section of the plan]
   - Problem: [What is unclear or missing]
   - Required Change: [Specific fix needed]

## Ready for Implementation

[If APPROVED] All checklist items pass. Coding Agent may proceed.

[If CHANGES REQUIRED] Return to Planning Agent for revision.
```

---

### Template 2: Implementation Report (Coding → Verification)

```markdown
# Implementation Report: [Feature Name]

## Summary
**Date:** YYYY-MM-DD
**Plan Reference:** [Link to implementation plan]

## Files Changed

### Created
- `src/frame_compare/[module]/file.py` — [Purpose]
- `tests/[module]/test_file.py` — [X tests]

### Modified
- `src/frame_compare/[module]/__init__.py` — Added exports

## Implementation Notes
[Any deviations from plan, decisions made, challenges faced]

## Test Results
```

$ .venv/bin/pytest -v tests/[module]
============= X passed in Y.YYs =============

```

## Quality Checks
- [x] Pyright: 0 errors
- [x] Ruff: 0 errors
- [x] Tests: X passed
- [x] Coverage: XX%

## Checklist Items Completed
- [x] [Item from master checklist]
- [x] [Item from master checklist]

## Open Questions
- [Any questions for review]

## Ready for Review
All acceptance criteria from the implementation plan have been addressed.
```

---

### Template 3: Review Report (Review → Next Step)

```markdown
# Review Report: [Feature Name]

## Verdict: [APPROVED / CHANGES REQUIRED / DESIGN ISSUE]

## Review Summary
**Reviewer:** Review Agent
**Date:** YYYY-MM-DD
**Files Reviewed:** [Count]

## Checklist Results

### Code Quality
- [x] Follows module specification
- [x] Type hints complete and correct
- [x] Docstrings present
- [x] Error handling follows patterns
- [ ] [Issue if any]

### Testing
- [x] Unit tests present
- [x] Edge cases covered
- [x] Tests are deterministic
- [ ] [Issue if any]

### Security
- [x] No hardcoded secrets
- [x] Input validation present
- [x] Safe error messages
- [ ] [Issue if any]

### Performance
- [x] No obvious inefficiencies
- [x] Appropriate caching
- [ ] [Issue if any]

## Issues Found

### Critical (Must Fix)
1. **[Issue Title]**
   - Location: `file.py:123`
   - Issue: [Description]
   - Fix: [Suggested fix]

### Minor (Should Fix)
1. **[Issue Title]**
   - Location: `file.py:45`
   - Issue: [Description]
   - Fix: [Suggested fix]

### Suggestions (Nice to Have)
1. [Suggestion]

## Acceptance Criteria Verification
- [x] GIVEN [context] WHEN [action] THEN [result] — ✓ Verified
- [x] GIVEN [context] WHEN [action] THEN [result] — ✓ Verified

## Next Steps

### If APPROVED:
- Update master checklist
- Proceed to next feature: [Next feature name]

### If CHANGES REQUIRED:
- Coding Agent: Address critical and minor issues
- Re-submit for review

### If DESIGN ISSUE:
- Planning Agent: Revise implementation plan
- Issue: [Description of design problem]
```

---

## State Management

### Current State File

Create and maintain `.agent-workflow/current-state.json`:

```json
{
  "current_phase": 2,
  "current_feature": "analysis-module",
  "current_agent": "coding",
  "iteration": 1,
  "last_updated": "2025-12-16T10:00:00Z",
  "history": [
    {
      "feature": "project-scaffold",
      "status": "approved",
      "iterations": 1
    }
  ]
}
```

### Session Handoff

When an agent session ends mid-work:

```markdown
## Session Handoff: [Agent Type]

**Date:** YYYY-MM-DD HH:MM
**Agent:** [Planning/Coding/Review]
**Feature:** [Current feature]

### Completed This Session
- [x] Item 1
- [x] Item 2

### In Progress
- [ ] Item with notes about state

### Next Steps
1. [Immediate next action]
2. [Following action]

### Context for Next Session
[Critical context the next agent needs to know]
```

---

## Quick Start Guide

### Starting a New Feature

> **Note:** All paths use the run directory convention: `.agent-workflow/runs/<RUN_ID>/`

1. **Orchestrator** confirms a RUN_ID (provided up-front, or confirmed after Planning proposes one).
   - You do **not** need to create the run directory manually; the agent creates `.agent-workflow/runs/<RUN_ID>/` when writing the first artifact.

2. **Planning Agent** reads specs and produces:
   - `.agent-workflow/runs/<RUN_ID>/plan-vN.md`

3. **Plan Review Agent** validates and produces:
   - `.agent-workflow/runs/<RUN_ID>/plan-review-vN.md`
   - If CHANGES REQUIRED → Planning Agent writes `plan-v(N+1).md` (and Plan Review repeats as `plan-review-v(N+1).md`)

4. **Coding Agent** (after plan is APPROVED) produces:
   - Source code and tests
   - `.agent-workflow/runs/<RUN_ID>/impl-vN.md`

5. **Verification Agent** runs gates and produces:
   - `.agent-workflow/runs/<RUN_ID>/verify-vN.md`
   - Updates master checklist and run index

6. **Review Agent** validates and produces:
   - `.agent-workflow/runs/<RUN_ID>/review-vN.md`
   - Issues verdict: APPROVED / CHANGES REQUIRED / DESIGN ISSUE

### Agent Initialization Prompts

> **Preferred:** Use the NEXT AGENT PROMPT blocks from artifact files instead of these minimal prompts.
> These are provided as a fallback for starting fresh runs.
>
> **Placeholder note:** The tokens like `<RUN_ID>` and `<N>` in the prompts below are placeholders for readability. Replace them with concrete values before running the next agent. Current-run artifacts under `.agent-workflow/runs/<RUN_ID>/` must not contain placeholders (exception: `NEW_RUN_ID` is allowed only inside the Review Agent’s APPROVED next-run stub).

**Prompt files (SSOT):**

- `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/01-planning-agent.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/02-plan-review-agent.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/03-coding-agent.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/04-verification-agent.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/05-review-agent.md`

#### Initialize Planning Agent

```text
You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Target
Phase: [X]
Item: [Item from checklist]

## Files to Read
1. docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
2. docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/[module]-module.md

## Output
Write file: .agent-workflow/runs/<RUN_ID>/plan-vN.md
```

#### Initialize Plan Review Agent

```text
You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Files to Read
1. .agent-workflow/runs/<RUN_ID>/plan-vN.md
2. docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Output
Write file: .agent-workflow/runs/<RUN_ID>/plan-review-vN.md
```

#### Initialize Coding Agent

```text
You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Precondition
Read file: .agent-workflow/runs/<RUN_ID>/plan-review-v<N>.md
Confirm: Verdict is APPROVED and Decision Points Remaining is NONE.

## Files to Read
1. .agent-workflow/runs/<RUN_ID>/plan-v<N>.md
2. .agent-workflow/runs/<RUN_ID>/plan-review-v<N>.md

## Output
Write file: .agent-workflow/runs/<RUN_ID>/impl-vN.md
```

#### Initialize Verification Agent

```text
You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Files to Read
1. .agent-workflow/runs/<RUN_ID>/impl-v<N>.md
2. .agent-workflow/runs/<RUN_ID>/plan-v<M>.md
3. .agent-workflow/runs/<RUN_ID>/plan-review-v<M>.md

## Output
Write file: .agent-workflow/runs/<RUN_ID>/verify-vN.md
```

#### Initialize Review Agent

```text
You are the Review Agent for Frame Compare 2.0.

## RUN_ID
<RUN_ID>

## Files to Read
1. .agent-workflow/runs/<RUN_ID>/verify-v<N>.md
2. .agent-workflow/runs/<RUN_ID>/impl-v<M>.md
3. .agent-workflow/runs/<RUN_ID>/plan-v<P>.md
4. .agent-workflow/runs/<RUN_ID>/plan-review-v<P>.md

## Output
Write file: .agent-workflow/runs/<RUN_ID>/review-vN.md
```

---

## Best Practices

### For Planning Agent

1. Be specific — vague plans lead to implementation drift
2. Include code templates for complex logic
3. Define edge cases explicitly
4. Keep scope small — one focused feature per plan

### For Coding Agent

1. Follow the plan exactly — deviation requires Planning Agent re-approval
2. Test as you code — don't leave tests for the end
3. Run quality checks after each file
4. Document decisions in the Implementation Report

### For Review Agent

1. Be thorough but not pedantic
2. Focus on correctness and maintainability
3. Distinguish critical vs minor issues
4. Provide actionable fix suggestions

---

## Metrics

Track these across the implementation:

| Metric | Target |
|--------|--------|
| Approval rate (first submission) | > 70% |
| Average iterations per feature | < 2 |
| Test coverage | > 80% |
| Pyright errors | 0 |
| Ruff errors | 0 |
