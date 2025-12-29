---
RUN_ID: 2025-12-29__p3-2__video-loading
VERSION: v1
TARGET: Phase 3 → Item 3.2 Video Loading
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v1.md
---

# Implementation Plan: Video Source Loading

## Context

**Phase:** 3 (VapourSynth Module)
**Module:** `frame_compare.vs`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** Phase 3.1 (VS Environment) completed - `env.py`, `types.py`, `loader.py` with stub exist

## Scope

This plan covers:

- [x] Create `src/frame_compare/vs/source.py`
- [x] Implement `load_source(path, core) -> SourceInfo`
- [x] Implement `apply_trim(source, start, end) -> vs.VideoNode`
- [x] Support formats: `.mkv`, `.mp4`, `.avi`, `.m2ts`, `.ts`
- [x] Use lsmas for loading
- [x] Extract clip properties (fps, frame_count, resolution)
- [x] Extract HDR metadata from first frame
- [x] Update `DefaultVSLoader.load()` to call `load_source`
- [x] Write unit tests with mocked VS
- [x] Write tests for HDR detection

This plan does NOT cover:

- Frame properties extraction module (`props.py`) - deferred to Phase 3.3
- Color operations (`color.py`) - deferred to Phase 3.4
- Tonemapping (`tonemap.py`) - deferred to Phase 3.5

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "3.2 Source Loading"
  - Section: "2.1 SourceInfo"
  - Section: "1.4 Plugin Detection"
  - Section: "6. Error Handling"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.4 Processing Errors (FC-4xxx) — Exit Code 5"

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/vs/source.py`

**Purpose:** Video source loading and metadata extraction.

**Functions to implement (spec-anchored):**

- `load_source(path: Path, core: vs.Core | None = None) -> SourceInfo` — Load video via LWLibavSource, extract metadata
- `apply_trim(source: SourceInfo, start: int, end: int | None = None) -> vs.VideoNode` — Apply frame trim

**Implementation details:**

```python
def load_source(path: Path, core: vs.Core | None = None) -> SourceInfo:
    """Load video source with automatic format detection.

    Algorithm:
    1. If core is None, call ensure_vs_environment()
    2. Call require_plugin(core, "lsmas")
    3. Determine loader namespace: core.lsmas or core.lw
    4. clip = loader.LWLibavSource(str(path))
    5. Extract clip properties: width, height, num_frames, fps, format
    6. Get first frame props via clip.get_frame(0).props
    7. Detect HDR via _detect_hdr(frame_props)
    8. Return SourceInfo with all metadata

    Raises:
        SourceLoadError: If file cannot be loaded or lsmas unavailable
    """
```

**HDR detection helper (inline or private):**

```python
def _detect_hdr(frame_props: Mapping[str, object]) -> tuple[bool, HDRMetadata | None]:
    """Detect HDR from frame properties.

    HDR detection criteria:
    - _Transfer == 16 (PQ) OR _Transfer == 18 (HLG)
    - _Primaries == 9 (BT.2020)

    Returns:
        (is_hdr, hdr_metadata) tuple
    """
```

---

### 2. [MODIFY] `src/frame_compare/vs/loader.py`

**Purpose:** Update `DefaultVSLoader.load()` to use `load_source`.

**Changes:**

Replace stub implementation with actual call:

```python
def load(self, path: Path) -> SourceInfo:
    from frame_compare.vs.source import load_source
    core = self.ensure_core()
    return load_source(path, core)
```

---

### 3. [MODIFY] `src/frame_compare/vs/__init__.py`

**Purpose:** Export `load_source` and `apply_trim` functions.

**Add to exports:**

```python
from frame_compare.vs.source import apply_trim, load_source

__all__ = [
    # ... existing exports ...
    "load_source",
    "apply_trim",
]
```

---

### 4. [NEW] `tests/vs/test_source.py`

**Purpose:** Unit tests for source loading.

**Mock structures for tests:**

```python
from types import SimpleNamespace

def make_mock_clip(
    width: int = 1920,
    height: int = 1080,
    num_frames: int = 1000,
    fps_num: int = 24,
    fps_den: int = 1,
    frame_props: dict | None = None,
) -> SimpleNamespace:
    """Create mock VS clip for testing."""
    format_ = SimpleNamespace(name="YUV420P8")
    fps = SimpleNamespace(numerator=fps_num, denominator=fps_den)
    frame_props = frame_props or {}
    frame = SimpleNamespace(props=frame_props)
    clip = SimpleNamespace(
        width=width,
        height=height,
        num_frames=num_frames,
        fps=fps,
        format=format_,
        get_frame=lambda n: frame,
    )
    return clip
```

**Tests required:**

- `test_load_source_returns_source_info` — Mock core with lsmas, verify `SourceInfo` fields populated
- `test_load_source_extracts_fps` — Mock clip with 24/1 fps, verify `fps == Fraction(24, 1)`
- `test_load_source_extracts_dimensions` — Mock 3840x2160 clip, verify width/height
- `test_load_source_missing_lsmas_raises_error` — Mock core without lsmas, verify `PluginNotFoundError` raised
- `test_load_source_file_not_found_raises_error` — Mock LWLibavSource to raise, verify `SourceLoadError` raised
- `test_detect_hdr_pq_transfer` — Frame props `{_Transfer: 16, _Primaries: 9}`, verify `is_hdr=True`
- `test_detect_hdr_hlg_transfer` — Frame props `{_Transfer: 18, _Primaries: 9}`, verify `is_hdr=True`
- `test_detect_hdr_sdr_content` — Frame props `{_Transfer: 1, _Primaries: 1}`, verify `is_hdr=False`
- `test_apply_trim_returns_trimmed_clip` — Mock clip with `std.Trim`, verify trim applied
- `test_apply_trim_end_none_trims_to_end` — Verify `end=None` trims from start to clip end

---

### 5. [MODIFY] `tests/vs/test_loader.py`

**Purpose:** Update loader test now that `load()` works.

**Changes:**

Replace stub test with integration test (using mocks):

- `test_default_vs_loader_load_calls_load_source` — Verify `load_source` is called with path and core

---

### 6. [MODIFY] `docs/DECISIONS.md`

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: 2025-12-29__p3-2__video-loading
- Scope: Video source loading via lsmas, HDR detection, DefaultVSLoader completion
- SSOT edits: None
- Design: lsmas namespace fallback (lsmas → lw), HDR via PQ/HLG transfer values

---

### 7. [MODIFY] `CHANGELOG.md`

**Purpose:** Add entry for video loading.

**Entry format:**

```markdown
### Added
- Video source loading (`load_source`) with LWLibavSource support
- HDR detection from frame properties (PQ, HLG, BT.2020)
```

## Acceptance Criteria

- [ ] GIVEN a valid video file path WHEN `load_source(path)` is called THEN it returns `SourceInfo` with clip and metadata
- [ ] GIVEN lsmas is not installed WHEN `load_source(path)` is called THEN it raises `PluginNotFoundError` with code `FC-2003`
- [ ] GIVEN an HDR video with PQ transfer WHEN `load_source(path)` is called THEN `SourceInfo.is_hdr=True`
- [ ] GIVEN an SDR video WHEN `load_source(path)` is called THEN `SourceInfo.is_hdr=False`
- [ ] GIVEN a `SourceInfo` WHEN `apply_trim(source, 100, 200)` is called THEN it returns a trimmed clip
- [ ] GIVEN `DefaultVSLoader().load(path)` WHEN VS is available THEN it returns `SourceInfo` from `load_source`

## Verification Commands

```bash
# Quality gates
.venv/bin/pyright --warnings src/frame_compare/vs
.venv/bin/ruff check src/frame_compare/vs
.venv/bin/pytest -v tests/vs/

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract gates (no changes expected)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Namespace fallback:** Check `core.lsmas` first, then `core.lw` for LWLibavSource
2. **fps extraction:** `Fraction(clip.fps.numerator, clip.fps.denominator)`
3. **Frame props access:** `clip.get_frame(0).props` returns dict-like object
4. **HDR detection values:**
   - PQ: `_Transfer == 16`
   - HLG: `_Transfer == 18`
   - BT.2020: `_Primaries == 9`
5. **Error wrapping:** Catch VS exceptions and wrap in `SourceLoadError`
6. **Test mocking:** Patch `frame_compare.vs.source.ensure_vs_environment` and mock `core.lsmas.LWLibavSource`
7. **STOP rule:** If SSOT ambiguity encountered, STOP and return to Planning

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-2__video-loading

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v1.md
