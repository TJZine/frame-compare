---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v4
TARGET: Phase 7 → Item 7.1 (Bundled) — Documentation — Complete README.md with usage examples — Bundled 4 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v4.md
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v4.md
---

# Plan Review Report: Phase 7.1 Documentation Bundle (README + Changelog + Docstrings + API Docs)

## Verdict: CHANGES_REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-05
**Plan Reference:** .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Exactly one checklist item (Phase 7 → 7.1) with bundled sub-tasks; out-of-scope is explicit. |
| 2 | Dependencies | PASS | Dev install + venv model is locked; AST-based generator avoids optional-dep imports. |
| 3 | File List | PASS | Files to create/modify are enumerated; plan is within size guardrail (327 lines). |
| 4 | Contract Impact | PASS | Contract impact declared NO; `--check` gates preserved. |
| 5 | Types Complete | PASS | Generator entrypoint signature is explicitly locked: `def main(argv: Sequence[str] | None = None) -> int:` |
| 6 | Tests Complete | FAIL | Tests specify assertions but do not lock (a) how tests load the script module from `scripts/`, (b) required generator CLI args to point at the tmp fixture (`--project-root` / `--output`), or (c) exact test function names. |
| 7 | Verification Complete | PASS | Command Canon gates + CLI `--help` checks + generator `--check` are present with pass criteria. |
| 8 | Decision-Minimizing | FAIL | Generator output format is not specified (constants/signatures/module sections), but tests assert a specific rendering (`constant (str)`), leaving decisions to Coding. |
| 9 | Determinism Defined | FAIL | Ordering/type-string rules are locked, but the full Markdown output format is not, risking unstable diffs and ambiguous test expectations. |

## Additional Quality Checks

- Error Codes: OK (exit codes and missing-output `--check` behavior are locked).
- Failure Modes: Issue — generator CLI surface and output formatting are not fully specified, making failure messages/output diffs nondeterministic.
- Derived Outputs: Issue — `docs/api.md` is declared generated, but the exact content/layout contract is not locked (hard to review and test deterministically).
- Rollback Guidance: OK.
- SSOT Update Audit (if SSOT changed this loop): OK (N/A — no SSOT changes proposed).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: 4

1. How tests load `scripts/generate_api_docs.py` as a module (import path vs `importlib.util.spec_from_file_location`).
2. The generator’s CLI args needed for tests to target `tmp_path` (`--project-root`, `--output`, and their defaults).
3. The exact Markdown output format (module headings, per-symbol formatting, constant rendering string) to match the test assertions.
4. Exact pytest test function names (to minimize churn and ensure reviewers can map assertions to cases).

## Concrete Edits Required (for `plan-v5.md`)

1. **Lock generator CLI surface (required for tests)**
   - Section: `scripts/generate_api_docs.py (CREATE)`
   - Problem: Plan references `--check` but does not specify how the generator is pointed at the tmp fixture project root/output path.
   - Required Change:
     - Add and document these flags (exact names required):
       - `--project-root <path>` (default: repo root)
       - `--output <path>` (default: `<project-root>/docs/api.md`)
       - `--check` (no writes; compare would-be output to existing output)
     - Specify interaction rules: `--check` compares against `--output`; missing output returns 2 with `MISSING:` message (already locked).

2. **Lock how tests import/load the generator module**
   - Section: `tests/test_generate_api_docs.py (CREATE)`
   - Problem: `scripts/` is not necessarily a Python package; “import the generator module itself” is ambiguous.
   - Required Change:
     - Require tests to load the script via `importlib.util.spec_from_file_location(...)` (matching the existing pattern in `tests/test_validate_traceability.py`), then call the loaded module’s `main([...])`.

3. **Lock the Markdown output format (must match test assertions)**
   - Section: `scripts/generate_api_docs.py (CREATE)` + `docs/api.md (GENERATED)`
   - Problem: Plan does not define the exact Markdown layout for modules/symbols/constants, but tests require a specific constant rendering.
   - Required Change:
     - Specify exact formatting for:
       - Module headings (e.g., `## frame_compare.utils`)
       - Per-symbol entries (e.g., `### a_func` followed by a fenced signature line or inline code)
       - Constant entries, including the exact string used (if tests assert `constant (str)`, lock that phrase and where it appears).
     - Specify how “first paragraph of docstring” is extracted and rendered.

4. **Provide exact pytest test function names**
   - Section: `tests/test_generate_api_docs.py (CREATE)`
   - Problem: 9-point checklist requires exact test names; current plan only lists scenarios.
   - Required Change:
     - Add a list of exact test function names (e.g., `test_ordering_is_case_insensitive`, etc.) mapped 1:1 to the 5 required scenarios.

## Ready for Implementation

Return to Planning Agent for `plan-v5.md` with the concrete edits above. Do not proceed to Coding until verdict is APPROVED and decision points are NONE.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Precondition (verify before starting)

Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v4.md`

Confirm:
- `## Verdict: APPROVED`
- `Implementation Agent Decision Points Remaining: NONE`

If either is not true, STOP and escalate back to the Human Orchestrator to re-run the Planning Agent for `plan-v5.md`.

## Files to Read

1. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v4.md`
2. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v4.md`

## Output

Write file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/impl-v1.md`
