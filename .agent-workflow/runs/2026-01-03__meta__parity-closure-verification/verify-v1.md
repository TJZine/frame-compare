# Parity Closure Verification Report

## Summary Verdict

| Check Area | Result | Issues |
|:-----------|:-------|:-------|
| Phase 6 Checklist Structure | PASS | 0 |
| SSOT Reference Links | FAIL | 1 |
| Test Name Matching | FAIL | 2 |
| Spec Content Fixes | FAIL | 1 |
| Code Reality Checks | PASS | 0 |
| Traceability Updates | PASS | 0 |
| Workflow Wiring | PASS | 0 |
| Legacy Parity | PASS | 0 |
| **OVERALL** | **FAIL** | - |

## Detailed Findings

### BLOCKERS (Must Fix Before Phase 6)

- Phase 6 checklist references a non-existent SSOT section for progress reporting.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:503` references `orchestration-module.md §4.2.3`.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:96` shows Progress types under `### 3.3 Progress Types` (not `§4.2.3`).
  - Expected: Phase 6 `**Reference:**` points to an actual spec section.
  - Actual: `§4.2.3` does not exist in `orchestration-module.md`.
  - Required correction: Update `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:503` to reference the correct section (appears to be `orchestration-module.md §3.3`).

- Phase 6 checklist phase ordering contradicts the orchestration SSOT (tonemap is not a standalone orchestration phase).
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:586` lists `Phase 6: Tonemap (uses 6.5)` and `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:593` lists `Phase 7: Render`.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:318` sets `Phase 6 | Render` (no Tonemap phase).
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:333` states “Tonemapping is not a separate orchestration phase. It is part of the render pipeline…”.
  - Expected: Phase ordering in checklist matches the SSOT table + note in `orchestration-module.md §4.3.4`.
  - Actual: Checklist introduces a Tonemap phase that SSOT explicitly rejects.
  - Required correction: Align `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:586` phase list to SSOT (keep tonemap as part of render; do not add a separate tonemap orchestration phase).

- FramePlan test requirements do not match SSOT: checklist lists 8 unit tests; spec lists 7.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:525` includes `test_select_uniform_seeded_frames_*` + two `test_create_frame_plan_*` tests, including `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:532` (`test_create_frame_plan_uses_default_seed_when_empty`).
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:320`–`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:328` lists only 7 tests and omits `test_create_frame_plan_uses_default_seed_when_empty`.
  - Expected: 100% match between checklist and spec §8.1 test names.
  - Actual: Missing spec test row; checklist/spec mismatch.
  - Required correction: Add the missing test to `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md` §8.1 (or remove it from the checklist), then re-verify.

- FramePlan default seed semantics are inconsistent between checklist and SSOT (and current config schema).
  - Evidence (checklist): `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:520` specifies `None/"" → "frame-compare-default"`.
  - Evidence (SSOT spec): `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:115` defines SSOT default seed as `42`.
  - Evidence (code schema): `src/frame_compare/config/schema.py:92` sets `AnalysisConfig.random_seed: int = 42`.
  - Expected: Checklist and module spec agree on the default seed and its type.
  - Actual: Checklist specifies a string sentinel; SSOT + schema specify `int=42`.
  - Required correction: Update `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:520` to match SSOT (`42`) and ensure the test expectations align.

### MAJOR Issues

- Progress reporting responsibilities appear inconsistent between the Phase 6 checklist and orchestration SSOT.
  - Evidence (checklist): `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:505`–`docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:509` requires implementing `RichProgressReporter`, `JsonProgressReporter`, `NullProgressReporter` in Phase 6.
  - Evidence (SSOT): `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:99`–`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:130` states the protocol is canonically defined in `frame_compare.utils.progress` and the orchestration module “MUST use the canonical implementations” there.
  - Expected: Checklist work items map cleanly onto SSOT-defined ownership and module boundaries.
  - Actual: Checklist implies new orchestration-local implementations that SSOT says must be canonical in `utils.progress`.
  - Required correction: Decide SSOT ownership (canonical `utils.progress` vs orchestration wrappers) and update either the checklist or orchestration spec to remove ambiguity.

### MINOR Issues

- Render module §1.4 defines settings resolution priority including “CLI overrides” while also describing CLI flags as “PLANNED”.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:94` says CLI flag is PLANNED; `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:100`–`:103` defines CLI override priority.
  - Note: Current CLI already defines `--tm-preset/--tm-target/--tm-curve` as parameters (stubs) in `src/frame_compare/cli_entry.py:39`–`:41`.

### Notes

- VSPreview spec testing table appears complete and matches Phase 6 checklist.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:564`–`:574` matches `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md:340`–`:349`.
- Orchestration spec includes the requested tonemap skip/fail NOTE block and matches the stated conditions.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:330`–`:338`.
- Render spec §1.4 includes gating rule, settings resolution, integration point, and FC-4004 fail-fast policy.
  - Evidence: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:68`–`:87` (gating), `:96`–`:103` (priority), `:135`–`:143` (integration), `:196`–`:207` (failure policy).
- Code reality checks confirm parity gaps remain gaps (expected).
  - Evidence (tonemap not wired): no `apply_tonemap`/`should_tonemap` usage in `src/frame_compare/render/orchestrator.py` (and signature unchanged at `src/frame_compare/render/orchestrator.py:128`–`:136` lacks `config` parameter).
  - Evidence (tonemap impl exists): `src/frame_compare/vs/tonemap.py:171` defines `apply_tonemap(clip, settings, hdr_metadata=None)`.
  - Evidence (config keys exist): `src/frame_compare/config/schema.py:103` (`use_vspreview`), `src/frame_compare/config/schema.py:117` (`enable_tonemap`).
  - Evidence (VSPreview not consumed): no `use_vspreview` references in `src/frame_compare/services/alignment.py`.
  - Evidence (CLI still stub): `src/frame_compare/cli_entry.py:55`–`:68`.

## Evidence Trail

### FAIL: SSOT Reference Links

- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:503`
  - Expected: `**Reference:** ... §<existing section>`
  - Actual: `§4.2.3` referenced, but orchestration spec has no `4.2.3` section.
  - SSOT reality: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:96` (`### 3.3 Progress Types`).

### FAIL: Test Name Matching

- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:531`–`:532` vs `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:320`–`:328`
  - Expected: Checklist FramePlan tests match spec §8.1 exactly (8 tests).
  - Actual: Spec lists 7 tests; missing `test_create_frame_plan_uses_default_seed_when_empty`.

- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:520` vs `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:115` vs `src/frame_compare/config/schema.py:92`
  - Expected: Default seed semantics and type consistent across checklist/spec/schema.
  - Actual: Checklist specifies string sentinel; spec+schema specify `int=42`.

### FAIL: Spec Content Fixes

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:314`–`:329`
  - Expected (per task): §8.1 includes test file path and 8 explicit test functions (including default seed cases).
  - Actual: Test file path present, but only 7 test functions listed.
