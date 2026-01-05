---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v5
TARGET: Phase 4 → Item 4.6
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v5.md
---

# Plan Review Report: Render Orchestrator

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v5.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope. |
| 2 | Dependencies | PASS | Uses typed errors + `DefaultVSLoader` per updated SSOT; bounded submission is reasonable. |
| 3 | File List | PASS | Includes `src/frame_compare/render/orchestrator.py`, `src/frame_compare/render/__init__.py`, tests, and docs updates. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | FAIL | Fails workflow gate: `validate_spec_anchors.py` reports “no function signatures found” because signatures are in code fences, not in required bullet format. |
| 6 | Tests Complete | PASS | Test matrix is specific and covers ordering, fail-fast, progress, VS load/fallback, wrapping, naming, and dict order. |
| 7 | Verification Complete | PASS | Includes `lint-imports` and explicit pass criteria. |
| 8 | Decision-Minimizing | PASS | Algorithm, naming, and exception policies are pinned; no remaining design choices once signature formatting is fixed. |
| 9 | Determinism Defined | PASS | Ordering policies are explicit and covered by tests. |

## SSOT Update Audit (Correctness / Best Practice)

The SSOT “Loading Strategy (Auto/VS)” update to typed errors and unknown-exception wrapping is correct and best-practice aligned for this repo/run:

- Uses typed `frame_compare.errors` (`VapourSynthNotFoundError`, `PluginNotFoundError`, `SourceLoadError`) instead of raw `ImportError`/undefined “PluginError”.
- Specifies `renderer="auto"` fallback with warning and no exception, which is appropriate for an orchestrator boundary.
- Wraps unknown exceptions into `RenderError` with `__cause__`, consistent with project error-chaining style.

No further SSOT changes are required for this run.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NONE (after signature-format fix below)

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Fix signature bullets to satisfy SSOT anchor validator (plan-only)**
   - File: `.agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v5.md`
   - Problem: `python3 scripts/validate_spec_anchors.py ...` fails because signatures are not in the required bullet form.
   - Required Change:
     - Replace the “Public API (signatures)” code fences with bullet entries, e.g.:
       - `- \`render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]\``
       - `- \`render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]\``
     - Ensure these bullets appear under a “Functions to implement” section (or equivalent) so the validator sees them.

## Ready for Implementation

Return to Planning Agent for a surgical plan-v6 revision that makes `validate_spec_anchors.py` pass (no other changes needed).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-6__orchestrator

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v5.md
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v5.md
Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v6.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
