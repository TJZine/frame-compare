---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v2
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v2.md
---

# Plan Review Report: Publishers Service (slow.pics)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: slow.pics publisher + tests + docs updates. |
| 2 | Dependencies | PASS | SSOT now reconciles DI with `async-semantics.md` “Golden Rule”; injected client signatures match. |
| 3 | File List | PASS | File list is explicit and minimal. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | PASS | Public signatures listed and match anchored SSOT headings. |
| 6 | Tests Complete | FAIL | Two SSOT-implied behaviors are still unspecified/test-unstated: (a) “Optionally delete local files” (config-driven) and (b) default title behavior when `metadata is None`. Plan currently leaves these as implementation decisions. |
| 7 | Verification Complete | PASS | Canonical gates listed (pyright/ruff/pytest + lint-imports + validate_spec_anchors). |
| 8 | Decision-Minimizing | FAIL | Coding Agent must choose deletion semantics and default title semantics. |
| 9 | Determinism Defined | PASS | Retry jitter formula defined and test strategy patches `asyncio.sleep` + jitter source. |

## Additional Quality Checks

- Error Codes: OK (uses existing `SlowpicsError`/`SlowpicsRateLimitedError`/`SlowpicsUnavailableError`).
- Failure Modes: OK for retryable vs fail-fast mapping; missing for delete/title semantics (see required edits).
- Derived Outputs: OK (none).
- Rollback Guidance: OK.
- SSOT Update Audit (this loop): OK — `services-module.md` updates to injected client + retry spec are consistent with `async-semantics.md` and are implementable.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. What title is sent to slow.pics when `metadata is None` (and whether/when `title` is omitted).
2. What “Optionally delete local files” means (exact config flag, when deletion occurs, and failure behavior).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT for default title + delete_after_upload**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`
   - Under heading: `### 4.2 Public API`
   - Required changes (minimal bullets inside `publish_to_slowpics` docstring):
     - **Title selection:** If `metadata is not None`, use `metadata.title`; otherwise use `screenshot_dir.name` as the title.
     - **Deletion semantics:** If `config.delete_after_upload` is true, delete the PNG files **only after** a successful upload + URL parse; never delete on any error/exception.

2. **Update plan + tests to cover the new SSOT behaviors**
   - File: `.agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v3.md`
   - Required plan changes:
     - Add/adjust tests with exact names and assertions:
       - `test_publish_to_slowpics_default_title_uses_directory_name` — ensure the computed title equals `screenshot_dir.name` when `metadata is None` (avoid brittle multipart-body parsing; use a targeted seam such as asserting the computed title passed into `_prepare_upload`).
       - `test_publish_to_slowpics_delete_after_upload_deletes_files_on_success` — with `config.delete_after_upload=True`, ensure PNGs are deleted after a mocked 200 upload.
       - `test_publish_to_slowpics_delete_after_upload_does_not_delete_on_error` — with `delete_after_upload=True` and a mocked failure, ensure PNGs remain.
     - Ensure the code-path for deleting uses the same sorted file list used for upload determinism.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-3__publishers

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- Under heading: "### 4.2 Public API" add/change:
  - In `publish_to_slowpics` docstring, define title selection: `metadata.title` if metadata provided, else `screenshot_dir.name`.
  - In `publish_to_slowpics` docstring, define deletion semantics for `config.delete_after_upload`: delete PNG files only after success; never delete on failure.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v2.md
Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
