---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v2
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v2.md
---

# Plan Review Report: Render Overlay Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md

Plan-v2 fixes the major v1 issues (public signature, Pillow dependency, deterministic non-visual testing approach, explicit exports). It still leaves implementation decisions and has test-spec errors that would cause incorrect/flake-prone tests.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Adds Pillow dependency and notes it as runtime. |
| 3 | File List | PASS | Includes `pyproject.toml`, module, tests, `render/__init__.py`, docs updates. |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | `apply_overlay(...) -> ...` signature present. |
| 6 | Tests Complete | FAIL | Several tests are under-specified (`OverlayConfig(..., ...)` placeholders), one expected string is incorrect (escaped `\\|`), and invalid-mode behavior is ambiguous. |
| 7 | Verification Complete | FAIL | Includes `uv sync` without workflow-consistent deterministic flags; plan should avoid introducing a non-deterministic “sync” step as a hard gate. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must choose concrete `OverlayConfig` values for multiple tests and decide how to validate “invalid overlay mode” deterministically. |
| 9 | Determinism Defined | FAIL | “Capture draw calls” is deterministic, but the plan does not fully define what is captured/ asserted per test (e.g., exact config values and string formatting). |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx`.
- Failure Modes: Issue — SSOT requires `ValueError("invalid overlay mode")` when `config.mode` is not a valid `OverlayMode`; plan must specify an exact runtime check strategy that works with the proposed invalid-mode test.
- Derived Outputs: OK — none.
- Rollback Guidance: OK.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Concrete `OverlayConfig` constructor values for tests that currently use `...`.
2. Exact invalid-mode detection strategy (must satisfy SSOT + proposed `cast(OverlayMode, "bogus")` test).
3. Whether/how to run `uv sync` deterministically in a restricted-network environment (the plan should not require an uncontrolled sync step).

## Concrete Edits Required (plan-only)

1. **Fully specify `OverlayConfig` values for every test**
   - Section: `tests/render/test_overlay.py` (test table and monkeypatch example)
   - Problem: Tests currently use `...`, forcing the Coding Agent to invent values for required fields (`frame_number`, `resolution`, `hdr_info`, `font_path`).
   - Required Change: For each test row, specify a complete config tuple, e.g.:
     - `frame_number=100`, `resolution=(1920, 1080)`, `hdr_info=None`, `font_path=None` unless the test varies them.

2. **Fix the expected STANDARD-mode string**
   - Section: `test_apply_overlay_standard_mode`
   - Problem: Plan asserts `"Ref \\| Frame 00100 \\| 1920x1080"` (escaped pipes). SSOT output uses literal `|`.
   - Required Change: Expected text must be exactly: `"Ref | Frame 00100 | 1920x1080"`.

3. **Pin invalid-mode detection behavior (no ambiguity)**
   - Section: `Notes for Coding Agent` + `test_apply_overlay_invalid_mode_raises`
   - Problem: “Check `config.mode in OverlayMode` or use enum member check” is ambiguous and may raise `TypeError` for a `str` value produced by `cast`.
   - Required Change: Specify the exact implementation requirement to match SSOT and the test:
     - `if not isinstance(config.mode, OverlayMode): raise ValueError("invalid overlay mode")`
     - Keep the invalid-mode test as `mode=cast(OverlayMode, "bogus")` and assert the exact message.

4. **Make the monkeypatch strategy consistent and deterministic**
   - Section: “Deterministic Testing Strategy” + example snippet
   - Problem: Plan says “monkeypatch `ImageDraw.Draw`”, but the snippet patches `PIL.ImageDraw.ImageDraw.text`.
   - Required Change: Choose one approach and specify exact patch target(s) for both `text` and `rectangle`, e.g.:
     - Patch `PIL.ImageDraw.ImageDraw.text` and `PIL.ImageDraw.ImageDraw.rectangle`, and assert captured calls.
     - Patch `frame_compare.render.overlay.calculate_overlay_position` to return `(10, 10)` and assert it was called with `position=config.position`.

5. **Replace `uv sync` with workflow-consistent, deterministic guidance**
   - Section: `## Verification Commands`
   - Problem: `uv sync` is not pinned (no `--frozen`) and may require network; the workflow prefers `.venv/bin/*` and documents an offline-friendly bootstrap.
   - Required Change: Remove the standalone `uv sync` line and instead state:
     - “If `.venv` is missing/outdated, bootstrap once: `uv sync --group dev --frozen` (or repo-approved equivalent) before running gates.”
     - Do not make an unpinned sync a mandatory verification step.

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: plan-v3.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-4__render-overlay

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md
Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
