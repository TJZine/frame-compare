---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v1
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v1.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v1.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: HDR Tonemapping

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-30
**Files Reviewed:** 8
**Commit Subject:** `feat(vs): implement HDR tonemapping presets`

> [!NOTE]
> The commit subject must summarize the **entire checklist item** (the full run), not just the review phase.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ .venv/bin/pyright --warnings src/frame_compare/vs/tonemap.py
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check src/frame_compare/vs/tonemap.py tests/vs/test_tonemap.py
All checks passed!

$ .venv/bin/pytest -v tests/vs/test_tonemap.py
23 passed in 0.03s

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 1 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria
- [ ] Issue: Missing SSOT-required HDR metadata extraction when `hdr_metadata` is None

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Follows patterns
- [x] Errors have codes and hints

### Testing

- [x] Tests cover main paths
- [ ] Issue: No test asserts `_detect_hdr` usage when `hdr_metadata` is None

### Documentation

- [x] Docstrings present

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **SSOT drift: HDR metadata extraction missing**
   - Location: `src/frame_compare/vs/tonemap.py:91` and `src/frame_compare/vs/tonemap.py:120`
   - Spec: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:548`
   - Issue: SSOT requires that when `hdr_metadata` is `None`, the tonemapping path must extract metadata from `clip.get_frame(0).props` using `_detect_hdr`. Current implementation falls back directly to `1000` without attempting extraction.
   - Fix: Import `_detect_hdr` from `src/frame_compare/vs/source.py` and, in both `_apply_libplacebo` and `_fallback_tonemap`, when `hdr_metadata` is `None`, call `_detect_hdr` on frame 0 props and use returned `HDRMetadata` for `src_max` calculation.

### Minor (Should Fix)

1. **Missing test coverage for HDR metadata extraction**
   - Location: `tests/vs/test_tonemap.py`
   - Issue: No test asserts that `_detect_hdr` is invoked when `hdr_metadata` is `None`.
   - Fix: Add a unit test that patches `_detect_hdr` and verifies it is called in both libplacebo and fallback paths; assert `src_max` uses `hdr_metadata.max_cll` when provided by the detection helper.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN `settings.enabled == False` WHEN `apply_tonemap()` THEN return clip unchanged — ✓ Verified
- [x] GIVEN "reference" preset WHEN `get_preset_settings()` THEN return correct settings — ✓ Verified
- [x] GIVEN libplacebo available WHEN `apply_tonemap()` THEN use libplacebo path — ✓ Verified
- [x] GIVEN libplacebo unavailable WHEN `apply_tonemap()` THEN use fallback silently — ✓ Verified
- [x] GIVEN unknown preset WHEN `get_preset_settings()` THEN raise `TonemapError(FC-4003)` — ✓ Verified
- [x] GIVEN unsupported tone_curve WHEN `apply_tonemap()` THEN raise `TonemapError(FC-4003)` — ✓ Verified
- [x] GIVEN clip already RGBS WHEN `_to_rgbs()` THEN return unchanged (no-op) — ✓ Verified
- [ ] GIVEN `hdr_metadata is None` WHEN `apply_tonemap()` THEN derive metadata from frame props — ✗ Not implemented

## Files Reviewed

- `src/frame_compare/vs/tonemap.py`
- `tests/vs/test_tonemap.py`
- `src/frame_compare/vs/__init__.py`
- `src/frame_compare/errors.py`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md`
- `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/verify-v1.md`

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Implement `_detect_hdr` usage when `hdr_metadata` is None in both libplacebo and fallback paths.
  2. Add tests to cover the metadata extraction behavior and `src_max` selection.
- Re-submit for review

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Issues to Fix
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md
3. Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/impl-v2.md
