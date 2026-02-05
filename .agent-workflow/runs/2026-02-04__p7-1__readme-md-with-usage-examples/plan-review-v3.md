---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v3
TARGET: Phase 7 → Item 7.1 (Bundled) — Documentation — Complete README.md with usage examples — Bundled 4 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v3.md
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md
---

# Plan Review Report: Phase 7.1 Documentation Bundle (README + Changelog + Docstrings + API Docs)

## Verdict: CHANGES_REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-05
**Plan Reference:** .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Exactly one checklist item (Phase 7 → 7.1) with bundled sub-tasks; out-of-scope is explicit. |
| 2 | Dependencies | PASS | Dev install + venv activation model is locked; AST-based generator avoids optional-dep imports. |
| 3 | File List | PASS | Files to create/modify are enumerated, including generator tests. |
| 4 | Contract Impact | PASS | Contract impact declared NO; `--check` gates preserved. |
| 5 | Types Complete | PASS | Generator entrypoint signature is explicitly locked: `def main(argv: Sequence[str] | None = None) -> int:` |
| 6 | Tests Complete | FAIL | Test fixture contents are underspecified (what fake `src/frame_compare/*` modules exist, and how they satisfy the locked 10-module list). `--check` behavior for missing output file is not defined, blocking exact assertions. |
| 7 | Verification Complete | PASS | Command Canon gates + CLI `--help` checks + generator `--check` are present with pass criteria. |
| 8 | Decision-Minimizing | FAIL | Remaining decisions are left to Coding: test fixture module set/contents; `--check` semantics when output file is missing; signature rendering format from AST; constant type string rules. |
| 9 | Determinism Defined | PASS | Module list/order is locked; stable ordering/no timestamps/LF endings are specified. |

## Additional Quality Checks

- Error Codes: OK (explicit exit code contract is specified).
- Failure Modes: Issue — `--check` behavior when output file is missing is not specified; this must be locked to avoid ad-hoc decisions.
- Derived Outputs: OK (`docs/api.md` treated as generated with required header + `--check`).
- Rollback Guidance: OK (explicit rollback steps included).
- SSOT Update Audit (if SSOT changed this loop): OK (N/A — no SSOT changes proposed).
- Plan Size & Churn Guardrail: Issue — `plan-v3.md` is 386 lines (> 350 hard budget). Must be reduced (token-bloat guardrail).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: 4

1. Exact `--check` behavior when the output file does not exist.
2. Exact test fixture module tree needed to satisfy the locked 10-module list.
3. Exact AST signature rendering format (how annotations/defaults are stringified).
4. Exact “best-effort type string” rules for constants.

## Concrete Edits Required (for `plan-v4.md`)

1. **Make generator test fixtures fully specified and compatible with the locked module list**
   - Section: `tests/test_generate_api_docs.py (CREATE)`
   - Problem: Plan requires a fake project root, but does not specify the required module tree under `src/` to satisfy the generator’s locked 10-module list.
   - Required Change:
     - Specify that tests create `tmp_path / "src" / "frame_compare"` plus subpackages for each locked module path:
       - `analysis/__init__.py`, `config/__init__.py`, `orchestration/__init__.py`, `render/__init__.py`, `services/__init__.py`, `utils/__init__.py`, `vs/__init__.py`, `vspreview/__init__.py`, and `runner.py`, plus `frame_compare/__init__.py`.
     - Specify minimal contents for “non-test” modules: a module docstring and `__all__ = []` (literal list) to keep the generator happy.
     - Specify the exact module(s) used for each assertion (ordering/constant handling/missing docstring) and the exact `__all__` plus definitions needed in those modules.

2. **Lock `--check` semantics when the output file is missing**
   - Section: `scripts/generate_api_docs.py (CREATE)` → CLI contract / exit-code contract
   - Problem: Current plan defines exit codes, but not the missing-output-file case for `--check` (cannot write tests without this).
   - Required Change (pick one and state it explicitly):
     - Recommended: If `--check` and output file does not exist, treat as drift and return exit code `2`, emitting a clear stderr message.

3. **Lock the AST signature rendering rule**
   - Section: `scripts/generate_api_docs.py (CREATE)` → Output format
   - Problem: “Signature (rendered from AST)” leaves formatting decisions to Coding and can cause unstable diffs.
   - Required Change:
     - Specify the deterministic formatting rule for function signatures, including how to stringify annotations/defaults (e.g., use `ast.unparse` for annotations and defaults; if unavailable/unparse fails, omit annotation/default for that parameter).
     - Specify whether the return annotation is included when present, and how varargs/kwargs are rendered.

4. **Lock the constant “type string” rule**
   - Section: `scripts/generate_api_docs.py (CREATE)` → constant output format
   - Problem: “Best-effort type string (literal type if trivially inferable)” is ambiguous.
   - Required Change:
     - Define exactly what is considered inferable (e.g., `ast.Constant` → `str/int/bool/None`, `ast.List` → `list`, `ast.Dict` → `dict`, else `unknown`), and the exact strings to emit.

5. **Reduce plan length to ≤ 350 lines (required guardrail)**
   - Section: Whole plan
   - Problem: `plan-v3.md` exceeds the 350-line budget.
   - Required Change:
     - Remove high-churn, non-essential verbosity (recommended: delete the long embedded `run(...)` Typer signature block and replace with a single reference to the CLI SSOT section + the already-listed `--help` verification commands).
     - Keep only the required locked decisions, file list, tests, acceptance criteria, and verification commands.

## Ready for Implementation

Return to the Planning Agent for `plan-v4.md` incorporating the concrete edits above. Do not proceed to Coding until verdict is APPROVED and decision points are NONE.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Precondition (verify before starting)

Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md`

Confirm:
- `## Verdict: APPROVED`
- `Implementation Agent Decision Points Remaining: NONE`

If either is not true, STOP and escalate back to the Human Orchestrator to re-run the Planning Agent for `plan-v4.md`.

## Files to Read

1. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v3.md`
2. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md`

## Output

Write file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/impl-v1.md`
