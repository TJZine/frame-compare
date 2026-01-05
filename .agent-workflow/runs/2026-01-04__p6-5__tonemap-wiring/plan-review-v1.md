---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v1
TARGET: Phase 6 → Item 6.5 (Tonemap Wiring)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v1.md
---

# Plan Review Report: Tonemap Wiring Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v1.md

Primary blockers:
- **SSOT conflict:** `render-module.md` §1.4.4 specifies raising `RenderError(FC-4004)` with a tonemap/VS-specific hint, but the canonical error contract for FC-4004 (`contracts/error_codes.yaml`) and `errors-module.md` define a different fixed hint/message template. Plan-v1 inherits this mismatch and is not contract-aligned.
- **Plan completeness:** Plan modifies the public signature of `render_screenshots(...)` but does not list the new signature in one-line backticked form and does not list all required call-site updates (existing tests and docs).
- **Test plan mismatch to SSOT:** `render-module.md` §7.2 specifies markers for the planned tonemap wiring tests (`vs_required` for the first two), but plan-v1 marks all four as `integration`.

The spec-anchor STOP gate passes (`validate_spec_anchors.py`), but the plan is not implementation-ready until the SSOT and plan are made internally consistent and call sites are enumerated.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Slice is focused on Phase 6.5 wiring only. |
| 2 | Dependencies | FAIL | Error policy for the VS-missing case is not contract-aligned (FC-4004 hint/message). Also, HDR detection inputs are only defined via VS `SourceInfo`, but plan expects VS-missing + HDR decisions without specifying a mechanism. |
| 3 | File List | FAIL | Missing required call-site updates for `render_screenshots` signature change (at minimum: `tests/render/test_orchestrator.py`, `tests/integration/test_render_orchestrator.py`). |
| 4 | Contract Impact | FAIL | Plan states “Contracts touched: NO” but also specifies behavior that conflicts with the canonical contract for FC-4004; this must be resolved (either adjust SSOT behavior to match contracts or run contract-first loop). |
| 5 | Types Complete | FAIL | Missing one-line backticked signature for the modified `render_screenshots(...)` public API. |
| 6 | Tests Complete | FAIL | Marker policy mismatch vs SSOT (§7.2), and the VS-missing + HDR test approach is underspecified/inconsistent (cannot rely on `SourceInfo.is_hdr` if VS load fails). |
| 7 | Verification Complete | FAIL | Verification commands do not include full quality gates (`.venv/bin/pyright --warnings`, `.venv/bin/ruff check .`) and do not cover all modified files. |
| 8 | Decision-Minimizing | FAIL | Key decisions remain: error type/code for VS-missing tonemap-required case; HDR detection strategy when VS is missing; exact call-site update list. |
| 9 | Determinism Defined | PASS | Gating rule and settings resolution are deterministic in SSOT. |

## Additional Quality Checks

- Error Codes: **Issue** — FC-4004 contract hint/message conflict with SSOT §1.4.4 and plan-v1.
- Failure Modes: **Issue** — “HDR + VS missing” behavior is not implementable as specified without clarifying HDR detection when VS cannot load.
- Derived Outputs: OK — no canonical contracts edited in plan-v1.
- Rollback Guidance: OK — plan includes STOP guidance if signature drift impacts runtime callers, but the plan must pre-enumerate in-repo call sites.
- SSOT Update Audit (if SSOT changed this loop): N/A (plan-v1 claims SSOT unchanged; this review requires SSOT changes).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. **VS-missing error mapping:** Keep FC-4004 (would require contract changes) vs switch to an existing dependency error (e.g., `VapourSynthNotFoundError` FC-2001).
2. **HDR detection when VS is missing:** Without VS, `SourceInfo.is_hdr` is unavailable; SSOT must define how (or whether) to detect HDR to enforce “no fallback when tonemap required”.
3. **Public API change propagation:** Exact set of in-repo callers that must be updated for the `render_screenshots(..., config: ConfigSchema, ...)` signature.

## Concrete Edits Required (plan-v2)

1. **Update SSOT first: make tonemap failure policy contract-aligned**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` → `"1.4.4 Failure Policy"`
   - Problem: Current SSOT example requires a VS/tonemap-specific hint on FC-4004, conflicting with `contracts/error_codes.yaml` for FC-4004 and `errors-module.md`.
   - Required Change: Replace the VS-missing error behavior with a contract-aligned exception mapping (recommended: use `VapourSynthNotFoundError (FC-2001)` for VS-missing in tonemap-required scenarios), and remove the `RenderError(code=..., message=..., hint=...)` example.

2. **Update SSOT first: define HDR detection / fallback rule when VS is unavailable**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` → `"1.4.1 Gating Rule (Deterministic)"` and/or `"Loading Strategy (Auto/VS)"` inside `render_screenshots`
   - Problem: SSOT requires “FFmpeg fallback allowed only when tonemap is not required” but currently only defines HDR detection via VS `SourceInfo` after load.
   - Required Change: Specify one deterministic rule for `renderer="auto"` when VS cannot load:
     - either define a non-VS HDR probe used for gating, or
     - define conservative behavior (e.g., treat tonemap-enabled runs as VS-required and do not fall back), or
     - relax the fail-fast requirement (but then update §1.4.4 + §7.2 accordingly).

3. **Make the plan type-complete for `render_screenshots`**
   - Section: `src/frame_compare/render/orchestrator.py` (MODIFY)
   - Problem: Plan changes a public signature but does not list it as a one-line backticked signature.
   - Required Change: Add a signature bullet reflecting the SSOT signature (including `config: ConfigSchema`).

4. **Complete the file list for signature-change call sites**
   - Section: “Files to Create/Modify”
   - Problem: In-repo call sites exist and will break when `render_screenshots` adds a required `config` parameter.
   - Required Change: Add explicit modifications for:
     - `tests/render/test_orchestrator.py` (MODIFY)
     - `tests/integration/test_render_orchestrator.py` (MODIFY)
     - (and any other `render_screenshots(...)` call sites discovered by search)

5. **Align test markers and expectations to SSOT**
   - Section: `tests/render/test_tonemap_wiring.py` (NEW)
   - Problem: Marker policy conflicts with SSOT §7.2; error expectation conflicts with resolved SSOT/contract decision.
   - Required Change: Update test table to match SSOT marker requirements and the revised error mapping (after SSOT is corrected).

6. **Make verification gates complete**
   - Section: “Verification Commands”
   - Problem: Missing full `pyright`/`ruff` gates and missing coverage for all modified files.
   - Required Change: Add:
     - `.venv/bin/pyright --warnings`
     - `.venv/bin/ruff check .`
     - and include targeted `pytest` runs for modified test modules.

## Ready for Implementation

Return to Planning Agent for SSOT + plan revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-5__tonemap-wiring

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "1.4.4 Failure Policy" add/change:
  - Replace the VS-missing “fail fast” exception mapping so it is contract-aligned (do not require FC-4004 custom hint/message); specify the exact exception type/code to raise.
- Under heading: "1.4.1 Gating Rule (Deterministic)" (and/or the `render_screenshots` loading strategy section) add/change:
  - Define a deterministic rule for how HDR/tonemap-required decisions are made when VS cannot load (or explicitly define conservative/fallback behavior and update §1.4.4 + §7.2 to match).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v1.md
Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
