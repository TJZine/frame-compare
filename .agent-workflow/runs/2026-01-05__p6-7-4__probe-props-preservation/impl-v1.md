---
RUN_ID: 2026-01-05__p6-7-4__probe-props-preservation
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Preserve HDR/DoVi Props + tonemap_prop_keys)
INPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md
  - src/frame_compare/orchestration/probe_props.py
  - tests/orchestration/test_probe_props.py
---

# Implementation Report: Probe Prop Preservation Helpers (tonemap_prop_keys + preserved_frame_props)

## Summary

**Date:** 2026-01-05
**Plan Reference:** .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
**Plan Review Report:** .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md (APPROVED)

## Files Changed (Exact Paths)

### Created

- `src/frame_compare/orchestration/probe_props.py` — Pure helpers for prop key normalization, tonemap key selection, and TOML-safe prop extraction
- `tests/orchestration/test_probe_props.py` — 9 unit tests covering all plan-specified scenarios

### Modified

- `src/frame_compare/orchestration/__init__.py` — Added exports for `normalize_probe_prop_key`, `compute_tonemap_prop_keys`, `compute_preserved_frame_props`

### Generated (Contract Views Regeneration)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

## Implementation Notes

**Deviations from plan:** NONE

### Cosmetic Fixes

- **Ruff UP038:** Changed `isinstance(..., (str, int, float))` to `isinstance(..., str | int | float)` in `probe_props.py` to satisfy Ruff.

All functions implemented exactly as specified in SSOT sections 3.5.2 and 3.5.3:

1. **`normalize_probe_prop_key(key: str) -> str`** — Strips leading underscores and lowercases for matching.

2. **`compute_tonemap_prop_keys(frame_props: Mapping[str, object]) -> tuple[str, ...]`** — Selects tonemap-related keys using exact and prefix matching per SSOT, returns deterministically sorted tuple by `(normalized, original)`.

3. **`compute_preserved_frame_props(frame_props: Mapping[str, object]) -> dict[str, str | int | float]`** — Filters to TOML-safe primitives, handles DolbyVisionRPU as presence indicator (value `1`), returns dict in sorted key order.

**Key implementation details:**

- Bool is explicitly excluded (`not isinstance(value, bool)`) as it's an int subclass but shouldn't be treated as TOML-safe primitive per SSOT intent.
- DolbyVisionRPU handling preserves the original key (not normalized) with value `1`.

## Local Sanity Checks

| Command | Result |
|---------|--------|
| `.venv/bin/pyright --warnings src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py` | exit 0 (0 errors, 0 warnings) |
| `.venv/bin/ruff check src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py` | exit 0 (All checks passed!) |
| `.venv/bin/pytest -q tests/orchestration/test_probe_props.py` | exit 0 (9 passed) |
| `.venv/bin/pyright --warnings` | exit 0 (0 errors, 0 warnings) |
| `.venv/bin/ruff check .` | exit 0 (All checks passed!) |
| `.venv/bin/pytest -q` | exit 0 (all pass, 2 skipped: VS mocked) |
| `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` | exit 0 (2 contracts kept) |
| `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` | exit 0 (after regeneration) |

## Checklist Item Implemented

> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 6.7: Preserve HDR/DoVi props (`tonemap_prop_keys` + `preserved_frame_props`) — pure helpers

## Open Questions

- None. All acceptance criteria met.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-05__p6-7-4__probe-props-preservation

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
3. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md

## Your Task

1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output

Write file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/verify-v1.md
