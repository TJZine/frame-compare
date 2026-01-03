# Parity Closure Verification Report

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

- None.

### Notes

- Progress reporting requirements now align with existing canonical implementations in `src/frame_compare/utils/progress.py` (Rich/Null/Log), and the Phase 6 checklist no longer requires a non-existent JSON-lines reporter.
- FramePlan seed handling and test list now align across checklist, SSOT spec, and `src/frame_compare/config/schema.py` (`random_seed=42`).
- Tonemap wiring test names now match the render SSOT planned integration tests (`tests/render/test_tonemap_wiring.py::...`) rather than ad-hoc checklist-only names.

## Evidence Trail

### Phase 6 Checklist Structure (PASS)

- Phase header and SSOT references present: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:467`–`:477`
- Subsections 6.1–6.8 present and unchecked: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:479`–`:610`

### SSOT Reference Links (PASS)

- Progress reporting reference resolves: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:503` → `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:96`
- Tonemap wiring reference resolves: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:537` → `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:57`
- FramePlan reference resolves: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:514` → `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:124`
- VSPreview reference resolves: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:554` → `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md:171`
- CLI module reference resolves: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:604` → `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md:44`

### Test Name Matching (PASS)

- FramePlan tests match checklist exactly (7):
  - Checklist: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:525`–`:533`
  - Spec: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:314`–`:330`
- VSPreview tests match checklist exactly (10):
  - Checklist: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:564`–`:573`
  - Spec: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md:336`–`:350`
- Tonemap wiring tests match SSOT planned integration tests (4):
  - Checklist: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:546`–`:550`
  - Spec: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:788`–`:791`

### Spec Content Fixes (PASS)

- VSPreview §8.1 includes test file + 10 tests: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md:334`–`:350`
- FramePlan §8.1 includes test file + 7 tests and clarifies seed type boundary: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md:314`–`:330`
- Orchestration tonemap skip/fail NOTE present and matches required conditions: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md:329`–`:338`
- Render §1.4 contains gating rule, settings resolution, integration point, and FC-4004 fail-fast policy: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:68`–`:207`

### Code Reality Checks (PASS)

- Tonemap not wired into render orchestrator (expected gap): no `apply_tonemap`/`should_tonemap` usage in `src/frame_compare/render/orchestrator.py` and `render_screenshots` signature remains without `config` (`src/frame_compare/render/orchestrator.py:128`–`:136`).
- Tonemap implementation exists: `src/frame_compare/vs/tonemap.py:171`
- Config keys exist: `src/frame_compare/config/schema.py:92`, `src/frame_compare/config/schema.py:103`, `src/frame_compare/config/schema.py:117`
- VSPreview not consumed by alignment service (expected gap): `src/frame_compare/services/alignment.py` has no `use_vspreview` references.
- CLI remains stubbed (expected): `src/frame_compare/cli_entry.py:55`–`:68`

### Traceability Updates (PASS)

- F-014/F-015/F-016 present with correct spec anchors: `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md:26`–`:28`
- GAP-001–GAP-004 present with correct SSOT anchors: `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md:100`–`:103`

### Workflow Wiring (PASS)

- Quick reference points to canonical workflow doc: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md:11`–`:16`
- Planning Agent doc pattern supports reading new module specs via `<target>.md`: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md:374`–`:381`

### Legacy Parity (PASS)

- VSPreview/interactive alignment exists in legacy and is covered by vspreview SSOT: `docs/legacy_project_dissection.md:150`
- Legacy tonemap hard-failure path for missing libplacebo aligns with fail-fast posture (no silent fallback for required tonemap): `docs/legacy_tonemap_info.md:93` and `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:196`–`:207`
