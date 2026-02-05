---
RUN_ID: 2026-02-04__p7-1__readme-md-with-usage-examples
VERSION: v2
TARGET: Phase 7 → Item 7.1 (Bundled) — Documentation — Complete README.md with usage examples — Bundled 4 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v2.md
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v2.md
---

# Plan Review Report: Phase 7.1 Documentation Bundle (README + Changelog + Docstrings + API Docs)

## Verdict: CHANGES_REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-05
**Plan Reference:** .agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Exactly one checklist item (Phase 7 → 7.1) with bundled sub-tasks; out-of-scope is clear. |
| 2 | Dependencies | PASS | CLI invocation model and “no imports” AST strategy are locked; external deps avoided for docs generator/tests. |
| 3 | File List | PASS | Files to create/modify are enumerated, including a generator test file. |
| 4 | Contract Impact | PASS | Contract impact declared NO; appropriate `--check` gates retained. |
| 5 | Types Complete | FAIL | Generator entrypoint signature is not explicitly specified (one-line, backticked), and the plan includes placeholder signatures (`run(...) -> None`) for unrelated CLI callables. |
| 6 | Tests Complete | FAIL | Test execution path is still ambiguous due to “call `main(argv=...)` (or equivalent CLI parsing entrypoint)” without locking the callable name/signature. |
| 7 | Verification Complete | PASS | Command Canon gates + explicit CLI help checks + generator `--check` are present with pass criteria. |
| 8 | Decision-Minimizing | FAIL | Remaining ambiguity around the generator’s callable interface and the placeholder “Functions to implement” section leaves decisions to Coding. |
| 9 | Determinism Defined | PASS | Module list/order locked; ordering and no-timestamp rules present; `--check` exit code contract defined. |

## Additional Quality Checks

- Error Codes: OK (explicit exit code contract is specified).
- Failure Modes: OK (AST-only; literal `__all__` requirement + exit code 4 for resolution failures).
- Derived Outputs: OK (`docs/api.md` is treated as generated with a required header and `--check` workflow).
- Rollback Guidance: OK (explicit rollback steps included).
- SSOT Update Audit (if SSOT changed this loop): OK (N/A — no SSOT changes proposed).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: 2

1. Exact generator callable interface to be used by tests and CLI (`main` signature and argv parsing contract).
2. Whether the “Functions to implement (spec-anchored)” section is normative (it contains placeholders) or should be removed to avoid implying code changes.

## Concrete Edits Required (for `plan-v3.md`)

1. **Lock generator entrypoint signature + test invocation**
   - Section: `scripts/generate_api_docs.py (CREATE)` and `tests/test_generate_api_docs.py (CREATE)`
   - Problem: Plan requires calling `main(argv=...)` but does not lock the required signature and still permits “equivalent entrypoint”.
   - Required Change:
     - Add an explicit one-line signature (backticked) in the plan, e.g. `def main(argv: Sequence[str] | None = None) -> int:`
     - Remove “or equivalent” language; require tests to call this exact function.
     - Specify that `main(None)` reads CLI args from `sys.argv[1:]` and returns the exit codes defined in the plan.

2. **Remove or correct the placeholder “Functions to implement (spec-anchored)” section**
   - Section: `## Functions to implement (spec-anchored)`
   - Problem: This run is docs/tooling-only; the listed CLI callables are not created/modified here and the signatures are placeholders (`run(...)`), which violates “Types Complete” and introduces drift risk.
   - Required Change (choose one, but specify explicitly in the plan):
     - Preferred: delete this section entirely and replace it with a short “CLI surfaces to validate” note pointing only to the `--help` commands already listed under Verification, OR
     - If you keep it: replace placeholders with the exact one-line signatures from the CLI SSOT (backticked) and explicitly state these are *not* being modified, only referenced for README alignment.

## Ready for Implementation

Return to the Planning Agent for `plan-v3.md` with the concrete edits above. Do not proceed to Coding until verdict is APPROVED and decision points are NONE.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-02-04__p7-1__readme-md-with-usage-examples

## Precondition (verify before starting)

Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v2.md`

Confirm:
- `## Verdict: APPROVED`
- `Implementation Agent Decision Points Remaining: NONE`

If either is not true, STOP and escalate back to the Human Orchestrator to re-run the Planning Agent for `plan-v3.md`.

## Files to Read

1. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v2.md`
2. Read file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-review-v2.md`

## Output

Write file: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/impl-v1.md`
