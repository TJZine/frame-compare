---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v1
TARGET: Phase 7 → Item 7.1 (Bundled)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/01-project-charter.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - README.md
  - CHANGELOG.md
  - src/frame_compare/
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v1.md
---

# Implementation Plan: Phase 7.1 Documentation Bundle (README + Changelog + Docstrings + API Docs)

## Context

**Phase:** 7
**Module:** Documentation + Public API docstrings
**Checklist Target:** `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` → Phase 7 → 7.1 Documentation (bundled 4 tasks)
**Dependencies:** Phase 6 features are implemented (CLI `run`/`wizard`/`doctor`, pipeline, and quality gates).

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`:
  - Section: "Phase 7: Polish & Documentation"
  - Section: "7.1 Documentation"

- `docs/OPUS_REBUILD_FRAME_COMPARE/01-project-charter.md`:
  - Section: "5.3 Documentation Standards"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2. CLI Entry Point"
  - Section: "2.1 Command Structure"
  - Section: "2.2 Exit Codes"

## Scope

This plan covers (ALL are required for Phase 7 → Item 7.1 completion):

- [ ] Complete `README.md` with concrete usage examples (install + CLI workflows)
- [ ] Update `CHANGELOG.md` (document the Phase 7.1 docs changes under Unreleased)
- [ ] Add/normalize docstrings for all public APIs (Google-style) across the `frame_compare.*` surface
- [ ] Generate API documentation (deterministic Markdown) and document the generation/check command in README

This plan does NOT cover:

- Phase 7.2 tasks (coverage, performance testing, repo-wide QA beyond running the standard gates)
- Any behavioral changes to the pipeline, config resolution, or error handling (docstrings/docs only)
- Contract edits under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` (NO contract loop in this run)

## Files to Create/Modify

### 1. `README.md` (MODIFY)

**Purpose:** Make the README usable as the primary “how do I run this?” entrypoint, with real commands and a minimal end-to-end workflow.

**Edits to make (exact structure):**

- Add a new top-level section `## Usage` directly after `## Quick start` (and include it in the Table of Contents).
- In `## Usage`, add subsections in this order:
  1. `### CLI overview` (mention `frame-compare --help`, and the three main commands: `run`, `wizard`, `doctor`)
  2. `### Create a workspace (wizard)` (show command and describe the created `config/config.toml`)
  3. `### Validate dependencies (doctor)` (show `doctor` and `doctor --json`; mention exit codes are meaningful)
  4. `### Run a comparison (run)` (show a minimal run and 2–3 common flags: `--no-upload`, `--skip-metadata`, `--skip-analysis`, `--tm-preset/--tm-target/--tm-curve` as appropriate)
  5. `### Workspace layout` (document the default directories at workspace root: `config/`, `input/`, `screenshots/`, `generated/`)
  6. `### Configuration reference` (link to the generated config reference under OPUS rebuild docs)
  7. `### API documentation` (link to `docs/api.md` generated in this run)

**Hard requirement:** Every README command example must match the real CLI surface (verify via `frame-compare --help` and subcommand `--help` during implementation).

**Usage examples to include (copy/paste, then verify outputs match real behavior):**

```bash
# Help / command discovery
frame-compare --help
frame-compare run --help
frame-compare doctor --help

# Workspace initialization (writes config/config.toml under --root)
frame-compare wizard --root /path/to/workspace

# Dependency diagnostics
frame-compare doctor
frame-compare doctor --json

# Typical run (uses config/config.toml under --root)
frame-compare run --root /path/to/workspace --no-upload
```

### 2. `CHANGELOG.md` (MODIFY)

**Purpose:** Record Phase 7.1 documentation work.

**Edits to make (under `## Unreleased`):**

- Add an entry under `### Added` or `### Changed` (choose the best fit) that mentions:
  - README now includes usage examples for `wizard`/`doctor`/`run`
  - Public API docstrings were added/normalized (Google style)
  - API docs Markdown was generated (and where it lives)

### 3. Public API Docstrings (MODIFY: `src/frame_compare/**/*.py`)

**Purpose:** Ensure every public API surface has a clear, Google-style docstring so API docs generation is meaningful.

**Definition of “public API” for this run (decision-minimizing rule):**

- Any object exported via `__all__` in:
  - `src/frame_compare/analysis/__init__.py`
  - `src/frame_compare/config/__init__.py`
  - `src/frame_compare/orchestration/__init__.py`
  - `src/frame_compare/render/__init__.py`
  - `src/frame_compare/services/__init__.py`
  - `src/frame_compare/utils/__init__.py`
  - `src/frame_compare/vs/__init__.py`
  - `src/frame_compare/vspreview/__init__.py`
  - `src/frame_compare/runner.py`
- Additionally, add/normalize module docstrings for any of the above packages/modules if missing (for example `src/frame_compare/render/__init__.py` currently lacks a module docstring).

**Docstring standards (apply consistently):**

- One-line summary first line.
- Google-style sections as applicable: `Args:`, `Returns:`, `Raises:`.
- Mention determinism/stability invariants where relevant (sorting, seed usage, stable paths).
- For dataclasses / TypedDict-style types: include `Attributes:` for key fields (high-level, not exhaustive).

**Functions to implement (spec-anchored):**

- `run(...) -> None` — CLI entrypoint docstring must accurately describe behavior and key options
- `wizard() -> None` — CLI entrypoint docstring must describe workspace initialization behavior
- `doctor(...) -> None` — CLI entrypoint docstring must describe human vs JSON output and exit code behavior

**Concrete file list (allowed to modify in this run):**

- `src/frame_compare/__init__.py`
- `src/frame_compare/cli_entry.py`
- `src/frame_compare/runner.py`
- `src/frame_compare/errors.py`
- `src/frame_compare/analysis/__init__.py`
- `src/frame_compare/analysis/cache_io.py`
- `src/frame_compare/analysis/frame_plan.py`
- `src/frame_compare/analysis/metrics.py`
- `src/frame_compare/analysis/selection.py`
- `src/frame_compare/analysis/types.py`
- `src/frame_compare/config/__init__.py`
- `src/frame_compare/config/defaults.py`
- `src/frame_compare/config/loader.py`
- `src/frame_compare/config/overrides.py`
- `src/frame_compare/config/presets.py`
- `src/frame_compare/config/schema.py`
- `src/frame_compare/orchestration/__init__.py`
- `src/frame_compare/orchestration/context.py`
- `src/frame_compare/orchestration/coordinator.py`
- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/orchestration/fps_report.py`
- `src/frame_compare/orchestration/phases.py`
- `src/frame_compare/orchestration/preflight.py`
- `src/frame_compare/orchestration/probe_cache.py`
- `src/frame_compare/orchestration/probe_props.py`
- `src/frame_compare/orchestration/progress.py`
- `src/frame_compare/render/__init__.py`
- `src/frame_compare/render/encoders.py`
- `src/frame_compare/render/geometry.py`
- `src/frame_compare/render/naming.py`
- `src/frame_compare/render/orchestrator.py`
- `src/frame_compare/render/overlay.py`
- `src/frame_compare/render/types.py`
- `src/frame_compare/services/__init__.py`
- `src/frame_compare/services/alignment.py`
- `src/frame_compare/services/metadata.py`
- `src/frame_compare/services/publishers.py`
- `src/frame_compare/services/report.py`
- `src/frame_compare/services/types.py`
- `src/frame_compare/utils/__init__.py`
- `src/frame_compare/utils/logging.py`
- `src/frame_compare/utils/perf.py`
- `src/frame_compare/utils/progress.py`
- `src/frame_compare/utils/subproc.py`
- `src/frame_compare/utils/types.py`
- `src/frame_compare/vs/__init__.py`
- `src/frame_compare/vs/color.py`
- `src/frame_compare/vs/env.py`
- `src/frame_compare/vs/loader.py`
- `src/frame_compare/vs/props.py`
- `src/frame_compare/vs/source.py`
- `src/frame_compare/vs/tonemap.py`
- `src/frame_compare/vs/types.py`
- `src/frame_compare/vspreview/__init__.py`
- `src/frame_compare/vspreview/adapter.py`
- `src/frame_compare/vspreview/overrides.py`

### 4. `scripts/generate_api_docs.py` (CREATE)

**Purpose:** Deterministically generate a Markdown API reference from the public export lists (`__all__`) and docstrings.

**Behavior requirements:**

- Output path: `docs/api.md`
- Deterministic ordering:
  - Module order is fixed (explicit list in the script).
  - Within a module, symbols are ordered case-insensitively by name.
- Include, per module:
  - A heading with the module import path (e.g. `frame_compare.render`)
  - A short module summary (module docstring first paragraph)
  - For each exported symbol:
    - Signature (best-effort via `inspect.signature`; fall back to `(...)` if not available)
    - First paragraph of the symbol docstring
- Hard failure mode (enforces docstrings task):
  - If any exported symbol is missing a docstring (empty or None), `--check` must exit non-zero with a clear message listing missing symbols.
- CLI:
  - Default mode rewrites `docs/api.md` (LF endings).
  - `--check` compares the would-be output against the committed file and exits 0 only if identical.

### 5. `docs/api.md` (CREATE, GENERATED)

**Purpose:** Committed, generated API reference (do not edit by hand).

**Header requirements (top of file):**

- A short note stating it is generated by `scripts/generate_api_docs.py` and should not be edited manually.
- No timestamps or environment-specific paths (keep diffs deterministic).

## Acceptance Criteria

- [ ] GIVEN a new user WHEN reading `README.md` THEN they can follow the Usage section to run `wizard`, `doctor`, and a minimal `run` invocation without needing to read OPUS workflow docs first
- [ ] GIVEN the real CLI surface WHEN running `frame-compare --help` and `frame-compare run --help` THEN the options/commands shown are consistent with the README usage examples (no stale flags)
- [ ] GIVEN the Phase 7.1 documentation bundle WHEN reading `CHANGELOG.md` THEN Unreleased includes an entry describing the README improvements, docstring normalization, and generated API docs
- [ ] GIVEN the public export lists (`__all__`) WHEN running the API docs generator in check mode THEN it exits 0 and `docs/api.md` is up-to-date
- [ ] GIVEN any exported symbol without a docstring WHEN running the API docs generator in check mode THEN it exits non-zero and lists the missing docstrings (enforcing completeness)

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Quality gates (repo-wide)
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract derived views remain fresh (should be a no-op in this run)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check

# API docs generation freshness
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings. `docs/api.md` matches generator output.

## Notes for Coding Agent

1. Do not change behavior: this run is documentation-only (README/CHANGELOG/docstrings + doc generation tooling).
2. Use `__all__` as the authoritative public export list for docstring completeness and API docs generation.
3. Keep the API docs generator stdlib-only and deterministic (no timestamps; stable ordering; LF endings).
4. If any docstring content is ambiguous, prefer documenting current behavior as implemented and validated via `--help` output rather than inventing new semantics.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Plan to Review

Read file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v1.md

## Context Files to Read (if needed)

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/01-project-charter.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md

## Your Task

Validate the plan is implementation-ready using the 9-point checklist in the workflow SSOT.

## Output

Write file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v1.md

If verdict is APPROVED, confirm:
- Verdict: APPROVED
- Implementation Agent Decision Points Remaining: NONE

If verdict is CHANGES REQUIRED, specify concrete edits for a `plan-v2.md` revision.
