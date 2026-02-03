---
RUN_ID: 2026-02-03__p6-7-12__consolidated-fps-report-5-4
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Bundled) — 6.7 Runner & Phase Orchestration — Implement consolidated FPS report per spec §5.4 (after LoadSources and after Align) — Bundled 2 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/impl-v1.md
  - .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-v2.md
  - .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/verify-v1.md
---

# Verification Report: Consolidated FPS Report (§5.4) + Unit Tests

## Summary

**Date:** 2026-02-03
**Plan Reference:** .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-v2.md
**Implementation Reference:** .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/impl-v1.md
**Verdict:** ✅ PASS

## Implementation Review

### Plan Compliance

- [x] Consolidated FPS report helpers implemented with JSON + human-readable output and quiet-mode suppression
- [x] `execute_run(...)` emits reports after LoadSources and after Align (even when Align is skipped)
- [x] Unit tests added for FPS report ordering/divergence/quiet behavior and probe cache missing-version + deterministic ordering

## Verification Results

### Quality Gates

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest -q
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 66%]
........................................................................ [ 79%]
........................................................................ [ 92%]
........................................                                 [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/integration/test_render_vs.py:13: vapoursynth is mocked
SKIPPED [1] tests/vs/test_integration.py:13: VapourSynth is mocked, skipping integration test

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

╔══╗─────────▶╔╗ ╔╗      ╔╗◀───┐
╚╣╠╝◀─────┐  ╔╝╚╗║║────▶╔╝╚╗   │
 ║║   ╔══╦══╦╩╗╔╝║║  ╔╦═╩╗╔╝╔═╦══╗
 ║║╔══╣╔╗║╔╗║╔╣║ ║║ ╔╬╣╔╗║║ ║│║╔═╝
╔╣╠╣║║║╚╝║╚╝║║║╚╗║╚═╝║║║║║╚╗║═╣║
╚══╩╩╩╣╔═╩══╩╝╚═╝╚═══╩╩╝╚╩═╩╩═╩╝
  └──▶║║                    ▲
      ╚╝────────────────────┘


---------
Contracts
---------

Analyzed 56 files, 134 dependencies.
------------------------------------

Layered Architecture KEPT
Domain Independence KEPT

Contracts: 2 kept, 0 broken.
```

### Contract + Traceability Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
Validating module spec references...
  ✓ frame-plan-module.md

Validating test references...
  ✓ tests/analysis/test_cache_io.py (real)
  ✓ tests/analysis/test_frame_plan.py (scaffold)
  ✓ tests/analysis/test_selection.py (real)
  ✓ tests/cli/test_cli_commands.py (real)
  ✓ tests/cli/test_cli_commands.py::test_doctor_stub_text (real)
  ✓ tests/cli/test_cli_commands.py::test_preset_apply_stub (real)
  ✓ tests/cli/test_cli_commands.py::test_preset_list_stub (real)
  ✓ tests/cli/test_cli_commands.py::test_preset_save_stub (real)
  ✓ tests/cli/test_cli_commands.py::test_run_json_sets_mode (scaffold)
  ✓ tests/cli/test_cli_commands.py::test_run_quiet_sets_mode (scaffold)
  ✓ tests/cli/test_cli_commands.py::test_run_stub_executes (real)
  ✓ tests/cli/test_cli_commands.py::test_run_verbose_sets_mode (scaffold)
  ✓ tests/cli/test_cli_commands.py::test_wizard_stub (real)
  ✓ tests/config/test_loader.py (real)
  ✓ tests/config/test_overrides.py::test_apply_cli_overrides_basic (real)
  ✓ tests/config/test_overrides.py::test_apply_cli_overrides_inverts_no_upload (real)
  ✓ tests/config/test_overrides.py::test_apply_cli_overrides_sets_overlay_mode (scaffold)
  ✓ tests/config/test_overrides.py::test_apply_cli_overrides_sets_random_seed (scaffold)
  ✓ tests/config/test_overrides.py::test_apply_cli_overrides_sets_tm_curve (scaffold)
  ✓ tests/config/test_overrides.py::test_apply_cli_overrides_sets_tm_preset (scaffold)
  ✓ tests/config/test_overrides.py::test_apply_cli_overrides_sets_tm_target_nits (scaffold)
  ✓ tests/e2e/test_cli_version.py (real)
  ✓ tests/e2e/test_golden_pipeline.py (scaffold)
  ✓ tests/e2e/test_load_hdr.py (scaffold)
  ✓ tests/e2e/test_publish.py (scaffold)
  ✓ tests/e2e/test_render_overlay.py (scaffold)
  ✓ tests/e2e/test_report.py (scaffold)
  ✓ tests/e2e/test_selection.py (scaffold)
  ✓ tests/e2e/test_tonemap_presets.py (scaffold)
  ✓ tests/render/test_orchestrator.py (real)
  ✓ tests/render/test_tonemap_wiring.py (scaffold)
  ✓ tests/services/test_alignment.py (real)
  ✓ tests/services/test_metadata.py (real)
  ✓ tests/services/test_publishers.py (real)
  ✓ tests/services/test_report.py (real)
  ✓ tests/vs/test_loader.py (real)
  ✓ tests/vs/test_props.py (real)
  ✓ tests/vs/test_tonemap.py (real)
  ✓ tests/vspreview/test_overrides.py (scaffold)

✅ All traceability references valid
```

## Ready for Review

All verification gates passed. Handoff to Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Review Agent for Frame Compare 2.0.

## RUN_ID

2026-02-03__p6-7-12__consolidated-fps-report-5-4

## Files to Read

1. Read file: .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/verify-v1.md
2. Read file: .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/impl-v1.md
3. Read file: .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-v2.md
4. Read file: .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-review-v2.md

## Preconditions

- Plan Review Report shows Verdict: APPROVED
- All verification gates passed

## Your Task

Perform final quality review and issue verdict.

## Output

Write file: .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/review-v1.md
