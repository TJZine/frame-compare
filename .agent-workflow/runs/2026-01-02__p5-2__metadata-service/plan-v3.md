---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v3
TARGET: Phase 5 → Item 5.2
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v2.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v3.md
---

# Implementation Plan: Metadata Service

## Changes Since plan-v2

- Added Spec Anchor: `testing-strategy.md` Section "3.1 Pytest Configuration"
- Specified async test mechanics: all `test_lookup_tmdb_*` and `test_resolve_metadata_*` are `async def` with `@pytest.mark.anyio`
- Added concrete fixture shape for injected `httpx.AsyncClient` in tests

## Context

**Phase:** 5
**Module:** `frame_compare.services.metadata`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` Section 3
**Dependencies:** Phase 5.1 (Audio Alignment) complete; requires new dependencies `guessit` and `anitopy`

## Scope

This plan covers:

- [x] Add `guessit` and `anitopy` dependencies to `pyproject.toml`
- [x] Add metadata types to `services/types.py`
- [x] Create `src/frame_compare/services/metadata.py`
- [x] Update `services/__init__.py` exports
- [x] Create unit tests in `tests/services/test_metadata.py`

This plan does NOT cover:

- Publishers service (Phase 5.3)
- Report service (Phase 5.4)
- Integration tests with real TMDB API (mocked)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "3. Metadata Service"
  - Section: "3.1 Types"
  - Section: "3.2 Public API"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md`:
  - Section: "6. TMDB Specifics"
  - Section: "7. HTTP Client Lifecycle Rules"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"
  - Section: "3.1 Pytest Configuration"

## Files to Create/Modify

### 1. `pyproject.toml` (MODIFY)

**Purpose:** Add required filename parsing dependencies

**Changes:**

- Add `guessit>=3.8.0` to `dependencies`
- Add `anitopy>=2.2.0` to `dependencies`

### 2. `src/frame_compare/services/types.py` (MODIFY)

**Purpose:** Add metadata types (spec-anchored in Section 3.1)

**Types to add:**

| Type | Fields |
|------|--------|
| `ParsedMetadata` | title, year, season, episode, release_group, source, resolution |
| `TmdbMetadata` | tmdb_id, title, original_title, year, media_type, poster_url, backdrop_url |
| `MetadataConfig` | api_key, unattended, timeout_seconds |

All types are frozen dataclasses as specified in SSOT Section 3.1.

### 3. `src/frame_compare/services/metadata.py` (NEW)

**Purpose:** Filename parsing and TMDB lookup service

**Public API (spec-anchored in Section 3.2):**

- `parse_filename(filename: str) -> ParsedMetadata`
- `lookup_tmdb(parsed: ParsedMetadata, config: MetadataConfig, client: httpx.AsyncClient) -> TmdbMetadata | None`
- `resolve_metadata(filenames: list[str], config: MetadataConfig, client: httpx.AsyncClient, prompt_callback: Callable[[list[TmdbMetadata]], int] | None = None) -> TmdbMetadata | None`

**Behavior (per SSOT):**

1. **`parse_filename`**:
   - If filename starts with `[`, use Anitopy first, then GuessIt fallback
   - Otherwise use GuessIt first, then Anitopy fallback
   - If both fail: title = filename stem (without extension)
   - Normalize separators (`.`, `_`, `-`) to spaces, strip whitespace
   - Always returns `ParsedMetadata`, never raises

2. **`lookup_tmdb`**:
   - If `config.api_key is None`: return `None` (no request)
   - Validate API key format: must match regex `^[0-9a-fA-F]{32}$`
   - Invalid format → raise `TmdbError("Invalid API key format")`
   - HTTP 401 → `TmdbError("Invalid API key")`
   - HTTP 429 → `TmdbRateLimitedError()`
   - HTTP 5xx → `TmdbError("TMDB service error: {status_code}")`
   - `httpx.TimeoutException` → `TmdbError("Request timed out")`
   - No results → return `None`
   - Has results → return first mapped to `TmdbMetadata`

3. **`resolve_metadata`**:
   - Parse first filename
   - Call `lookup_tmdb`
   - No results → return `None`
   - Single result or `unattended=True` → return first
   - Multiple results + `prompt_callback is None` → return first (index 0)
   - Multiple results + `prompt_callback` provided → call callback
   - Invalid callback index (`< 0` or `>= len(results)`) → raise `MetadataError("invalid selection index")`

### 4. `src/frame_compare/services/__init__.py` (MODIFY)

**Purpose:** Export metadata service public API

**Exports to add:**

```python
from frame_compare.services.metadata import lookup_tmdb, parse_filename, resolve_metadata
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata
```

### 5. `tests/services/test_metadata.py` (NEW)

**Purpose:** Unit tests for metadata service

#### Async Test Mechanics (per SSOT Section 3.1 Pytest Configuration)

All `test_lookup_tmdb_*` and `test_resolve_metadata_*` tests are:

- `async def` functions
- Decorated with `@pytest.mark.anyio`
- Use `respx` for HTTP mocking

**Required fixture (add to `tests/services/conftest.py` or inline):**

```python
import pytest
import httpx

@pytest.fixture
async def async_client():
    """Provide an httpx.AsyncClient for async tests."""
    async with httpx.AsyncClient() as client:
        yield client
```

#### Mocked TMDB Response Payloads

**Movie response:**

```python
MOCK_TMDB_MOVIE = {
    "results": [{
        "id": 550,
        "title": "Fight Club",
        "original_title": "Fight Club",
        "release_date": "1999-10-15",
        "media_type": "movie",
        "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
        "backdrop_path": "/hZkgoQYus5vegHoetLkCJzb17zJ.jpg",
    }]
}
```

**TV response:**

```python
MOCK_TMDB_TV = {
    "results": [{
        "id": 1399,
        "name": "Game of Thrones",
        "original_name": "Game of Thrones",
        "first_air_date": "2011-04-17",
        "media_type": "tv",
        "poster_path": "/1XS1oqL89opfnbLl8WnZY1O1uJx.jpg",
        "backdrop_path": "/suopoADq0k8YZr4dQXcU6pToj6s.jpg",
    }]
}
```

**Empty response:** `{"results": []}`

#### Test Cases

**Filename parsing (5 sync tests):**

| Test | Input | Assertions |
|------|-------|------------|
| `test_parse_filename_western_movie` | `"Movie.Name.2024.BluRay.1080p.mkv"` | `title=="Movie Name"`, `year==2024`, `source=="BluRay"`, `resolution=="1080p"` |
| `test_parse_filename_anime_with_group` | `"[SubGroup] Anime Title - 01 [1080p].mkv"` | `title=="Anime Title"`, `episode==1`, `release_group=="SubGroup"` |
| `test_parse_filename_tv_show` | `"Show.Name.S01E05.720p.WEB-DL.mkv"` | `title=="Show Name"`, `season==1`, `episode==5` |
| `test_parse_filename_minimal` | `"video.mkv"` | `title=="video"`, all other fields `None` |
| `test_parse_filename_empty` | `""` | `title==""`, all other fields `None` |

**TMDB lookup (7 async tests with `@pytest.mark.anyio`):**

| Test | Setup | Assertions |
|------|-------|------------|
| `test_lookup_tmdb_returns_metadata` | Mock 200 with `MOCK_TMDB_MOVIE` | Returns `TmdbMetadata(tmdb_id=550, title="Fight Club", year=1999, media_type="movie")` |
| `test_lookup_tmdb_tv_uses_first_air_date` | Mock 200 with `MOCK_TMDB_TV` | Returns `TmdbMetadata(year=2011, media_type="tv")` |
| `test_lookup_tmdb_no_results` | Mock 200 with empty results | Returns `None` |
| `test_lookup_tmdb_api_key_none` | `config.api_key=None` | Returns `None`, assert `respx_mock.calls.call_count == 0` |
| `test_lookup_tmdb_invalid_api_key_format` | `config.api_key="not-hex"` | Raises `TmdbError`, `"Invalid API key format"` in message |
| `test_lookup_tmdb_rate_limited` | Mock 429 | Raises `TmdbRateLimitedError` |
| `test_lookup_tmdb_server_error` | Mock 500 | Raises `TmdbError`, `"500"` in message |

**Resolve metadata (5 async tests with `@pytest.mark.anyio`):**

| Test | Setup | Assertions |
|------|-------|------------|
| `test_resolve_metadata_single_result` | Mock single result | Returns that result |
| `test_resolve_metadata_no_results` | Mock empty | Returns `None` |
| `test_resolve_metadata_unattended_mode` | Multiple results, `unattended=True` | Returns first, callback not called |
| `test_resolve_metadata_with_callback` | Multiple results, callback returns `1` | Returns second result |
| `test_resolve_metadata_invalid_callback_index` | Callback returns `99` | Raises `MetadataError`, `"invalid selection index"` in message |

### 6. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry

**Required facts:** RUN_ID, artifact versions, scope, SSOT edits (Section 3.2 updated), verification gates

### 7. `CHANGELOG.md` (MODIFY)

**Purpose:** Add metadata service entry

## Acceptance Criteria

- [ ] GIVEN a western movie filename WHEN `parse_filename` is called THEN returns `ParsedMetadata` with normalized title
- [ ] GIVEN an anime filename starting with `[` WHEN `parse_filename` is called THEN Anitopy is used first
- [ ] GIVEN `api_key=None` WHEN `lookup_tmdb` is called THEN returns `None` without HTTP request
- [ ] GIVEN invalid API key format WHEN `lookup_tmdb` is called THEN raises `TmdbError`
- [ ] GIVEN multiple TMDB results and no callback WHEN `resolve_metadata` is called THEN returns first result
- [ ] GIVEN invalid callback index WHEN `resolve_metadata` is called THEN raises `MetadataError`

## Verification Commands

Per `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` Command Canon:

```bash
# Quality gates
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# Import linter
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **HTTP Client Injection:** Per SSOT, `lookup_tmdb` and `resolve_metadata` receive `client: httpx.AsyncClient` — never create your own.

2. **Error Imports:** Use existing classes from `frame_compare.errors`: `MetadataError` (FC-4016), `TmdbError` (FC-5005), `TmdbRateLimitedError` (FC-5006).

3. **API Key Validation Regex:** `^[0-9a-fA-F]{32}$` — use `re.fullmatch()`.

4. **TMDB Year Extraction:** For movies use `release_date[:4]`; for TV use `first_air_date[:4]`.

5. **Async Tests:** All `test_lookup_tmdb_*` and `test_resolve_metadata_*` must be `async def` with `@pytest.mark.anyio` decorator.

6. **Test Mocking:** Use `respx` (already in dev dependencies):

   ```python
   @pytest.mark.anyio
   async def test_lookup_tmdb_returns_metadata(respx_mock, async_client):
       respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
           return_value=httpx.Response(200, json=MOCK_TMDB_MOVIE)
       )
       result = await lookup_tmdb(parsed, config, async_client)
       assert result.tmdb_id == 550
   ```

7. **Verify no-request for api_key=None:** In `test_lookup_tmdb_api_key_none`, assert `respx_mock.calls.call_count == 0`.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__p5-2__metadata-service

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v3.md
