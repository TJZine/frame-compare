---
RUN_ID: 2026-01-02__p5-3__publishers
VERSION: v4
TARGET: Phase 5 → Item 5.3 (Publishers)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md
---

# Implementation Plan: Publishers Service (slow.pics)

## Changes Since plan-v3

1. **Fixed delete-on-error test structure:**
   - `test_publish_to_slowpics_delete_after_upload_does_not_delete_on_error` now uses `with pytest.raises(SlowpicsUnavailableError):` wrapper, then asserts PNGs remain after the `with` block

2. **Specified visibility conversion:**
   - Use `visibility = config.visibility.value` (gets string value from Enum)
   - Added test assertion for visibility in `test_publish_to_slowpics_uses_correct_visibility`

---

## Context

**Phase:** 5
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 4)
**Dependencies:**

- `SlowpicsConfig` exists in `src/frame_compare/config/schema.py`
- Error hierarchy exists in `src/frame_compare/errors.py`
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

## Contract Impact

**Contracts touched:** NO

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

**Types to define (per SSOT Section 4.1):**

- `PublishResult` — frozen dataclass with fields: `url: str`, `screenshot_count: int`, `upload_duration_seconds: float`

**Public API (signatures per SSOT Section 4.2):**

- `async def publish_to_slowpics(screenshot_dir: Path, config: SlowpicsConfig, client: httpx.AsyncClient, metadata: TmdbMetadata | None = None, progress: ProgressReporter | None = None) -> PublishResult`

**Class (per SSOT Section 4.2):**

- `SlowpicsPublisher`
  - `__init__(self, config: SlowpicsConfig, client: httpx.AsyncClient)` — stores `_client`
  - `async def upload(self, files: list[Path], title: str | None = None) -> str`
  - No `close()` method

**Private helpers (per SSOT Section 4.3):**

- `async def _prepare_upload(files: list[Path], title: str | None, visibility: str) -> dict`
- `async def _upload_with_retry(client: httpx.AsyncClient, data: dict, max_retries: int, timeout_seconds: float) -> httpx.Response`

**Implementation details (per SSOT Section 4.2 & 4.3):**

1. **URL constant:** `SLOWPICS_UPLOAD_URL = "https://slow.pics/api/comparison"`

2. **File collection:** `sorted(screenshot_dir.glob("*.png"))` for determinism

3. **Title selection (per SSOT):**
   - `title = metadata.title if metadata else screenshot_dir.name`

4. **Visibility conversion:**
   - `visibility = config.visibility.value` (extracts string from Enum, e.g., `"unlisted"`)

5. **Deletion semantics (per SSOT):**
   - If `config.delete_after_upload is True`:
     - Delete PNG files ONLY after successful upload + URL parse
     - NEVER delete on any error or exception
     - Use the same sorted file list as upload

6. **Retry configuration (per SSOT Section 4.3):**
   - `max_attempts = config.max_retries` (default 3)
   - `initial_delay = 1.0` seconds
   - `max_delay = 30.0` seconds
   - `exponential_base = 2.0`
   - `jitter_factor = 0.1`
   - **Jitter formula:** `delay * (1.0 + random.uniform(-jitter_factor, jitter_factor))`

7. **Retryable vs fail-fast (per SSOT table):**
   - HTTP 429 → Retry with `Retry-After` header (default 60s)
   - HTTP 5xx → Retry with exponential backoff
   - HTTP 4xx (except 429) → Fail immediately
   - Timeout → Retry with exponential backoff

8. **Error mapping:**
   - HTTP 429 after retries → `SlowpicsRateLimitedError`
   - HTTP 5xx after retries → `SlowpicsUnavailableError`
   - Other failures → `SlowpicsError`
   - No PNG files found → `SlowpicsError("No PNG files found in {directory}")`

---

### 2. `src/frame_compare/services/__init__.py` [MODIFY]

**Changes:**

```python
from frame_compare.services.publishers import (
    PublishResult,
    SlowpicsPublisher,
    publish_to_slowpics,
)

__all__ = [
    # ... existing exports ...
    "PublishResult",
    "SlowpicsPublisher",
    "publish_to_slowpics",
]
```

---

### 3. `tests/services/test_publishers.py` [NEW]

**Purpose:** Unit tests for slow.pics publishing

**Deterministic test fixtures:**

```python
@pytest.fixture
def mock_sleep(mocker):
    return mocker.patch(
        "frame_compare.services.publishers.asyncio.sleep",
        new_callable=lambda: AsyncMock(return_value=None),
    )

@pytest.fixture
def mock_jitter(mocker):
    return mocker.patch(
        "frame_compare.services.publishers.random.uniform",
        return_value=0.0,
    )

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

**Tests required:**

| Test | Description | Key Assertions |
|------|-------------|----------------|
| `test_publish_to_slowpics_success_returns_url` | Mock 200 response | `result.url == "https://slow.pics/c/abc123"`, `result.screenshot_count == 2` |
| `test_publish_to_slowpics_rate_limited_raises_error` | Mock 429 response | `pytest.raises(SlowpicsRateLimitedError)` |
| `test_publish_to_slowpics_server_error_raises_unavailable` | Mock 503 after retries | `pytest.raises(SlowpicsUnavailableError)`, `mock_sleep.await_count == 2` |
| `test_publish_to_slowpics_timeout_raises_error` | Mock timeout | `pytest.raises(SlowpicsError)`, `"timed out" in str(exc.value)` |
| `test_publish_to_slowpics_retry_success` | Mock 503 then 200 | `result.url == "https://slow.pics/c/abc123"`, `mock_sleep.await_count == 1` |
| `test_publish_to_slowpics_4xx_fails_immediately` | Mock 400 response | `pytest.raises(SlowpicsError)`, `mock_sleep.await_count == 0` |
| `test_publish_to_slowpics_uses_metadata_title` | Verify title from metadata | Mock `_prepare_upload`, assert `title == metadata.title` |
| `test_publish_to_slowpics_default_title_uses_directory_name` | Verify fallback title | Mock `_prepare_upload`, assert `title == screenshot_dir.name` |
| `test_publish_to_slowpics_uses_correct_visibility` | Verify visibility conversion | Mock `_prepare_upload`, assert `visibility == config.visibility.value` (e.g., `"unlisted"`) |
| `test_publish_to_slowpics_empty_dir_raises_error` | Empty directory | `pytest.raises(SlowpicsError)`, `"No PNG files found" in str(exc.value)` |
| `test_publish_to_slowpics_delete_after_upload_deletes_files_on_success` | Delete on success | `config.delete_after_upload=True`, after 200: `assert not any(screenshot_dir.glob("*.png"))` |
| `test_publish_to_slowpics_delete_after_upload_does_not_delete_on_error` | No delete on failure | See structure below |
| `test_slowpics_publisher_upload_returns_url` | Test class method | `result == "https://slow.pics/c/abc123"` |
| `test_slowpics_publisher_does_not_own_client` | Verify no close | `assert not async_client.is_closed` after use |

**Delete-on-error test structure (per plan-review-v3):**

```python
@pytest.mark.anyio
async def test_publish_to_slowpics_delete_after_upload_does_not_delete_on_error(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    # Setup: mock 503 to trigger SlowpicsUnavailableError after retries
    respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(503)
    )
    config = SlowpicsConfig(delete_after_upload=True, max_retries=1)

    # Act + Assert exception
    with pytest.raises(SlowpicsUnavailableError):
        await publish_to_slowpics(screenshot_dir, config, async_client)

    # Assert files remain after exception
    assert len(list(screenshot_dir.glob("*.png"))) == 2
```

**Test markers:** `@pytest.mark.anyio` for all async tests

---

### 4. `docs/DECISIONS.md` [MODIFY]

**Required facts to record:**

- RUN_ID: `2026-01-02__p5-3__publishers`
- Scope: slow.pics publisher with injected HTTP client, title/visibility/deletion semantics
- SSOT edits: Updated `services-module.md` Section 4.2 with title selection and deletion semantics
- Verification gates: pyright, ruff, pytest, lint-imports

---

### 5. `CHANGELOG.md` [MODIFY]

**Content:** Add entry noting slow.pics publishing capability added

---

## Acceptance Criteria

- [ ] GIVEN a directory with PNG screenshots WHEN `publish_to_slowpics` is called THEN it returns a `PublishResult` with valid URL
- [ ] GIVEN slow.pics returns 429 WHEN uploading THEN `SlowpicsRateLimitedError` is raised
- [ ] GIVEN slow.pics returns 5xx WHEN uploading after retries THEN `SlowpicsUnavailableError` is raised
- [ ] GIVEN a 5xx followed by 200 WHEN uploading THEN retry logic recovers and returns URL
- [ ] GIVEN HTTP 4xx (not 429) WHEN uploading THEN fails immediately without retry
- [ ] GIVEN `metadata=None` WHEN publishing THEN title equals `screenshot_dir.name`
- [ ] GIVEN `config.visibility = Visibility.UNLISTED` WHEN publishing THEN visibility sent equals `"unlisted"`
- [ ] GIVEN `config.delete_after_upload=True` and success WHEN publishing THEN PNG files are deleted
- [ ] GIVEN `config.delete_after_upload=True` and failure WHEN publishing THEN PNG files remain
- [ ] GIVEN `SlowpicsPublisher` WHEN used and completed THEN injected client remains open
- [ ] GIVEN an empty screenshot directory WHEN publishing THEN `SlowpicsError` is raised

---

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md

# Quality gates
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# Import layering
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

---

## Notes for Coding Agent

1. **Visibility conversion:** `visibility = config.visibility.value`

2. **Title selection:** `title = metadata.title if metadata else screenshot_dir.name`

3. **Deletion (only on success):**

   ```python
   # After successful upload + URL parse
   if config.delete_after_upload:
       for file in files:
           file.unlink()
   ```

4. **Import requirements:** `asyncio`, `random`, `time`, `Path`, `dataclass`, `httpx`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__p5-3__publishers

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__p5-3__publishers/plan-review-v4.md
