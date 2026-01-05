---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v5
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v5.md
---

# Implementation Plan: Metadata Service (Design Fix)

## Changes Since plan-v4

Per review-v1.md DESIGN ISSUE verdict:

1. **SSOT updated** (`services-module.md` Section 3.2):
   - Added "Source representation" rule: `source` field returned verbatim from parser (e.g., "Blu-ray", not normalized)
   - Added "Exception handling" contract: all parser calls wrapped in try/except, function NEVER raises

2. **Test expectation updated**: `test_parse_filename_western_movie` now expects `source=="Blu-ray"` (parser output)

3. **Implementation fix required**: Wrap GuessIt and Anitopy calls in try/except blocks

## Context

**Phase:** 5
**Module:** `frame_compare.services.metadata`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` Section 3

## Scope

This plan covers the **design fixes only** (incremental from impl-v1):

- [x] Update SSOT with source representation and exception handling rules
- [ ] Fix `parse_filename` to wrap parser calls in try/except
- [ ] Update test assertion from `source=="BluRay"` to `source=="Blu-ray"`

## Contract Impact

**Contracts touched:** NO (SSOT spec update only, not contracts)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "3.2 Public API"

## Files to Modify

### 1. `src/frame_compare/services/metadata.py` (MODIFY)

**Purpose:** Add exception guards to satisfy "never raises" contract

**Public API (spec-anchored in Section 3.2):**

- `parse_filename(filename: str) -> ParsedMetadata`

**Changes:**

Wrap both parser calls in try/except blocks:

```python
# Before (unsafe)
result = guessit(filename)

# After (safe)
try:
    result = guessit(filename)
except Exception:
    result = {}
```

Apply the same pattern to `anitopy.parse()` call.

### 2. `tests/services/test_metadata.py` (MODIFY)

**Purpose:** Update test assertion to match actual parser output

**Change:**

In `test_parse_filename_western_movie`:

- Before: `assert result.source == "BluRay"`
- After: `assert result.source == "Blu-ray"`

## Acceptance Criteria

- [ ] GIVEN a parser that raises an exception WHEN `parse_filename` is called THEN returns fallback `ParsedMetadata` without raising
- [ ] GIVEN `"Movie.Name.2024.BluRay.1080p.mkv"` WHEN `parse_filename` is called THEN `source == "Blu-ray"` (parser verbatim output)

## Verification Commands

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Exception Guard Pattern:**

   ```python
   try:
       result = guessit(filename)
   except Exception:
       result = {}
   ```

   Apply to both `guessit()` and `anitopy.parse()` calls.

2. **Source Assertion:** Change from `"BluRay"` to `"Blu-ray"` — this is the actual GuessIt output format.

3. **No other changes needed** — all other functionality from impl-v1 is correct.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__p5-2__metadata-service

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v5.md
