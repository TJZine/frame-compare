---
RUN_ID: 2026-01-02__p5-4__report-service
VERSION: v1
TARGET: Phase 5 → Item 5.4 (Report Generator)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/verify-v2.md
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/impl-v2.md
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v3.md
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Report Generator Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-02
**Files Reviewed:** 9
**Commit Subject:** `feat(services): implement Phase 5 Item 5.4 — report generator`

## Files Reviewed
1. src/frame_compare/services/report.py
2. src/frame_compare/services/__init__.py
3. tests/services/test_report.py
4. docs/DECISIONS.md
5. CHANGELOG.md
6. docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md
7. docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
8. docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
9. docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md

> [!NOTE]
> Generated contract-view artifacts were not manually edited; verification confirms freshness.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v3.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v3.md

$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q --ignore=tests/vs/test_exports.py --ignore=tests/vs/test_tonemap.py
394 passed, 2 skipped
coverage: 88%
Required test coverage of 80.0% reached. Total coverage: 88.08%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [ ] Issue: Zoom controls do not affect the canvas (missing CSS transform binding).
- [ ] Issue: Diff mode cycling does not update compare/base selection (click/arrow keys update unused state).
- [ ] Issue: Keyboard help modal and `?`/`Escape` handling missing.

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Follows patterns
- [x] Errors have codes and hints

### Testing

- [x] Tests cover main paths
- [x] Coverage: 88%

### Documentation

- [ ] Issue: SSOT mismatch for `default_mode` value (`difference` vs `diff`).

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **Zoom controls are non-functional (CSS missing scale binding)**
   - Location: `src/frame_compare/services/report.py:284`
   - Issue: `.rv-canvas` never applies `transform: scale(var(--zoom-level))`, so zoom UI updates state but does not change rendering.
   - Fix: Add `transform: scale(var(--zoom-level, 1));` to `.rv-canvas` per spec Section 5.4.

2. **Diff mode cycling ignores input state**
   - Location: `src/frame_compare/services/report.py:507`, `src/frame_compare/services/report.py:619`, `src/frame_compare/services/report.py:648`
   - Issue: In diff mode, click/ArrowUp/Down update `activeClipIdx`, but `updateImages` uses `leftClipIdx`/`rightClipIdx`, so cycling has no effect.
   - Fix: For diff mode, cycle `rightClipIdx` (or a dedicated compare index) and render using that index; update selectors accordingly.

3. **Missing keyboard help modal and required shortcuts**
   - Location: `src/frame_compare/services/report.py:540`
   - Issue: Spec Section 6.5 requires `?` to open a keyboard help modal and `Escape` to close; no modal or handlers exist.
   - Fix: Add modal markup/CSS and implement `?`/`Escape` handling per spec Section 6.5 and Section 8.2 focus management.

4. **Accessibility requirements not met (ARIA roles/checked + image alt text)**
   - Location: `src/frame_compare/services/report.py:765`, `src/frame_compare/services/report.py:782`, `src/frame_compare/services/report.py:796`
   - Issue: Mode buttons lack `role="radio"` and `aria-checked`, zoom slider lacks `aria-valuenow`/min/max updates, and image/thumbnail `alt` text does not follow spec Section 8.3.
   - Fix: Add radio roles + `aria-checked` updates in JS, ensure zoom slider gets `aria-valuenow` updates, and set alt text to `"{label} - Frame {frame_number}"` for main images and thumbnails.

5. **SSOT mismatch for `default_mode` enum value**
   - Location: `src/frame_compare/services/report.py:149` and `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md:75`
   - Issue: Embedded JSON uses `"diff"` (from `ViewerMode.DIFF`), but SSOT lists `"difference"` as the allowed value.
   - Fix: Update `report-viewer-spec.md` Section 2.2 to align with `ViewerMode.DIFF` (or adjust code + CSS/JS to use `"difference"` consistently).

### Minor (Should Fix)

1. **Filmstrip sizing deviates from SSOT**
   - Location: `src/frame_compare/services/report.py:347`
   - Issue: Spec Section 7.1 calls for 80px width with auto height; CSS uses `width: 120px` and a fixed 100px container.
   - Fix: Align CSS to spec dimensions or update spec with rationale if the new size is intentional.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [ ] GIVEN valid ReportData WHEN `generate_report()` called THEN HTML file created — blocked by functional gaps (zoom + diff mode).
- [ ] GIVEN `config.embed_images=True` THEN images base64 encoded — covered by tests.
- [ ] GIVEN `config.embed_images=False` THEN images use relative paths — covered by tests.
- [ ] GIVEN `config.include_filmstrip=True` THEN filmstrip present — covered by tests.
- [ ] GIVEN empty clips THEN `ReportError("no clips provided")` — covered by tests.
- [ ] GIVEN 1 clip THEN `ReportError("at least 2 clips required for comparison")` — covered by tests.
- [ ] GIVEN any screenshots validation failure THEN `ReportError("no screenshots provided")` — covered by tests.
- [ ] GIVEN missing screenshot file THEN `ReportError("screenshot not found: {path}")` — covered by tests.
- [ ] GIVEN OSError reading image THEN `ReportError("failed to encode image: {path}")` — covered by tests.
- [ ] GIVEN OSError writing file THEN `ReportError("failed to write report: {reason}")` — covered by tests.
- [ ] HTML includes dark theme CSS variables per spec Section 3.1 — covered by tests.
- [ ] HTML includes keyboard handlers per spec Section 6 — missing `?`/`Escape` handlers.
- [ ] HTML includes ARIA labels per spec Section 8 — incomplete vs Section 8.1/8.3.
- [ ] Embedded JSON preserves `data.clips` and `data.frames` order — logic ok, but spec value mismatch for `default_mode`.

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Implement zoom scaling per spec (bind `--zoom-level` to `.rv-canvas` transform).
  2. Correct diff-mode cycling so click/ArrowUp/Down updates the compare clip (and renders accordingly).
  3. Add keyboard help modal with `?`/`Escape` support and focus management per spec.
  4. Apply missing ARIA roles/attributes and alt text formatting per spec Section 8.
  5. Resolve `default_mode` spec mismatch (`diff` vs `difference`) in SSOT or code.
  6. Align filmstrip sizing to SSOT (or update SSOT with justification).
- Re-submit for review

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-4__report-service

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v3.md
2. Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v3.md
3. Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-4__report-service/impl-v3.md
