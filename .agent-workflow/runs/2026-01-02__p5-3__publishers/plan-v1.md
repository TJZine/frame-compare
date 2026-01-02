---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v1
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v1.md
---

# Implementation Plan: Publishers Service (slow.pics)

## Context

**Phase:** 5
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 4)
**Dependencies:**

- `SlowpicsConfig` exists in `src/frame_compare/config/schema.py`
- Error hierarchy exists in `src/frame_compare/errors.py` (`SlowpicsError`, `SlowpicsRateLimitedError`, `SlowpicsUnavailableError`)
- `ProgressReporter` Protocol exists in `src/frame_compare/utils/progress.py`
- `TmdbMetadata` exists in `src/frame_compare/services/types.py`

## Scope

This plan covers:

- [x] Create `src/frame_compare/services/publishers.py`
- [x] Implement `SlowpicsPublisher` class with injected HTTP client
- [x] Implement `publish_to_slowpics` convenience function
- [x] Implement retry logic with exponential backoff
- [x] Handle rate limiting (HTTP 429)
- [x] Write unit tests for publishers (mocked network)

This plan does NOT cover:

- Report generation (Phase 5.4)
- Dolby Vision service (Phase 5.5)
- Local-only mode (simple fallback, handled naturally by not calling upload)

## Contract Impact

**Contracts touched:** NO

This plan does not modify any canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "4. Publishers Service"
  - Section: "4.1 Types"
  - Section: "4.2 Public API"
  - Section: "4.3 Implementation Details"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md`:
  - Section: "1. Timeout Policy"
  - Section: "2. Retry Configuration"
  - Section: "5. slow.pics Specifics"
  - Section: "7. HTTP Client Lifecycle Rules"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "4.2 External API Mocking"

---

## Files to Create/Modify

### 1. `src/frame_compare/services/publishers.py` [NEW]

**Purpose:** slow.pics upload service with retry logic and rate limit handling

**Types to define:**

- `PublishResult` — dataclass with `url: str`, `screenshot_count: int`, `upload_duration_seconds: float`

**Functions to implement (spec-anchored):**

- `publish_to_slowpics(screenshot_dir: Path, config: SlowpicsConfig, client: httpx.AsyncClient, metadata: TmdbMetadata | None = None, progress: ProgressReporter | None = None) -> PublishResult`
- `_prepare_upload(files: list[Path], title: str | None, visibility: str) -> dict`
- `_upload_with_retry(client: httpx.AsyncClient, data: dict, max_retries: int, timeout_seconds: float) -> httpx.Response`

**Class to implement:**

- `SlowpicsPublisher` — async publisher with injected HTTP client (per async-semantics.md Section 7)
  - Constructor: `__init__(self, config: SlowpicsConfig, client: httpx.AsyncClient)`
  - Method: `async def upload(self, files: list[Path], title: str | None = None) -> str`

**Implementation details (per SSOT spec):**

1. **URL constant:** `SLOWPICS_UPLOAD_URL = "https://slow.pics/api/comparison"`

2. **File collection:** Collect all `*.png` files from `screenshot_dir`, sorted by name for determinism

3. **Multipart upload format:** Build multipart form data with:
   - `title`: comparison title (from metadata.title or default)
   - `visibility`: from config (public/unlisted/private)
   - `images[]`: binary PNG data for each file

4. **Retry with exponential backoff** (per async-semantics.md Section 2):
   - `max_attempts = config.max_retries` (default 3)
   - `initial_delay = 1.0s`
   - `max_delay = 30.0s`
   - `exponential_base = 2.0`
   - `jitter = 0.1` (±10% randomization)

5. **Rate limiting handling** (per async-semantics.md Section 5.1):
   - On HTTP 429, read `Retry-After` header (default 60s)
   - Raise `SlowpicsRateLimitedError` if retries exhausted

6. **Error mapping:**
   - HTTP 429 → `SlowpicsRateLimitedError`
   - HTTP 5xx → `SlowpicsUnavailableError`
   - Other failures after retries → `SlowpicsError`
   - Timeout → `SlowpicsError` with "Upload timed out" message

7. **Response parsing:** Extract comparison URL from JSON response (expected key: `"url"`)

8. **Progress reporting:** Use `progress.start_phase("Uploading to slow.pics", len(files))` and `progress.advance()` per file

9. **Client lifecycle:** Service MUST NOT create its own `httpx.AsyncClient` — it is injected and not owned (per async-semantics.md Section 7)

---

### 2. `src/frame_compare/services/__init__.py` [MODIFY]

**Purpose:** Export new publisher types and functions

**Changes:**

- Add import: `from frame_compare.services.publishers import SlowpicsPublisher, publish_to_slowpics, PublishResult`
- Add to `__all__`: `"SlowpicsPublisher"`, `"publish_to_slowpics"`, `"PublishResult"`

---

### 3. `tests/services/test_publishers.py` [NEW]

**Purpose:** Unit tests for slow.pics publishing

**Tests required:**

- `test_publish_to_slowpics_success_returns_url` — Mock 200 response with URL, verify `PublishResult.url` matches
- `test_publish_to_slowpics_rate_limited_raises_error` — Mock 429 response, verify `SlowpicsRateLimitedError` raised
- `test_publish_to_slowpics_server_error_raises_unavailable` — Mock 503 response after retries, verify `SlowpicsUnavailableError`
- `test_publish_to_slowpics_timeout_raises_error` — Mock timeout, verify `SlowpicsError` with "timed out" message
- `test_publish_to_slowpics_retry_success` — Mock failure then success, verify retry logic recovers and returns URL
- `test_publish_to_slowpics_uses_metadata_title` — Verify title from metadata is passed to upload
- `test_publish_to_slowpics_empty_dir_raises_error` — Verify `SlowpicsError` when no PNG files found
- `test_slowpics_publisher_upload_returns_url` — Test `SlowpicsPublisher.upload()` method directly
- `test_slowpics_publisher_does_not_own_client` — Verify publisher does not close injected client

**Fixtures:**

```python
@pytest.fixture
def mock_slowpics_success(respx_mock):
    respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(200, json={"url": "https://slow.pics/c/abc123"})
    )
    return respx_mock

@pytest.fixture
def screenshot_dir(tmp_path: Path) -> Path:
    dir_path = tmp_path / "screenshots"
    dir_path.mkdir()
    (dir_path / "test_00001.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    (dir_path / "test_00002.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return dir_path

@pytest.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client
```

**Test markers:** `@pytest.mark.anyio` for all async tests

---

### 4. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append a run decision entry

**Required facts to record:**

- RUN_ID: `2026-01-02__p5-3__publishers`
- Artifact versions: plan-v1, plan-review-v1, impl-v1, verify-v1, review-v1
- Scope: slow.pics publisher service implementation
- Out of scope: report generation, dovi service, local-only mode
- SSOT edits: none (spec already complete)
- Verification gates: pyright, ruff, pytest, lint-imports

---

### 5. `CHANGELOG.md` [MODIFY]

**Purpose:** Add short entry for publishers implementation

**Content:** Add entry under Phase 5 noting slow.pics publishing capability added

---

## Acceptance Criteria

- [ ] GIVEN a directory with PNG screenshots WHEN `publish_to_slowpics` is called THEN it returns a `PublishResult` with valid URL
- [ ] GIVEN slow.pics returns 429 WHEN uploading THEN `SlowpicsRateLimitedError` is raised
- [ ] GIVEN slow.pics returns 5xx WHEN uploading after retries THEN `SlowpicsUnavailableError` is raised
- [ ] GIVEN a failed attempt followed by success WHEN uploading THEN retry logic recovers and returns URL
- [ ] GIVEN `SlowpicsPublisher` WHEN constructed with injected client THEN it does not close the client on completion
- [ ] GIVEN an empty screenshot directory WHEN publishing THEN `SlowpicsError` is raised with descriptive message

---

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v1.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/services
.venv/bin/ruff check src/frame_compare/services
.venv/bin/pytest -v tests/services/test_publishers.py

# Import layering
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

---

## Notes for Coding Agent

1. **Client injection pattern:** Follow the exact pattern from `metadata.py` — the `httpx.AsyncClient` is passed to functions, not created internally. This matches async-semantics.md Section 7 "Golden Rule".

2. **Retry implementation:** Use a simple loop with `asyncio.sleep()` for delays. Calculate delay as `min(initial_delay * (exponential_base ** attempt), max_delay)` with jitter.

3. **File ordering:** Sort PNG files by filename for deterministic upload order. Use `sorted(screenshot_dir.glob("*.png"))`.

4. **Multipart form:** Use `httpx`'s built-in multipart support. Files should be passed as a list of tuples: `[("images[]", (filename, content, "image/png"))]`.

5. **Duration tracking:** Use `time.perf_counter()` around the upload call to measure `upload_duration_seconds`.

6. **Progress integration:** Import `ProgressReporter` from `frame_compare.utils.progress`. Handle `None` progress gracefully.

7. **Error messages:** Include descriptive context in error messages (e.g., "Upload timed out after 60.0s", "No PNG files found in {directory}").

8. **Import order:** Ensure proper import ordering for Ruff (standard library, third-party, local).

---

> **Proposed RUN_ID:** 2026-01-02__p5-3__publishers
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2026-01-02__p5-3__publishers` before running Plan Review Agent.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__p5-3__publishers

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v1.md
