---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v1
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v1.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 5 → 5.1). |
| 2 | Dependencies | FAIL | Missing/resolved dependencies for `ProgressReporter` source and FPS probing (must not violate import layering). |
| 3 | File List | FAIL | Leaves “if exists” branches (progress), and does not list any file that would define/centralize `ProgressReporter`. |
| 4 | Contract Impact | PASS | Explicit **NO**; no derived views required. |
| 5 | Types Complete | FAIL | Public signature bullets include `def`/`async def` prefixes, which will fail `scripts/validate_spec_anchors.py` signature-name matching. |
| 6 | Tests Complete | FAIL | Test names listed, but key test vectors/expected offsets are unspecified (shift direction/sign, tolerances, and cache key semantics). |
| 7 | Verification Complete | PASS | Commands + pass criteria present (but current plan will fail spec-anchor validation until signatures are fixed). |
| 8 | Decision-Minimizing | FAIL | Open decisions: FPS source, cache schema/keying, error propagation, and progress reporter contract/source. |
| 9 | Determinism Defined | FAIL | Deterministic cross-correlation vectors/ordering not specified. |

## Additional Quality Checks

- Error Codes: OK (no new errors proposed), but `align_clips` error propagation is underspecified vs SSOT (`AudioAlignmentError` vs `FFmpeg*`/cache errors).
- Failure Modes: Issue — missing handling policy for empty audio, zero-norm signals (division by zero), and cache parse/version failures.
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: Issue — no explicit “STOP and return to Planning” rule when SSOT gaps are encountered.
- SSOT Update Audit (if SSOT changed this loop): N/A

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. **ProgressReporter source + interface** — plan says “import if exists” but SSOT must define where it lives and which methods are required.
2. **FPS acquisition** — `_samples_to_frames(..., fps: Fraction)` requires a deterministic FPS source that does not violate the import layer contract.
3. **Cache semantics** — file name, schema, dict key meaning for `load_cached_offsets()`, and behavior on parse/version mismatch must be specified.
4. **Error propagation policy** — SSOT currently says `align_clips` raises `AudioAlignmentError`, but plan/tests currently expect `FFmpegError` / `FFmpegNotFoundError` from `_extract_audio`; this must be reconciled explicitly.
5. **Deterministic test vectors** — exact input arrays, expected offsets (including sign), and numeric tolerances must be stated.

## Concrete Edits Required (plan-v2)

1. **Update SSOT first: fill Audio Alignment spec gaps**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`
   - Problem: The Audio Alignment SSOT does not define (a) FPS sourcing, (b) cache schema/keying and error behavior, or (c) the canonical `ProgressReporter` contract/source used by the public API.
   - Required Change: Add the missing requirements under the exact headings listed in the NEXT prompt below, then re-anchor the plan to them.

2. **Make spec-anchor validation pass**
   - Section: Plan → “Public API (signatures…)”
   - Problem: Signature bullets use `def`/`async def` prefixes; `validate_spec_anchors.py` extracts the name as `async def align_clips`, which will never match SSOT’s `def align_clips`.
   - Required Change: Rewrite signature bullets to the validator format, e.g. `align_clips(reference: Path, ...) -> list[AlignmentResult]` (no `def` / `async def`).

3. **Eliminate “if exists” branches**
   - Section: Plan → “Notes for Coding Agent” (#6 ProgressReporter)
   - Problem: “If it exists” forces the Coding Agent to decide file layout and interface.
   - Required Change: Replace with a single explicit source module for `ProgressReporter` and list any file(s) that must be created/modified to provide it.

4. **Make tests deterministic**
   - Section: Plan → “Tests required”
   - Problem: Tests list names but not the exact vectors, expected offset sign, or tolerances.
   - Required Change: For each `_cross_correlate` test, specify (a) the exact reference/comparison arrays, (b) expected `(sample_offset, score)` assertions, and (c) tolerance policy (e.g., `pytest.approx` with explicit abs/rel).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- Under heading: "### 2.2 Public API" add/change:
  - Clarify `align_clips` raised exceptions: explicitly list which of `AudioAlignmentError`, `FFmpegNotFoundError`, `FFmpegError`, `CacheCorruptionError`, `CacheVersionMismatchError` can be raised, and the condition for each.
  - Define the canonical `ProgressReporter` interface used by services (methods + parameter names) OR explicitly reference the canonical source module that provides it.
  - Define `load_cached_offsets(cache_dir: Path, clips: list[Path]) -> dict[str, AlignmentResult] | None` key semantics (what the `str` keys represent) and behavior on corrupted/version-mismatched cache.
- Under heading: "### 2.3 Implementation Details" add/change:
  - Specify the deterministic source of `fps: Fraction` for `_samples_to_frames` (including how `align_clips` obtains it without importing `frame_compare.render`).
  - Specify the cache file name and schema for audio offsets (including a cache version field, and the mapping shape used to round-trip `AlignmentResult`).
  - Specify failure-mode rules for empty audio and zero-norm correlation normalization (exact error raised and required `reason` string content policy).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v1.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
