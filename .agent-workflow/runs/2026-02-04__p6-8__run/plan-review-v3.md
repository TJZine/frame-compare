---
RUN_ID: 2026-02-04__p6-8__run
VERSION: v3
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v3.md
---

# Plan Review Report: Phase 6.8 — CLI `run` Command (Bundled)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-04
**Plan Reference:** `.agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Bundled slice matches the three requested sub-items; out-of-scope is explicit. |
| 2 | Dependencies | PASS | Correctly references runner/coordinator and the relevant SSOT sections. |
| 3 | File List | PASS | Includes required code + tests + contract touch. |
| 4 | Contract Impact | PASS | “Contracts touched: YES” with regen/freshness/traceability gates is complete. |
| 5 | Types Complete | PASS | New/changed call surfaces are enumerated; `discover_inputs(...)` signature is explicit and ruff-safe. |
| 6 | Tests Complete | FAIL | Plan omits tests that lock in critical CLI→RunRequest field mapping (esp. name mismatches) and leaves orchestration override dict keying ambiguous/unverified. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit; spec-anchor STOP gate passes for `plan-v3.md`. |
| 8 | Decision-Minimizing | FAIL | Leaves a key implementation decision: exact `cli_args` dict keys passed to `apply_cli_overrides(...)` (must match override-map keys, not RunRequest field names). |
| 9 | Determinism Defined | PASS | Stable ordering and error code requirements are explicit and tested. |

## Additional Quality Checks

- Error Codes: OK (exit-code mapping aligns with `api-design.md` and existing `handle_error(...)` tests).
- Failure Modes: OK (empty inputs -> `NoVideosFoundError(FC-3001)`; unsuccessful run -> exit code 5).
- Derived Outputs: OK (derived outputs listed; regen/check commands included).
- Rollback Guidance: OK (localized edits; standard revert).
- SSOT Update Audit (if SSOT changed this loop): OK (verified spec docs now include `force_interactive_alignment` and the required `use_vspreview` implication).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

Remaining decision points to remove in `plan-v4.md`:
1. Exact override-dict key mapping inside `execute_run(...)` (must use override-map keys: `tm_target`, `overlay`, etc., not RunRequest field names like `tm_target_nits`, `overlay_mode`).
2. Concrete tests that assert the CLI constructs `RunRequest` correctly for name-mismatched fields (`--tm-target`→`tm_target_nits`, `--overlay`→`overlay_mode`) and the new `--force-interactive-alignment` flag.

## Concrete Edits Required (for `plan-v4.md`)

1. **Make orchestration override dict keying explicit (remove ambiguity)**
   - Section: `src/frame_compare/orchestration/coordinator.py`
   - Problem: The plan says “build `cli_args` dict from `RunRequest` values (`tm_target_nits`, `overlay_mode`, ...)” but does not specify the *dict keys*. `apply_cli_overrides(...)` consumes keys matching `CLI_OVERRIDE_MAP` / §4.4.5 (e.g. `tm_target`, `overlay`), so using RunRequest field names would silently drop overrides.
   - Required Change: Add a normative snippet (or equivalent explicit mapping) to the plan such as:
     - `cli_args = {`
       - `"tm_preset": request.tm_preset,`
       - `"tm_target": request.tm_target_nits,`
       - `"tm_curve": request.tm_curve,`
       - `"frame_count": request.frame_count,`
       - `"seed": request.seed,`
       - `"overlay": request.overlay_mode,`
       - `"no_upload": request.no_upload,`
       - `"force_interactive_alignment": request.force_interactive_alignment,`
     - `}`
     - and then `config = apply_cli_overrides(preflight.config, cli_args=cli_args)`.

2. **Add/extend orchestration test assertions to cover the name-mismatch mappings**
   - Section: `tests/orchestration/test_execute_run.py`
   - Problem: The planned test only asserts `tm_preset` and `force_interactive_alignment` behavior; it does not assert that `tm_target_nits` and `overlay_mode` are mapped via the correct override keys, nor that `no_upload` inversion is realized in the final `RunContext.config`.
   - Required Change: Update the planned test (or add a second one with an explicit name) so it also asserts at least:
     - `config.color.target_nits == <value from request.tm_target_nits>`
     - `config.screenshots.overlay_mode == <value from request.overlay_mode>`
     - `config.slowpics.auto_upload is False` when `request.no_upload is True`
     - (optional but recommended) `config.analysis.random_seed == <value from request.seed>`

3. **Add a CLI test that captures the constructed `RunRequest` (locks in CLI→request mapping)**
   - Section: `tests/cli/test_cli_commands.py`
   - Problem: The plan replaces the stub test with exit-code-only tests. That does not validate the core “run command implementation” requirement: correct construction of `RunRequest` from CLI flags, including name mismatches and the new flag.
   - Required Change: Add a concrete test (exact name + key assertions), e.g.:
     - `test_run_builds_run_request_from_cli_args`
       - Monkeypatch `frame_compare.cli_entry.runner.run` to capture the incoming `RunRequest` and return `RunResult(success=True)`.
       - Invoke `frame-compare run` with `--tm-target`, `--overlay`, and `--force-interactive-alignment`.
       - Assert captured request fields:
         - `request.tm_target_nits == <cli tm-target value>`
         - `request.overlay_mode == <cli overlay value>`
         - `request.force_interactive_alignment is True`

## Ready for Implementation

Return to Planning Agent for `plan-v4.md` addressing the concrete edits above. Coding must not proceed until the revised plan is APPROVED and decision points are NONE.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8__run

## Files to Read
1. Read file: `.agent-workflow/runs/2026-02-04__p6-8__run/plan-v3.md`
2. Read file: `.agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v3.md`
3. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` (§4.4.5)
4. Read file: `src/frame_compare/config/overrides.py` (current `CLI_OVERRIDE_MAP` keys)

## Your Task
Revise the plan to remove all decision points called out in `plan-review-v3.md`, producing an implementation-ready `plan-v4.md` with:
- An explicit `cli_args` dict key mapping for `apply_cli_overrides(...)` (handles `tm_target_nits`/`overlay_mode` field-name mismatches)
- Tests that directly assert the CLI builds the correct `RunRequest` for `--tm-target`, `--overlay`, and `--force-interactive-alignment`
- Orchestration test assertions that cover the name-mismatch override mappings (at least `target_nits` + `overlay_mode`, and `no_upload` inversion)

## Output
Write file: `.agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md`

## Note
After plan approval, the Coding Agent output for this run remains: `.agent-workflow/runs/2026-02-04__p6-8__run/impl-v1.md`
