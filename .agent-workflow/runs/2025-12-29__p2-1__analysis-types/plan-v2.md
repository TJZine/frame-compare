---
RUN_ID: 2025-12-29__p2-1__analysis-types
VERSION: v2
TARGET: Phase 2 → Item 2.1
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v2.md
---

# Implementation Plan: Analysis Types

## Changes Since plan-v1

1. **SSOT Updated:** All analysis dataclasses now use `@dataclass(frozen=True, slots=True)` in analysis-module.md.
2. **Added DECISIONS.md:** Required workflow artifact.
3. **Added importlinter.ini:** Adds `frame_compare.analysis` to import layers.

## Context

**Phase:** 2
**Module:** `frame_compare.analysis`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 1 (Config, Errors, Logging, CLI) ✅

## Scope

- [ ] Create `src/frame_compare/analysis/types.py` with frozen dataclasses
- [ ] Create `src/frame_compare/analysis/__init__.py` with exports
- [ ] Write unit tests in `tests/analysis/test_types.py`
- [ ] Update `importlinter.ini` with new module layer
- [ ] Update `docs/DECISIONS.md` with run facts

Out of scope: `metrics.py`, `selection.py`, `cache_io.py`, VapourSynth integration.

## Contract Impact

**Contracts touched:** NO (no canonical contracts affected)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "2.1 FrameMetrics"
  - Section: "2.2 FrameSelection"
  - Section: "2.3 CacheLoadResult"
  - Section: "3.1 calculate_metrics"

## Public API Signatures (spec-anchored)

**Dataclasses to implement (per SSOT Section 2, now frozen):**

1. **ClipIdentity** — `@dataclass(frozen=True, slots=True)` — path, size, mtime, sha1
2. **MetricsMetadata** — `@dataclass(frozen=True, slots=True)` — frame_count, fps, config_fingerprint, clips, version
3. **FrameMetrics** — `@dataclass(frozen=True, slots=True)` — luminance, motion, metadata
4. **SelectionBreakdown** — `@dataclass(frozen=True, slots=True)` — quantile_dark, quantile_bright, motion, random
5. **FrameSelection** — `@dataclass(frozen=True, slots=True)` — frames, mode, seed, breakdown
6. **CacheLoadResult** — `@dataclass(frozen=True, slots=True)` — success, metrics, reason

**Function reference (NOT implemented in this phase):**

- `calculate_metrics(video_paths: list[Path], config: AnalysisConfig, cache_dir: Path, reporter: ProgressReporter | None = None) -> FrameMetrics`

## Files to Create/Modify

### 1. `src/frame_compare/analysis/__init__.py` (NEW)

Export all public types.

### 2. `src/frame_compare/analysis/types.py` (NEW)

Copy dataclass definitions exactly from SSOT Section 2 code blocks.

### 3. `tests/analysis/__init__.py` (NEW)

Empty marker file.

### 4. `tests/analysis/test_types.py` (NEW)

**Tests required:**

- `test_clip_identity_creation`
- `test_clip_identity_optional_sha1`
- `test_clip_identity_frozen` — assignment raises `FrozenInstanceError`
- `test_metrics_metadata_creation`
- `test_metrics_metadata_default_version`
- `test_frame_metrics_creation`
- `test_selection_breakdown_creation`
- `test_frame_selection_creation`
- `test_cache_load_result_success`
- `test_cache_load_result_failure`

### 5. `importlinter.ini` (MODIFY)

Add `frame_compare.analysis` to the import layers contract. Place immediately after `frame_compare.cli_entry`:

```ini
[importlinter:contract:layers]
name = Layers
type = layers
layers =
    frame_compare.cli_entry
    frame_compare.analysis
    frame_compare.config
    frame_compare.utils
    frame_compare.errors
```

### 6. `docs/DECISIONS.md` (MODIFY)

Append run decision entry:

```markdown
## 2025-12-29__p2-1__analysis-types

- **Scope:** Analysis module types (`ClipIdentity`, `MetricsMetadata`, `FrameMetrics`, `SelectionBreakdown`, `FrameSelection`, `CacheLoadResult`)
- **SSOT edits:** analysis-module.md updated to use `@dataclass(frozen=True, slots=True)` for all types
- **Import layers:** Added `frame_compare.analysis` between cli_entry and config
```

### 7. `CHANGELOG.md` (MODIFY)

Under `## [Unreleased]`, add:

```markdown
### Added
- Analysis module types: `ClipIdentity`, `MetricsMetadata`, `FrameMetrics`, `SelectionBreakdown`, `FrameSelection`, `CacheLoadResult`
```

## Acceptance Criteria

- [ ] All dataclasses use `@dataclass(frozen=True, slots=True)`
- [ ] Assignment to frozen field raises `FrozenInstanceError`
- [ ] `SelectionMode` imported from `frame_compare.config`
- [ ] `lint-imports` passes with new layer
- [ ] pyright shows 0 errors

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
.venv/bin/pyright --warnings
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All exit 0.

## Notes for Coding Agent

1. **Frozen dataclasses:** SSOT now specifies `@dataclass(frozen=True, slots=True)` — copy exactly.
2. **SelectionMode:** Import from `frame_compare.config`.
3. **Import layers:** `analysis` goes between `cli_entry` and `config`.
4. **Rollback:** If import contracts fail, STOP and return to Planning.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-1__analysis-types

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-review-v2.md
