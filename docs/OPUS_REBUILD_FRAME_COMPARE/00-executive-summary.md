# Frame Compare 2.0 — Project Recreation Master Plan

> **Document Version:** 1.0
> **Last Updated:** 2025-12-27
> **Status:** Planning Phase

---

## Executive Summary

```yaml
Project Name: Frame Compare
Project Code: FC-2.0
Version: "2.0 - Ground-Up Rebuild"
Document Version: 1.0
Last Updated: 2025-12-27
Authors: AI-Assisted Planning

Purpose: |
  Frame Compare is a Python CLI tool for automated video frame comparison and HDR tonemapping.
  This rebuild aims to eliminate accumulated technical debt, modernize the architecture with
  container-first deployment, and improve maintainability while preserving 100% feature parity.

Vision Statement: |
  Deliver a zero-configuration, containerized video comparison suite that democratizes professional
  video analysis workflows—enabling fansub teams, archivists, and encoding enthusiasts to produce
  publication-ready comparisons with a single command.

Success Criteria:
  - 100% feature parity with v0.0.14 for all P0/P1 features
  - Zero-config Docker deployment ("docker compose up" is sufficient)
  - Test coverage ≥80% with strict type checking
  - Sub-500ms CLI response time for cached operations (warm cache + warm process)
  - Clean separation between CLI, services, and core domain
```

---

## Human Operator Workflow (5-Agent Run Loop)

This section is a **human-readable** guide for running the canonical file-based workflow. The authoritative source is:

- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`

### What You Do Every Run

1. Start the run by telling the Planning Agent it’s their turn:
   - Default: “Pick the next unchecked item in `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` and write `plan-v1.md`.”
   - If you want to override selection: specify “Target: Phase X → Item Y”.
2. Confirm a `RUN_ID` (or allow Planning to propose, then you confirm):
   - `RUN_ID = YYYY-MM-DD__p<phase>-<item>__<short_slug>`
   - You do **not** create folders manually; the agent creates `.agent-workflow/runs/<RUN_ID>/` when writing the first artifact.
3. For each phase handoff, paste the `## NEXT AGENT PROMPT (COPY/PASTE)` block from the artifact file that was just written:
   1. Planning → writes `plan-vN.md` (ends with NEXT → Plan Review)
   2. Plan Review → writes `plan-review-vN.md` (ends with NEXT → Coding or Planning loop)
   3. Coding → writes `impl-vN.md` + code/tests (ends with NEXT → Verification)
   4. Verification → writes `verify-vN.md` + updates checklist/index (ends with NEXT → Review or Coding loop)
   5. Review → writes `review-vN.md` + finalizes index (ends with NEXT → next run stub)

### Stop / Loop Rules (Non-Negotiable)

- Coding must **not** start unless:
  - `.agent-workflow/runs/<RUN_ID>/plan-review-vN.md` exists
  - Verdict is **APPROVED**
  - `Implementation Agent Decision Points Remaining: NONE`
- Plans must include `## Spec Anchors (SSOT)` pointing to exact spec headings for behavior/signatures; plans list one-line signatures for planned public functions.
- If Plan Review verdict is **CHANGES REQUIRED**:
  - Planning writes `plan-v(N+1).md`, then Plan Review repeats (`plan-review-v(N+1).md`)
- If Review verdict is **CHANGES REQUIRED**:
  - Coding writes `impl-v(N+1).md`, then Verification repeats (`verify-v(N+1).md`), then Review repeats
- If Review verdict is **DESIGN ISSUE**:
  - Return to Planning (`plan-v(N+1).md`) and re-run Plan Review

### SSOT Drift Rule (Hard Gate)

If Review finds that implementation behavior/signatures drift from the SSOT spec:

- Do **not** approve.
- Require SSOT spec update + re-verification in the same run; if intended behavior changes, return to Planning + Plan Review.

### Minimal Commands (Operator Sanity Checks)

Default: you should not have to run anything during the run. The Verification Agent runs commands and pastes outputs into `verify-vN.md`; your job is to confirm the evidence exists and is green.

If you want to spot-check locally:

```bash
# One-command readiness gates:
./scripts/check-all-gates.sh

# Tooling (preferred):
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Repo-script gates (always --no-sync):
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/<RUN_ID>/plan-v<N>.md
```

### Artifact/Index Policy (So You Don’t Have to Remember)

- Run artifacts are always under `.agent-workflow/runs/<RUN_ID>/` as `*-vN.md`.
- `.agent-workflow/index.md`:
  - Verification appends a `PENDING_REVIEW` row (links: plan/plan-review/impl/verify)
  - Review finalizes that row (replace verdict, add review link)

### Agent Reset Policy (Context Hygiene)

Goal: your day-to-day operation is “confirm the current step is complete, then paste the NEXT block”.

- **Default:** keep one persistent thread per agent role and only paste the NEXT block each turn.
- **Restart + re-send the agent’s full system prompt** when:
  - Remaining context is **<30%** (or **<40%** for smaller-window models), or
  - You see “rot” (missed STOP rules, invented paths/versions, missing required report sections), or
  - You start a new run and want a clean slate.
- **Ideal reset points (safe boundaries):**
  - After each run completes (Review verdict written).
  - At phase boundaries (`## Phase N` changes in the master checklist).
  - Before/after each `### Phase N Quality Gate ✓` checkpoint.

### Optional: Codex Skills (Productivity)

If you want more “operator-as-confirmation” behavior, install and use the repo’s Codex skills:

- `codex-skills/fc2-orchestrator/SKILL.md` (run-loop orchestration + NEXT handoffs)
- `codex-skills/fc2-readiness-audit/SKILL.md` (readiness gate audit + timestamp/log updates)
- `codex-skills/fc2-run-validate/SKILL.md` (validate a run directory after each artifact write)
- `codex-skills/fc2-next-prompt/SKILL.md` (extract the NEXT block from an artifact for copy/paste)
- `codex-skills/fc2-ci-triage/SKILL.md` (deterministic local CI reproduction + minimal fix plan)

---

## 1. Project Objectives

### 1.1 Primary Objectives

| ID | Objective | Success Metric | Priority |
|----|-----------|----------------|----------|
| O1 | Recreate all critical functionality | 100% feature parity for frame selection, HDR tonemap, audio alignment, slow.pics | Critical |
| O2 | Eliminate technical debt | Zero known issues from dissection at launch | High |
| O3 | Container-first deployment | Single `docker compose up` starts complete environment | Critical |
| O4 | Improve maintainability | Pyright strict mode, 80%+ coverage, import-linter contracts | High |
| O5 | Enhance developer experience | DevContainer support, `uv` toolchain, pre-commit hooks | Medium |
| O6 | Preserve programmatic API | `RunRequest`/`RunResult` pattern maintained | High |

### 1.2 Anti-Objectives (Explicitly Out of Scope)

| ID | What We Will NOT Do | Rationale |
|----|---------------------|-----------|
| A1 | Add new features beyond v0.0.14 | Focus on clean recreation first |
| A2 | Support macOS (initially) | VapourSynth toolchain issues; defer to Phase 2 |
| A3 | GPU-accelerated tonemapping | Maintain software rasterization for universality |
| A4 | Web UI or SPA | CLI-first; HTML report is offline-only |
| A5 | Real-time video preview | Batch processing only |

---

## 2. Stakeholder Analysis

| Stakeholder | Role | Interest | Influence | Key Concerns |
|-------------|------|----------|-----------|--------------|
| Fansub/QC Teams | Primary users | High | High | Feature parity, overlay accuracy |
| Encoding Enthusiasts | Power users | High | Medium | HDR tonemap quality, preset flexibility |
| Automation Engineers | Integrators | Medium | Medium | Programmatic API stability |
| Archivists | Secondary users | Medium | Low | Reproducibility, caching |
| Maintainers | Developers | High | High | Code quality, testability, DX |

---

## 3. Constraints & Assumptions

### 3.1 Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| Runtime | Python 3.13+ only | Limits deployment to modern environments |
| Dependency | VapourSynth ≥72 required | Complex installation; mitigated by containerization |
| Platform | Linux/Windows 64-bit only (macOS paused) | Narrow initial platform matrix |
| Processing | Local CPU execution only | No cloud offload; large files require local resources |
| Storage | Direct volume mounts for video files | Must handle multi-GB files efficiently |

### 3.2 Assumptions

1. Docker is available on target deployment systems
2. VapourSynth plugins (libplacebo, etc.) can be compiled with software rasterization
3. slow.pics API remains stable and accessible
4. TMDB API continues to allow metadata lookups
5. Existing config.toml format is acceptable for backward compatibility

### 3.3 External Dependencies

| Dependency | Type | Owner | Risk if Unavailable |
|------------|------|-------|---------------------|
| VapourSynth | Core | VS Community | Critical - no HDR pipeline |
| libplacebo | Core | Niklas Haas | High - no tonemapping |
| slow.pics | External API | Third party | Medium - local-only mode fallback |
| TMDB | External API | Third party | Low - manual metadata entry |
| FFmpeg | Fallback renderer | FFmpeg team | Low - VS is primary |

---

## 4. Technology Stack Selection

### 4.1 Core Stack (Best Practices — Ground-Up)

| Category | Technology | Purpose | Why |
|----------|------------|---------|-----|
| **Language** | Python 3.13+ | Core runtime | Latest performance, typing |
| **Video Engine** | VapourSynth R72+ | Primary renderer, tonemapping | No alternative for HDR |
| **CLI Framework** | **Typer** | Command-line interface | Type-hint native, better UX than Click |
| **Config** | **Pydantic v2 Settings** | Configuration management | Type-safe, validation, env vars |
| **Serialization** | **msgspec** | JSON/cache I/O | 10-50x faster than stdlib |
| **UI** | Rich | Progress bars, formatted output | Standard, excellent |
| **Audio** | NumPy, Librosa, SoundFile | Audio alignment | No better alternatives |
| **Network** | **httpx (async)** + **anyio** | slow.pics, TMDB | Parallel uploads, structured concurrency |
| **Parsing** | GuessIt, Anitopy | Filename metadata | Proven parsers |

### 4.2 Development Stack

| Tool | Purpose |
|------|---------|
| `uv` | Package management (fastest) |
| `pytest` + `pytest-mock` + `anyio` | Testing framework |
| `ruff` | Linting + formatting (replaces black) |
| `pyright` | Type checking (strict mode) |
| `import-linter` | Dependency contracts |
| `pre-commit` | Git hooks |

### 4.3 Modern Patterns Adopted

| Pattern | Implementation | Benefit |
|---------|----------------|---------|
| **Result Types** | `Ok[T] \| Err[E]` | Explicit error handling, no hidden exceptions |
| **Dependency Injection** | `RunDependencies` dataclass | Testability, mockability |
| **Async Network** | httpx + anyio task groups | Parallel uploads, clean cancellation |
| **Validated Config** | Pydantic models | Type-safe, schema generation |

### 4.4 Infrastructure Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Container | Docker with multi-stage builds | Reproducible deployment |
| DevContainer | VS Code DevContainers | Immediate "Click-to-Code" setup |
| CI/CD | GitHub Actions | Build, test, publish |

---

## 5. High-Level Architecture

### 5.1 Layered Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│  frame_compare.py → cli_entry.py                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                       │
│  runner.py → WorkflowCoordinator → phases/                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                           │
│  alignment.py │ metadata.py │ publishers.py │ dovi_tool.py  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Core Domain                             │
│  analysis/ │ vs/ │ render/ │ screenshot/                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Infrastructure                           │
│  VapourSynth │ FFmpeg │ slow.pics API │ TMDB API           │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Key Design Principles

1. **Clean Layer Boundaries**: CLI → Orchestration → Services → Domain → Infrastructure
2. **Dependency Injection**: `RunDependencies`, `RunContext` for testability
3. **Type Safety**: Pyright strict mode, `py.typed` marker
4. **Import Contracts**: Enforced via import-linter
5. **Cache-First**: Deterministic caching with hash-versioned metadata

---

## 6. Core Features to Recreate

| Feature | Priority | Complexity | Dependencies |
|---------|----------|------------|--------------|
| Frame Discovery & Selection | P0 | High | VapourSynth |
| HDR Tonemapping (libplacebo) | P0 | High | VapourSynth, libplacebo |
| Audio Alignment | P0 | Medium | NumPy, Librosa |
| Screenshot Rendering | P0 | Medium | VapourSynth/FFmpeg |
| slow.pics Publishing | P0 | Medium | httpx |
| TMDB Metadata Resolution | P1 | Low | httpx |
| HTML Report Generation | P1 | Low | Jinja2-style templates |
| VSPreview Integration | P2 | Medium | VSPreview, PySide6 |
| Dolby Vision Support | P1 | High | dovi_tool |

---

## 7. Document Suite Structure

```
docs/OPUS_REBUILD_FRAME_COMPARE/
├── 00-executive-summary.md          # This document
├── 01-project-charter.md            # Detailed charter & governance
├── 02-requirements/
│   ├── business-requirements.md     # BR matrix & process flows
│   ├── functional-requirements.md   # FR by module
│   └── non-functional-requirements.md
├── 03-architecture/
│   ├── system-design.md             # C4 diagrams, component specs
│   ├── data-architecture.md         # Data models, caching strategy
│   ├── api-design.md                # CLI & programmatic API design
│   └── adr/                         # Architecture Decision Records
│       ├── 001-language-runtime.md
│       ├── 002-containerization.md
│       ├── 003-video-processing.md
│       ├── 004-testing-strategy.md
│       ├── 005-cli-config-stack.md
│       └── 006-network-architecture.md
├── 04-roadmap/
│   ├── phases.md                    # Phase breakdown
│   ├── milestones.md                # Milestone definitions
│   └── sprint-templates.md          # Sprint planning with story templates
├── 05-implementation/
│   ├── module-specs/                # Per-module blueprints
│   │   ├── errors-module.md         # Exception hierarchy (P0)
│   │   ├── utils-module.md          # Utilities & result types (P0)
│   │   ├── config-module.md         # Configuration loading (P1)
│   │   ├── vs-module.md             # VapourSynth abstraction (P1)
│   │   ├── analysis-module.md       # Frame metrics & selection (P2)
│   │   ├── render-module.md         # Screenshot rendering (P2)
│   │   ├── services-module.md       # Alignment, metadata, upload (P2)
│   │   └── cli-module.md            # CLI & orchestration (P3)
│   ├── error-codes.md               # FC-xxxx error registry
│   ├── config-reference.md          # Configuration reference
│   ├── testing-strategy.md          # Test types, coverage, CI
│   └── error-handling.md            # Exception hierarchy & patterns
├── 06-operations/
│   ├── deployment.md                # Docker, DevContainer setup
│   ├── monitoring.md                # Logging, metrics, tracing
│   └── runbooks.md                  # Operational procedures
├── 07-risk-management.md            # Risk register & contingencies
├── 08-quality-standards.md          # Code quality, review process
├── agent-prompts/                   # Canonical agent prompts (file-based run workflow)
│   ├── 01-planning-agent.md
│   ├── 02-plan-review-agent.md
│   ├── 03-coding-agent.md
│   ├── 04-verification-agent.md
│   └── 05-review-agent.md
└── 10-agent-master-checklist.md     # Master implementation tracking
```

---

## 8. Next Steps

1. **Review & Approve** this executive summary
2. **Generate** detailed requirements documents
3. **Create** Architecture Decision Records for key choices
4. **Define** implementation phases and milestones
5. **Write** module-level implementation specifications

## 9. PROJECT START GUIDANCE

- Moving docs/OPUS_REBUILD_FRAME_COMPARE/ into a new repo does transplant the FC‑2.0 docs + contracts + agent prompts,
    and it also carries a docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/ “starter project” you can promote to be your repo’s
    actual codebase.
- But it does not automatically make the new repo runnable, because the scaffold is still nested under docs/.../
    scaffold/ and the contract tooling (scripts/*.py) lives at repo root.

  Here’s the guided “what to do next” after you copy docs/OPUS_REBUILD_FRAME_COMPARE/ into the new empty repo.

## 1) Decide: “promote scaffold” vs “docs-only”

  For a new empty repo, you almost certainly want to promote the scaffold to repo root so you can start implementing
  immediately with working tooling.

## 2) Copy the contract tooling to repo root (required)

  In the new repo root, create/copy:

- scripts/generate_contract_views.py
- scripts/validate_traceability.py

  These scripts currently assume the contracts live at docs/OPUS_REBUILD_FRAME_COMPARE/contracts/ (which you are
  keeping), so that part will work as-is once the scripts exist.

## 3) Promote the scaffold to be the real project (recommended)

  From docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/, copy these into the new repo root (same relative paths):

- pyproject.toml
- uv.lock (if you want the lockfile pinned from day 1)
- src/frame_compare/ (entire package)
- tests/
- .github/workflows/ci.yml (optional now, but recommended early)
- .gitignore (merge/extend your root ignore rules)

  Then delete/avoid committing scaffold artifacts that were only for the monorepo snapshot:

- docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/.venv/
- docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/.pytest_cache/
- docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/.ruff_cache/

## 4) Set up agent working dirs (so your prompts “just work”)

  Create (one-time):

- .agent-workflow/runs/    # All run artifacts stored in .agent-workflow/runs/<RUN_ID>/
- .agent-workflow/index.md # Run tracking index (copy from template)

## 5) Run the “day 0” gates in the new repo

  Run (from repo root):

- uv sync --group dev --frozen
- .venv/bin/pyright --warnings
- .venv/bin/ruff check .
- .venv/bin/pytest -q
- Readiness gates (all three): `./scripts/check-all-gates.sh`
- Or, run the canonical commands individually:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
  - `(cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a)`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`

  If those are green, you’re ready to start the 5‑agent loop.

## 6) Start implementing (your role)

  Even with “auto-orchestration” prompts, you have two options each run:
  - Minimal: tell the Planning Agent to pick the next unchecked item from `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` and propose a RUN_ID; you only confirm the RUN_ID.
  - Directed: provide “Target: Phase X → Item Y” when you want to override checklist selection.

  If you want, tell me whether you’re promoting all of scaffold/ (including its .github/workflows/ci.yml) or just the
  Python package + tests, and I’ll give you a precise “copy list” tailored to that choice.
