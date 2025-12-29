---
RUN_ID: 2025-12-29__p3-1__vs-environment
VERSION: v1
TARGET: Phase 3 → Item 3.1 Environment
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v1.md
---

# Implementation Plan: VapourSynth Environment (Minimal Vertical Slice)

## Context

**Phase:** 3 (VapourSynth Module)
**Module:** `frame_compare.vs`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** `frame_compare.errors` (leaf module, already implemented)

**Rationale:** Phase 2.2 (Metrics Calculation) requires the VS layer to provide `is_vapoursynth_available()`, `ensure_vs_environment()`, `VSLoader` protocol, and proper typed errors. This run implements the minimal vertical slice of Phase 3.1 needed to unblock Phase 2.2.

## Scope

This plan covers:

- [x] Create `src/frame_compare/vs/` module structure
- [x] Implement `is_vapoursynth_available() -> bool`
- [x] Implement `ensure_vs_environment() -> vs.Core`
- [x] Implement `detect_plugins(core) -> dict[str, bool]`
- [x] Implement `require_plugin(core, plugin) -> None`
- [x] Define `VSLoader` protocol and `DefaultVSLoader` stub
- [x] Define `SourceInfo`, `HDRMetadata`, `TonemapSettings` types
- [x] Add `@pytest.mark.vs_required` marker to conftest
- [x] Write unit tests for availability check and plugin detection

This plan does NOT cover:

- Full source loading (`load_source`) - deferred to Phase 3.2
- Frame properties extraction - deferred to Phase 3.3
- Color operations - deferred to Phase 3.4
- Tonemapping implementation - deferred to Phase 3.5
- `@pytest.mark.vs_required` tests that require actual VapourSynth installation

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
  - Section: "2.4 VapourSynth Tests"
  - Section: "3.1 Pytest Configuration"

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/vs/__init__.py`

**Purpose:** Public exports for VS module.

**Exports:**

- `VSLoader` (Protocol)
- `DefaultVSLoader`
- `SourceInfo`, `HDRMetadata`, `TonemapSettings`
- `is_vapoursynth_available`, `ensure_vs_environment`
- `detect_plugins`, `require_plugin`

---

### 2. [NEW] `src/frame_compare/vs/types.py`

**Purpose:** Type definitions for VS module.

**Types to define:**

- `SourceInfo` — dataclass with fields: `clip`, `width`, `height`, `num_frames`, `fps`, `format`, `frame_props`, `is_hdr`, `hdr_metadata`
- `HDRMetadata` — dataclass with fields: `mastering_display`, `max_cll`, `max_fall`, `color_primaries`, `transfer`, `matrix`
- `TonemapSettings` — dataclass with fields: `enabled`, `preset`, `tone_curve`, `target_nits`, `source_peak`, `contrast_recovery`, `gamma_lift`

**Functions to implement (spec-anchored):**

None in this file (pure types).

---

### 3. [NEW] `src/frame_compare/vs/env.py`

**Purpose:** VapourSynth environment setup and dependency detection.

**Functions to implement (spec-anchored):**

- `is_vapoursynth_available() -> bool` — Check if VapourSynth module can be imported
- `ensure_vs_environment() -> vs.Core` — Initialize and return VapourSynth Core, raise `VapourSynthNotFoundError` if not available
- `detect_plugins(core: vs.Core) -> dict[str, bool]` — Return dict of plugin availability (lsmas, libplacebo, bestsource, ffms2)
- `require_plugin(core: vs.Core, plugin: str) -> None` — Raise `PluginNotFoundError` if plugin not available

---

### 4. [NEW] `src/frame_compare/vs/loader.py`

**Purpose:** VSLoader protocol and default implementation.

**Types to define:**

- `VSLoader` — Protocol with methods `load(path: Path) -> SourceInfo` and `ensure_core() -> vs.Core`
- `DefaultVSLoader` — Class implementing VSLoader with singleton Core pattern

**Methods to implement (spec-anchored via VSLoader Protocol):**

Per section 1.3 VSLoader Protocol, `DefaultVSLoader` implements:

- `ensure_core(self) -> vs.Core` — Get or create singleton Core via `ensure_vs_environment()`
- `load(self, path: Path) -> SourceInfo` — Stub that raises `NotImplementedError` (full impl in Phase 3.2)

---

### 5. [NEW] `tests/vs/__init__.py`

**Purpose:** Test package initialization.

---

### 6. [NEW] `tests/vs/test_env.py`

**Purpose:** Unit tests for VS environment functions.

**Tests required:**

- `test_is_vapoursynth_available_returns_bool` — Verify function returns True/False
- `test_is_vapoursynth_available_no_vs_returns_false` — Mock `importlib.import_module` to simulate missing VS
- `test_ensure_vs_environment_missing_vs_raises_error` — Mock VS unavailable, verify `VapourSynthNotFoundError` raised
- `test_detect_plugins_returns_dict` — Mock Core with plugins, verify dict keys
- `test_detect_plugins_missing_plugin` — Mock Core without plugin, verify False in dict
- `test_require_plugin_missing_raises_error` — Mock Core without plugin, verify `PluginNotFoundError` raised

---

### 7. [MODIFY] `tests/conftest.py`

**Purpose:** Add `vs_required` marker registration.

**Changes:**

- Add `pytest.mark.vs_required` marker to `pytest_configure` or verify it's in `pyproject.toml`

---

### 8. [MODIFY] `importlinter.ini`

**Purpose:** Add `frame_compare.vs` to the layered architecture.

**Changes:**

- Insert `frame_compare.vs` layer between `frame_compare.analysis` and `frame_compare.config`

---

### 9. [MODIFY] `docs/DECISIONS.md`

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: 2025-12-29__p3-1__vs-environment
- Scope: Minimal VS vertical slice for Phase 2.2 unblocking
- SSOT edits: None (types/functions match spec exactly)
- Out-of-scope: Full source loading, tonemapping, color ops
- Deferred items: `load_source` stub raises `NotImplementedError` pending Phase 3.2

---

### 10. [MODIFY] `CHANGELOG.md`

**Purpose:** Add entry for VS module foundation.

**Entry format:**

```
## [Unreleased]
### Added
- VapourSynth module foundation (`frame_compare.vs`) with environment detection and plugin checks
```

## Acceptance Criteria

- [ ] GIVEN VapourSynth is not installed WHEN `is_vapoursynth_available()` is called THEN it returns `False`
- [ ] GIVEN VapourSynth is not installed WHEN `ensure_vs_environment()` is called THEN it raises `VapourSynthNotFoundError` with code `FC-2001`
- [ ] GIVEN a VS Core with lsmas installed WHEN `detect_plugins(core)` is called THEN `{"lsmas": True, ...}` is returned
- [ ] GIVEN a VS Core without libplacebo WHEN `require_plugin(core, "libplacebo")` is called THEN it raises `PluginNotFoundError` with code `FC-2003`
- [ ] GIVEN `DefaultVSLoader.load()` is called THEN it raises `NotImplementedError` (pending Phase 3.2)
- [ ] GIVEN the VS module is imported WHEN `lint-imports` is run THEN it passes (layer architecture respected)

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Quality gates
.venv/bin/pyright --warnings src/frame_compare/vs
.venv/bin/ruff check src/frame_compare/vs
.venv/bin/pytest -v tests/vs/

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract gates (should still pass - no contract changes)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Import guard pattern:** Use try/except ImportError for VS availability check, not `sys.modules` inspection
2. **Singleton Core:** `DefaultVSLoader._core` is a class variable, not instance variable
3. **Plugin namespace aliases:** lsmas may appear as `core.lsmas` or `core.lw` - check both
4. **Type stubs:** VapourSynth types (`vs.Core`, `vs.VideoNode`, `vs.VideoFormat`) should use `TYPE_CHECKING` guard for import
5. **Error imports:** Use `from frame_compare.errors import VapourSynthNotFoundError, PluginNotFoundError`
6. **Test mocking:** When mocking VS unavailability, patch at `frame_compare.vs.env` level, not globally

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-1__vs-environment

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-review-v1.md
