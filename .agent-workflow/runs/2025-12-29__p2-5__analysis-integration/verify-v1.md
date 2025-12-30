---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v1
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v1.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v5.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/verify-v1.md
---

# Verification Failed: Analysis Module Integration

## Summary

**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v5.md
**Implementation Report:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v1.md

## Implementation Review

### Plan Review Gate

- [x] Plan Review Report exists
- [x] Verdict: APPROVED

### Plan Compliance

- [x] All files in plan were created/modified
- [x] No extra files created

## Verification Results

### Quality Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
OK: Spec Anchors valid

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
FAILED (exit 1)

$ .venv/bin/pytest --cov
202 passed, coverage: 94.34%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
No violations
```

### Failed Gate: Ruff

```text
SIM103 Return the condition directly
   --> tests/analysis/test_metrics.py:317:9
    |
315 |               return True
316 |           # Handle: if typing.TYPE_CHECKING:
317 | /         if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
318 | |             return True
319 | |         return False
    | |____________________^
320 |
321 |       def has_vapoursynth_import(nodes: list[ast.stmt]) -> tuple[bool, int]:
    |
help: Inline condition

Found 1 error.
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
✓ All derived views are fresh

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✓ All requirements traced
```

## Issue Analysis

**Root Cause:** The `is_type_checking_guard` function in `test_no_toplevel_vapoursynth_import` uses an if/return pattern that Ruff flags as SIM103 (should inline condition directly).

**Required Fix:** Refactor to:

```python
def is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
```

## Ready for Review

**NO — Return to Coding Agent for fixes.**

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-5__analysis-integration

## Issue to Fix

Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/verify-v1.md
Ruff SIM103 lint error in `tests/analysis/test_metrics.py:317`.

## Your Task

Fix the `is_type_checking_guard` function to inline the condition:

```python
def is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
```

Re-run verification locally:

```bash
.venv/bin/ruff check tests/analysis/test_metrics.py
```

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v2.md
