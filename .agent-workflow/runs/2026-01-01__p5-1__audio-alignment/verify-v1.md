## Verification Failed: Phase 5.1 Audio Alignment

**RUN_ID:** 2026-01-01__p5-1__audio-alignment
**Failed Gate:** ruff
**Error Output:**

```text
W292 [*] No newline at end of file
  --> src/frame_compare/utils/__init__.py:22:2
   |
20 |     "RichProgressReporter",
21 |     "LogProgressReporter",
22 | ]
   |  ^
   |
help: Add trailing newline

I001 [*] Import block is un-sorted or un-formatted
  --> tests/services/test_alignment.py:3:1
   |
 3 | / from fractions import Fraction
 4 | | from pathlib import Path
 5 | | from unittest.mock import MagicMock, patch
 6 | |
 7 | | import numpy as np
 8 | | import pytest
 9 | | import tomli_w
10 | | from dataclasses import FrozenInstanceError
11 | | from frame_compare.errors import (
...
   |
help: Organize imports

F401 [*] `unittest.mock.MagicMock` imported but unused
 --> tests/services/test_alignment.py:5:27
  |
3 | from fractions import Fraction
4 | from pathlib import Path
5 | from unittest.mock import MagicMock, patch
  |                           ^^^^^^^^^
6 |
7 | import numpy as np
  |
help: Remove unused import: `unittest.mock.MagicMock`
```

**Required Fix:**

1. Add trailing newline to `src/frame_compare/utils/__init__.py`.
2. Sort imports in `tests/services/test_alignment.py`.
3. Remove unused `MagicMock` import in `tests/services/test_alignment.py`.

Return to Coding Agent for fixes.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Issue to Fix

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/verify-v1.md
See "Verification Results" section for the specific failure.

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v9.md

## Your Task

Fix the verification failure. Re-run verification locally.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/impl-v2.md
