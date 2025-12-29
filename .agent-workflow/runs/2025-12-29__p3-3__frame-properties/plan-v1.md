---
RUN_ID: 2025-12-29__p3-3__frame-properties
VERSION: v1
TARGET: Phase 3 → Item 3.3 Frame Properties
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-v1.md
---

# Implementation Plan: Frame Properties

## Context

**Phase:** 3
**Module:** vs (VapourSynth)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** Phase 3.1 Environment (complete), Phase 3.2 Video Loading (complete)

## Scope

This plan covers:

- [x] Create `src/frame_compare/vs/props.py`
- [x] Implement `get_color_props(clip) -> ColorProps`
- [x] Implement `is_hdr(clip) -> bool`
- [x] Detect PQ (_Transfer == 16)
- [x] Detect HLG (_Transfer == 18)
- [x] Detect BT.2020 primaries (_Primaries == 9)
- [x] Define `ColorProps` dataclass in `types.py`
- [x] Export new types and functions from `__init__.py`
- [x] Write unit tests for `props.py`

This plan does NOT cover:

- Refactoring `_detect_hdr` in `source.py` (leave as-is per SSOT)
- Tonemapping (Phase 3.5)
- Color operations (Phase 3.4)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "2.3 ColorProps"
  - Section: "3.4 Frame Properties"
  - Section: "5.1 HDR Detection"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `src/frame_compare/vs/types.py` (MODIFY)

**Purpose:** Add `ColorProps` dataclass per SSOT 2.3.

**Types to define:**

- `ColorProps` — Color space properties extracted from frame (primaries, transfer, matrix, color_range)

**Signature (from SSOT 2.3):**

```python
@dataclass
class ColorProps:
    primaries: int    # _Primaries, default 2
    transfer: int     # _Transfer, default 2
    matrix: int       # _Matrix, default 2
    color_range: int  # _ColorRange, default 0
```

### 2. `src/frame_compare/vs/props.py` (NEW)

**Purpose:** Frame property extraction functions.

**Functions to implement (spec-anchored):**

- `get_color_props(clip: vs.VideoNode) -> ColorProps` — signature + behavior defined in **SSOT 3.4 Frame Properties**
- `is_hdr(clip: vs.VideoNode) -> bool` — signature + behavior defined in **SSOT 3.4 Frame Properties**

**Implementation notes:**

- Both functions read frame 0 via `clip.get_frame(0)`
- `is_hdr()` uses HDR Detection Rule: `_Transfer in (16, 18) AND _Primaries == 9`
- Field mapping follows SSOT 2.3 ColorProps Field Mapping table

### 3. `src/frame_compare/vs/__init__.py` (MODIFY)

**Purpose:** Export new types and functions.

**Changes:**

- Import `ColorProps` from `types`
- Import `get_color_props`, `is_hdr` from `props`
- Add to `__all__`: `"ColorProps"`, `"get_color_props"`, `"is_hdr"`

### 4. `tests/vs/test_props.py` (NEW)

**Purpose:** Unit tests for frame property extraction.

**Tests required:**

Per SSOT 1.3 Deterministic Test Vector Policy:

- `test_get_color_props_returns_colorprops_with_defaults` — Mock frame with no props, verify defaults (2, 2, 2, 0)
- `test_get_color_props_extracts_all_fields` — Mock frame with all props set, verify extraction
- `test_get_color_props_partial_props_uses_defaults` — Mock frame with some props missing
- `test_is_hdr_pq_bt2020_returns_true` — Mock frame with `_Transfer=16, _Primaries=9`
- `test_is_hdr_hlg_bt2020_returns_true` — Mock frame with `_Transfer=18, _Primaries=9`
- `test_is_hdr_sdr_returns_false` — Mock frame with `_Transfer=1, _Primaries=1`
- `test_is_hdr_pq_without_bt2020_returns_false` — Mock frame with `_Transfer=16, _Primaries=1`
- `test_is_hdr_bt2020_without_pq_hlg_returns_false` — Mock frame with `_Transfer=1, _Primaries=9`

**Assertions (deterministic):**

- `get_color_props` tests assert exact field values
- `is_hdr` tests assert boolean result

**Mocking strategy:**

- Use `unittest.mock.MagicMock` for `vs.VideoNode`
- Mock `clip.get_frame(0).props` to return dict with test values

### 5. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-29__p3-3__frame-properties`
- Artifact versions: plan-v1
- Scope: ColorProps type + get_color_props/is_hdr public API
- SSOT edits: Added sections 2.3 and 3.4 to vs-module.md
- Out-of-scope: `_detect_hdr` refactoring (left in source.py)

### 6. `CHANGELOG.md` (MODIFY)

**Purpose:** Add short entry for user-visible changes.

**Entry format:**

```markdown
### Added
- `ColorProps` type for color space properties
- `get_color_props()` function to extract color properties from clip
- `is_hdr()` function to detect HDR clips
```

## Acceptance Criteria

- [ ] GIVEN a VapourSynth clip WHEN `get_color_props(clip)` is called THEN returns ColorProps with correct field values from frame 0
- [ ] GIVEN a VapourSynth clip with missing frame props WHEN `get_color_props(clip)` is called THEN returns ColorProps with default values per SSOT 2.3
- [ ] GIVEN an HDR clip with PQ transfer and BT.2020 primaries WHEN `is_hdr(clip)` is called THEN returns True
- [ ] GIVEN an HDR clip with HLG transfer and BT.2020 primaries WHEN `is_hdr(clip)` is called THEN returns True
- [ ] GIVEN an SDR clip WHEN `is_hdr(clip)` is called THEN returns False
- [ ] GIVEN a clip with BT.2020 but SDR transfer WHEN `is_hdr(clip)` is called THEN returns False

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-v1.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/vs/
.venv/bin/ruff check src/frame_compare/vs/
.venv/bin/pytest -v tests/vs/

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- **Do NOT refactor** `_detect_hdr` in `source.py`. Leave it as-is.
- `is_hdr()` in `props.py` implements the same logic as `_detect_hdr()` but operates on a clip directly (reads frame 0).
- `get_color_props()` extracts the four color-related frame properties; it does NOT extract HDR metadata (that's `_detect_hdr`'s job).
- Use `TYPE_CHECKING` guard for `vapoursynth` import in `props.py` (same pattern as `source.py`).
- Test mocking pattern: Mock `clip.get_frame(0)` to return a mock with `.props` dict containing test values.

---

> **Proposed RUN_ID:** 2025-12-29__p3-3__frame-properties
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2025-12-29__p3-3__frame-properties` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-3__frame-properties

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-review-v1.md
