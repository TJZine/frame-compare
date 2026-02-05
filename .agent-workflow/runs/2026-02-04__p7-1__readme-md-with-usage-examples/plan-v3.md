---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v3
TARGET: Phase 7 → Item 7.1 (Bundled) — Documentation — Complete README.md with usage examples — Bundled 4 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v2.md
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/01-project-charter.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - README.md
  - CHANGELOG.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v3.md
---

# Implementation Plan: Phase 7.1 Documentation Bundle (README + Changelog + Docstrings + API Docs)

## Changes Since plan-v2

Edits required by `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v2.md` (2026-02-05):

1. Locked the generator entrypoint callable interface (explicit `main(argv=...) -> int` contract) and removed “or equivalent” language from tests.
2. Removed placeholder function signatures from the plan; retained only SSOT-referenced signatures needed for Spec Anchors validation and clarified they are referenced (not modified) for README alignment.

## Context

**Phase:** 7
**Target:** Phase 7 → Item 7.1 (Bundled) — Documentation (4 tasks)
**Purpose:** Ship a README that is copy/paste runnable, ensure public API docstrings are complete (Google style),
and generate deterministic API reference docs.

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

- [ ] Complete `README.md` with usage examples for `wizard`, `doctor`, and `run`
- [ ] Update `CHANGELOG.md` under `## Unreleased` to reflect these documentation deliverables
- [ ] Add/normalize docstrings for all public APIs (definition below; Google style)
- [ ] Generate deterministic Markdown API documentation and commit it

This plan does NOT cover:

- Phase 7.2 tasks (coverage changes, performance work, or repo-wide refactors unrelated to docstrings)
- Contract edits under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`
- Any behavior changes to the runtime pipeline (docstrings/docs/tooling only)

## Decisions Locked (No Further Decision Points)

### A) Canonical CLI invocation for README examples

README examples MUST assume the developer workflow:

1) `uv sync --group dev --frozen`
2) `source .venv/bin/activate`
3) Use `frame-compare ...` (binary is on PATH from the activated venv)

### B) Public API definition for docstrings (enforced)

Docstring completeness is enforced for exports (by kind) from the locked module list in the API docs generator section:

- Enforced: functions, classes (including dataclasses), enums, protocols, TypedDict-like classes.
- Not enforced (but documented): exported constants (strings, mappings, config templates, etc.).

### C) API docs generation strategy (non-importing)

The generator MUST NOT import `frame_compare.*` modules at runtime (to avoid optional dependency import failures,
notably VapourSynth). Instead, it MUST parse source files under `src/` using the stdlib AST.

### D) Generator entrypoint contract (locked)

The generator MUST expose an explicit entrypoint that tests call directly:

`def main(argv: Sequence[str] | None = None) -> int:`

Rules:

- `main(None)` parses CLI arguments from `sys.argv[1:]`.
- `main([...])` parses arguments from the provided list and MUST NOT read `sys.argv`.
- `main(...)` returns an `int` exit code; the script’s `__main__` calls `raise SystemExit(main())`.

### E) Exit code contract for the generator script (enforced)

`scripts/generate_api_docs.py` exit codes:

- 0: success (output written) or `--check` passes
- 2: `--check` detected output drift (generated != existing)
- 3: missing required docstrings for enforced symbol kinds
- 4: resolution/import-path error (module path not found under `src/`, unresolved `__all__`, or missing symbol)
- 1: unexpected exception (internal error)

## Files to Create/Modify

### 1) `README.md` (MODIFY)

**Purpose:** Provide a copy/paste runnable “Usage” section aligned with the real CLI behavior.

**Edits to make (exact structure):**

- Update Table of Contents to include `Usage`.
- Add `## Usage` directly after `## Quick start`.
- Under `## Usage`, add subsections in this order:
  1. `### CLI overview`
  2. `### Create a workspace (wizard)`
  3. `### Validate dependencies (doctor)`
  4. `### Run a comparison (run)`
  5. `### Workspace layout`
  6. `### Configuration reference`
  7. `### API documentation`

**Hard requirements (must be true):**

- README MUST NOT claim `wizard` supports `--root` (it does not; it writes `./config/config.toml` in the CWD).
- Every flag shown in README examples MUST exist in `frame-compare run --help` (no “as appropriate” placeholders).

**Usage examples to include (verbatim), using the canonical invocation model:**

```bash
# Repo dev install (once)
uv sync --group dev --frozen
source .venv/bin/activate

# Workspace setup (run wizard from inside the workspace directory)
mkdir -p /path/to/workspace
cd /path/to/workspace
frame-compare wizard

# Dependency diagnostics
frame-compare doctor
frame-compare doctor --json

# Run (from workspace root: --root defaults to ".")
frame-compare run --no-upload --skip-metadata

# Run with analysis skipped (uniform sampling) and explicit seed/frame count
frame-compare run --skip-analysis --seed 123 --frame-count 24 --no-upload --skip-metadata

# Run with tonemap overrides (example preset/curve/target)
frame-compare run --tm-preset filmic --tm-curve spline --tm-target 203 --no-upload --skip-metadata
```

**Workspace layout section MUST document (truthful to current behavior):**

- `config/config.toml` is written by `frame-compare wizard` in the current directory.
- `paths.input_dir` in config points to an existing directory with video files (wizard validates it exists).
- `screenshots/` and `generated/` are output/cache directories controlled by config defaults and created as needed.

**Links to add:**

- Config reference: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- API docs: `docs/api.md` (generated in this run)

### 2) `CHANGELOG.md` (MODIFY)

**Purpose:** Record Phase 7.1 documentation work under `## Unreleased`.

**Edits to make:**

- Add one bullet under `## Unreleased` (either `### Added` or `### Changed`) that mentions:
  - README usage examples for `wizard`/`doctor`/`run`
  - Public API docstrings normalized (Google style)
  - Generated API documentation at `docs/api.md` (and generator script path)

### 3) `scripts/generate_api_docs.py` (CREATE)

**Purpose:** Deterministically generate `docs/api.md` from public exports (`__all__`) and docstrings.

**Locked entrypoint signature:**

`def main(argv: Sequence[str] | None = None) -> int:`

**Module list and order (locked):**

The generator MUST document exactly these modules, in this order:

1. `frame_compare` (from `src/frame_compare/__init__.py`)
2. `frame_compare.analysis` (from `src/frame_compare/analysis/__init__.py`)
3. `frame_compare.config` (from `src/frame_compare/config/__init__.py`)
4. `frame_compare.orchestration` (from `src/frame_compare/orchestration/__init__.py`)
5. `frame_compare.render` (from `src/frame_compare/render/__init__.py`)
6. `frame_compare.services` (from `src/frame_compare/services/__init__.py`)
7. `frame_compare.utils` (from `src/frame_compare/utils/__init__.py`)
8. `frame_compare.vs` (from `src/frame_compare/vs/__init__.py`)
9. `frame_compare.vspreview` (from `src/frame_compare/vspreview/__init__.py`)
10. `frame_compare.runner` (from `src/frame_compare/runner.py`)

**Input discovery rules (AST-based, no imports):**

- For each module path above:
  - Resolve its source file under `src/` (package `__init__.py` or module `.py`).
  - Parse the module AST and extract `__all__` (must be a literal list/tuple of string literals).
  - For each exported name:
    - Resolve the symbol to a definition node:
      - In-module `def` / `class` definitions
      - `from ... import ... as ...` re-exports (resolve to the source module and find the definition there)
      - Simple alias assignment (`alias = name`) inside the module
    - If resolution fails, treat as an error (exit code 4 in `--check`).

**Docstring enforcement rules (locked):**

- If an exported symbol resolves to a function or class:
  - It MUST have a docstring (non-empty) or `--check` fails with exit code 3.
- If an exported symbol resolves to a constant / assignment (no def/class):
  - It is exempt from docstring enforcement, but MUST be documented in `docs/api.md` as a constant.

**Output format (locked):**

- Output path default: `docs/api.md`
- Top-of-file header MUST state it is generated by `scripts/generate_api_docs.py` and must not be edited by hand.
- For each module:
  - H2 heading: the module path
  - Module summary: first paragraph of module docstring (or `"(no module docstring)"`)
  - A per-symbol entry, sorted case-insensitively by symbol name:
    - For functions: show signature (rendered from AST; no runtime evaluation) and first paragraph of docstring
    - For classes: show class name and first paragraph of docstring
    - For constants: show `NAME: constant` plus best-effort type string (literal type if trivially inferable)
- Determinism:
  - Stable ordering everywhere; no timestamps; LF line endings on write.

**CLI contract (to support tests without repo writes):**

- Default: rewrite `docs/api.md`.
- `--check`: do not write; compare would-be output to existing output file.
- Optional flags:
  - `--project-root <path>` (defaults to repo root)
  - `--output <path>` (defaults to `<project-root>/docs/api.md`)

### 4) `docs/api.md` (CREATE, GENERATED)

**Purpose:** Committed, generated API reference output from the generator.

**Workflow requirement:** Do not hand-edit. Update by running:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py
```

### 5) `tests/test_generate_api_docs.py` (CREATE)

**Purpose:** Unit tests for the API docs generator (no external dependencies).

**Test strategy (must be implemented):**

- Use `tmp_path` to create a minimal fake project root with a `src/` tree.
- Import the generator module itself (safe; it is stdlib-only) and call its exact entrypoint:
  - Call `main([...])` with explicit argv lists (do not rely on `sys.argv` in tests).

**Tests required (exact assertions):**

1. Deterministic ordering: generated output lists symbols in case-insensitive order.
2. Constant handling: exported constant does not trigger missing-docstring failure and is rendered as a constant entry.
3. Missing docstrings: `--check` fails with exit code 3 and includes the missing symbol name(s) in stderr output.
4. Drift detection: when output file differs, `--check` fails with exit code 2.

### 6) Public API Docstrings (MODIFY: `src/frame_compare/**/*.py`)

**Purpose:** Ensure docstrings exist and are Google-style for enforced public API symbol kinds.

**Concrete docstring enforcement set (locked):**

- For each of the 10 modules listed in the generator module list:
  - Every exported function/class (as resolved via the generator’s AST resolution) MUST have a non-empty docstring.
- Exported constants are exempt from docstring enforcement.

**Docstring style rules:**

- Google-style sections as relevant: `Args:`, `Returns:`, `Raises:`.
- Document determinism/stability invariants where relevant (sorting, seeds, stable JSON output).

## Functions to implement (spec-anchored; referenced only)

These signatures are referenced for README alignment and Spec Anchors validation. They are NOT being implemented or
changed in this docs/tooling run.

- `run(root: Path = typer.Option(\".\", \"--root\", \"-r\"), config: Path | None = typer.Option(None, \"--config\", \"-c\"), input_dir: Path | None = typer.Option(None, \"--input\", \"-i\"), no_cache: bool = typer.Option(False, \"--no-cache\"), from_cache_only: bool = typer.Option(False, \"--from-cache-only\"), no_upload: bool = typer.Option(False, \"--no-upload\"), tm_preset: str | None = typer.Option(None, \"--tm-preset\"), tm_target: int | None = typer.Option(None, \"--tm-target\"), tm_curve: str | None = typer.Option(None, \"--tm-curve\"), frame_count: int | None = typer.Option(None, \"--frame-count\", \"-n\"), seed: int | None = typer.Option(None, \"--seed\"), overlay: str | None = typer.Option(None, \"--overlay\"), skip_analysis: bool = typer.Option(False, \"--skip-analysis\"), skip_metadata: bool = typer.Option(False, \"--skip-metadata\"), skip_dovi: bool = typer.Option(False, \"--skip-dovi\"), force_interactive_alignment: bool = typer.Option(False, \"--force-interactive-alignment\"), json_output: bool = typer.Option(False, \"--json\"), no_color: bool = typer.Option(False, \"--no-color\"), write_config: bool = typer.Option(False, \"--write-config\"), diagnose_paths: bool = typer.Option(False, \"--diagnose-paths\"), quiet: bool = typer.Option(False, \"--quiet\", \"-q\"), verbose: bool = typer.Option(False, \"--verbose\", \"-v\")) -> None`
- `wizard() -> None`
- `doctor(json_output: bool = typer.Option(False, \"--json\")) -> None`

## Acceptance Criteria

- [ ] GIVEN a developer with repo checkout WHEN following the README Usage section THEN they can:
  - create a workspace (`wizard`)
  - run diagnostics (`doctor`, `doctor --json`)
  - run a minimal comparison (`run --no-upload --skip-metadata`)
- [ ] GIVEN the real CLI surface WHEN running `frame-compare run --help` THEN every flag used in README examples exists
- [ ] GIVEN Phase 7.1 documentation bundle WHEN reading `CHANGELOG.md` THEN `## Unreleased` includes an entry describing README, docstrings, and API docs generation
- [ ] GIVEN the public exports in the locked module list WHEN running the generator in `--check` mode THEN it exits 0 and `docs/api.md` is up-to-date
- [ ] GIVEN a missing docstring for an enforced exported function/class WHEN running the generator in `--check` mode THEN it exits with code 3 and reports the missing symbols

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Local CLI validation for README example correctness (must not error)
.venv/bin/frame-compare --help
.venv/bin/frame-compare run --help
.venv/bin/frame-compare doctor --help

# Quality gates (repo-wide)
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract derived views remain fresh (should be a no-op in this run)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check

# API docs generator checks
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings. `docs/api.md` matches generator output.

## Rollback

If this run introduces unacceptable churn or doc inaccuracies:

1. Revert touched files (`README.md`, `CHANGELOG.md`, docstring edits in `src/frame_compare/`, generator script,
and generator outputs).
2. Regenerate `docs/api.md` using `scripts/generate_api_docs.py` to restore determinism (or remove it if the run is reverted).

## Notes for Coding Agent

1. Keep runtime behavior unchanged: docstrings and docs tooling only.
2. The API docs generator MUST be AST-based (no importing `frame_compare.*`) to remain stable without VapourSynth.
3. Do not broaden scope beyond the locked module list and docstring enforcement rules.
4. Ensure `docs/api.md` is treated as generated (header + check mode must enforce freshness).

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Plan to Review

Read file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v3.md

## Context Files to Read (if needed)

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
4. Read file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v2.md

## Your Task

Validate the plan is implementation-ready using the 9-point checklist in the workflow SSOT.

## Output

Write file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md

If verdict is APPROVED, confirm:
- Verdict: APPROVED
- Implementation Agent Decision Points Remaining: NONE

If verdict is CHANGES REQUIRED, specify concrete edits for a `plan-v4.md` revision.
