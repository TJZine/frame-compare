---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v3
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v3.md
---

# Plan Review Report: Render Overlay Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md

Plan-v3 is close and resolves prior ambiguity around invalid-mode handling and deterministic testing mechanics. Two remaining gaps prevent approval: (1) one test case still uses `OverlayConfig(..., ...)` placeholders, and (2) several assertions are written as “captured text is …” even though SSOT requires two `draw.text()` calls (shadow + foreground), so the plan must specify “contains at least once” to stay deterministic.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Pillow dependency change is included. |
| 3 | File List | PASS | Explicit create/modify list inc. `pyproject.toml`, module/tests, exports, docs. |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | Public signature is present and spec-anchored. |
| 6 | Tests Complete | FAIL | One test row still has config placeholders; some assertions conflict with expected double `text()` draw behavior. |
| 7 | Verification Complete | PASS | Includes spec-anchor validation + pyright/ruff/pytest and deterministic bootstrap note. |
| 8 | Decision-Minimizing | FAIL | Placeholder config requires the Coding Agent to choose values. |
| 9 | Determinism Defined | PASS | Monkeypatch strategy is deterministic once configs/assertions are fully pinned. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx`.
- Failure Modes: OK — invalid-mode behavior is pinned (`ValueError("invalid overlay mode")`).
- Derived Outputs: OK — none.
- Rollback Guidance: OK.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Concrete config values for `test_apply_overlay_calls_position_function` (currently `OverlayConfig(..., ...)`).
2. Exact captured-text assertion semantics for STANDARD/DIAGNOSTIC cases given shadow + foreground draw calls.

## Concrete Edits Required (plan-only)

1. **Eliminate the remaining `OverlayConfig(..., ...)` placeholder**
   - Section: `tests/render/test_overlay.py` test table
   - Problem: `test_apply_overlay_calls_position_function` uses `OverlayConfig(..., position="bottom-right", ...)`.
   - Required Change: Replace with a fully specified config (all required fields), e.g.:
     - `OverlayConfig(mode=OverlayMode.MINIMAL, label="PosTest", frame_number=1, resolution=(100, 100), hdr_info=None, font_path=None, position="bottom-right")`

2. **Make text-capture assertions compatible with shadow + foreground draws**
   - Section: `tests/render/test_overlay.py` test table (STANDARD/DIAGNOSTIC rows)
   - Problem: SSOT requires drawing text twice (shadow then white); tests must not assume a single call.
   - Required Change: Update assertions to “captured text list contains … at least once”, e.g.:
     - STANDARD: `assert any(t == "Ref | Frame 00100 | 1920x1080" for t in captured_text)`
     - DIAGNOSTIC: `assert any("PQ / BT.2020" in t for t in captured_text)` and `assert any("SDR" in t for t in captured_text)`

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: plan-v4.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-4__render-overlay

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md
Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
