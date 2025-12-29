---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v2
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v2.md
---

# Plan Review Report: CLI Foundation

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (CLI foundation stubs) + explicit out-of-scope list. |
| 2 | Dependencies | PASS | Depends on existing errors/logging modules; no new dependency decisions. |
| 3 | File List | PASS | Explicit file list; no “and related files”. |
| 4 | Contract Impact | PASS | Declares **NO**; no contract regen required. |
| 5 | Types Complete | FAIL | Spec Anchors are not verbatim headings; required one-line public signatures are incomplete (`run(...)`) and `doctor` signature default does not match SSOT template. |
| 6 | Tests Complete | FAIL | `run --help` test asserts only 4 flags (can miss required SSOT options); exit-code tests use incorrect/mismatched exception constructors vs errors-module SSOT. |
| 7 | Verification Complete | PASS | Commands are explicit and include `lint-imports`. |
| 8 | Decision-Minimizing | FAIL | Remaining ambiguity stems from incorrect SSOT anchoring + mismatched exception instances; Coding Agent would need to choose correct constructors and which run options are required. |
| 9 | Determinism Defined | PASS | Stub output contracts are explicit; `doctor --json` schema is fixed and test parses JSON. |

## Additional Quality Checks

- Error Codes: Issue — plan references non-SSOT exceptions (`SlowpicsUploadError`, `InternalError(message=...)`) instead of errors-module SSOT (`SlowpicsError(details)`, `GenericInternalError(details)`).
- Failure Modes: OK for this slice (stubs exit 0); error-path behavior only exercised via `handle_error()` unit tests.
- Derived Outputs: OK — no generated artifacts.
- Rollback Guidance: OK — includes “STOP and return to Planning” note.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Which headings count as SSOT anchors (plan uses “Section: 2.1 …” instead of verbatim heading text required by `validate_spec_anchors.py`).
2. Full public signature coverage (especially `run(...)` and Typer `Option(...)` defaults) is missing, forcing inference.
3. Which `run` options are required (test only checks 4 options; SSOT lists many more).
4. Which concrete exception constructors to use in exit-code mapping tests (current table does not match errors-module SSOT signatures/classes).

## Concrete Edits Required (for plan-v3)

1. **Update SSOT spec first: reconcile CLI-layer error mapping reference**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md`
   - Under heading: `### 4.1 CLI Layer` change the exit-code mapping portion to use errors-module SSOT:
     - Import `get_exit_code` (and `FrameCompareError`) from `frame_compare.errors`
     - Replace the local `exit_codes = { ... }` mapping logic with `return int(get_exit_code(error))`
     - Keep the console output formatting (error message + hint) otherwise unchanged

2. **Fix Spec Anchors (SSOT) to be mechanically valid**
   - Section: `## Spec Anchors (SSOT)`
   - Required change: replace quoted “Section: …” strings with exact heading text (verbatim), e.g.:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` → `### 2.1 Command Structure`, `### 2.2 Exit Codes`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` → `## 4. Exit Code Mapping`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md` → `### 4.1 CLI Layer`
   - Hard gate: revised plan must pass `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v3.md`

3. **Add required one-line public signatures (no ellipses)**
   - Section: immediately after `## Spec Anchors (SSOT)`
   - Required change: add a list of one-line backticked signatures for every public function planned in `cli_entry.py`, matching SSOT templates (including `typer.Option(...)` defaults). Must include:
     - `main() -> None`
     - `version() -> None`
     - `run(root: Path = ..., config: Path | None = ..., input_dir: Path | None = ..., no_cache: bool = ..., from_cache_only: bool = ..., no_upload: bool = ..., tm_preset: str | None = ..., tm_target: int | None = ..., tm_curve: str | None = ..., frame_count: int | None = ..., seed: int | None = ..., overlay: str | None = ..., skip_analysis: bool = ..., skip_metadata: bool = ..., skip_dovi: bool = ..., json_output: bool = ..., no_color: bool = ..., write_config: bool = ..., diagnose_paths: bool = ..., quiet: bool = ..., verbose: bool = ...) -> None`
     - `wizard() -> None`
     - `doctor(json_output: bool = typer.Option(...)) -> None`
     - `preset_list() -> None`
     - `preset_apply(name: str) -> None`
     - `preset_save(name: str) -> None`
     - `handle_error(error: FrameCompareError) -> int`

4. **Make `run --help` test enforce the full SSOT option surface**
   - Section: `tests/cli/test_cli_commands.py`
   - Required change: `test_run_help_shows_all_options` must assert presence of every option flag defined in `cli-module.md` `### 2.1 Command Structure` (not a subset). The plan must list the exact expected flags (full list) so the Coding Agent does not choose.

5. **Fix exit-code tests to use SSOT-correct exception constructors**
   - Section: `tests/cli/test_exit_codes.py`
   - Required change: replace the current “Concrete Exception Instances” table with SSOT-matching constructors/classes, e.g.:
     - `ConfigNotFoundError(Path(\"/nonexistent/config.toml\"))`
     - `VapourSynthNotFoundError()`
     - `NoVideosFoundError(Path(\"/empty\"), patterns=[\"*.mkv\"])`
     - `FrameExtractionError(frame=0, clip=Path(\"/video.mkv\"))`
     - `SlowpicsError(\"error\")`
     - `GenericInternalError(\"test internal error\")`

## Ready for Implementation

Return to Planning Agent for revision after SSOT update. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p1-4__cli-foundation

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
- Under heading: "### 4.1 CLI Layer" add/change:
  - Replace the local `exit_codes = {...}` type-mapping block with `return int(get_exit_code(error))` and import `get_exit_code` from `frame_compare.errors`.
  - Keep the console output formatting (error message + hint) otherwise unchanged.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
