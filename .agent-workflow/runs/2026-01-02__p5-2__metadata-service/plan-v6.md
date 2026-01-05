---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v6
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v5.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v6.md
---

# Implementation Plan: Metadata Service (Design Fix)

## Changes Since plan-v5

- Added explicit step to remove source normalization (any `"Blu-ray"` → `"BluRay"` conversion)
- Added concrete test `test_parse_filename_parsers_raise_falls_back_to_stem` for parser exception handling

## Context

**Phase:** 5
**Module:** `frame_compare.services.metadata`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` Section 3

## Scope

This plan covers the **design fixes only** (incremental from impl-v1):

- [x] SSOT already updated with source representation and exception handling rules
- [ ] Remove source normalization code from `parse_filename`
- [ ] Ensure parser calls wrapped in try/except (verify existing guards are correct)
- [ ] Update test assertion from `source=="BluRay"` to `source=="Blu-ray"`
- [ ] Add test for parser exception fallback

## Contract Impact

**Contracts touched:** NO (SSOT spec update only, not contracts)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "3.2 Public API"

## Files to Modify

### 1. `src/frame_compare/services/metadata.py` (MODIFY)

**Purpose:** Remove source normalization and ensure exception guards

**Public API (spec-anchored in Section 3.2):**

- `parse_filename(filename: str) -> ParsedMetadata`

**Changes:**

1. **Remove source normalization:**
   - Locate any code that maps/normalizes `source` values (e.g., `"Blu-ray"` → `"BluRay"`)
   - Remove that normalization — `source` must be returned verbatim from the parser
   - Post-condition: if parser returns `"Blu-ray"`, `ParsedMetadata.source == "Blu-ray"`

2. **Verify exception guards exist (if not, add them):**

   Ensure both parser calls are wrapped:

   ```python
   try:
       result = guessit(filename)
   except Exception:
       result = {}
   ```

   Apply same pattern to `anitopy.parse()` call.

### 2. `tests/services/test_metadata.py` (MODIFY)

**Purpose:** Update source assertion and add parser exception test

**Changes:**

1. **Update `test_parse_filename_western_movie`:**
   - Before: `assert result.source == "BluRay"`
   - After: `assert result.source == "Blu-ray"`

2. **Add new test `test_parse_filename_parsers_raise_falls_back_to_stem`:**

   ```python
   def test_parse_filename_parsers_raise_falls_back_to_stem(mocker):
       """When both parsers raise, fall back to filename stem."""
       # Arrange
       mocker.patch(
           "frame_compare.services.metadata.guessit",
           side_effect=Exception("guessit error"),
       )
       mocker.patch(
           "frame_compare.services.metadata.anitopy.parse",
           side_effect=Exception("anitopy error"),
       )

       # Act
       result = parse_filename("Movie.Name.2024.BluRay.1080p.mkv")

       # Assert - no exception raised, falls back to stem with normalized separators
       assert result.title == "Movie Name 2024 BluRay 1080p"
       assert result.year is None
       assert result.season is None
       assert result.episode is None
       assert result.release_group is None
       assert result.source is None
       assert result.resolution is None
   ```

## Acceptance Criteria

- [ ] GIVEN a parser that raises an exception WHEN `parse_filename` is called THEN returns fallback `ParsedMetadata` without raising
- [ ] GIVEN `"Movie.Name.2024.BluRay.1080p.mkv"` WHEN `parse_filename` is called THEN `source == "Blu-ray"` (parser verbatim output)
- [ ] GIVEN both parsers raise WHEN `parse_filename` is called THEN `title` equals normalized stem and all other fields are `None`

## Verification Commands

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Source Normalization Removal:** Search for any dict/mapping that converts source strings (like `{"Blu-ray": "BluRay"}`). Remove it entirely.

2. **Exception Guard Pattern:**

   ```python
   try:
       result = guessit(filename)
   except Exception:
       result = {}
   ```

   Apply to both `guessit()` and `anitopy.parse()` calls.

3. **Test Mocking:** Use `mocker.patch()` to make both parsers raise `Exception`.

4. **Stem Fallback Test:** When both parsers fail, the title is the filename without extension, with separators normalized to spaces: `"Movie.Name.2024.BluRay.1080p.mkv"` → `"Movie Name 2024 BluRay 1080p"`.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__p5-2__metadata-service

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v6.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v6.md
