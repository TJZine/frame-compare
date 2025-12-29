---
RUN_ID: 2025-12-29__p3-2__video-loading
VERSION: v4
TARGET: Phase 3 → Item 3.2 Video Loading
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v2.md
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v3.md
---

# Implementation Plan: Video Source Loading

## Changes Since plan-v3

1. **HDR defaults test fixed:** Split invalid test into two SSOT-compliant tests:
   - `test_detect_hdr_empty_props_returns_false_and_none` — `{}` → `is_hdr=False`, `hdr_metadata=None`
   - `test_detect_hdr_defaults_matrix_when_missing` — HDR props without `_Matrix` → `matrix=2` (default observable)

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
- [x] Implement `_detect_hdr(frame_props) -> tuple[bool, HDRMetadata | None]`
- [x] Support formats via LWLibavSource (no extension whitelist)
- [x] Extract clip properties (fps, frame_count, resolution)
- [x] Extract HDR metadata per SSOT field mapping
- [x] Update `DefaultVSLoader.load()` to call `load_source`
- [x] Write unit tests with proper mock classes
- [x] Write tests for HDR detection per SSOT mapping

This plan does NOT cover:

- Frame properties extraction module (`props.py`) - deferred to Phase 3.3
- Color operations (`color.py`) - deferred to Phase 3.4
- Tonemapping (`tonemap.py`) - deferred to Phase 3.5

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "3.2 Source Loading"
  - Section: "5.1 HDR Detection"
  - Section: "2.1 SourceInfo"
  - Section: "1.3 VSLoader Protocol"
  - Section: "1.4 Plugin Detection"
  - Section: "6. Error Handling"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.2 Dependency Errors (FC-2xxx) — Exit Code 3"
  - Section: "3.4 Processing Errors (FC-4xxx) — Exit Code 5"

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/vs/source.py`

**Purpose:** Video source loading and metadata extraction.

**Functions to implement (spec-anchored):**

- `load_source(path: Path, core: vs.Core | None = None) -> SourceInfo`
- `apply_trim(source: SourceInfo, start: int, end: int | None = None) -> vs.VideoNode`
- `_detect_hdr(frame_props: Mapping[str, object]) -> tuple[bool, HDRMetadata | None]`

**Implementation details for `load_source` (loader selection per SSOT 1.4):**

```python
def load_source(path: Path, core: vs.Core | None = None) -> SourceInfo:
    """Load video source with automatic format detection.

    Raises:
        PluginNotFoundError: If lsmas plugin is not available (FC-2003, propagates)
        SourceLoadError: If file cannot be opened or is corrupt (FC-4015)
    """
    if core is None:
        core = ensure_vs_environment()

    # Propagates PluginNotFoundError (FC-2003) if lsmas missing
    require_plugin(core, "lsmas")

    # Loader selection per SSOT 1.4 Plugin Detection:
    # Check for LWLibavSource on the namespace, not just namespace existence
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        loader = core.lsmas
    else:
        # require_plugin passed, so core.lw.LWLibavSource must exist
        loader = core.lw

    try:
        clip = loader.LWLibavSource(str(path))
    except Exception as e:
        raise SourceLoadError(path, str(e))

    # Extract properties
    frame = clip.get_frame(0)
    fps = Fraction(clip.fps.numerator, clip.fps.denominator)
    is_hdr, hdr_metadata = _detect_hdr(dict(frame.props))

    return SourceInfo(
        clip=clip,
        width=clip.width,
        height=clip.height,
        num_frames=clip.num_frames,
        fps=fps,
        format=clip.format,
        frame_props=dict(frame.props),
        is_hdr=is_hdr,
        hdr_metadata=hdr_metadata,
    )
```

**Implementation details for `apply_trim`:**

```python
def apply_trim(source: SourceInfo, start: int, end: int | None = None) -> vs.VideoNode:
    """Apply frame trim to clip.

    Args:
        start: First frame to include (0-indexed, inclusive)
        end: Last frame to include (0-indexed, inclusive).
             If None, trims to end of clip.

    Returns:
        Trimmed clip with frames [start, end] inclusive.
    """
    if end is None:
        return source.clip[start:]
    return source.clip[start:end + 1]  # end+1 because VS slice is exclusive on right
```

**Implementation details for `_detect_hdr` (per SSOT 5.1):**

```python
def _detect_hdr(frame_props: Mapping[str, object]) -> tuple[bool, HDRMetadata | None]:
    """Detect HDR from frame properties per SSOT 5.1 mapping.

    HDR Detection: is_hdr = _Transfer in (16, 18) AND _Primaries == 9
    """
    transfer = int(frame_props.get("_Transfer", 2))
    primaries = int(frame_props.get("_Primaries", 2))

    is_hdr = transfer in (16, 18) and primaries == 9

    if not is_hdr:
        return (False, None)

    return (True, HDRMetadata(
        mastering_display=str(frame_props["MasteringDisplayPrimaries"])
            if "MasteringDisplayPrimaries" in frame_props else None,
        max_cll=int(frame_props["ContentLightLevelMax"])
            if "ContentLightLevelMax" in frame_props else None,
        max_fall=int(frame_props["ContentLightLevelAverage"])
            if "ContentLightLevelAverage" in frame_props else None,
        color_primaries=primaries,
        transfer=transfer,
        matrix=int(frame_props.get("_Matrix", 2)),
    ))
```

---

### 2. [MODIFY] `src/frame_compare/vs/loader.py`

**Purpose:** Update `DefaultVSLoader.load()` to use `load_source`.

**Changes:**

```python
def load(self, path: Path) -> SourceInfo:
    from frame_compare.vs.source import load_source
    core = self.ensure_core()
    return load_source(path, core)
```

---

### 3. [MODIFY] `src/frame_compare/vs/__init__.py`

**Purpose:** Export `load_source` and `apply_trim` functions.

**Exact addition to `__all__`:**

```python
from frame_compare.vs.source import apply_trim, load_source

__all__ = [
    # existing...
    "load_source",
    "apply_trim",
]
```

---

### 4. [NEW] `tests/vs/test_source.py`

**Purpose:** Unit tests for source loading.

**Test helper - MockClip class (supports slicing):**

```python
from fractions import Fraction
from types import SimpleNamespace
from typing import Mapping


class MockClip:
    """Mock VS clip that supports slicing via __getitem__."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        num_frames: int = 1000,
        fps_num: int = 24,
        fps_den: int = 1,
        frame_props: Mapping[str, object] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.num_frames = num_frames
        self.fps = SimpleNamespace(numerator=fps_num, denominator=fps_den)
        self.format = SimpleNamespace(name="YUV420P8")
        self._frame_props = frame_props or {}

    def get_frame(self, n: int) -> SimpleNamespace:
        return SimpleNamespace(props=self._frame_props)

    def __getitem__(self, s: slice) -> "MockClip":
        """Return sliced clip with updated num_frames."""
        start = s.start or 0
        stop = s.stop if s.stop is not None else self.num_frames
        return MockClip(
            width=self.width,
            height=self.height,
            num_frames=stop - start,
            fps_num=self.fps.numerator,
            fps_den=self.fps.denominator,
            frame_props=self._frame_props,
        )


def make_mock_core(with_lsmas: bool = True, use_lw_namespace: bool = False) -> SimpleNamespace:
    """Create mock VS core with optional lsmas plugin.

    Args:
        with_lsmas: Whether lsmas plugin is available
        use_lw_namespace: If True, use core.lw instead of core.lsmas
    """
    core = SimpleNamespace()
    if with_lsmas:
        loader = SimpleNamespace(LWLibavSource=lambda path: MockClip())
        if use_lw_namespace:
            core.lw = loader
        else:
            core.lsmas = loader
    return core
```

**Tests required (with explicit assertions):**

Load Source Tests:

- `test_load_source_returns_source_info` — Mock core with lsmas, verify all `SourceInfo` fields populated
- `test_load_source_extracts_fps` — Mock clip with 24/1 fps, assert `fps == Fraction(24, 1)`
- `test_load_source_extracts_dimensions` — Mock 3840x2160 clip, assert `width == 3840`, `height == 2160`
- `test_load_source_uses_lw_namespace_fallback` — Mock core with `core.lw.LWLibavSource`, verify loads successfully
- `test_load_source_missing_lsmas_raises_plugin_not_found` — Mock core without lsmas, assert `PluginNotFoundError` raised with `e.code == "FC-2003"`
- `test_load_source_file_error_raises_source_load_error` — Mock `LWLibavSource` to raise, assert `SourceLoadError` raised with `e.code == "FC-4015"`

HDR Detection Tests (per SSOT 5.1 field mapping):

- `test_detect_hdr_pq_bt2020_returns_true` — `{_Transfer: 16, _Primaries: 9}` → `is_hdr=True`
- `test_detect_hdr_hlg_bt2020_returns_true` — `{_Transfer: 18, _Primaries: 9}` → `is_hdr=True`
- `test_detect_hdr_pq_bt709_returns_false` — `{_Transfer: 16, _Primaries: 1}` → `is_hdr=False` (wrong primaries)
- `test_detect_hdr_sdr_returns_false` — `{_Transfer: 1, _Primaries: 1}` → `is_hdr=False`
- `test_detect_hdr_extracts_metadata_fields` — Full HDR props → verify each `HDRMetadata` field matches mapping
- `test_detect_hdr_empty_props_returns_false_and_none` — `{}` → `is_hdr is False` and `hdr_metadata is None`
- `test_detect_hdr_defaults_matrix_when_missing` — `{_Transfer: 16, _Primaries: 9}` (no `_Matrix`) → `is_hdr=True` and `hdr_metadata.matrix == 2`

Apply Trim Tests (per SSOT semantics):

- `test_apply_trim_with_end_is_inclusive` — `apply_trim(source, 100, 200)` → `result.num_frames == 101` (frames 100-200 inclusive)
- `test_apply_trim_end_none_trims_to_end` — `apply_trim(source, 100, None)` on 1000-frame clip → `result.num_frames == 900`

---

### 5. [MODIFY] `tests/vs/test_loader.py`

**Purpose:** Update loader test now that `load()` is implemented.

**Changes:**

- `test_default_vs_loader_load_calls_load_source` — Patch `load_source`, verify called with path and core

---

### 6. [MODIFY] `docs/DECISIONS.md`

**Purpose:** Append run decision entry.

**Required facts:**

- RUN_ID: 2025-12-29__p3-2__video-loading
- Scope: Video source loading via lsmas, HDR detection, DefaultVSLoader completion
- SSOT edits: Added raise contract, apply_trim semantics, HDR field mapping
- Design: lsmas/lw namespace selection per SSOT 1.4, end-inclusive trim

---

### 7. [MODIFY] `CHANGELOG.md`

**Purpose:** Add entry for video loading.

**Entry:**

```markdown
### Added
- Video source loading (`load_source`) with LWLibavSource support
- HDR detection from frame properties (PQ, HLG, BT.2020)
- Frame trimming with inclusive end semantics
```

## Acceptance Criteria

- [ ] GIVEN a valid video path WHEN `load_source(path)` called THEN returns `SourceInfo` with all fields populated
- [ ] GIVEN lsmas is not installed WHEN `load_source(path)` called THEN raises `PluginNotFoundError` with code `FC-2003`
- [ ] GIVEN file is corrupt WHEN `load_source(path)` called THEN raises `SourceLoadError` with code `FC-4015`
- [ ] GIVEN HDR video (_Transfer=16,_Primaries=9) WHEN `load_source(path)` called THEN `is_hdr=True` and `HDRMetadata` populated
- [ ] GIVEN SDR video WHEN `load_source(path)` called THEN `is_hdr=False` and `hdr_metadata=None`
- [ ] GIVEN `apply_trim(source, 100, 200)` WHEN called THEN returns clip with 101 frames (inclusive end)
- [ ] GIVEN `apply_trim(source, 100, None)` on 1000-frame clip WHEN called THEN returns clip with 900 frames
- [ ] GIVEN `DefaultVSLoader().load(path)` WHEN VS available THEN returns `SourceInfo`

## Verification Commands

```bash
# Plan artifact validation (must pass before implementation)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v4.md

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

1. **Loader selection (per SSOT 1.4):** Check `hasattr(core.lsmas, 'LWLibavSource')` not just `hasattr(core, 'lsmas')`
2. **Error propagation:** `PluginNotFoundError` (FC-2003) propagates directly; only file/decode errors become `SourceLoadError`
3. **fps extraction:** `Fraction(clip.fps.numerator, clip.fps.denominator)`
4. **HDR detection (per SSOT 5.1):** `is_hdr = _Transfer in (16, 18) AND _Primaries == 9`
5. **HDR field defaults:** `color_primaries=2, transfer=2, matrix=2` (unspecified per ITU)
6. **Trim semantics:** `end` is inclusive → use `clip[start:end+1]`; `end=None` → `clip[start:]`
7. **Test MockClip:** Must be a class (not SimpleNamespace) so `__getitem__` works for slicing
8. **STOP rule:** If SSOT ambiguity encountered, STOP and return to Planning

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-2__video-loading

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v4.md
