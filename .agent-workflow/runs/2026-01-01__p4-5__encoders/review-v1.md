---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v1
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/verify-v2.md
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v2.md
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v6.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Render Encoders

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-01
**Files Reviewed:** 16
**Commit Subject:** `feat(render): implement Phase 4.5 render encoders`

> [!NOTE]
> The commit subject must summarize the entire checklist item (the full run), not just the review phase.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md

$ .venv/bin/pyright --warnings src/frame_compare/render/ src/frame_compare/utils/
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check src/frame_compare/render/ src/frame_compare/utils/ tests/render/ tests/utils/
All checks passed

$ .venv/bin/pytest --cov=src/frame_compare/render --cov=src/frame_compare/utils tests/render/ tests/utils/
77 passed in 0.43s
TOTAL coverage: 84% (Pass > 80%)

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [ ] Algorithms match spec (render-module.md Sections 3.1, 4.2) — see Issues

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Follows patterns
- [x] Errors have codes and hints

### Testing

- [x] Unit tests cover main paths
- [x] Edge cases tested
- [x] Tests are deterministic

### Documentation

- [x] Docstrings present

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **FFprobe uses the wrong FPS field (spec/plan mismatch)**
   - Location: `src/frame_compare/render/encoders.py:139-147`
   - Issue: `_probe_fps` queries `stream=r_frame_rate`, but plan-v6 requires parsing `avg_frame_rate` from ffprobe bytes. This is a direct spec/plan mismatch and can yield incorrect seek times for VFR content.
   - Fix: Change the ffprobe query to use `stream=avg_frame_rate` and update tests to assert the expected ffprobe args (or otherwise cover this requirement).

2. **FFmpeg command deviates from SSOT command list**
   - Location: `src/frame_compare/render/encoders.py:177-191`
   - Issue: SSOT Section 4.2 specifies the ffmpeg command list using `-q:v 1`, but the implementation uses `-c:v png -compression_level <n>`. This is behavior drift from the spec anchor.
   - Fix: Update `_render_ffmpeg` to align with the SSOT command list (or update SSOT if the intended behavior changed, then re-anchor and re-verify).

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] Render dispatch and error wrapping behaviors — ✓ Verified
- [x] Overlay integration — ✓ Verified
- [ ] FFmpeg seek policy and probe source match SSOT — ✗ See Issues

## Files Reviewed

- .agent-workflow/runs/2026-01-01__p4-5__encoders/verify-v2.md
- .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v2.md
- .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
- .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v6.md
- src/frame_compare/render/encoders.py
- src/frame_compare/utils/subproc.py
- tests/render/test_encoders.py
- tests/utils/test_subproc.py
- src/frame_compare/render/__init__.py
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- docs/DECISIONS.md
- CHANGELOG.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md
- docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
- docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Use `avg_frame_rate` in ffprobe and add/adjust tests to cover this requirement.
  2. Align the ffmpeg command list with SSOT Section 4.2 (or update SSOT and re-verify if intended behavior differs).
- Re-submit for verification and review.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md
2. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v6.md
3. Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/impl-v3.md
