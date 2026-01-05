---
RUN_ID: 2026-01-04__p6-7-3__probe-cache-io
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache I/O)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/verify-v1.md
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/impl-v1.md
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Probe Snapshot Cache I/O

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-04
**Files Reviewed:** 7
**Commit Subject:** `feat(orchestration): implement Phase 6.7 probe cache I/O`

### Files Reviewed
- src/frame_compare/orchestration/probe_cache.py
- tests/orchestration/test_probe_cache_io.py
- src/frame_compare/orchestration/__init__.py
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
- .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/impl-v1.md
- .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
- .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest --cov
501 passed, 2 skipped in 3.56s

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [ ] Issue: Probe cache I/O does not follow SSOT `hdr_metadata` table structure
- [ ] Issue: Cache writer does not create parent directories as required by SSOT
- [ ] Issue: Test file path does not match plan (plan requires tests/orchestration/test_probe_cache.py)

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Warn-only behavior for parse/version mismatch implemented

### Testing

- [x] Coverage for failure modes present
- [ ] Issue: Tests do not validate SSOT `hdr_metadata` nested table format

### Documentation

- [x] Public API documented in SSOT

### SSOT Drift (Hard Gate)

- [ ] Issue: Loader/writer uses flattened HDR fields instead of `hdr_metadata` table

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **HDR metadata persistence format deviates from SSOT**
   - Location: src/frame_compare/orchestration/probe_cache.py:89-110, 159-170
   - Issue: SSOT requires an `hdr_metadata` table nested under each entry. Current implementation flattens HDR fields at the entry level and loads from flat keys, which violates the spec and breaks forward compatibility.
   - Fix: Write `hdr_metadata` as a nested table and load from that table only when `is_hdr` is True; update tests to assert nested table serialization.

2. **Cache writer does not create parent directory**
   - Location: src/frame_compare/orchestration/probe_cache.py:174
   - Issue: SSOT mandates that `save_clip_probe_cache` must create parent directories if missing. Current implementation writes directly to `cache_path` without `mkdir`, which will fail for fresh workspaces.
   - Fix: `cache_path.parent.mkdir(parents=True, exist_ok=True)` before writing.

3. **Out-of-plan test file path**
   - Location: tests/orchestration/test_probe_cache_io.py
   - Issue: plan-v2 requires modifying `tests/orchestration/test_probe_cache.py`, but the implementation created `tests/orchestration/test_probe_cache_io.py`. This is a plan deviation and breaks plan compliance.
   - Fix: Move/merge tests into `tests/orchestration/test_probe_cache.py` (or update plan via Planning + Plan Review if a new file is required).

### Minor (Should Fix)

None.

### Suggestions (Nice to Have)

- Consider logging dropped `preserved_frame_props` keys as warn-only per SSOT guidance.

## Acceptance Criteria Verification

- [ ] HDR metadata round-trip per SSOT table format (blocked by Critical #1)
- [ ] Deterministic cache writer creates directories (blocked by Critical #2)
- [x] Missing/parse/version mismatch returns empty mapping
- [x] Invalid entries skipped while valid entries load

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Implement nested `hdr_metadata` table serialization/deserialization per SSOT and update tests accordingly.
  2. Ensure `save_clip_probe_cache` creates parent directories before writing.
  3. Align tests with plan file paths (`tests/orchestration/test_probe_cache.py`) or return to Planning if a new file is required.
- Re-submit for review

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-3__probe-cache-io

## Issues to Fix
Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md
3. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/impl-v2.md
