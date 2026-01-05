---
RUN_ID: 2025-12-29__p3-4__color-operations
VERSION: v1
TARGET: Phase 3 → Item 3.4 Color Operations
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-review-v1.md
---

# Implementation Plan (Reconciliation): Color Operations + Perf Spans

## Context

This run reconciles Phase 3.4 “Color Operations” with code that has already been implemented in the repo, plus an opt-in performance instrumentation facility. The purpose is to:

- ensure SSOT/spec is complete and aligned with implementation
- ensure defaults match legacy-proven behavior for older encodes (missing metadata → limited range)
- ensure other agents (Verify/Review) perform a careful audit for regressions and doc contradictions

## Scope

This plan covers:

- [x] Implement `src/frame_compare/vs/color.py` as the single choke-point for:
  - deterministic color metadata inference (BT.709/BT.2020 + SD/HD defaults)
  - deterministic limited/full range handling (default missing → limited)
  - screenshot-oriented RGB24 conversion with full-range export default and optional limited→full expansion
- [x] Align `get_color_props()` default `_ColorRange` with SSOT (missing defaults to limited)
- [x] Add opt-in perf timing spans (`FRAME_COMPARE_PERF=1`) for heavy pipeline sections
- [x] Update SSOT and docs to reflect the above
- [x] Add/adjust tests

Out of scope:

- Implementing `vs/tonemap.py` (Phase 3.5) and its libplacebo integration
- Implementing `render` module and overlay pipeline (Phase 4)
- Adding “signal-based range inference” (PlaneStats sampling). This run intentionally stays deterministic and metadata-driven.

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "2.3 ColorProps"
  - Section: "3.5 Color Operations"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: "4.3 Performance Instrumentation (Opt-in)"

## Public API Signatures (mechanically checkable)

Color ops:

- `infer_color_props(clip: vs.VideoNode, props: ColorProps) -> ColorProps`
- `apply_color_props(clip: vs.VideoNode, props: ColorProps) -> vs.VideoNode`
- `expand_limited_rgb_to_full(clip: vs.VideoNode) -> vs.VideoNode`
- `to_rgb24(clip: vs.VideoNode, *, props: ColorProps, output_range: int = 0, expand_to_full: bool = True, dither_type: str = "error_diffusion") -> vs.VideoNode`

Perf spans:

- `is_perf_enabled() -> bool`
- `perf_span(name: str, **fields: object) -> Iterator[None]`

## Determinism (Required)

- All inference rules are deterministic (purely based on integer props + clip height).
- No content sampling (no PlaneStats) is performed in this run.
- Perf logging is opt-in only. With perf disabled (default), behavior is unchanged.

## Files to Create/Modify (Complete List)

### VS: Color operations + defaults

- `src/frame_compare/vs/color.py` (NEW)
- `src/frame_compare/vs/props.py` (MODIFY: default `_ColorRange` missing → 1)
- `src/frame_compare/vs/types.py` (MODIFY: docstring default clarification)
- `src/frame_compare/vs/__init__.py` (MODIFY: export color ops)

### Perf spans

- `src/frame_compare/utils/perf.py` (NEW)
- `src/frame_compare/utils/__init__.py` (MODIFY: export perf helpers)
- `src/frame_compare/analysis/metrics.py` (MODIFY: add perf spans around heavy loops)

### Typing

- `typings/vapoursynth.pyi` (MODIFY: add constants used by code)

### Tests

- `tests/vs/test_color.py` (NEW: mocked VS color ops tests)
- `tests/vs/test_props.py` (MODIFY: `_ColorRange` defaults assertions)
- `tests/utils/test_perf.py` (NEW: perf enabled/disabled behavior)

### Docs

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` (MODIFY: exports list aligns with new API)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` (MODIFY: add perf module + API spec)
- `docs/DECISIONS.md` (MODIFY: record SSOT decision + perf instrumentation)
- `CHANGELOG.md` (MODIFY: note perf span feature + SSOT clarification)

## Tests (Exact Names + Assertions)

### `tests/vs/test_props.py`

- `test_get_color_props_returns_colorprops_with_defaults`
  - Asserts defaults: `primaries=2`, `transfer=2`, `matrix=2`, `color_range=1`
- `test_get_color_props_partial_props_uses_defaults`
  - Asserts missing range defaults to `1`

### `tests/vs/test_color.py`

- `test_infer_color_props_sd_defaults_to_smpte170m`
  - For height 480 and unspecified values, asserts `matrix/transfer/primaries==6`, range normalized to `1`
- `test_infer_color_props_hd_defaults_to_bt709`
  - For height 1080 and unspecified values, asserts `matrix/transfer/primaries==1`
- `test_infer_color_props_hdr_transfer_backfills_bt2020`
  - For `_Transfer=16` (PQ) and unspecified primaries/matrix, asserts `primaries==9` and matrix backfilled to BT.2020 code
- `test_to_rgb24_passes_resize_kwargs_and_sets_output_props`
  - Asserts `resize.Point` is called with `range_in` and inferred `matrix_in/transfer_in/primaries_in`
  - Asserts expansion runs for input limited + output full
  - Asserts output props: `_Matrix=0`, `_ColorRange=<output_range>`, and transfer/primaries set
- `test_to_rgb24_does_not_expand_when_output_range_limited`
  - Asserts expansion is not called when `output_range==1`

### `tests/utils/test_perf.py`

- `test_is_perf_enabled_default_false` (unset env → False)
- `test_perf_span_disabled_no_log` (unset env → does not call logger)
- `test_perf_span_enabled_logs` (`FRAME_COMPARE_PERF=1` → emits one `perf` event with `elapsed_ms` float)

## Risk / Review Focus (Mandatory Manual Checks)

Verification Agent and Review Agent must manually confirm:

1) **Default `_ColorRange` alignment**
   - SSOT: `vs-module.md` `2.3 ColorProps` default `_ColorRange` is `1`
   - Code: `src/frame_compare/vs/props.py` uses default `1`
   - Tests: `tests/vs/test_props.py` asserts default `1`

2) **No double-expansion of range**
   - `to_rgb24()` expands limited→full only when `(expand_to_full is True) AND (output_range == 0) AND (input range inferred as limited)`

3) **Perf spans are opt-in and leaf-safe**
   - Default behavior unchanged when `FRAME_COMPARE_PERF` unset
   - `src/frame_compare/utils/perf.py` imports only stdlib + structlog (no `analysis/vs/render/...`)

4) **No “unknown Any leakage” / typing regressions**
   - No new `Any` in public signatures
   - Pyright strict remains clean

5) **Docs consistency**
   - `vs-module.md` exports list matches `src/frame_compare/vs/__init__.py`
   - `utils-module.md` includes `perf.py` in module structure and documents its API
   - `DECISIONS.md` and `CHANGELOG.md` reflect the change accurately

## Docs Consistency Audit (Required)

Run this grep and ensure no contradictions remain about `_ColorRange` defaulting to 0:

```bash
rg -n "\\(2, 2, 2, 0\\)|_ColorRange\\\", 0|\\| `color_range`\\s+\\| `_ColorRange`\\s+\\|\\s+int\\s+\\|\\s+0\\b|defaults \\(2, 2, 2, 0\\)" docs src tests
```

**Pass criteria:** no hits outside of legacy-only notes (e.g., `docs/legacy_color_operations_report.md`) or explicitly historical sections. Any hits must be listed by file path and resolved before approval.

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → Command Canon.

```bash
# Validate plan anchors
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-29__p3-4__color-operations
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-29__p3-4__color-operations
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md

# Quality gates
.venv/bin/pyright --warnings
.venv/bin/ruff check src tests
.venv/bin/pytest -q

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** all commands exit 0.

## Rollback Guidance

If any regression in overlay/tonemap output is detected later:

- revert the VS range default change (`src/frame_compare/vs/props.py`) only if SSOT is also reverted
- revert `src/frame_compare/vs/color.py` and restore prior per-call conversion behavior only after creating a new SSOT section that replaces it
- disable perf spans by unsetting `FRAME_COMPARE_PERF` (no code change required)

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-4__color-operations

## Plan to Review
Read file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-review-v1.md
