---
RUN_ID: 2025-12-29__p3-1__vs-environment
VERSION: v3
TARGET: Phase 3 → Item 3.1 Environment
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v2.md
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v3.md
---

# Implementation Plan: VapourSynth Environment (Minimal Vertical Slice)

## Changes Since plan-v2

1. **VS import mechanism explicit:** `env.py` uses `importlib.import_module("vapoursynth")` so tests can patch `frame_compare.vs.env.importlib.import_module`. Updated Notes for Coding Agent to match.
2. **Mock core shapes explicit:** Added deterministic mock core snippet for plugin detection tests using `types.SimpleNamespace`.

## Context

**Phase:** 3 (VapourSynth Module)
**Module:** `frame_compare.vs`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** `frame_compare.errors` (leaf module, already implemented)

## Scope

This plan covers:

- [x] Create `src/frame_compare/vs/` module structure
- [x] Implement `is_vapoursynth_available() -> bool`
- [x] Implement `ensure_vs_environment() -> vs.Core`
- [x] Implement `detect_plugins(core) -> dict[str, bool]`
- [x] Implement `require_plugin(core, plugin) -> None`
- [x] Define `VSLoader` protocol and `DefaultVSLoader` (with typed stub)
- [x] Define `SourceInfo`, `HDRMetadata`, `TonemapSettings` types
- [x] Add `mock_vs` fixture to conftest.py
- [x] Write unit tests for availability check and plugin detection

This plan does NOT cover:

- Full source loading logic (`load_source` function body) - deferred to Phase 3.2
- Frame properties extraction - deferred to Phase 3.3
- Tonemapping implementation - deferred to Phase 3.5

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "3.1 Environment"
  - Section: "1.3 VSLoader Protocol"
  - Section: "1.4 Plugin Detection"
  - Section: "2.1 SourceInfo"
  - Section: "2.2 TonemapSettings"
  - Section: "6. Error Handling"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.2 Dependency Errors (FC-2xxx) — Exit Code 3"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "3.2 Conftest Organization"

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/vs/__init__.py`

**Purpose:** Public exports for VS module.

**Exports (verbatim `__all__`):**

```python
__all__ = [
    "VSLoader",
    "DefaultVSLoader",
    "SourceInfo",
    "HDRMetadata",
    "TonemapSettings",
    "is_vapoursynth_available",
    "ensure_vs_environment",
    "detect_plugins",
    "require_plugin",
]
```

---

### 2. [NEW] `src/frame_compare/vs/types.py`

**Purpose:** Type definitions for VS module.

**Types to define (exact fields per SSOT 2.1/2.2):**

```python
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    import vapoursynth as vs

@dataclass
class HDRMetadata:
    """HDR metadata extracted from source."""
    mastering_display: str | None
    max_cll: int | None
    max_fall: int | None
    color_primaries: int
    transfer: int
    matrix: int

@dataclass
class SourceInfo:
    """Video source metadata."""
    clip: "vs.VideoNode"
    width: int
    height: int
    num_frames: int
    fps: Fraction
    format: "vs.VideoFormat"
    frame_props: Mapping[str, object]
    is_hdr: bool
    hdr_metadata: HDRMetadata | None

@dataclass
class TonemapSettings:
    """Resolved tonemap settings for VS operations."""
    enabled: bool = True
    preset: str = "reference"
    tone_curve: str = "bt2390"
    target_nits: int = 203
    source_peak: int | None = None
    contrast_recovery: float = 0.0
    gamma_lift: bool = False
```

---

### 3. [NEW] `src/frame_compare/vs/env.py`

**Purpose:** VapourSynth environment setup and dependency detection.

**Import mechanism:** Use `importlib.import_module("vapoursynth")` for testability.

**Functions to implement (spec-anchored):**

- `is_vapoursynth_available() -> bool` — Try `importlib.import_module("vapoursynth")` + core creation, return True/False
- `ensure_vs_environment() -> vs.Core` — Return Core, raise `VapourSynthNotFoundError` (FC-2001) if import fails, raise `VapourSynthError` (FC-2002) if core creation fails
- `detect_plugins(core: vs.Core) -> dict[str, bool]` — Return dict with keys: lsmas, libplacebo, bestsource, ffms2
- `require_plugin(core: vs.Core, plugin: str) -> None` — Raise `PluginNotFoundError` (FC-2003) if plugin not available

---

### 4. [NEW] `src/frame_compare/vs/loader.py`

**Purpose:** VSLoader protocol and default implementation.

**Types to define:**

```python
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import vapoursynth as vs
from frame_compare.vs.types import SourceInfo

class VSLoader(Protocol):
    """Protocol for loading VapourSynth clips."""

    def load(self, path: Path) -> SourceInfo:
        """Load a video source, returning clip and metadata."""
        ...

    def ensure_core(self) -> "vs.Core":
        """Get or create a VapourSynth core."""
        ...

class DefaultVSLoader:
    """Default VapourSynth loader implementation using LWLibavSource."""

    _core: "vs.Core | None" = None  # Singleton pattern

    def ensure_core(self) -> "vs.Core":
        if self._core is None:
            from frame_compare.vs.env import ensure_vs_environment
            self._core = ensure_vs_environment()
        return self._core

    def load(self, path: Path) -> SourceInfo:
        from frame_compare.errors import SourceLoadError
        raise SourceLoadError(path, "load_source not implemented (see Phase 3.2)")
```

**Methods (spec-anchored via VSLoader Protocol):**

- `ensure_core(self) -> vs.Core` — Get or create singleton Core via `ensure_vs_environment()`
- `load(self, path: Path) -> SourceInfo` — Raises `SourceLoadError` until Phase 3.2 implements `load_source`

---

### 5. [NEW] `tests/vs/__init__.py`

**Purpose:** Test package initialization (empty file).

---

### 6. [NEW] `tests/vs/test_env.py`

**Purpose:** Unit tests for VS environment functions.

**Mock core shape for plugin tests:**

```python
from types import SimpleNamespace

def make_mock_core(*, lsmas: bool = False, libplacebo: bool = False,
                   bestsource: bool = False, ffms2: bool = False) -> SimpleNamespace:
    """Create a mock VS core with specified plugins."""
    core = SimpleNamespace()
    if lsmas:
        core.lsmas = SimpleNamespace(LWLibavSource=lambda: None)
    if libplacebo:
        core.placebo = SimpleNamespace(Tonemap=lambda: None)
    if bestsource:
        core.bs = SimpleNamespace(VideoSource=lambda: None)
    if ffms2:
        core.ffms2 = SimpleNamespace(Source=lambda: None)
    return core
```

**Tests required:**

- `test_is_vapoursynth_available_returns_bool` — Verify function returns bool type
- `test_is_vapoursynth_available_no_vs_returns_false` — Patch `frame_compare.vs.env.importlib.import_module` to raise `ModuleNotFoundError`, assert returns `False`
- `test_ensure_vs_environment_missing_vs_raises_not_found_error` — Patch `frame_compare.vs.env.importlib.import_module` to raise `ModuleNotFoundError`, verify `VapourSynthNotFoundError` raised with code `FC-2001`
- `test_ensure_vs_environment_core_failure_raises_vs_error` — Patch import success, then mock `.core` access to raise `Exception`, verify `VapourSynthError` raised with code `FC-2002`
- `test_detect_plugins_all_present` — Call `detect_plugins(make_mock_core(lsmas=True, libplacebo=True, bestsource=True, ffms2=True))`, assert all values `True`
- `test_detect_plugins_none_present` — Call `detect_plugins(make_mock_core())`, assert all values `False`
- `test_detect_plugins_lsmas_alias` — Create core with `core.lw.LWLibavSource`, verify `{"lsmas": True, ...}`
- `test_require_plugin_missing_raises_error` — Call `require_plugin(make_mock_core(), "libplacebo")`, verify `PluginNotFoundError` raised with code `FC-2003`
- `test_require_plugin_present_passes` — Call `require_plugin(make_mock_core(lsmas=True), "lsmas")`, verify no exception

---

### 7. [NEW] `tests/vs/test_loader.py`

**Purpose:** Unit tests for VSLoader.

**Tests required:**

- `test_default_vs_loader_load_raises_source_load_error` — Call `DefaultVSLoader().load(tmp_path / "video.mkv")`, verify `SourceLoadError` raised with code `FC-4015`

---

### 8. [MODIFY] `tests/conftest.py`

**Purpose:** Add `mock_vs` fixture per testing-strategy.md section 3.2.

**Exact addition (append after existing fixtures):**

```python
# ─── VapourSynth Stubs ─────────────────────────────────────

@pytest.fixture
def mock_vs(mocker):
    """Mock VapourSynth for unit tests."""
    mock = mocker.MagicMock()
    mocker.patch.dict("sys.modules", {"vapoursynth": mock})
    return mock
```

---

### 9. [MODIFY] `importlinter.ini`

**Purpose:** Add `frame_compare.vs` to the layered architecture.

**Exact final content:**

```ini
[importlinter]
root_package = frame_compare

[importlinter:contract:layers]
name = Layered Architecture
type = layers
layers =
    frame_compare.cli_entry
    frame_compare.analysis
    frame_compare.vs
    frame_compare.config
    frame_compare.utils
    frame_compare.errors
```

---

### 10. [MODIFY] `docs/DECISIONS.md`

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: 2025-12-29__p3-1__vs-environment
- Scope: Minimal VS vertical slice for Phase 2.2 unblocking
- SSOT edits: Updated vs-module.md sections 3.1 and 6 to clarify error classes
- Out-of-scope: Full source loading, tonemapping, color ops
- DefaultVSLoader.load() raises typed `SourceLoadError` pending Phase 3.2

---

### 11. [MODIFY] `CHANGELOG.md`

**Purpose:** Add entry for VS module foundation.

**Entry format:**

```markdown
## [Unreleased]
### Added
- VapourSynth module foundation (`frame_compare.vs`) with environment detection and plugin checks
```

## Acceptance Criteria

- [ ] GIVEN VapourSynth is not installed WHEN `is_vapoursynth_available()` is called THEN it returns `False`
- [ ] GIVEN VapourSynth import fails WHEN `ensure_vs_environment()` is called THEN it raises `VapourSynthNotFoundError` with code `FC-2001`
- [ ] GIVEN VS Core initialization fails WHEN `ensure_vs_environment()` is called THEN it raises `VapourSynthError` with code `FC-2002`
- [ ] GIVEN a mock Core with all plugins WHEN `detect_plugins(core)` is called THEN all values are `True`
- [ ] GIVEN a mock Core without libplacebo WHEN `require_plugin(core, "libplacebo")` is called THEN it raises `PluginNotFoundError` with code `FC-2003`
- [ ] GIVEN `DefaultVSLoader.load(path)` is called THEN it raises `SourceLoadError` with code `FC-4015`
- [ ] GIVEN the VS module is imported WHEN `lint-imports` is run THEN it passes

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

1. **Import mechanism (mandatory):** Use `importlib.import_module("vapoursynth")` in `env.py`:

   ```python
   import importlib

   def is_vapoursynth_available() -> bool:
       try:
           vs = importlib.import_module("vapoursynth")
           _ = vs.core  # Validate core creation
           return True
       except (ImportError, ModuleNotFoundError):
           return False
       except Exception:
           return False
   ```

2. **Tests patch:** `mocker.patch("frame_compare.vs.env.importlib.import_module", ...)`
3. **Singleton Core:** `DefaultVSLoader._core` is a **class variable**, not instance
4. **Plugin namespace aliases:** lsmas → check both `hasattr(core, 'lsmas')` and `hasattr(core, 'lw')`
5. **TYPE_CHECKING guard:** Import `vapoursynth as vs` only under `TYPE_CHECKING`
6. **Error imports:** `from frame_compare.errors import VapourSynthNotFoundError, VapourSynthError, PluginNotFoundError, SourceLoadError`
7. **STOP rule:** If SSOT ambiguity encountered, STOP and return to Planning

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-1__vs-environment

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-review-v3.md
