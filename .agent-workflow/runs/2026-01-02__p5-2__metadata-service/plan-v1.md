---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v1
TARGET: Phase 5 → Item 5.2
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v1.md
---

# Implementation Plan: Metadata Service

## Context

**Phase:** 5
**Module:** `frame_compare.services.metadata`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` Section 3
**Dependencies:** Phase 5.1 (Audio Alignment) complete; requires new dependencies `guessit` and `anitopy`

## Scope

This plan covers:

- [x] Add `guessit` and `anitopy` dependencies to `pyproject.toml`
- [x] Add metadata types to `services/types.py` (`ParsedMetadata`, `TmdbMetadata`, `MetadataConfig`)
- [x] Create `src/frame_compare/services/metadata.py` with:
  - `parse_filename(filename: str) -> ParsedMetadata`
  - `lookup_tmdb(parsed: ParsedMetadata, config: MetadataConfig, client: httpx.AsyncClient) -> TmdbMetadata | None`
  - `resolve_metadata(filenames: list[str], config: MetadataConfig, client: httpx.AsyncClient, prompt_callback: Callable[[list[TmdbMetadata]], int] | None) -> TmdbMetadata | None`
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

## Files to Create/Modify

### 1. `pyproject.toml` (MODIFY)

**Purpose:** Add required filename parsing dependencies

**Changes:**

- Add `guessit>=3.8.0` to `dependencies`
- Add `anitopy>=2.2.0` to `dependencies`

### 2. `src/frame_compare/services/types.py` (MODIFY)

**Purpose:** Add metadata service types

**Types to add (spec-anchored in Section 3.1):**

```python
@dataclass(frozen=True)
class ParsedMetadata:
    """Metadata extracted from filename."""
    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    release_group: str | None = None
    source: str | None = None  # BluRay, WEB-DL, etc.
    resolution: str | None = None

@dataclass(frozen=True)
class TmdbMetadata:
    """Metadata from TMDB API."""
    tmdb_id: int
    title: str
    original_title: str
    year: int
    media_type: str  # "movie" | "tv"
    poster_url: str | None = None
    backdrop_url: str | None = None

@dataclass(frozen=True)
class MetadataConfig:
    """Configuration for metadata service."""
    api_key: str | None = None
    unattended: bool = False  # Auto-select first match
    timeout_seconds: float = 10.0
```

### 3. `src/frame_compare/services/metadata.py` (NEW)

**Purpose:** Filename parsing and TMDB lookup service

**Public API (signatures spec-anchored in Section 3.2):**

- `parse_filename(filename: str) -> ParsedMetadata`
- `lookup_tmdb(parsed: ParsedMetadata, config: MetadataConfig, client: httpx.AsyncClient) -> TmdbMetadata | None`
- `resolve_metadata(filenames: list[str], config: MetadataConfig, client: httpx.AsyncClient, prompt_callback: Callable[[list[TmdbMetadata]], int] | None = None) -> TmdbMetadata | None`

**Implementation details:**

1. **`parse_filename`**:
   - Call `guessit.guessit(filename)` first
   - If `guessit` returns a title, prefer it (western media)
   - If `guessit` fails or returns low-confidence anime pattern, call `anitopy.parse(filename)`
   - Map parsed fields to `ParsedMetadata`
   - **Determinism:** Always return a `ParsedMetadata` even if parsing fails (with just the raw filename as title)

2. **`lookup_tmdb`**:
   - Uses injected `httpx.AsyncClient` (per async-semantics.md Section 7)
   - Base URL: `https://api.themoviedb.org/3/search/multi`
   - Query params: `api_key={key}`, `query={parsed.title}`, `year={parsed.year}` (if present)
   - Timeout: `config.timeout_seconds` (default 10s per async-semantics.md)
   - **Error mapping:**
     - HTTP 401 → `TmdbError("Invalid API key")`
     - HTTP 429 → `TmdbRateLimitedError()`
     - HTTP 5xx → `TmdbError("TMDB service error: {status_code}")`
     - `httpx.TimeoutException` → `TmdbError("Request timed out")`
     - `httpx.RequestError` → `TmdbError("Network error: {error}")`
   - Returns `None` if no results found
   - Returns first result mapped to `TmdbMetadata` if results exist

3. **`resolve_metadata`**:
   - Parse first filename via `parse_filename`
   - Search TMDB via `lookup_tmdb`
   - If no results, return `None`
   - If one result or `config.unattended=True`, return first result
   - If multiple results and `prompt_callback` provided, call it with results list and use returned index
   - If multiple results and no callback, return first result

### 4. `src/frame_compare/services/__init__.py` (MODIFY)

**Purpose:** Export metadata service public API

**Exports to add:**

```python
from frame_compare.services.metadata import (
    lookup_tmdb,
    parse_filename,
    resolve_metadata,
)
from frame_compare.services.types import (
    MetadataConfig,
    ParsedMetadata,
    TmdbMetadata,
)
```

### 5. `tests/services/test_metadata.py` (NEW)

**Purpose:** Unit tests for metadata service

**Tests required (spec-anchored in Section 1.3 Deterministic Test Vector Policy):**

**Filename parsing tests:**

- `test_parse_filename_western_movie` — Input: `"Movie.Name.2024.BluRay.1080p.mkv"`, Assert: `title="Movie Name"`, `year=2024`, `source="BluRay"`, `resolution="1080p"`
- `test_parse_filename_anime_with_group` — Input: `"[SubGroup] Anime Title - 01 [1080p].mkv"`, Assert: `title="Anime Title"`, `episode=1`, `release_group="SubGroup"`, `resolution="1080p"`
- `test_parse_filename_tv_show` — Input: `"Show.Name.S01E05.720p.WEB-DL.mkv"`, Assert: `title="Show Name"`, `season=1`, `episode=5`, `source="WEB-DL"`, `resolution="720p"`
- `test_parse_filename_minimal` — Input: `"video.mkv"`, Assert: `title="video"`, all other fields `None`
- `test_parse_filename_empty` — Input: `""`, Assert: `title=""`, all other fields `None`

**TMDB lookup tests (mocked):**

- `test_lookup_tmdb_returns_metadata` — Mock 200 response with single result, assert returns `TmdbMetadata` with correct fields
- `test_lookup_tmdb_no_results` — Mock 200 response with empty results, assert returns `None`
- `test_lookup_tmdb_invalid_api_key` — Mock 401 response, assert raises `TmdbError` with `"Invalid API key"` in message
- `test_lookup_tmdb_rate_limited` — Mock 429 response, assert raises `TmdbRateLimitedError`
- `test_lookup_tmdb_server_error` — Mock 500 response, assert raises `TmdbError` with status code in message
- `test_lookup_tmdb_timeout` — Mock timeout exception, assert raises `TmdbError` with `"timed out"` in message

**Resolve metadata tests:**

- `test_resolve_metadata_single_result` — Mock single TMDB result, assert returns that result
- `test_resolve_metadata_no_results` — Mock empty TMDB results, assert returns `None`
- `test_resolve_metadata_unattended_mode` — Mock multiple results with `unattended=True`, assert returns first result without calling callback
- `test_resolve_metadata_with_callback` — Mock multiple results with callback returning index 1, assert returns second result

### 6. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append a run decision entry

**Required facts to record:**

- RUN_ID: `2026-01-02__p5-2__metadata-service`
- Artifact versions: plan-v1, plan-review-vN, impl-vN, verify-vN, review-vN
- Scope: Metadata service with GuessIt/Anitopy parsing and TMDB lookup
- Out-of-scope: Publishers, Report services
- SSOT edits: None
- Verification gates: pyright, ruff, pytest, lint-imports

### 7. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for metadata service

**Entry:**

```markdown
### Added
- Metadata service with filename parsing via GuessIt and Anitopy
- TMDB lookup integration for media metadata enrichment
```

## Acceptance Criteria

- [ ] GIVEN a western movie filename WHEN `parse_filename` is called THEN returns `ParsedMetadata` with title, year, source, resolution
- [ ] GIVEN an anime filename with group WHEN `parse_filename` is called THEN returns `ParsedMetadata` with title, episode, release_group
- [ ] GIVEN a valid TMDB API key and title WHEN `lookup_tmdb` is called THEN returns `TmdbMetadata` with tmdb_id, title, year, media_type
- [ ] GIVEN an invalid TMDB API key WHEN `lookup_tmdb` is called THEN raises `TmdbError`
- [ ] GIVEN rate limiting WHEN `lookup_tmdb` is called THEN raises `TmdbRateLimitedError`
- [ ] GIVEN multiple TMDB results and unattended mode WHEN `resolve_metadata` is called THEN returns first result

## Verification Commands

```bash
# Quality gates
.venv/bin/pyright --warnings src/frame_compare/services/metadata.py
.venv/bin/ruff check src/frame_compare/services
.venv/bin/pytest -v tests/services/test_metadata.py

# Import linter
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Full test suite
.venv/bin/pytest -v tests/services/
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **HTTP Client Injection:** Per `async-semantics.md` Section 7, services MUST NOT create their own `AsyncClient`. The `lookup_tmdb` and `resolve_metadata` functions receive the client as a parameter.

2. **Error Imports:** Use existing error classes from `frame_compare.errors`:
   - `MetadataError` (FC-4016)
   - `TmdbError` (FC-5005)
   - `TmdbRateLimitedError` (FC-5006)

3. **GuessIt Fallback:** GuessIt is the primary parser. Only fall back to Anitopy if GuessIt's result looks like anime (presence of episode without season, or specific patterns).

4. **TMDB Response Parsing:** The TMDB `/search/multi` endpoint returns results with `media_type` field (`"movie"` or `"tv"`). For movies, use `release_date[:4]` for year; for TV, use `first_air_date[:4]`.

5. **Test Mocking Strategy:** Use `respx` for mocking httpx responses (already in dev dependencies). Example:

   ```python
   @pytest.fixture
   def mock_tmdb(respx_mock):
       respx_mock.get("https://api.themoviedb.org/3/search/multi").mock(
           return_value=httpx.Response(200, json={"results": [...]})
       )
   ```

6. **Deterministic Test Values:** Per testing-strategy.md Section 1.3, use canonical values:
   - `timeout: float` → `1.0`
   - Prefer `tmp_path` fixtures for any path arguments

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__p5-2__metadata-service

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v1.md
