---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v4
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v4.md
---

# Plan Review Report: Render Overlay Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md

Plan-v4 fixes the remaining placeholder config and updates assertions to account for shadow+foreground draws, but it reintroduces an incorrect expected string for STANDARD mode (escaped pipes) and regresses verification completeness (missing uv-run fallbacks for tooling gates).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Pillow dependency change included. |
| 3 | File List | PASS | Explicit create/modify list. |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | Public signature present and spec-anchored. |
| 6 | Tests Complete | FAIL | STANDARD-mode expected string incorrectly escapes `|` (should be literal), causing a deterministic failure. |
| 7 | Verification Complete | FAIL | Missing deterministic uv-run fallbacks for pyright/ruff/pytest (workflow requires `.venv/bin/*` preferred + fallback). |
| 8 | Decision-Minimizing | PASS | No remaining placeholders/choices once the string and verification commands are corrected. |
| 9 | Determinism Defined | PASS | Monkeypatch strategy is deterministic with corrected expected strings. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx`.
- Failure Modes: OK — invalid-mode behavior pinned to `ValueError("invalid overlay mode")`.
- Derived Outputs: OK — none.
- Rollback Guidance: OK.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to treat the escaped `\\|` as literal (plan currently does) vs SSOT-required literal `|` output.
2. What fallback commands to run when `.venv/bin/*` is unavailable (plan omits them).

## Concrete Edits Required (plan-only)

1. **Fix STANDARD-mode expected text to match SSOT**
   - Section: `tests/render/test_overlay.py` test table (`test_apply_overlay_standard_mode`)
   - Problem: Plan asserts `t == "Ref \\| Frame 00100 \\| 1920x1080"`, but SSOT format uses literal pipes: `"{label} | Frame {frame_number:05d} | {width}x{height}"`.
   - Required Change: Replace the assertion with:
     - `assert any(t == "Ref | Frame 00100 | 1920x1080" for t in captured_text)`

2. **Restore workflow-consistent tooling fallbacks**
   - Section: `## Verification Commands`
   - Problem: Only `.venv/bin/*` commands are listed; no deterministic fallback commands are provided.
   - Required Change: Add uv-run fallbacks (uncommented) mirroring the primary gates:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/ tests/render/`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/test_overlay.py`

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: plan-v5.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-4__render-overlay

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v4.md
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md
Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
