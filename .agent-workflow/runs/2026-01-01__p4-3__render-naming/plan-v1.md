---
RUN_ID: 2026-01-01__p4-3__render-naming
VERSION: v1
TARGET: Phase 4 → Item 4.3
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-v1.md
---

# Implementation Plan: Render Naming Utilities

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** Phase 4.1 (types), Phase 4.2 (geometry) — completed

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/naming.py`
- [x] Implement `generate_screenshot_name()` per SSOT Section 3.3.1
- [x] Implement `generate_screenshot_path()` per SSOT Section 3.3.2
- [x] Write unit tests including input validation

This plan does NOT cover:

- Overlay rendering (Phase 4.4)
- Encoder integration (Phase 4.5)
- Orchestrator (Phase 4.6)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "3.3 Naming"
  - Section: "3.3.1 `generate_screenshot_name` Behavior"
  - Section: "3.3.2 `generate_screenshot_path` Behavior"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. [MODIFY] `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`

**Purpose:** Added Sections 3.3.1 and 3.3.2 with deterministic behavior rules during this run.

**Changes made:** Added `#### 3.3.1 generate_screenshot_name Behavior`, `#### 3.3.2 generate_screenshot_path Behavior` with algorithm and invalid-input rules.

---

### 2. [NEW] `src/frame_compare/render/naming.py`

**Purpose:** Screenshot file naming utilities.

**Functions to implement:**

- `generate_screenshot_name(label: str, frame_number: int, extension: str = "png") -> str`
- `generate_screenshot_path(output_dir: Path, label: str, frame_number: int) -> Path`

All behavior is defined in SSOT Sections 3.3.1–3.3.2.

---

### 3. [NEW] `tests/render/test_naming.py`

**Tests required:**

| Test Name | Scenario | Expected |
|-----------|----------|----------|
| `test_generate_name_simple` | label="Source", frame=100 | `"Source_00100.png"` |
| `test_generate_name_zero_frame` | label="Ref", frame=0 | `"Ref_00000.png"` |
| `test_generate_name_custom_extension` | label="Test", frame=1, ext="jpg" | `"Test_00001.jpg"` |
| `test_generate_name_sanitizes_spaces` | label="My Source", frame=50 | `"My_Source_00050.png"` |
| `test_generate_name_sanitizes_special_chars` | label="$ource@123!", frame=10 | `"ource_123_00010.png"` |
| `test_generate_name_collapses_underscores` | label="A___B", frame=1 | `"A_B_00001.png"` |
| `test_generate_name_strips_leading_trailing` | label="_**Test**_", frame=1 | `"Test_00001.png"` |
| `test_generate_name_empty_becomes_unnamed` | label="", frame=1 | `"unnamed_00001.png"` |
| `test_generate_name_all_special_becomes_unnamed` | label="@#$%", frame=1 | `"unnamed_00001.png"` |
| `test_generate_name_preserves_hyphen` | label="My-Source", frame=1 | `"My-Source_00001.png"` |
| `test_generate_name_negative_frame_raises` | frame=-1 | `ValueError("frame_number must be non-negative")` |
| `test_generate_name_empty_extension_raises` | ext="" | `ValueError("extension must not be empty")` |
| `test_generate_path_simple` | dir=tmp_path, label="Ref", frame=100 | `tmp_path / "Ref_00100.png"` |
| `test_generate_path_sanitizes` | dir=tmp_path, label="My Source", frame=1 | `tmp_path / "My_Source_00001.png"` |

---

### 4. [MODIFY] `src/frame_compare/render/__init__.py`

**Purpose:** Export naming utilities.

**Exact change:**

1. Add imports after existing imports:

   ```python
   from frame_compare.render.naming import (
       generate_screenshot_name,
       generate_screenshot_path,
   )
   ```

2. Append to existing `__all__` list (keep all entries unchanged, append in order):

   ```python
   __all__ = [
       # ... existing 9 exports ...
       "generate_screenshot_name",
       "generate_screenshot_path",
   ]
   ```

---

### 5. [MODIFY] `docs/DECISIONS.md`

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-3__render-naming`
- SSOT edits: Added Sections 3.3.1–3.3.2 to `render-module.md`
- Scope: naming utilities only

---

### 6. [MODIFY] `CHANGELOG.md`

**Entry:**

```markdown
### Added
- `render.naming` module with screenshot name generation and label sanitization
```

## Acceptance Criteria

- [ ] GIVEN `generate_screenshot_name("Source", 100)` THEN returns `"Source_00100.png"`
- [ ] GIVEN `generate_screenshot_name("My Source", 50)` THEN returns `"My_Source_00050.png"`
- [ ] GIVEN `generate_screenshot_name("", 1)` THEN returns `"unnamed_00001.png"`
- [ ] GIVEN `generate_screenshot_name("Test", -1)` THEN raises `ValueError`
- [ ] GIVEN `generate_screenshot_path(Path("/tmp"), "Ref", 100)` THEN returns `Path("/tmp/Ref_00100.png")`
- [ ] GIVEN Pyright strict mode WHEN analyzing `render/` THEN 0 errors
- [ ] GIVEN `pytest tests/render/test_naming.py` THEN all tests pass

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-v1.md

# Quality gates (primary)
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/ tests/render/
.venv/bin/pytest -v tests/render/test_naming.py

# Quality gates (fallback)
UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/ tests/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/test_naming.py

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors.

## Notes for Coding Agent

1. **Sanitization regex:** `re.sub(r'[^A-Za-z0-9_-]', '_', label)`
2. **Collapse underscores:** `re.sub(r'_+', '_', sanitized)`
3. **Strip:** `sanitized.strip('_')`
4. **Empty fallback:** `sanitized or "unnamed"`
5. **Format string:** `f"{sanitized}_{frame_number:05d}.{extension}"`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-3__render-naming

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-review-v1.md
