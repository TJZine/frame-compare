---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v3
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v3.md
---

# Plan Review Report: CLI Foundation

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | One slice; clear out-of-scope list. |
| 2 | Dependencies | PASS | No new module layering decisions; uses existing `frame_compare.errors`. |
| 3 | File List | PASS | Explicit file list (no ambiguous “related files”). |
| 4 | Contract Impact | PASS | Declares **NO**; no contract regen required. |
| 5 | Types Complete | FAIL | Spec Anchors are not verbatim headings; public signatures are not SSOT-exact (missing Typer `Option(...)` defaults) and omit existing public CLI functions (`main()`, `version()`). |
| 6 | Tests Complete | PASS | Test names + deterministic assertions + full flag list + concrete exception constructors are specified. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | Due to non-verbatim anchors and non-exact signatures, Coding Agent must infer required-vs-optional CLI params and which SSOT headings to treat as canonical. |
| 9 | Determinism Defined | PASS | Stub output contracts + JSON schema are explicit and testable. |

## Additional Quality Checks

- Error Codes: OK — plan now uses SSOT-correct error classes/constructors and maps via `get_exit_code()`.
- Failure Modes: OK for this slice (commands are stubs; error handling unit-tested).
- Derived Outputs: OK — no generated artifacts.
- Rollback Guidance: OK — includes “STOP and return to Planning”.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Spec anchor resolution: plan uses quoted “Section: …” strings (e.g., `"2.1 Command Structure"`) instead of verbatim markdown headings required by the workflow gates.
2. CLI signature exactness: `run(...)`/`doctor(...)` signatures omit Typer defaults (`typer.Option(...)`) which changes whether options are required; Coding Agent would need to choose the correct signature.
3. Whether to retain / modify existing public `main()` callback and `version()` command (plan does not specify them under public signatures).

## Concrete Edits Required (plan-v4; plan-only)

1. **Fix `## Spec Anchors (SSOT)` to be verbatim headings**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: entries are not exact headings (they include `Section:` and omit `###`/`##` prefixes).
   - Required Change: replace with exact heading strings as they appear in the SSOT files:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` → `### 2.1 Command Structure`, `### 2.2 Exit Codes`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` → `## 4. Exit Code Mapping`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md` → `### 4.1 CLI Layer`

2. **Make Public API signatures SSOT-exact (one-line, backticked)**
   - Section: `## Public API Signatures (spec-anchored)`
   - Problem: `run(...)`/`doctor(...)` omit Typer defaults, making CLI option requiredness ambiguous.
   - Required Change: copy the SSOT function signatures exactly from `cli-module.md` `### 2.1 Command Structure`, including `typer.Option(...)` default expressions (still as a single line per function). Include existing public CLI functions and explicitly mark unchanged:
     - `main() -> None` (unchanged)
     - `version() -> None` (unchanged)
     - `run(...typer.Option(...)...) -> None`
     - `wizard() -> None`
     - `doctor(json_output: bool = typer.Option(...)) -> None`
     - `preset_list() -> None`
     - `preset_apply(name: str) -> None`
     - `preset_save(name: str) -> None`
     - `handle_error(error: FrameCompareError) -> int`

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p1-4__cli-foundation

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v3.md
Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
