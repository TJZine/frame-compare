---
RUN_ID: 2026-02-02__p6-7-7__rundependencies
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement RunDependencies for dependency injection
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v3.md
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/impl-v1.md
  - src/frame_compare/orchestration/coordinator.py
  - src/frame_compare/orchestration/__init__.py
  - tests/orchestration/test_run_dependencies.py
  - docs/DECISIONS.md
  - CHANGELOG.md
---

# Implementation Report: RunDependencies (Dependency Injection)

## Summary
**Date:** 2026-02-03
**Plan Reference:** .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v3.md
**Plan Review Report:** .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v3.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `tests/orchestration/test_run_dependencies.py` — Unit tests for DI defaults and injected overrides.

### Modified
- `src/frame_compare/orchestration/coordinator.py` — Added `FFmpegRunner` protocol, `DefaultFFmpegRunner` stub, and `RunDependencies` with lazy defaults.
- `src/frame_compare/orchestration/__init__.py` — Re-exported `RunDependencies`.
- `docs/DECISIONS.md` — Logged the stub FFmpeg runner decision and export location.
- `CHANGELOG.md` — Added RunDependencies entry under Unreleased/Added.

## Implementation Notes
- `DefaultFFmpegRunner` is intentionally a stub in this slice and raises `NotImplementedError` in both methods.
- `RunDependencies` lazily constructs default VS/FFmpeg providers on first access.
- `uv run` checks required escalated permissions to access the uv cache; commands were re-run with approval.

## Verification Evidence

### Pyright Output
```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations
```

### Ruff Output
```text
$ .venv/bin/ruff check .
All checks passed!
```

### Pytest Output
```text
$ .venv/bin/pytest -q
........................................................................ [ 13%]
........................................................................ [ 27%]
........................................................................ [ 41%]
........................................................................ [ 54%]
........................................................................ [ 68%]
........................................................................ [ 82%]
........................................................................ [ 96%]
.....................                                                    [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/integration/test_render_vs.py:13: vapoursynth is mocked
SKIPPED [1] tests/vs/test_integration.py:13: VapourSynth is mocked, skipping integration test
```

### Import Lint Output
```text
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

Analyzed 54 files, 120 dependencies.
------------------------------------

Layered Architecture KEPT
Domain Independence KEPT

Contracts: 2 kept, 0 broken.
```

### Contract View Check Output
```text
$ uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date
```

### Traceability Check Output
```text
$ uv run --no-sync python scripts/validate_traceability.py --check
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
- [x] Phase 6 → Item 6.7 — Runner & Phase Orchestration — RunDependencies DI container

## Open Questions
- None.

## Ready for Verification
All required gates passed and outputs recorded above.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-7__rundependencies

## Files to Read
1. Read file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/impl-v1.md
2. Read file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v3.md
3. Read file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v3.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/verify-v1.md
