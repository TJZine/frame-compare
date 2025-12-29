---
RUN_ID: 2025-12-29__p3-3__frame-properties
VERSION: v1
TARGET: Phase 3 → Item 3.3 Frame Properties
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-3__frame-properties/impl-v1.md
  - src/frame_compare/vs/props.py
  - tests/vs/test_props.py
---

# Implementation Report: Frame Properties

## Summary
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-v1.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-review-v1.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/vs/props.py` — Implemented `get_color_props` and `is_hdr` per SSOT 3.4.
- `tests/vs/test_props.py` — 8 unit tests covering color property extraction and HDR detection rules.

### Modified
- `src/frame_compare/vs/types.py` — Added `ColorProps` dataclass per SSOT 2.3.
- `src/frame_compare/vs/__init__.py` — Exported `ColorProps`, `get_color_props`, and `is_hdr`.
- `docs/DECISIONS.md` — Appended Phase 3.3 implementation details.
- `CHANGELOG.md` — Added entries for new frame property features.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` — Regenerated (contract hygiene).
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Regenerated (contract hygiene).
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py` — Regenerated (contract hygiene).

## Implementation Notes
- **Pyright:** Used `# type: ignore` for `clip.get_frame(0)` and `frame.props` as the current `vapoursynth.pyi` stub is incomplete and does not define these members, while `VideoNode` is explicitly typed. This matches the pattern in `source.py`.
- **SSOT Compliance:** HDR detection rule matches `source.py`'s `_detect_hdr` exactly: `_Transfer in (16, 18) AND _Primaries == 9`.
- **Contract Hygiene:** Regenerated derived contract views as they were found to be stale during final verification.

## Local Sanity Checks (Optional)

- `.venv/bin/pyright --warnings src/frame_compare/vs/` — [exit 0]
- `.venv/bin/ruff check src/frame_compare/vs/` — [exit 0]
- `.venv/bin/pytest -v tests/vs/` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented
- [x] Phase 3.3 Frame Properties

## Open Questions
- None.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-3__frame-properties

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p3-3__frame-properties/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-v1.md
3. Read file: .agent-workflow/runs/2025-12-29__p3-3__frame-properties/plan-review-v1.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-3__frame-properties/verify-v1.md
