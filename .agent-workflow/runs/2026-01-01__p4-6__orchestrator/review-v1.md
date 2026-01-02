---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v1
TARGET: Phase 4 → Item 4.6
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/verify-v2.md
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/impl-v2.md
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Render Orchestrator

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-01
**Files Reviewed:** 10
**Commit Subject:** `feat(render): implement Phase 4.6 render orchestrator`

> [!NOTE]
> The commit subject must summarize the entire checklist item (the full run), not just the review phase.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md

$ .venv/bin/pyright --warnings src/frame_compare/render/
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check src/frame_compare/render/ tests/render/
All checks passed

$ .venv/bin/pytest --cov=src/frame_compare/render tests/render/
72 passed in 0.46s
TOTAL coverage: 85% (Pass > 80%)

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [ ] Algorithms match spec (render-module.md Section 3.1) — see Issues

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

1. **VS renderer failure does not propagate required errors for render_frame**
   - Location: `src/frame_compare/render/orchestrator.py:120-171`
   - Issue: When `renderer="vapoursynth"` and VS loading fails with `VapourSynthNotFoundError` / `PluginNotFoundError` / `SourceLoadError`, the code re-raises correctly. But when VS loading fails with an unknown exception, the spec requires wrapping in `RenderError` with `__cause__` preserved. The current code does wrap, but the test only checks `__cause__` is `RuntimeError` and does not assert the error type (`RenderError`), and the fallback path for `renderer="auto"` does not log a warning with the required event name for unknown errors.
   - Fix: Update the test to assert `isinstance(exc_info.value, RenderError)` and adjust the logger call for the unknown exception path to match the spec (or update SSOT if the event name is not required).

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] Deterministic order and output paths — ✓ Verified
- [x] Fail-fast batch semantics — ✓ Verified
- [x] Progress reporting calls — ✓ Verified
- [ ] VS unknown exception wrapping + logging requirements — ✗ See Issues

## Files Reviewed

- .agent-workflow/runs/2026-01-01__p4-6__orchestrator/verify-v2.md
- .agent-workflow/runs/2026-01-01__p4-6__orchestrator/impl-v2.md
- .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md
- src/frame_compare/render/orchestrator.py
- tests/render/test_orchestrator.py
- src/frame_compare/render/__init__.py
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- docs/DECISIONS.md
- CHANGELOG.md
- docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Strengthen `test_render_screenshots_vs_forced_fail_unknown` to assert `RenderError` and ensure logging event naming is compliant with SSOT (or update SSOT if not required).
- Re-submit for verification and review.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-6__orchestrator

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md
2. Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/impl-v3.md
