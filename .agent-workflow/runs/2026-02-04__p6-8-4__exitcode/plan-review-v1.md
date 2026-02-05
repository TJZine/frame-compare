---
RUN_ID: 2026-02-04__p6-8-4__exitcode
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Exit codes (`ExitCode`, error mapping, CLI integration tests)
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-review-v1.md
---

# Plan Review Report: CLI Exit Codes (`ExitCode` + Error→Exit Mapping + Tests)

## Verdict: APPROVED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-04
**Plan Reference:** `.agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Stays within checklist item 6.8 (exit codes + mapping + CLI tests); explicit out-of-scope listed. |
| 2 | Dependencies | PASS | Uses existing `frame_compare.errors` + `cli_entry` patterns; no new external deps. |
| 3 | File List | PASS | Target files exist and are the minimal set to remove magic numbers + enforce mapping. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”; mapping conforms to `contracts/error_codes.yaml`. |
| 5 | Types Complete | PASS | `ExitCode`, `get_exit_code(...)`, and `handle_error(...)` are explicitly specified and spec-anchored. |
| 6 | Tests Complete | PASS | Adds missing coverage for generic `FrameCompareError` mapping and CLI JSON-mode exit codes. |
| 7 | Verification Complete | PASS | Commands listed for pyright/ruff/pytest + import-linter; scoped to touched files. |
| 8 | Decision-Minimizing | PASS | Mapping rules, CLI exit sites, and JSON constraints are explicit; no design choices left. |
| 9 | Determinism Defined | PASS | Deterministic mapping; JSON output stability constraints called out (sort keys, stdout purity). |

## Additional Quality Checks

- Error Codes: OK (explicitly grounded in `contracts/error_codes.yaml` + `errors-module.md` exit mapping)
- Failure Modes: OK (covers Ctrl+C, unsuccessful run result, and error-category mapping)
- Derived Outputs: OK (no contract/spec edits; no regeneration required)
- Rollback Guidance: OK (changes isolated to exit-code mapping + CLI behavior + tests; safe revert)
- SSOT Update Audit (if SSOT changed this loop): OK (no SSOT edits in this loop)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NONE

## Ready for Implementation

All checklist items pass. Coding Agent may proceed.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md`

## RUN_ID
2026-02-04__p6-8-4__exitcode

## Target
Phase 6 → Item 6.8 (Bundled) — CLI Commands — Implement `ExitCode` enum per spec (and error→exit-code mapping) + CLI integration tests

## Input Artifacts
- Read file: `.agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md`
- Read file: `.agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-review-v1.md`

## Your Task
Implement the plan exactly (no scope changes). Write code + tests, run the verification commands from the plan, and produce an Implementation Report.

## Output
- Write file: `.agent-workflow/runs/2026-02-04__p6-8-4__exitcode/impl-v1.md`
