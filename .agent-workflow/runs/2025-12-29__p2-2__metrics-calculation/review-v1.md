---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v1
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/verify-v2.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v2.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Metrics Calculation

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent
**Date:** 2025-12-29
**Files Reviewed:** 8

- src/frame_compare/analysis/metrics.py
- tests/analysis/test_metrics.py
- docs/DECISIONS.md
- CHANGELOG.md
- .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
- .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md
- .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v2.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
OK: Spec Anchors valid for .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
All checks passed

$ .venv/bin/pytest --cov
199 passed, coverage: 94.32%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
No violations

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
✓ All derived views are fresh

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✓ All requirements traced
```

## Checklist Results

### Correctness

- [ ] Issue: calculate_metrics error propagation diverges from SSOT

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [ ] Issue: PluginNotFoundError and SourceLoadError are masked by MetricsCalculationError

### Testing

- [x] Unit tests cover main paths
- [x] Edge cases tested
- [ ] Issue: No test asserting PluginNotFoundError/SourceLoadError propagation from calculate_metrics

### Documentation

- [ ] Issue: calculate_metrics docstring omits raised PluginNotFoundError/SourceLoadError

### Security

- [x] No hardcoded secrets
- [x] Input validation present

### Performance

- [x] No obvious inefficiencies

## Issues Found

### Critical (Must Fix)

None.

### Minor (Should Fix)

1. **calculate_metrics masks source/plugin errors**
   - Location: `src/frame_compare/analysis/metrics.py:85`
   - Issue: `calculate_metrics` catches all exceptions from `loader.load()` and wraps them in `MetricsCalculationError`, but SSOT requires `PluginNotFoundError (FC-2003)` and `SourceLoadError (FC-4015)` to propagate directly.
   - Why it matters: Violates the public error contract in `analysis-module.md` and makes caller error handling ambiguous.
   - Fix: Re-raise `PluginNotFoundError` and `SourceLoadError` untouched; only wrap other exceptions in `MetricsCalculationError`.
   - Minimal suggested diff:

```python
from frame_compare.errors import MetricsCalculationError, PluginNotFoundError, SourceLoadError

try:
    source = loader.load(reference_path)
except (PluginNotFoundError, SourceLoadError):
    raise
except Exception as e:
    raise MetricsCalculationError(f"Failed to load reference video: {e}") from e
```

2. **calculate_metrics docstring missing error contract**
   - Location: `src/frame_compare/analysis/metrics.py:63`
   - Issue: Docstring only lists `MetricsCalculationError`; SSOT lists `PluginNotFoundError` and `SourceLoadError` as raised.
   - Why it matters: Public API docs should match spec and behavior.
   - Fix: Update the Raises section to include `PluginNotFoundError (FC-2003)` and `SourceLoadError (FC-4015)`.

3. **Add propagation tests for error contract**
   - Location: `tests/analysis/test_metrics.py`
   - Issue: No test ensures `calculate_metrics` propagates `PluginNotFoundError`/`SourceLoadError`.
   - Why it matters: Prevents regression and enforces SSOT contract.
   - Fix: Add tests that patch `DefaultVSLoader.load` to raise each error and assert they bubble up unwrapped.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN reference clip WHEN `_calculate_luminance(clip)` called THEN returns list with values in [0.0, 1.0]
- [x] GIVEN static frames WHEN `_calculate_motion(clip)` called THEN returns near-zero scores with `motion[0] == 0.0`
- [x] GIVEN changing frames WHEN `_calculate_motion(clip)` called THEN returns positive motion scores
- [x] GIVEN 0-frame clip WHEN `_calculate_luminance` called THEN raises `MetricsCalculationError (FC-4002)`
- [x] GIVEN 0-frame clip WHEN `_calculate_motion` called THEN raises `MetricsCalculationError (FC-4002)`
- [x] GIVEN valid cache WHEN `calculate_metrics()` called THEN returns cached metrics without recomputing
- [x] GIVEN cache miss WHEN `calculate_metrics()` called THEN computes and caches metrics
- [x] GIVEN multiple video_paths WHEN `calculate_metrics()` called THEN only `video_paths[0]` is analyzed

## Next Steps

### If CHANGES REQUIRED

- Coding Agent: Fix the following:
  1. Update `calculate_metrics` to propagate `PluginNotFoundError` and `SourceLoadError` instead of wrapping them.
  2. Update the `calculate_metrics` docstring to list the propagated errors.
  3. Add tests to assert propagation for both errors.
- Re-submit for review

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-2__metrics-calculation

## Issues to Fix
Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md
See "Issues Found" section for specific fixes required.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md
3. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/review-v1.md

## Your Task
Address all Critical and Minor issues listed in the review report.
Do NOT address Suggestions unless explicitly requested.

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v3.md
