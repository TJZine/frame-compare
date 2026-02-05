---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v1
TARGET: Phase 7 → Item 7.1 (Bundled) — Documentation — Complete README.md with usage examples — Bundled 4 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v1.md
---

# Plan Review Report: Phase 7.1 Documentation Bundle (README + Changelog + Docstrings + API Docs)

## Verdict: CHANGES_REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-05
**Plan Reference:** .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single checklist item (Phase 7 → 7.1) with explicitly bundled sub-tasks; out-of-scope stated. |
| 2 | Dependencies | FAIL | Missing explicit, runnable CLI invocation to validate README examples (e.g. `.venv/bin/frame-compare` vs `uv run frame-compare`). Also missing constraints for doc generation regarding optional deps/import-time side effects. |
| 3 | File List | FAIL | New code (`scripts/generate_api_docs.py`) is planned but no test file(s) are planned; docstrings scope references broad globs without an explicit “touch list” strategy for limiting churn. |
| 4 | Contract Impact | PASS | Contract impact declared NO; appropriate “--check” commands included as no-ops. |
| 5 | Types Complete | FAIL | Plan introduces new generator script but does not specify its public entrypoint signature(s) (one-line, backticked) or expected return codes. |
| 6 | Tests Complete | FAIL | No test plan for the generator script; relying solely on `--check` against a committed output can allow “consistently wrong” output to pass. |
| 7 | Verification Complete | PASS | Command Canon gates listed, plus `scripts/generate_api_docs.py --check`. |
| 8 | Decision-Minimizing | FAIL | Multiple key decisions are deferred (“as appropriate” flags for README; module list/order for docs generator; how to handle constants in `__all__`; what constitutes “missing docstring”). |
| 9 | Determinism Defined | PASS | Deterministic ordering and “no timestamps” requirements are present; needs tighter definition of module list to fully eliminate drift. |

## Additional Quality Checks

- Error Codes: Issue — generator script exit codes are not specified (success, diff detected, missing docstrings, import failures).
- Failure Modes: Issue — plan does not define behavior when `__all__` exports non-docstringable values (e.g. `DEFAULT_CONFIG_TOML`, `CLI_OVERRIDE_MAP`) or when a module import fails due to optional deps.
- Derived Outputs: Issue — `docs/api.md` is a derived artifact; plan should require a “generated, do not edit” header and define the exact update/check workflow (including line endings) as a must-follow rule.
- Rollback Guidance: Issue — missing. Even for docs-only runs, include a one-line rollback (revert changed files; regenerate `docs/api.md` from script).
- SSOT Update Audit (if SSOT changed this loop): OK (N/A — no SSOT changes proposed).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: 5

1. Exact CLI invocation form to verify README examples (`frame-compare` vs `.venv/bin/frame-compare` vs `uv run frame-compare`) and to ensure examples are copy/paste runnable.
2. Exact module list (and order) for API docs generation.
3. Exact rule for which `__all__` exports must have docstrings (functions/classes only vs also module-level constants), and how to represent/document constants in `docs/api.md`.
4. Exact generator failure/exit-code contract for: missing docstrings, import errors, output drift in `--check`.
5. Exact set of “common flags” shown in README `run` examples (must map to real `--help` output; no “as appropriate”).

## Concrete Edits Required (for `plan-v2.md`)

1. **Make CLI usage examples fully deterministic**
   - Section: `README.md (MODIFY)` → “Hard requirement” + example commands
   - Problem: Examples assume `frame-compare` is directly runnable without specifying the repo/dev invocation path.
   - Required Change:
     - Specify the canonical invocation for all examples (choose one):
       - `.venv/bin/frame-compare ...` (requires `.venv` bootstrapped via `uv sync --group dev --frozen`), OR
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync frame-compare ...`
     - Replace all README command snippets in the plan with that chosen form.

2. **Define the API docs generator contract precisely (signatures + exit codes)**
   - Section: `scripts/generate_api_docs.py (CREATE)`
   - Problem: Script behavior is described but its callable interface and exit-code semantics are not.
   - Required Change:
     - Add explicit signatures (one-line, backticked), e.g. `def main(argv: Sequence[str] | None = None) -> int:`
     - Specify exit codes for each failure mode (missing docstrings, import failure, diff detected in `--check`).

3. **Remove ambiguity around exported constants and docstring completeness**
   - Section: Public API docstrings + generator “Hard failure mode”
   - Problem: Many `__all__` exports are constants/mappings that cannot carry docstrings; current “missing docstring” rule is not implementable as written.
   - Required Change:
     - Define which symbol kinds are enforced (recommended: functions + classes + enums + modules; constants are documented with type/value summary and are exempt from docstring-missing failure).
     - Define how constants appear in `docs/api.md` (recommended: `NAME: <type>` plus one-line module-context note).

4. **Lock the module list and ordering for API docs generation**
   - Section: `scripts/generate_api_docs.py (CREATE)` → “Deterministic ordering”
   - Problem: Plan states “explicit list in the script” but does not provide the list; this is a decision left to Coding.
   - Required Change:
     - Add a concrete ordered list of module import paths to the plan (the exact list the script must use).
     - Confirm each module can be imported in the default unit-test environment without requiring VapourSynth/FFmpeg.

5. **Add minimal tests for the generator script**
   - Section: Add a new `Tests` section under plan + update “Files to Create/Modify”
   - Problem: No tests are planned for new generator logic; `--check` vs committed output can be self-consistent even when wrong.
   - Required Change:
     - Add a focused unit test file (exact path specified) that asserts:
       - Deterministic output ordering for a small fixture module
       - `--check` behavior on mismatched output
       - Missing-docstring detection behavior (per the clarified symbol-kind rules)
     - Tests must not require external binaries or network.

6. **Add rollback guidance**
   - Section: New `## Rollback` section near Acceptance/Verification
   - Problem: Missing required operational guidance.
   - Required Change:
     - State rollback as: revert touched docs/docstrings + delete/regenerate `docs/api.md` via the generator to restore determinism.

## Ready for Implementation

Return to Planning Agent for `plan-v2.md` incorporating the concrete edits above. Do not proceed to Coding until the plan review verdict is APPROVED and decision points are NONE.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Precondition (verify before starting)

Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v1.md`

Confirm:
- `## Verdict: APPROVED`
- `Implementation Agent Decision Points Remaining: NONE`

If either is not true, STOP and escalate back to the Human Orchestrator to re-run the Planning Agent for `plan-v2.md`.

## Files to Read

1. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v1.md`
2. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v1.md`

## Output

Write file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/impl-v1.md`
