---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v3
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v2.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v3.md
---

# Implementation Plan: Analysis Module Integration

## Changes Since plan-v2

- **Expanded scope to include `metrics.py` modification** (Review Issue #1: impl-v2 required lazy VapourSynth imports to pass gates on non-VS systems)
- Added explicit file change entry for `metrics.py` lazy imports
- Updated STOP rule for scope clarity

## Context

**Phase:** 2
**Module:** `frame_compare.analysis`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phases 2.1-2.4 completed (types, metrics, selection, cache_io)

This run completes the Analysis Module by:

1. Adding missing `calculate_metrics` export to `__init__.py`
2. Converting `metrics.py` to use lazy VapourSynth imports (required for non-VS test environments)
3. Verifying import contracts pass via `lint-imports`

## Scope

This plan covers:

- [ ] Add `calculate_metrics` export to `analysis/__init__.py`
- [ ] Refactor `metrics.py` to use lazy VapourSynth imports
- [ ] Verify import contracts (no cross-layer imports)
- [ ] Run full quality gates on the analysis module

This plan does NOT cover:

- Changes to `selection.py`, `cache_io.py`, or `types.py`
- Integration with higher layers (Phase 6 runner)
- `ProgressReporter` export (internal protocol, not in SSOT public API)

## Contract Impact

**Contracts touched:** NO

No canonical contract files are modified by this run.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "1.2 Module Structure"
  - Section: "3.1 calculate_metrics"

## Files to Create/Modify

### 1. `src/frame_compare/analysis/__init__.py` (MODIFY)

**Purpose:** Add missing public API export per spec section 3.1.

**Current exports (already present):**

- `CacheLoadResult`, `ClipIdentity`, `FrameMetrics`, `FrameSelection`, `MetricsMetadata`, `SelectionBreakdown`
- `compute_cache_key`, `load_cached_metrics`, `save_metrics_cache`, `select_frames`

**Export to add:**

- `calculate_metrics(video_paths: list[Path], config: AnalysisConfig, cache_dir: Path, reporter: ProgressReporter | None = None) -> FrameMetrics` — from `metrics.py`, per spec section 3.1

**Final `__all__` list (sorted alphabetically):**

```python
__all__ = [
    "CacheLoadResult",
    "ClipIdentity",
    "FrameMetrics",
    "FrameSelection",
    "MetricsMetadata",
    "SelectionBreakdown",
    "calculate_metrics",
    "compute_cache_key",
    "load_cached_metrics",
    "save_metrics_cache",
    "select_frames",
]
```

### 2. `src/frame_compare/analysis/metrics.py` (MODIFY)

**Purpose:** Convert to lazy VapourSynth imports for non-VS test environments.

**Change required:**

1. Move `import vapoursynth as vs` from top-level to `TYPE_CHECKING` block (for type hints only)
2. Add local `import vapoursynth as vs` inside `_calculate_luminance()` function body
3. Add local `import vapoursynth as vs` inside `_calculate_motion()` function body

**Rationale:** This allows `from frame_compare.analysis import calculate_metrics` to succeed on systems without VapourSynth installed (e.g., CI test collection, type checking). The actual VS import only occurs when the functions are called with a real clip.

### 3. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append a run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-29__p2-5__analysis-integration`
- Scope: Added `calculate_metrics` export; refactored to lazy VS imports
- SSOT edits: none
- Verification gates: pass/fail status

### 4. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for Analysis module completion.

**Entry template:** Under `[Unreleased]`:

```markdown
### Changed
- Completed Analysis module public API exports (`calculate_metrics`)
- Refactored metrics module to use lazy VapourSynth imports for non-VS environments
```

## Acceptance Criteria

- [ ] GIVEN `from frame_compare.analysis import calculate_metrics` WHEN Python interpreter runs (without VS) THEN import succeeds
- [ ] GIVEN `.venv/bin/pyright --warnings src/frame_compare/analysis/` WHEN run THEN exits 0 with 0 errors
- [ ] GIVEN `.venv/bin/ruff check src/frame_compare/analysis/` WHEN run THEN exits 0
- [ ] GIVEN `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` WHEN run THEN exits 0 (layered imports pass)
- [ ] GIVEN `.venv/bin/pytest -v tests/analysis/` WHEN run THEN all tests pass

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Plan artifact validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v3.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/

# Import contract gate
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Modify `__init__.py` to add `calculate_metrics` import and `__all__` entry
- Modify `metrics.py` to use lazy imports:
  - Keep `import vapoursynth as vs` in `TYPE_CHECKING` block for type hints
  - Add `import vapoursynth as vs` as first line inside `_calculate_luminance()` and `_calculate_motion()` function bodies
- Do not export `ProgressReporter` — it is an internal protocol
- The `__all__` list should be sorted alphabetically for consistency
- **STOP rule:** If SSOT ambiguity encountered, STOP and return to Planning

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-5__analysis-integration

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v3.md
