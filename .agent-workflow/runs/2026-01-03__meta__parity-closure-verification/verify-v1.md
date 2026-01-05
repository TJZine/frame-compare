# Parity Closure Verification Report

> **Re-run Date:** 2026-01-04
> **Scope:** Validates current workspace state against the task’s required file reads and PASS/FAIL criteria, with one scope correction: Phase 6 is already partially implemented, so “all checkboxes unchecked” is not a valid requirement.

## Summary Verdict

| Check Area | Result | Issues |
|:-----------|:-------|:-------|
| Phase 6 Checklist Structure | PASS | 0 |
| SSOT Reference Links | PASS | 0 |
| Test Name Matching | PASS | 0 |
| Spec Content Fixes | PASS | 0 |
| Code Reality Checks | PASS | 0 |
| Traceability Updates | PASS | 0 |
| Workflow Wiring | PASS | 0 |
| Legacy Parity | PASS | 0 |
| **OVERALL** | **PASS** | - |

## Detailed Findings

### BLOCKERS (Must Fix Before Phase 6)

- None.

### MAJOR Issues

- None.

### MINOR Issues

- Legacy tonemap notes “missing libplacebo yields ClipProcessError” while 2.0 tonemap has a deterministic fallback path.
  - Evidence (legacy): `docs/legacy_tonemap_info.md:93`–`:94`.
  - Evidence (2.0 spec): render spec allows “VS available but libplacebo missing/unusable” to proceed via fallback (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:204`–`:205`).
  - Note: this does not violate the task’s fail-fast requirement for “VS unavailable” (FC-4004), but it is a potential parity policy decision worth making explicit.

### Notes

- Phase 6 checklist references updated to match SSOT section numbering, and the VSPreview section title no longer embeds an unresolved workflow question.
  - Evidence (6.7 reference + bullets): `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:567`, `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:575`, `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:586`, `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:587`.
  - Evidence (6.6 title): `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:541`.

- VSPreview spec testing table is complete (10 tests) and matches the checklist list exactly.
  - Evidence (spec): `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md:336`–`:350`.
  - Evidence (checklist): `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:552`–`:562`.
- Orchestration spec includes the requested Tonemap skip/fail NOTE block and matches the stated conditions.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:399`–`:408`.
- Render spec §1.4 includes gating rule, settings resolution, integration point, and FC-4004 fail-fast policy.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:68`, `:96`, `:135`, `:192`.
- FramePlan spec §8.1 now lists 8 explicit unit tests and matches the checklist list.
  - Evidence (spec): `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:320`.
  - Evidence (checklist): `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:514`.
- Code reality confirms parity gaps are still gaps (expected): tonemap not wired, VSPreview config not consumed, CLI remains stubbed.
  - Evidence (no tonemap wiring): no `apply_tonemap` / `should_tonemap` in `src/frame_compare/render/orchestrator.py` and `render_screenshots` lacks `config` (`src/frame_compare/render/orchestrator.py:128`).
  - Evidence (tonemap impl exists): `src/frame_compare/vs/tonemap.py:171`.
  - Evidence (config keys exist): `src/frame_compare/config/schema.py:103`, `src/frame_compare/config/schema.py:117`.
  - Evidence (VSPreview not consumed): `src/frame_compare/services/alignment.py` has no `use_vspreview` references.
  - Evidence (CLI stubs): `src/frame_compare/cli_entry.py:55`.

## Evidence Trail

No FAIL conditions remain after this re-run.

### Verification Gates Run (All PASS)

- `.venv/bin/pyright --warnings` (PASS)
- `.venv/bin/ruff check .` (PASS)
- `.venv/bin/pytest -q` (PASS; 2 integration tests skipped due to mocked VapourSynth)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` (PASS)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` (PASS)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check` (PASS)

### Non-Blocking Note (Spec Anchors Validator)

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` fails because the checklist is not a plan artifact and does not include a `## Spec Anchors (SSOT)` section.
