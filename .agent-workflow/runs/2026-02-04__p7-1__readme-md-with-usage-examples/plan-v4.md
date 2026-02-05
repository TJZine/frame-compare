---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v4
TARGET: Phase 7 → Item 7.1 (Bundled) — Documentation — Complete README.md with usage examples — Bundled 4 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v3.md
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/01-project-charter.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - README.md
  - CHANGELOG.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v4.md
---

# Implementation Plan: Phase 7.1 Documentation Bundle (README + Changelog + Docstrings + API Docs)

## Changes Since plan-v3

Edits required by `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md` (2026-02-05):

1. Locked `--check` behavior when output file is missing.
2. Fully specified generator test fixture project tree and exact module contents (compatible with the locked 10-module list).
3. Locked AST signature rendering and constant “type string” rules.
4. Reduced plan size by removing non-essential verbosity and the long embedded `run(...)` signature block.

## Context

**Phase:** 7. **Target:** Phase 7 → Item 7.1 (Bundled) — Documentation (4 tasks).
README usage examples are copy/paste runnable, CHANGELOG documents the docs work, public APIs have Google-style
docstrings, and `docs/api.md` is generated deterministically with a `--check` gate.

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
- [ ] Generate deterministic Markdown API documentation and commit it (`docs/api.md`)

This plan does NOT cover:

- Phase 7.2 tasks (coverage/perf/cleanup beyond docstring edits needed to satisfy the generator gate)
- Contract edits under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`
- Any behavior changes to runtime code (docstrings/docs/tooling only)

## Locked Decisions (No Further Decision Points)

- README examples assume: `uv sync --group dev --frozen` → `source .venv/bin/activate` → `frame-compare ...`.
- Generator is AST-based (stdlib only) and MUST NOT import `frame_compare.*`.
- Docstrings enforced only for exported functions/classes; exported constants are exempt but must be documented.
- Generator entrypoint (tests call this exact function): `def main(argv: Sequence[str] | None = None) -> int:`.
  - `main(None)` parses `sys.argv[1:]`; `main([...])` parses the provided list; `__main__` raises `SystemExit(main())`.
- Exit codes: 0 success / 2 drift or missing output / 3 missing docstrings / 4 resolution error / 1 internal error.
- `--check` missing output: print `MISSING: <path>` to stderr and return 2.
- Signature rendering: use `ast.unparse` for annotations/defaults, include return when present; if unparse fails for
  a node, omit that annotation/default segment (do not fail generation).
- Constant type strings: `ast.Constant` → `str|int|float|bool|None`, `ast.List|ast.Tuple` → `list`, `ast.Dict` → `dict`,
  `ast.Set` → `set`, else `unknown`.

## Files to Create/Modify

### 1) `README.md` (MODIFY)

**Purpose:** Add a copy/paste runnable `## Usage` section aligned with the real CLI behavior.

**Exact structure edits:**

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

**Hard requirements:**

- README MUST NOT claim `wizard` supports `--root` (it does not).
- Every flag shown in README examples MUST exist in `frame-compare run --help`.

**Usage examples to include (verbatim):**

```bash
uv sync --group dev --frozen
source .venv/bin/activate

mkdir -p /path/to/workspace
cd /path/to/workspace
frame-compare wizard

frame-compare doctor
frame-compare doctor --json

frame-compare run --no-upload --skip-metadata
frame-compare run --skip-analysis --seed 123 --frame-count 24 --no-upload --skip-metadata
frame-compare run --tm-preset filmic --tm-curve spline --tm-target 203 --no-upload --skip-metadata
```

**Workspace layout must state (truthful to current behavior):**

- `frame-compare wizard` writes `./config/config.toml` in the current directory.
- `paths.input_dir` points to an existing directory with video files (wizard validates it exists).
- `screenshots/` and `generated/` directories are controlled by config and created as needed during execution.

**Links:**

- Config reference: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- API docs: `docs/api.md`

### 2) `CHANGELOG.md` (MODIFY)

Under `## Unreleased`, add one bullet mentioning:

- README usage examples for `wizard`/`doctor`/`run`
- Public API docstrings normalized (Google style)
- Generated API documentation at `docs/api.md` via `scripts/generate_api_docs.py`

### 3) `scripts/generate_api_docs.py` (CREATE)

**Purpose:** Deterministically generate `docs/api.md` from `__all__` exports and docstrings using AST (no imports).

**Locked module list/order (document in the script and implement exactly):**

1. `frame_compare` → `src/frame_compare/__init__.py`
2. `frame_compare.analysis` → `src/frame_compare/analysis/__init__.py`
3. `frame_compare.config` → `src/frame_compare/config/__init__.py`
4. `frame_compare.orchestration` → `src/frame_compare/orchestration/__init__.py`
5. `frame_compare.render` → `src/frame_compare/render/__init__.py`
6. `frame_compare.services` → `src/frame_compare/services/__init__.py`
7. `frame_compare.utils` → `src/frame_compare/utils/__init__.py`
8. `frame_compare.vs` → `src/frame_compare/vs/__init__.py`
9. `frame_compare.vspreview` → `src/frame_compare/vspreview/__init__.py`
10. `frame_compare.runner` → `src/frame_compare/runner.py`

**`__all__` rule:** Must be a literal list/tuple of string literals; otherwise exit code 4.

**Re-export resolution rule (AST-based):** Support:

- local `def` / `class`
- `from x import y as z` (follow to source module and resolve)
- simple alias assignments (`z = y`)

### 4) `docs/api.md` (CREATE, GENERATED)

Generated output; add a header indicating it is generated by `scripts/generate_api_docs.py` and must not be edited.

### 5) `tests/test_generate_api_docs.py` (CREATE)

**Purpose:** Unit tests for the generator (no external deps).

**Fixture project tree (tests must create this exactly under `tmp_path`):**

Create directories/files:

- `src/frame_compare/__init__.py`
- `src/frame_compare/analysis/__init__.py`
- `src/frame_compare/config/__init__.py`
- `src/frame_compare/orchestration/__init__.py`
- `src/frame_compare/render/__init__.py`
- `src/frame_compare/services/__init__.py`
- `src/frame_compare/utils/__init__.py`
- `src/frame_compare/vs/__init__.py`
- `src/frame_compare/vspreview/__init__.py`
- `src/frame_compare/runner.py`

**Minimal contents for “non-focus” modules (all fixture modules except `utils` and `services`):**

- Module docstring present.
- `__all__ = []`

**Focus module contents (utils) to drive assertions:**

`src/frame_compare/utils/__init__.py` MUST contain:

- module docstring
- `__all__ = ["a_func", "BClass", "CONST_STR"]`
- `def a_func(x: int) -> int:` with a docstring and a simple body
- `class BClass:` with a docstring and a simple method/body
- `CONST_STR = "hello"` (no docstring)

**Missing docstring module contents (services) to drive exit code 3:**

`src/frame_compare/services/__init__.py` MUST contain:

- module docstring
- `__all__ = ["missing_func"]`
- `def missing_func() -> None:` with NO docstring

**Output drift setup to drive exit code 2:**

- Write an initial output file at `<tmp_root>/docs/api.md` with content that will not match generated output.
- Run generator with `--check` and assert exit code 2.

**Missing output file setup to drive exit code 2:**

- Ensure `<tmp_root>/docs/api.md` does not exist.
- Run generator with `--check` and assert exit code 2 and stderr contains `MISSING:`.

**Required tests (must be implemented):**

1. Deterministic ordering: symbols for utils appear in case-insensitive order: `a_func`, `BClass`, `CONST_STR`.
2. Constant handling: `CONST_STR` is documented as `constant (str)` and does not trigger docstring failure.
3. Missing docstrings: `--check` fails with exit code 3 and names `missing_func`.
4. Drift detection: `--check` fails with exit code 2 when output differs.
5. Missing output: `--check` fails with exit code 2 when output file is absent.

### 6) Public API docstrings (MODIFY: `src/frame_compare/**/*.py`)

**Purpose:** Ensure docstrings exist (Google style) for exported functions/classes in the locked module list and their
direct re-export targets.

Implementation rule (decision-minimizing):

- Implement the generator first.
- Run `scripts/generate_api_docs.py --check` to identify missing docstrings (exit code 3).
- Add docstrings only for the specific missing exported functions/classes reported.
- Do not change runtime logic while editing docstrings.

## Functions to implement (spec-anchored)

This docs/tooling run does not implement new CLI behavior. These spec-anchored signatures are included to satisfy
the Spec Anchors validator and to align README command examples with the CLI SSOT.

- `wizard() -> None`
- `doctor(json_output: bool = typer.Option(False, \"--json\")) -> None`

## Acceptance Criteria

- [ ] README contains `## Usage` with working examples for `wizard`, `doctor`, and `run` (no nonexistent flags)
- [ ] `CHANGELOG.md` Unreleased documents README/docstrings/API docs changes
- [ ] `docs/api.md` is generated and `scripts/generate_api_docs.py --check` passes
- [ ] Generator tests pass and cover: ordering, constants, missing docstrings, drift, missing output

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# CLI help validation for README example correctness
.venv/bin/frame-compare --help
.venv/bin/frame-compare run --help
.venv/bin/frame-compare doctor --help

# Quality gates
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract derived views remain fresh (should be no-op in this run)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check

# API docs generator checks
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings. `docs/api.md` matches generator output.

## Rollback

1. Revert touched files (`README.md`, `CHANGELOG.md`, docstring-only edits under `src/frame_compare/`,
`scripts/generate_api_docs.py`, `docs/api.md`, `tests/test_generate_api_docs.py`).
2. Re-run generator to confirm determinism after rollback (or remove `docs/api.md` if reverting the generator entirely).

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Plan to Review

Read file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v4.md

## Context Files to Read (if needed)

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
4. Read file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md

## Your Task

Validate the plan is implementation-ready using the 9-point checklist in the workflow SSOT.

## Output

Write file: .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v4.md

If verdict is APPROVED, confirm:
- Verdict: APPROVED
- Implementation Agent Decision Points Remaining: NONE

If verdict is CHANGES REQUIRED, specify concrete edits for a `plan-v5.md` revision.
