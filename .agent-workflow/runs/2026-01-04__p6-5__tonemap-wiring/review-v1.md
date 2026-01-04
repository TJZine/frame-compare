---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v1
TARGET: Phase 6 → Item 6.5 (Tonemap Wiring)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/verify-v2.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v2.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v1.md
  - .agent-workflow/index.md
---

# Review Report: Tonemap Wiring Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-04
**Files Reviewed:** 10
**Commit Subject:** `feat(render): implement Phase 6.5 tonemap wiring`

### Files Reviewed
- src/frame_compare/render/orchestrator.py
- src/frame_compare/render/__init__.py
- tests/render/test_orchestrator.py
- tests/integration/test_render_orchestrator.py
- tests/render/test_tonemap_wiring.py
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
- docs/DECISIONS.md
- CHANGELOG.md

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest --cov
476 passed, 2 skipped, coverage: 87.98%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria
- [x] Algorithms match spec anchors in render-module.md (§1.4.1–§1.4.6, §3.1, §7.2)

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Follows patterns
- [x] Errors have codes and hints

### Testing

- [x] Tests cover main paths
- [x] Coverage: 87.98%

### Documentation

- [ ] Issue: docs/DECISIONS.md entry missing required run metadata per plan-v3

### SSOT Drift (Hard Gate)

- [ ] Issue: Public API export added without SSOT/plan coverage (probe_is_hdr_ffprobe)

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **Public API export not specified in plan/SSOT**
   - Location: src/frame_compare/render/__init__.py:11
   - Issue: `probe_is_hdr_ffprobe` is exported in `__all__`, which expands the public API beyond plan-v3 scope.
   - Fix: Remove `probe_is_hdr_ffprobe` from exports, or return to Planning/Plan Review to explicitly add it to SSOT/public API.

2. **DECISIONS entry incomplete vs plan requirements**
   - Location: docs/DECISIONS.md:518
   - Issue: The Phase 6.5 entry omits required facts from plan-v3 (artifact versions including verify/review, SSOT edit headings, contract alignment decision, probe determinism decision, out-of-scope items, and full verification gate list).
   - Fix: Expand the entry to include all required bullets per plan-v3, and update artifact versions to the current run outputs.

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN HDR source AND enable_tonemap=True WHEN should_tonemap(...) THEN True
- [x] GIVEN SDR source WHEN should_tonemap(...) THEN False
- [x] GIVEN HDR source AND enable_tonemap=False WHEN should_tonemap(...) THEN False
- [x] GIVEN HDR source + enable_tonemap=True + VS missing + renderer="auto" WHEN render_screenshots(...) THEN raises VS failure or probe failure per spec
- [x] GIVEN HDR source + enable_tonemap=True + VS missing + renderer="ffmpeg" WHEN render_screenshots(...) THEN raises VapourSynthNotFoundError
- [x] GIVEN HDR source + enable_tonemap=False + VS missing WHEN render_screenshots(...) THEN renders via FFmpeg
- [x] GIVEN SDR source + VS missing WHEN render_screenshots(...) THEN renders via FFmpeg
- [x] GIVEN probe failure AND enable_tonemap=True WHEN VS missing THEN render_screenshots(...) propagates probe exception
- [x] GIVEN HDR source + tonemapped WHEN overlay is rendered THEN hdr_info contains tonemapped info
- [x] GIVEN HDR source + tonemap disabled WHEN overlay is rendered THEN hdr_info contains native HDR info

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Remove or formally specify the `probe_is_hdr_ffprobe` export in the public API (plan/SSOT alignment).
  2. Update docs/DECISIONS.md with the required run metadata per plan-v3 (artifact versions, SSOT headings, contract alignment and probe determinism decisions, out-of-scope items, full gate list).
- Re-submit for review

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-5__tonemap-wiring

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
3. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v3.md
