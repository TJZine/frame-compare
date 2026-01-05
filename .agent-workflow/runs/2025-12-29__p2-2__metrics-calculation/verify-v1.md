---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v1
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v1.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/verify-v1.md
---

# Verification Failed: Metrics Calculation

## Summary

**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v3.md
**Implementation Report:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v1.md

## Implementation Review

### Plan Review Gate

- [x] Plan Review Report exists
- [x] Verdict: APPROVED

### Plan Compliance

- [x] All files in plan were created
- [x] No extra files created
- [x] Only listed files modified
- [x] Implementation matches plan exactly
- [ ] Deviations: None

### SSOT Drift Check (Hard Gate)

- [x] `scripts/validate_spec_anchors.py` passed for the approved plan

## Verification Results

### Quality Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md
OK: Spec Anchors valid for .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md

$ .venv/bin/pyright --warnings
0 errors

$ .venv/bin/ruff check .
FAILED - 6 errors (see below)

$ .venv/bin/pytest --cov
199 passed, coverage: 94.32%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
No violations
```

### Failed Gate: Ruff

```text
F401 [*] `types.SimpleNamespace` imported but unused
 --> tests/analysis/test_metrics.py:7:19
  |
5 | import sys
6 | from fractions import Fraction
7 | from types import SimpleNamespace
  |                   ^^^^^^^^^^^^^^^
8 | from unittest.mock import MagicMock, patch
  |
help: Remove unused import: `types.SimpleNamespace`

E402 Module level import not at top of file
  --> tests/analysis/test_metrics.py:21:1
   |
19 |   sys.modules["vapoursynth"] = vs_mock
20 |
21 | / from frame_compare.analysis.metrics import (
22 | |     ProgressReporter,
23 | |     _calculate_luminance,
24 | |     _calculate_motion,
25 | |     calculate_metrics,
26 | | )
   | |_^
27 |   from frame_compare.analysis.types import FrameMetrics
28 |   from frame_compare.config.schema import AnalysisConfig
   |

E402 Module level import not at top of file
  --> tests/analysis/test_metrics.py:27:1
   |
25 |     calculate_metrics,
26 | )
27 | from frame_compare.analysis.types import FrameMetrics
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
28 | from frame_compare.config.schema import AnalysisConfig
29 | from frame_compare.errors import MetricsCalculationError
   |

E402 Module level import not at top of file
  --> tests/analysis/test_metrics.py:28:1
   |
26 | )
27 | from frame_compare.analysis.types import FrameMetrics
28 | from frame_compare.config.schema import AnalysisConfig
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
29 | from frame_compare.errors import MetricsCalculationError
   |

E402 Module level import not at top of file
  --> tests/analysis/test_metrics.py:29:1
   |
27 | from frame_compare.analysis.types import FrameMetrics
28 | from frame_compare.config.schema import AnalysisConfig
29 | from frame_compare.errors import MetricsCalculationError
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   |

W292 [*] No newline at end of file
   --> tests/analysis/test_metrics.py:250:61
    |
249 |     # loader.load should only be called once with reference path
250 |     mock_loader.load.assert_called_once_with(video_paths[0])
    |                                                             ^
    |
help: Add trailing newline

Found 6 errors.
[*] 2 fixable with the `--fix` option.
```

## Issues Found

**BLOCKER:** Ruff lint errors in `tests/analysis/test_metrics.py`:

1. **F401:** Unused import `types.SimpleNamespace` — remove it
2. **E402 (x4):** Module-level imports not at top of file — add `# noqa: E402` comments after the `sys.modules` patching block (this pattern is required for vapoursynth mocking)
3. **W292:** No newline at end of file — add trailing newline

## Ready for Review

**NO — Return to Coding Agent for fixes.**

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-2__metrics-calculation

## Issue to Fix

Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/verify-v1.md
See "Verification Results" section for the specific failure.

## Files to Read

1. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v3.md

## Your Task

Fix the Ruff lint errors in `tests/analysis/test_metrics.py`:

1. Remove unused import `types.SimpleNamespace`
2. Add `# noqa: E402` comments to the imports after the sys.modules patching
3. Add trailing newline at end of file

Re-run verification locally:

```bash
.venv/bin/ruff check tests/analysis/test_metrics.py
```

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/impl-v2.md
