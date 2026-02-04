---
RUN_ID: 2026-02-04__p6-8__run
VERSION: v2
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v2.md
---

# Plan Review Report: Phase 6.8 — CLI `run` Command (Bundled)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-04
**Plan Reference:** `.agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Bundled slice matches the three requested sub-items and has a clear out-of-scope section. |
| 2 | Dependencies | PASS | Correctly references existing `runner.run(...)` and `coordinator.execute_run(...)` and the relevant SSOT sections. |
| 3 | File List | FAIL | Plan is missing SSOT/spec doc updates required to prevent drift (see Concrete Edits #1). |
| 4 | Contract Impact | PASS | “Contracts touched: YES” is explicit and includes regeneration + freshness + traceability gates. |
| 5 | Types Complete | PASS | Public signatures are listed for `cli_entry.run(...)`, `coordinator.execute_run(...)`, `preflight.discover_inputs(...)`, and `config.overrides.apply_cli_overrides(...)`. |
| 6 | Tests Complete | FAIL | New tests are described but not fully specified (exact test names/assertions), and `discover_inputs(...)` empty-directory error behavior is not directly tested (see Concrete Edits #3–#4). |
| 7 | Verification Complete | PASS | Commands are explicit and include pass criteria; spec-anchor STOP gate was run and passed for `plan-v2.md`. |
| 8 | Decision-Minimizing | FAIL | Leaves key implementation choices to the Coding Agent (ruff-safe default arg strategy for `discover_inputs`, plus unspecified new test names). |
| 9 | Determinism Defined | PASS | Stable, case-insensitive ordering for input discovery is explicit and acceptance criteria include deterministic behavior. |

## Additional Quality Checks

- Error Codes: OK (CLI error mapping and exit codes are specified and align with CLI/orchestration specs).
- Failure Modes: OK (empty inputs mapped to `NoVideosFoundError(FC-3001)`; unsuccessful run mapped to exit code 5).
- Derived Outputs: OK (contract-derived outputs are identified; regen/check commands included).
- Rollback Guidance: OK (localized changes; revert run-scope files).
- SSOT Update Audit (if SSOT changed this loop): Issue (contract change is planned; spec docs must be updated in the same run to avoid drift — see Concrete Edits #1).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

Remaining decision points to remove in `plan-v3.md`:
1. Which SSOT docs are updated in this run to keep `cli-module.md` / `config-module.md` consistent with the contract + implementation (currently implied but not planned).
2. Ruff-safe strategy for `discover_inputs(...)` default patterns (avoid mutable-default `B006` while matching SSOT behavior).
3. Exact test function names and core assertions for the new/updated tests described in the plan.

## Concrete Edits Required (for `plan-v3.md`)

1. **Add SSOT/spec doc updates to prevent drift**
   - Section: `## Files to Create/Modify` + `## Spec Anchors (SSOT)`
   - Problem: The plan changes public behavior/contracts (adds `--force-interactive-alignment`, adds a new request field, changes override-key naming), but does not plan the corresponding SSOT spec updates required by the workflow’s “no silent drift” rule.
   - Required Change:
     - Add **[MODIFY] `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`**:
       - In §3.1 `RunRequest`, add `force_interactive_alignment: bool = False` and note it is used to apply §4.4.5’s implied `audio_alignment.use_vspreview = True`.
     - Add **[MODIFY] `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`**:
       - In §4.1 `CLI_OVERRIDE_MAP`, replace `random_seed` with `seed` (align with `--seed` and `RunRequest.seed`), and add `force_interactive_alignment` → `audio_alignment.force_interactive` with the required implication on `audio_alignment.use_vspreview`.

2. **Make `discover_inputs(...)` plan ruff-safe and unambiguous**
   - Section: `src/frame_compare/orchestration/preflight.py`
   - Problem: The plan currently specifies a mutable default list for `patterns`, which will trip Ruff `B006` unless a suppression is chosen (decision point).
   - Required Change (pick one and make it normative):
     - Preferred: `def discover_inputs(input_dir: Path, patterns: list[str] | None = None) -> list[Path]:` and set `patterns = _VIDEO_PATTERNS` when `None` (ensuring the error includes the effective patterns list), OR
     - If keeping the literal list default, explicitly require a targeted Ruff suppression on that line (and justify why it’s safe).

3. **Add direct unit coverage for empty discovery error**
   - Section: `tests/orchestration/test_preflight.py`
   - Problem: Acceptance criteria require `discover_inputs(...)` to raise `NoVideosFoundError(FC-3001)` when empty and preserve the patterns list, but the plan does not require a direct unit test for that function’s error case.
   - Required Change:
     - Add a concrete test (exact name + assertions), e.g.:
       - `def test_discover_inputs_empty_raises_no_videos_found_error_preserves_patterns(...) -> None:`
       - Assert `error.code == "FC-3001"`, `error.path == input_dir.resolve()`, and `error.patterns == expected_patterns`.

4. **Specify exact new/updated test function names and key assertions**
   - Section: `tests/config/test_overrides.py` and `tests/orchestration/test_execute_run.py`
   - Problem: The plan describes new tests but does not pin exact test names and the minimum required assertions, leaving decisions to the Coding Agent.
   - Required Change:
     - Provide exact test names for each new test and list the key asserts (including the `force_interactive_alignment=True` implied `use_vspreview=True` assertion).

## Ready for Implementation

Return to Planning Agent for `plan-v3.md` addressing the concrete edits above. Coding must not proceed until the revised plan is APPROVED and decision points are NONE.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8__run

## Files to Read
1. Read file: `.agent-workflow/runs/2026-02-04__p6-8__run/plan-v2.md`
2. Read file: `.agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v2.md`
3. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` (CLI `run` + Runner types)
4. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` (§§4.4.3, 4.4.5, 4.4.6)
5. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md` (§4.1 Override Mapping)
6. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`
7. Read file: `pyproject.toml` (`[tool.ruff.lint]` for `B006`)

## Your Task
Revise the plan to remove all decision points called out in `plan-review-v2.md`, producing an implementation-ready `plan-v3.md` with complete file list (including SSOT spec doc updates), ruff-safe discovery rules, and fully specified tests (exact names + key assertions).

## Output
Write file: `.agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md`

## Note
After plan approval, the Coding Agent output for this run remains: `.agent-workflow/runs/2026-02-04__p6-8__run/impl-v1.md`
