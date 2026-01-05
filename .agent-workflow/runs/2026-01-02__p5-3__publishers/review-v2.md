---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v2
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/verify-v2.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v2.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v2.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Publishers Service (slow.pics)

## Verdict: APPROVED

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
Required test coverage of 80.0% reached. Total coverage: 82.66%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Files Reviewed
- .agent-workflow/runs/2026-01-02__p5-3__publishers/verify-v2.md
- .agent-workflow/runs/2026-01-02__p5-3__publishers/impl-v2.md
- .agent-workflow/runs/2026-01-02__p5-3__publishers/review-v1.md
- .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
- .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- src/frame_compare/services/publishers.py
- tests/services/test_publishers.py
- src/frame_compare/services/__init__.py
- tests/vs/test_exports.py
- tests/vs/test_tonemap.py

## Checklist Results

### Correctness

- [x] Implements all acceptance criteria
- [x] Retry semantics align with SSOT (`max_attempts = config.max_retries`)
- [x] SlowpicsPublisher public API matches SSOT
- [x] No out-of-plan file changes remain

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Error hierarchy used

### Testing

- [x] Tests cover retry, rate-limit, deletion semantics, and client ownership
- [x] Updated retry sleep expectations

### Documentation

- [x] Decisions and changelog updated

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

None.

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN a directory with PNG screenshots WHEN `publish_to_slowpics` is called THEN it returns a `PublishResult` with valid URL — ✓ Verified
- [x] GIVEN slow.pics returns 429 WHEN uploading THEN `SlowpicsRateLimitedError` is raised — ✓ Verified
- [x] GIVEN slow.pics returns 5xx WHEN uploading after retries THEN `SlowpicsUnavailableError` is raised — ✓ Verified
- [x] GIVEN a 5xx followed by 200 WHEN uploading THEN retry logic recovers and returns URL — ✓ Verified
- [x] GIVEN HTTP 4xx (not 429) WHEN uploading THEN fails immediately without retry — ✓ Verified
- [x] GIVEN `metadata=None` WHEN publishing THEN title equals `screenshot_dir.name` — ✓ Verified
- [x] GIVEN `config.visibility = Visibility.UNLISTED` WHEN publishing THEN visibility sent equals "unlisted" — ✓ Verified
- [x] GIVEN `config.delete_after_upload=True` and success WHEN publishing THEN PNG files are deleted — ✓ Verified
- [x] GIVEN `config.delete_after_upload=True` and failure WHEN publishing THEN PNG files remain — ✓ Verified
- [x] GIVEN `SlowpicsPublisher` WHEN used and completed THEN injected client remains open — ✓ Verified
- [x] GIVEN an empty screenshot directory WHEN publishing THEN `SlowpicsError` is raised — ✓ Verified

## Next Steps

### If APPROVED

- ✅ Phase 5.3 Publishers Service complete
- ➡️ Proceed to next unchecked checklist item

## NEXT AGENT PROMPT (COPY/PASTE)

### ✅ Run Complete: 2026-01-02__p5-3__publishers

**Orchestrator Actions:**
1. Commit the changes:
    ```bash
   git add -A
   git commit -m "feat(services): add slow.pics publishers service" \
     -m "Run: 2026-01-02__p5-3__publishers" \
     -m "Closes Phase 5 Item 5.3"
   ```

2. Verify master checklist is updated
3. Pick the next unchecked item from the checklist

---

### To Start Next Run

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID

NEW_RUN_ID
(ORCHESTRATOR: replace `NEW_RUN_ID` with the next run’s confirmed RUN_ID before running the Planning Agent)

## Target

Pick the next unchecked checklist item (Planning Agent will read the checklist).

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Pick the next unchecked checklist item and create a detailed Implementation Plan.

## Output

Write file: .agent-workflow/runs/NEW_RUN_ID/plan-v1.md
