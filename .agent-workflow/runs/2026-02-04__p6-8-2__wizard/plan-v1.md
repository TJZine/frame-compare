---
RUN_ID: 2026-02-04__p6-8-2__wizard
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — `wizard` + `doctor`
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/functional-requirements.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/business-requirements.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/doctor_report_schema.json
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md
---

# Implementation Plan: Complete CLI `wizard` + `doctor` Commands

## Context
**Phase:** 6
**Module:** `frame_compare.cli_entry` (CLI commands) + orchestration doctor plumbing
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
**Dependencies:** Existing `frame_compare.config` schema/loader + existing `frame_compare.orchestration.doctor.run_doctor()`

## Scope
This plan covers:
- [ ] Implement `frame-compare wizard` interactive config writer that produces a valid `config/config.toml`
- [ ] Implement `frame-compare doctor` dependency diagnostics with human output and `--json` output
- [ ] Update/replace CLI unit tests to remove stub expectations and verify new behaviors deterministically (no real network calls)

This plan does NOT cover:
- Auto-triggering wizard from `frame-compare run` when config is missing
- Implementing `preset` subcommands (list/apply/save)
- Adding new doctor checks beyond the SSOT deterministic check list
- Integration tests that require real external binaries or real network connectivity by default

## Contract Impact
**Contracts touched:** NO

Contract to conform to (no edits planned):
- `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/doctor_report_schema.json` (doctor `--json` output shape, baseline_version)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2. CLI Entry Point"
  - Section: "2.1 Command Structure"
  - Section: "2.2 Exit Codes"
  - Section: "8. Error Handling"
  - Section: "9. Testing Strategy"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`:
  - Section: "2. Configuration Schema"
  - Section: "2.1 Root Schema"
  - Section: "2.2 Section Schemas"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.2 Doctor"
  - Section: "4.2.1 Check List (Deterministic)"
  - Section: "4.2.2 slow.pics Reachability Probe"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "1.4 Plugin Detection"
- `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/functional-requirements.md`:
  - Section: "FR-CLI-002: Wizard Command"
  - Section: "FR-CLI-003: Doctor Command"
- `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/business-requirements.md`:
  - Section: "3.2 Configuration Wizard Workflow"
  - Section: "3.3 Doctor/Diagnostics Workflow"

## Files to Create/Modify

### 1. `src/frame_compare/cli_entry.py` (MODIFY)
**Purpose:** Replace `wizard`/`doctor` stubs with fully functional CLI commands.

**Functions to implement (spec-anchored):**
- `wizard() -> None` — interactive config prompts; writes `config/config.toml` under the current workspace root
- `doctor(json_output: bool) -> None` — runs doctor checks; emits human report or JSON report; exits with correct code

**Key implementation notes:**
- Wizard prompt flow (fixed order; testable via `CliRunner.invoke(..., input=...)`):
  1) Prompt for input directory (default: `ConfigSchema.paths.input_dir`, validate that the directory exists relative to the current working directory unless an absolute path is provided).
  2) Prompt for slow.pics auto-upload enable/disable (maps to `slowpics.auto_upload`).
  3) Prompt for slow.pics visibility (maps to `slowpics.visibility`, must be one of `public|unlisted|private`).
  4) Prompt for “delete after upload” (maps to `slowpics.delete_after_upload`).
  5) Prompt for TMDB API key (optional; empty -> `None`, maps to `tmdb.api_key`, input should be hidden).
  6) Validate final config via `ConfigSchema.model_validate(...)` (or equivalent) and write TOML to `config/config.toml` (create the `config/` directory if missing).
- Wizard cancellation:
  - If the user cancels (Ctrl+C / Typer abort), exit with `ExitCode.INTERRUPTED` and do not write/overwrite the config file.
- Doctor behavior:
  - Invoke `frame_compare.orchestration.run_doctor(checks=None, reporter=None)` and use `DoctorReport.critical_failures` to determine “critical” failures.
  - Exit codes:
    - Exit 0 when no core checks failed.
    - Exit `ExitCode.DEPENDENCY_ERROR` when one or more core checks failed (even if optional/network checks also failed).
  - `--json` output MUST conform to `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/doctor_report_schema.json`:
    - Top-level keys: `success` and `doctor`
    - `doctor.baseline_version` is exactly `R73`
    - `doctor.checks` is a stable-order array matching the SSOT check ordering
    - Each check object includes at least: `id`, `category`, `status` plus optional fields (`message`, `install_hint`, `discovered_namespace`, `expected_namespace`, `version`, `details`)
  - JSON determinism: serialize with stable key ordering and stable separators; avoid non-deterministic dict ordering derived from runtime discovery.
- Unit tests must not require real network access:
  - CLI doctor tests MUST monkeypatch the doctor runner to avoid calling the real slow.pics probe.

### 2. `tests/cli/test_cli_commands.py` (MODIFY)
**Purpose:** Replace stub-based expectations with deterministic tests for `wizard` + `doctor`.

**Tests required:**
- test_wizard_writes_valid_config_toml — simulate prompts; verify `config/config.toml` exists and contains expected keys/values for input_dir + slow.pics + tmdb
- test_wizard_cancel_exits_130_and_writes_nothing — simulate cancel; verify exit code 130 and no config file
- test_doctor_json_conforms_to_schema_shape — monkeypatch CLI-layer doctor invocation to return a deterministic DoctorReport; parse JSON; assert required top-level structure + baseline_version + per-check required fields
- test_doctor_exit_code_is_3_on_core_failure — `critical_failures` non-empty -> exit code 3
- test_doctor_exit_code_is_0_on_optional_or_network_failure — no core failures but some failed checks -> exit code 0

## Acceptance Criteria

- [ ] GIVEN a workspace with an existing input directory WHEN the user runs `frame-compare wizard` and completes prompts THEN `config/config.toml` is created and is loadable as a valid `ConfigSchema`
- [ ] GIVEN the user cancels the wizard WHEN cancellation occurs THEN exit code is 130 and no config file is written
- [ ] GIVEN doctor checks pass for all core dependencies WHEN the user runs `frame-compare doctor` THEN exit code is 0
- [ ] GIVEN doctor checks fail for one or more core dependencies WHEN the user runs `frame-compare doctor` THEN exit code is 3
- [ ] GIVEN the user runs `frame-compare doctor --json` WHEN the command completes THEN output is valid JSON conforming to `doctor_report_schema.json` and reports `success` based only on core check failures

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/cli_entry.py tests/cli/test_cli_commands.py
.venv/bin/ruff check src/frame_compare/cli_entry.py tests/cli/test_cli_commands.py
.venv/bin/pytest -q tests/cli/test_cli_commands.py
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- Keep CLI tests hermetic: monkeypatch doctor execution so unit tests never perform the real slow.pics `HEAD` probe.
- Keep wizard prompts stable and in the exact order listed above so tests remain deterministic.
- Do not introduce new third-party deps (e.g., JSON schema validators) just for tests; assert the required JSON shape directly.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8-2__wizard

## Plan to Review
Read file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-review-v1.md
