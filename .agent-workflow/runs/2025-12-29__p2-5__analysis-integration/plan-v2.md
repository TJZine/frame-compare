---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v2
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md
---

# Implementation Plan: Analysis Module Integration

## Changes Since plan-v1

- Removed `ProgressReporter` export from scope (Review Item #1: not required by checklist or SSOT public API)
- Added `validate_spec_anchors.py` to Verification Commands (Review Item #2)
- Fixed typo in scope bullet ("Run full quality gates on `-the" → "Run full quality gates on the analysis module") (Review Item #3)
- Added explicit STOP rule to Notes for Coding Agent (Review Item #3)

## Context

**Phase:** 2
**Module:** `frame_compare.analysis`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phases 2.1-2.4 completed (types, metrics, selection, cache_io)

This run completes the Analysis Module by:

1. Adding missing `calculate_metrics` export to `__init__.py`
2. Verifying import contracts pass via `lint-imports`
3. Ensuring the module is ready for integration with higher layers

## Scope

This plan covers:

- [ ] Add `calculate_metrics` export to `analysis/__init__.py`
- [ ] Verify import contracts (no cross-layer imports)
- [ ] Run full quality gates on the analysis module

This plan does NOT cover:

- Implementation of any new functions (all already exist)
- Changes to `metrics.py`, `selection.py`, `cache_io.py`, or `types.py`
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

**Export to add (already implemented, adding to public API):**

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

### 2. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append a run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-29__p2-5__analysis-integration`
- Scope: Added `calculate_metrics` export to complete Analysis module public API
- SSOT edits: none
- Verification gates: pass/fail status

### 3. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for Analysis module completion.

**Entry template:** Under `[Unreleased]`:

```markdown
### Changed
- Completed Analysis module public API exports (`calculate_metrics`)
```

## Acceptance Criteria

- [ ] GIVEN `from frame_compare.analysis import calculate_metrics` WHEN Python interpreter runs THEN import succeeds
- [ ] GIVEN `.venv/bin/pyright --warnings src/frame_compare/analysis/` WHEN run THEN exits 0 with 0 errors
- [ ] GIVEN `.venv/bin/ruff check src/frame_compare/analysis/` WHEN run THEN exits 0
- [ ] GIVEN `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` WHEN run THEN exits 0 (layered imports pass)
- [ ] GIVEN `.venv/bin/pytest -v tests/analysis/` WHEN run THEN all tests pass

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Plan artifact validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/

# Import contract gate
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- This is a minimal change: only `__init__.py` needs modification (add one import and one `__all__` entry)
- Do not export `ProgressReporter` — it is an internal protocol, not part of the SSOT public API
- Do not modify any other files in `analysis/` — all implementation is complete
- The `__all__` list should be sorted alphabetically for consistency
- After modifying `__init__.py`, run `lint-imports` to confirm no layering violations
- **STOP rule:** If SSOT ambiguity encountered, STOP and return to Planning

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-5__analysis-integration

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v2.md
