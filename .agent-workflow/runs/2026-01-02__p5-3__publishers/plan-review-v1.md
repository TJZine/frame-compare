---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v1
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v1.md
---

# Plan Review Report: Publishers Service (slow.pics)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: slow.pics publisher + unit tests + docs updates. |
| 2 | Dependencies | FAIL | Hard SSOT conflict: `services-module.md` “4.2 Public API” defines `SlowpicsPublisher` owning an `httpx.AsyncClient` (and `publish_to_slowpics` without injected client), but `async-semantics.md` “7. HTTP Client Lifecycle Rules” forbids services creating their own client. Plan chooses injected-client API not reflected in SSOT. |
| 3 | File List | PASS | Explicit file list. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | FAIL | Public signatures in plan do not match anchored SSOT (notably `publish_to_slowpics(..., client: httpx.AsyncClient, ...)`). |
| 6 | Tests Complete | FAIL | Retry logic includes jitter + `asyncio.sleep`; plan does not specify deterministic/no-sleep testing strategy (patching `asyncio.sleep` / jitter source), leaving a Coding Agent decision and risking slow/flaky tests. |
| 7 | Verification Complete | FAIL | Verification commands are not canonical (scoped `pyright`/`ruff` and `pytest -v` instead of canonical `.venv/bin/*` gates). |
| 8 | Decision-Minimizing | FAIL | Multiple implementation/test decisions remain (DI vs owned client; retryable conditions; sleep/jitter mocking; “does not close client” assertion shape). |
| 9 | Determinism Defined | FAIL | Deterministic retry behavior for unit tests is not defined (jitter/randomness and sleeps). |

## Additional Quality Checks

- Error Codes: OK (uses existing `SlowpicsError`/`SlowpicsRateLimitedError`/`SlowpicsUnavailableError`).
- Failure Modes: Issue — plan doesn’t specify which failures are retryable vs fail-fast (e.g., 5xx retryable; 4xx except 429 fail-fast).
- Derived Outputs: OK (none).
- Rollback Guidance: OK (return to Planning on SSOT mismatch).
- SSOT Update Audit (if SSOT changed this loop): N/A (plan-v1 claims “SSOT edits: none”, but SSOT edits are required to approve).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Whether `publish_to_slowpics` / `SlowpicsPublisher` accept an injected `httpx.AsyncClient` vs owning one (SSOT conflict).
2. Retry loop details (which statuses/exceptions retry, how jitter is computed).
3. How unit tests avoid real `asyncio.sleep` and nondeterministic jitter.
4. What “publisher does not close injected client” means as an assertion (`async_client.is_closed` vs mocking `aclose`).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Update SSOT to reconcile publishers API with HTTP client DI**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`
   - Under heading: `### 4.2 Public API`
   - Required changes (minimal SSOT-level bullets):
     - Update `publish_to_slowpics` signature to include `client: httpx.AsyncClient` parameter.
     - Update `SlowpicsPublisher.__init__` signature to `def __init__(self, config: SlowpicsConfig, client: httpx.AsyncClient):` and store injected client (not owned).
     - Remove the `close()` method from `SlowpicsPublisher` (client is managed by orchestration).
     - Add an explicit statement mirroring `async-semantics.md` “Golden Rule”: publishers MUST NOT create their own `httpx.AsyncClient`.

2. **Align plan signatures with updated SSOT**
   - File: `.agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v2.md`
   - Required changes:
     - Ensure all public signatures match the updated SSOT exactly (especially `publish_to_slowpics(..., client: httpx.AsyncClient, ...)` and `SlowpicsPublisher.__init__(..., client: httpx.AsyncClient)`).
     - Ensure `services/__init__.py` export list matches the final symbol locations (`PublishResult` source file stated explicitly).

3. **Make retry + tests deterministic**
   - File: `.agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v2.md`
   - Required changes:
     - Specify the exact jitter formula used in `_upload_with_retry` (e.g., `delay * (1 + random.uniform(-jitter, jitter))`).
     - Specify unit test strategy to avoid real sleeps:
       - Patch `frame_compare.services.publishers.asyncio.sleep` to an async no-op, and
       - Patch the jitter source (`random.uniform` or equivalent) to return `0.0` for deterministic delays.
     - Add/update at least one retry test assertion to confirm `asyncio.sleep` was awaited the expected number of times.

4. **Use canonical verification gates**
   - Section: `## Verification Commands`
   - Required changes (plan-v2):
     - Replace scoped commands with:
       - `.venv/bin/pyright --warnings`
       - `.venv/bin/ruff check .`
       - `.venv/bin/pytest -q`
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-3__publishers

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- Under heading: "### 4.2 Public API" add/change:
  - Update `publish_to_slowpics` signature to include `client: httpx.AsyncClient`.
  - Update `SlowpicsPublisher.__init__` to accept `client: httpx.AsyncClient` (injected, not owned) and store it as `_client`.
  - Remove `SlowpicsPublisher.close()` from the public API; client lifecycle is managed externally.
  - Add an explicit note that publishers MUST NOT create their own `httpx.AsyncClient` (align with `async-semantics.md` Section 7 “Golden Rule”).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v1.md
Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
