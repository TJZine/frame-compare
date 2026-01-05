---
RUN_ID: 2026-01-05__p6-7-4__probe-props-preservation
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Preserve HDR/DoVi Props + tonemap_prop_keys)
INPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/verify-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md (updated)
  - .agent-workflow/index.md (appended)
---

# Verification Handoff: Probe Props Preservation (Amended)

## Summary

**Date:** 2026-01-05
**Plan Reference:** .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
**Plan Review Report:** .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md
**Implementation Report:** .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md

## Implementation Review

### Plan Review Gate

- [x] Plan Review Report exists
- [x] Verdict: APPROVED

### Plan Compliance

- [x] All files in plan were created
- [x] No extra files created
- [x] Only listed files modified
- [x] Implementation matches plan exactly
- [x] **Cosmetic Fix:** Ruff UP038 (`isinstance` union type) applied in `probe_props.py`

### SSOT Drift Check (Hard Gate)

- [x] `scripts/validate_spec_anchors.py` passed for the approved plan
- [x] No behavior/signature drift vs anchored SSOT sections detected

### Documentation Check

- [x] All public functions have docstrings
- [x] Type hints complete
- [x] Module descriptions present

## Verification Results

### Quality Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md

$ .venv/bin/pyright --warnings src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py
0 errors, 0 warnings

$ .venv/bin/ruff check src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py
All checks passed

$ .venv/bin/pytest -q tests/orchestration/test_probe_props.py
9 passed

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Updates

- [x] Marked complete: Preserve HDR/DoVi props in `ClipProbeSnapshot` per spec §3.5 (portable primitives only; record `tonemap_prop_keys`)
- [x] Updated: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md

## Index Updates

- [x] Appended to: .agent-workflow/index.md

## Issues Found

None.

## Ready for Review

All verification gates passed. Handoff to Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-05__p6-7-4__probe-props-preservation

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/verify-v1.md
2. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md
3. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
4. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md

## Preconditions

- Plan Review Report shows Verdict: APPROVED
- All verification gates passed

## Your Task

Perform final quality review and issue verdict.

## Output

Write file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/review-v1.md
