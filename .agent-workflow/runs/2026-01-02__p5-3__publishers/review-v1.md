---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v1
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/verify-v1.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v1.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Publishers Service (slow.pics)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-02
**Files Reviewed:** 11
**Commit Subject:** `feat(services): add slow.pics publishers service`

> [!NOTE]
> The commit subject must summarize the entire checklist item, not just the review phase.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md

$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q --ignore tests/vs/
317 passed, 1 skipped
Required test coverage of 80.0% reached. Total coverage: 83.17%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Files Reviewed
- .agent-workflow/runs/2026-01-02__p5-3__publishers/verify-v1.md
- .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v1.md
- .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
- .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- src/frame_compare/services/publishers.py
- tests/services/test_publishers.py
- src/frame_compare/services/__init__.py
- tests/vs/test_exports.py
- tests/vs/test_tonemap.py
- docs/DECISIONS.md

## Checklist Results

### Correctness

- [x] Core upload, retry, and deletion logic implemented
- [ ] Issue: retry attempt semantics do not match SSOT
- [ ] Issue: public class method signature deviates from SSOT
- [ ] Issue: out-of-plan modifications to `tests/vs/*` files

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Errors are mapped to Slowpics* hierarchy

### Testing

- [x] Unit tests cover success, retry, deletion, and rate limits
- [ ] Issue: tests encode off-by-one retry behavior that conflicts with SSOT

### Documentation

- [x] Decision log updated
- [x] Changelog updated

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **Out-of-plan modifications to `tests/vs/*`**
   - Location: `tests/vs/test_exports.py:7`, `tests/vs/test_tonemap.py:9`
   - Issue: These files were modified but are not listed in the approved plan. Non-plan changes are not allowed unless they are auto-generated artifacts (these are not).
   - Fix: Revert these changes or move them to a separate, explicitly planned run.

2. **Retry attempt count is off-by-one vs SSOT**
   - Location: `src/frame_compare/services/publishers.py:185` through `src/frame_compare/services/publishers.py:260`
   - Issue: SSOT specifies `max_attempts = config.max_retries`, but the current loop allows `max_retries + 1` attempts by checking `attempt > max_retries`. This changes retry timing and breaks the spec’s retry model.
   - Fix: Align retry semantics to SSOT by treating `max_retries` as total attempts. Update tests to expect the corrected sleep counts and failure timing.

3. **SlowpicsPublisher.upload signature drift**
   - Location: `src/frame_compare/services/publishers.py:42`
   - Issue: SSOT defines `upload(self, files: list[Path], title: str | None = None) -> str`, but implementation adds `progress: ProgressReporter | None = None`. This is a public API deviation.
   - Fix: Remove the `progress` parameter from `SlowpicsPublisher.upload` and handle progress reporting in `publish_to_slowpics` if needed.

### Minor (Should Fix)

1. **Test expectations encode the off-by-one retry behavior**
   - Location: `tests/services/test_publishers.py:49` and `tests/services/test_publishers.py:70`
   - Issue: Tests assert sleep counts that assume `max_retries + 1` attempts (e.g., `mock_sleep.await_count == 2` for `max_retries=2`). These should be adjusted to match SSOT’s `max_attempts = max_retries`.
   - Fix: Update tests after fixing retry semantics.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN a directory with PNG screenshots WHEN `publish_to_slowpics` is called THEN it returns a `PublishResult` with valid URL — ✓ Verified
- [x] GIVEN slow.pics returns 429 WHEN uploading THEN `SlowpicsRateLimitedError` is raised — ✓ Verified
- [x] GIVEN slow.pics returns 5xx WHEN uploading after retries THEN `SlowpicsUnavailableError` is raised — ⚠️ Retry semantics need SSOT alignment
- [x] GIVEN a 5xx followed by 200 WHEN uploading THEN retry logic recovers and returns URL — ⚠️ Retry semantics need SSOT alignment
- [x] GIVEN HTTP 4xx (not 429) WHEN uploading THEN fails immediately without retry — ✓ Verified
- [x] GIVEN `metadata=None` WHEN publishing THEN title equals `screenshot_dir.name` — ✓ Verified
- [x] GIVEN `config.visibility = Visibility.UNLISTED` WHEN publishing THEN visibility sent equals `"unlisted"` — ✓ Verified
- [x] GIVEN `config.delete_after_upload=True` and success WHEN publishing THEN PNG files are deleted — ✓ Verified
- [x] GIVEN `config.delete_after_upload=True` and failure WHEN publishing THEN PNG files remain — ✓ Verified
- [x] GIVEN `SlowpicsPublisher` WHEN used and completed THEN injected client remains open — ✓ Verified
- [x] GIVEN an empty screenshot directory WHEN publishing THEN `SlowpicsError` is raised — ✓ Verified

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Revert or isolate the `tests/vs/*` changes into a separate, planned run.
  2. Align retry attempt semantics to SSOT (`max_attempts = config.max_retries`) and update tests accordingly.
  3. Remove `progress` from `SlowpicsPublisher.upload` to match SSOT, and keep progress handling in `publish_to_slowpics` if needed.
- Re-submit for review.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-3__publishers

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
2. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
3. Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v2.md
