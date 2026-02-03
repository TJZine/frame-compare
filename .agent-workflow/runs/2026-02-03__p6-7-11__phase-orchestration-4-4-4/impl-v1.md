---
RUN_ID: 2026-02-03__p6-7-11__phase-orchestration-4-4-4
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement phase orchestration per spec §4.4.4:
INPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v3.md
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-review-v3.md
OUTPUTS:
  - /Users/tristan/Software/frame-compare/.agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/impl-v1.md
  - src/frame_compare/orchestration/phases.py
  - src/frame_compare/orchestration/coordinator.py
  - tests/orchestration/test_phases.py
  - tests/orchestration/test_execute_run.py
---

# Implementation Report: Phase Orchestration (Phase Ordering §4.4.4)

## Summary
**Date:** 2026-02-03
**Plan Reference:** .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v3.md
**Plan Review Report:** .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-review-v3.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/orchestration/phases.py` — Phase types + execution loop
- `tests/orchestration/test_phases.py` — Phase ordering/skip/warn/fail-fast tests

### Modified
- `src/frame_compare/orchestration/coordinator.py` — Execute phases 1–10, load sources, timings
- `tests/orchestration/test_execute_run.py` — Updated run expectations + fake VS loader

## Implementation Notes
- No deviations from the plan.

## Local Sanity Checks (Command Output)

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v3.md`

```text
OK: Spec Anchors valid for .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v3.md
```

- `.venv/bin/pyright --warnings`

```text
0 errors, 0 warnings, 0 informations
```

- `.venv/bin/ruff check .`

```text
All checks passed!
```

- `.venv/bin/pytest -q`

```text
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 40%]
........................................................................ [ 53%]
........................................................................ [ 66%]
........................................................................ [ 80%]
........................................................................ [ 93%]
..................................                                       [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/integration/test_render_vs.py:13: vapoursynth is mocked
SKIPPED [1] tests/vs/test_integration.py:13: VapourSynth is mocked, skipping integration test
```

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`

```text

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

Analyzed 55 files, 132 dependencies.
------------------------------------

Layered Architecture KEPT
Domain Independence KEPT

Contracts: 2 kept, 0 broken.
```

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`

```text
OK: All derived files are up-to-date
```

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`

```text
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

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement phase orchestration per spec §4.4.4

## Open Questions
- None.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-02-03__p6-7-11__phase-orchestration-4-4-4

## Files to Read
1. Read file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/impl-v1.md
2. Read file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v3.md
3. Read file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-review-v3.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/verify-v1.md
