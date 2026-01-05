---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v1
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v1.md
---

# Plan Review Report: Render Overlay Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v1.md

The plan is not implementation-ready because it fails the SSOT anchoring/mechanical gate expectations (missing backticked one-line signatures), omits a required runtime dependency (`pillow`) from the change list, and leaves test strategy ambiguous/non-deterministic (“pixel sampling or image diff” without a deterministic mechanism).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope list explicit. |
| 2 | Dependencies | FAIL | Runtime dependency on Pillow is implied (`PIL`) but not listed/added; strict Pyright `reportMissingImports=true` will fail if Pillow isn’t installed. |
| 3 | File List | FAIL | Missing `pyproject.toml` update for Pillow; also plan claims it “adds Section 3.2.1” but SSOT already contains `#### 3.2.1` (avoid unnecessary SSOT churn). |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | FAIL | Plan does not provide required backticked one-line public signatures (SSOT anchoring rule / `validate_spec_anchors.py` readiness). |
| 6 | Tests Complete | FAIL | Tests rely on non-deterministic visual assertions and do not specify a deterministic technique (e.g., monkeypatching draw calls to capture text/rect coords). Missing negative test for invalid `config.mode` per SSOT. |
| 7 | Verification Complete | FAIL | Includes `validate_spec_anchors.py` but the plan as written will fail it (no backticked signatures). |
| 8 | Decision-Minimizing | FAIL | Leaves multiple decisions: how to assert text content/position deterministically; whether/how to modify SSOT; how to satisfy Pillow dependency. |
| 9 | Determinism Defined | FAIL | Overlay tests explicitly allow non-determinism (“font rendering varies”) without defining stable assertions. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx` errors.
- Failure Modes: Issue — plan must specify what happens for invalid `config.mode` (SSOT says `ValueError("invalid overlay mode")`) and how to test it deterministically.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — not required beyond correcting plan gates.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How to add/declare Pillow dependency for runtime + Pyright.
2. Deterministic testing strategy for overlay text string and placement.
3. Whether SSOT needs edits in this run (plan claims it does, repo already has `3.2.1`).

## Concrete Edits Required (plan-only)

1. **Add mechanically checkable public signature(s)**
   - Section: Add `## Public API (signatures)` immediately after `## Spec Anchors (SSOT)`
   - Problem: Required by SSOT anchoring rule; also needed so the plan’s own `validate_spec_anchors.py` command can pass.
   - Required Change: Add a backticked one-line signature bullet, e.g.:
     - `apply_overlay(image: Image.Image | np.ndarray, config: OverlayConfig) -> Image.Image`

2. **Declare and add Pillow as a dependency**
   - Section: `## Files to Create/Modify` + `## Dependencies`
   - Problem: Plan imports/uses `PIL` but repo `pyproject.toml` does not include `pillow`; Pyright and runtime will fail.
   - Required Change:
     - Add `pyproject.toml` [MODIFY] to add dependency `pillow>=10.0.0` (matches `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/pyproject.toml`).

3. **Remove incorrect/duplicative SSOT edit claim (avoid churn)**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` [MODIFY]
   - Problem: SSOT already contains `#### 3.2.1 \`apply_overlay\` Behavior` with constants/invalid inputs; plan claims it will add it “during this run”.
   - Required Change: Either:
     - Remove the SSOT doc from the file list and set “SSOT edits: None”, OR
     - If SSOT edits are still needed, specify the exact delta under the exact heading(s) (no vague “added section”).

4. **Make tests deterministic and non-visual**
   - Section: `tests/render/test_overlay.py` test spec
   - Problem: “pixel sampling or image diff” leaves implementation choices and will be flaky across platforms/fonts.
   - Required Change: Replace visual assertions with deterministic call-capture, e.g.:
     - Monkeypatch `frame_compare.render.overlay.ImageDraw.Draw` to a stub that records `text(...)` calls (captures the rendered string) and `rectangle(...)` calls (captures placement).
     - Monkeypatch `frame_compare.render.overlay.calculate_overlay_position` to return a fixed coordinate (e.g., `(10, 10)`) so rectangle placement is deterministic, and assert it is called with `position=config.position`.
     - Add explicit negative test: invalid mode triggers `ValueError("invalid overlay mode")` by constructing `OverlayConfig` with `mode=cast(OverlayMode, "bogus")` (or equivalent deterministic bypass) and asserting the exception/message.

5. **Update `src/frame_compare/render/__init__.py` exports deterministically**
   - Section: `src/frame_compare/render/__init__.py` [MODIFY]
   - Problem: “existing 11 exports …” is a placeholder; plan must not rely on manual inspection.
   - Required Change: Specify: keep all existing entries unchanged and append `"apply_overlay"` to `__all__` (end of list).

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v2.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-4__render-overlay

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v1.md
Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
