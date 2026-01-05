---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v2
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v2.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md

Notes:
- `scripts/validate_spec_anchors.py` passes for `plan-v2.md` (signature format issue fixed).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 5 → 5.1). |
| 2 | Dependencies | FAIL | Plan assumes `frame_compare.utils.progress` exists; it does **not** exist in `src/frame_compare/utils/` in the repo state being reviewed. |
| 3 | File List | FAIL | Missing required dependency files (`src/frame_compare/utils/progress.py`, `src/frame_compare/utils/__init__.py` update) OR an explicit precondition/STOP if utils progress is not yet implemented. |
| 4 | Contract Impact | PASS | Explicit **NO**; no contract regen required. |
| 5 | Types Complete | PASS | Public signatures are one-line backticked call forms; SSOT headings are anchored; spec-anchor validator passes. |
| 6 | Tests Complete | FAIL | Cache tests lack concrete TOML bodies + expected parsed `AlignmentResult` values; `_probe_fps` has no test coverage despite being a new SSOT-defined internal with error mapping. |
| 7 | Verification Complete | PASS | Commands + pass criteria present, but must be expanded if the plan adds utils files (typecheck/lint scope). |
| 8 | Decision-Minimizing | FAIL | Remaining decisions: `load_cached_offsets(..., clips)` ordering/selection semantics (SSOT gap), plus how to satisfy `ProgressReporter` import given missing module. |
| 9 | Determinism Defined | PASS | Cross-correlation test vectors + sign convention are explicit; remaining nondeterminism is in cache tests (missing concrete fixtures). |

## Additional Quality Checks

- Error Codes: OK (no new errors proposed).
- Failure Modes: Issue — `load_cached_offsets` behavior for “cache exists but no relevant keys” is not specified (should it return `{}` vs `None`?), and `clips` ordering is ambiguous.
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: Issue — plan needs an explicit STOP rule if a dependency module required by SSOT is missing.
- SSOT Update Audit (if SSOT changed this loop): **Issue**
  - The SSOT updates to `services-module.md` 2.2/2.3 are internally consistent and implementable, but `load_cached_offsets(..., clips)` still has an underspecified contract for how `clips` maps to `{reference_stem}:{comparison_stem}` keys.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. **Missing dependency module:** `from frame_compare.utils.progress import ProgressReporter` cannot work until `src/frame_compare/utils/progress.py` exists (and is exported consistently).
2. **`load_cached_offsets` clip semantics (SSOT gap):** Must define which element is the reference clip, which are comparisons, and whether to ignore extra cache entries / return `{}` vs `None` when no keys match.
3. **Cache round-trip fixtures:** Tests do not specify the exact TOML content and the exact `AlignmentResult` expected after parsing (leaves decisions to the Coding Agent).
4. **`_probe_fps` tests:** No deterministic tests for parsing `r_frame_rate` output or mapping ffprobe failures to `FFmpeg*` errors.

## Concrete Edits Required (plan-v3)

1. **Update SSOT first: finish `load_cached_offsets` contract**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` → `### 2.2 Public API`
   - Problem: `clips` list semantics and cache-hit semantics are ambiguous.
   - Required Change: Specify (a) reference-vs-comparison ordering, (b) what keys are considered “requested”, and (c) whether “cache exists but none requested keys present” returns `{}` or `None`.

2. **Make the plan implementable in the current repo state**
   - Section: Plan → “Files to Create/Modify”
   - Problem: `frame_compare.utils.progress` is referenced but missing in `src/`.
   - Required Change: Add `src/frame_compare/utils/progress.py` (SSOT-aligned) and the exact `src/frame_compare/utils/__init__.py` export changes, OR declare an explicit precondition and STOP (but then this run cannot proceed until the dependency run lands).

3. **Make cache tests mechanically checkable**
   - Section: Plan → `tests/services/test_alignment.py`
   - Problem: Cache tests only assert “key format/schema” without a concrete TOML fixture and expected parsed `AlignmentResult` values.
   - Required Change: Provide the exact TOML fixture text (version + one entry) and the exact expected dict + `AlignmentResult` fields asserted.

4. **Add `_probe_fps` unit tests**
   - Section: Plan → `tests/services/test_alignment.py`
   - Required Change: Add tests for:
     - parsing `"24000/1001"` → `Fraction(24000, 1001)`
     - parsing `"24"` → `Fraction(24, 1)`
     - `FileNotFoundError` → `FFmpegNotFoundError`
     - non-zero exit → `FFmpegError`

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- Under heading: "### 2.2 Public API" add/change:
  - In `load_cached_offsets(cache_dir: Path, clips: list[Path]) -> dict[str, AlignmentResult] | None` docstring, define `clips` ordering as: `clips[0]` is the reference clip and `clips[1:]` are comparisons.
  - Define matching semantics: only keys for `f\"{clips[0].stem}:{comparison.stem}\"` where `comparison` is each element in `clips[1:]` are considered requested; extra entries in the cache file are ignored.
  - Define cache-hit semantics: if the cache file exists and is valid TOML/version, but none of the requested keys are present, return `{}` (not `None`).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
