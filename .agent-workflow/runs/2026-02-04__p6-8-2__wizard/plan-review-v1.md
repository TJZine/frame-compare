---
RUN_ID: 2026-02-04__p6-8-2__wizard
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — `wizard` + `doctor`
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/doctor_report_schema.json
  - docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/business-requirements.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-review-v1.md
---

# Plan Review Report: Complete CLI `wizard` + `doctor` Commands

## Verdict: APPROVED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-04
**Plan Reference:** .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md

Plan is implementation-ready and covers both bundled tasks (`wizard`, `doctor`) with deterministic tests and gate commands.

To eliminate any remaining ambiguity for the Coding Agent, this Plan Review report adds the following **binding clarifications** (no SSOT changes required):

1. **Wizard root + paths**
   - Treat “workspace root” as the current working directory at invocation time (`Path(".")`).
   - Write config to exactly `config/config.toml` (relative to CWD), creating `config/` if missing.
   - Validate `input_dir` by checking existence of `Path(".") / <input_dir>` when a relative path is entered; absolute paths are validated as-is.

2. **Wizard invalid input handling (re-prompt)**
   - If an entered `input_dir` does not exist or is not a directory: print a short error and re-prompt until valid or interrupted.

3. **Wizard defaults source (test hermeticity)**
   - Use `frame_compare.config.get_default_config()` (or equivalent “defaults only” source) to derive prompt defaults so unit tests are not affected by environment variables or any existing TOML config.

4. **Wizard output shape**
   - Write a minimal TOML containing only the fields prompted in the plan:
     - `[paths] input_dir`
     - `[slowpics] auto_upload`, `visibility`, `delete_after_upload`
     - `[tmdb] api_key`
   - All other sections may be omitted (defaults apply via schema).

5. **Doctor JSON field mapping**
   - For each `(DoctorCheck, CheckResult)` in `DoctorReport.checks`:
     - `id` = `check.name`
     - `category` = `check.category`
     - `status` = `"pass"` if `result.passed` else `"fail"` (no `"skip"` emitted by the CLI layer for current deterministic checks)
     - `message` = `result.message`
     - `install_hint` = `result.hint` (may be null/omitted)
     - `details` = `result.details` (may be omitted if empty)
   - Top-level:
     - `doctor.baseline_version` = `"R73"`
     - `success` = `len(report.critical_failures) == 0`
   - Deterministic JSON serialization: use `json.dumps(..., sort_keys=True, separators=(",", ":"))`.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Bundled tasks match target; clear out-of-scope list. |
| 2 | Dependencies | PASS | Depends on existing `frame_compare.config` + `frame_compare.orchestration.run_doctor`. |
| 3 | File List | PASS | Only `src/frame_compare/cli_entry.py` + `tests/cli/test_cli_commands.py`. |
| 4 | Contract Impact | PASS | No contract edits; `doctor --json` conforms to `doctor_report_schema.json`. |
| 5 | Types Complete | PASS | `wizard() -> None`, `doctor(json_output: bool) -> None` are explicit and spec-anchored. |
| 6 | Tests Complete | PASS | Deterministic wizard + doctor tests; monkeypatch avoids network. |
| 7 | Verification Complete | PASS | Pyright/Ruff/Pytest + `lint-imports` listed. |
| 8 | Decision-Minimizing | PASS | Clarifications above eliminate remaining CLI behavior choices. |
| 9 | Determinism Defined | PASS | Doctor JSON determinism is explicit; wizard output is constrained to a stable minimal shape. |

## Additional Quality Checks

- Error Codes: OK (uses `ExitCode.DEPENDENCY_ERROR` and `ExitCode.INTERRUPTED` per SSOT)
- Failure Modes: OK (wizard cancel = 130 with no write; doctor exit code depends only on core failures)
- Derived Outputs: OK (no contract/view generation required)
- Rollback Guidance: OK (single-module + tests; revert `cli_entry.py` + `test_cli_commands.py` changes)
- SSOT Update Audit (if SSOT changed this loop): OK (N/A; no SSOT edits)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NONE

## Ready for Implementation

All checklist items pass. Coding Agent may proceed.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8-2__wizard

## Inputs (Read These)
1. Read file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md
2. Read file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-review-v1.md (must be APPROVED)
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/contracts/doctor_report_schema.json
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## Your Task
Implement the plan exactly (including the binding clarifications in plan-review-v1). Update only the files listed in the plan. Add/modify unit tests as specified. Do not add network-dependent tests.

## Output
Write file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/impl-v1.md
