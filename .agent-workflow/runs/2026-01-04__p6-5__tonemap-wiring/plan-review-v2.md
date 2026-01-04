---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v2
TARGET: Phase 6 → Item 6.5 (Tonemap Wiring)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v2.md
---

# Plan Review Report: Tonemap Wiring Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v2.md

Plan-v2 resolves the major blockers from plan-review-v1:
- SSOT is now contract-aligned for the VS-missing tonemap-required case (uses `VapourSynthNotFoundError (FC-2001)`).
- SSOT defines a deterministic non-VS HDR probe (`probe_is_hdr_ffprobe`) and updates the `render_screenshots(...)` signature to include `config: ConfigSchema`.
- Plan enumerates in-repo call sites and restores full verification gates.
- `validate_spec_anchors.py` passes for plan-v2.

Remaining issues are SSOT/plan completeness gaps that still leave implementation decisions.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Phase 6.5 slice is explicit and bounded. |
| 2 | Dependencies | PASS | Dependencies are named; FFmpeg/ffprobe usage is explicitly isolated behind a probe helper. |
| 3 | File List | PASS | Explicit list includes SSOT spec edit + all in-repo call sites. |
| 4 | Contract Impact | PASS | Contracts are not edited; SSOT behavior now aligns to existing error-code contracts. |
| 5 | Types Complete | PASS | One-line signatures are listed for the public API change and new helpers. |
| 6 | Tests Complete | FAIL | Plan adds new helpers and new control flow but does not specify tests for helper behavior or probe failure modes; existing orchestrator tests will also need explicit mock updates for new `config` parameter. |
| 7 | Verification Complete | PASS | Includes full pyright/ruff/pytest gates + import-linter. |
| 8 | Decision-Minimizing | FAIL | Probe failure behavior is unspecified (SSOT uses `...`), leaving error-handling and fallback decisions to the Coding Agent. |
| 9 | Determinism Defined | PASS | Gating inputs and HDR probe rule are deterministic; remaining gap is failure-policy determinism. |

## Additional Quality Checks

- Error Codes: OK — VS-missing tonemap-required now maps to FC-2001 and avoids FC-4004 customization.
- Failure Modes: **Issue** — `probe_is_hdr_ffprobe` error handling (missing fields / invalid JSON / ffprobe missing) is not specified in SSOT; required for deterministic fallback policy.
- Derived Outputs: OK — no canonical contracts edited.
- Rollback Guidance: OK — STOP guidance exists if signature drift impacts unexpected callers.
- SSOT Update Audit (this loop): OK for the already-applied SSOT edits (error mapping + signature + integration-test marker table); additional SSOT edits are still required to eliminate remaining ambiguity.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. What `probe_is_hdr_ffprobe` does on ffprobe failure / missing metadata (return value vs raised exception, and which error types).
2. How `render_screenshots` behaves when VS load fails AND HDR probe fails (re-raise original VS failure vs raise probe failure).
3. Exact test coverage for new helper functions and new gating branches (currently under-specified).

## Concrete Edits Required (plan-v3)

1. **Update SSOT: define `probe_is_hdr_ffprobe` failure behavior**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Under heading: "1.4.1 Gating Rule (Deterministic)"
   - Problem: The probe function is specified only as `...`, so Coding Agent must decide parse rules and error mapping.
   - Required Change (minimal, deterministic; 3–6 bullets):
     - Define how the probe extracts `color_transfer` and `color_primaries` from ffprobe JSON (stream selection and field names).
     - Define behavior when either field is missing/empty/unknown (raise vs return False).
     - Define behavior when `ffprobe` is missing or returns non-zero / invalid JSON (which exception type is raised).
     - Define how probe failure affects the fallback decision in `render_screenshots` (no fallback vs allow fallback vs propagate).

2. **Update the plan: add explicit tests for helper behavior and new branches**
   - Section: `tests/render/test_tonemap_wiring.py` (NEW) and `tests/render/test_orchestrator.py` (MODIFY)
   - Problem: Current test list covers only VS-missing branches and mocks `probe_is_hdr_ffprobe` directly; it does not validate `should_tonemap`, `resolve_tonemap_settings`, or probe failure behavior that drives determinism.
   - Required Change:
     - Add exact test names and assertions for:
       - `should_tonemap(...)` truth table (HDR/SDR × enable_tonemap True/False).
       - `resolve_tonemap_settings(...)` config-driven overrides (preset + target_nits + tone_curve).
       - At least one probe failure case per the revised SSOT (ensures deterministic non-fallback behavior).
     - For `tests/render/test_orchestrator.py`, specify how to construct a deterministic `ConfigSchema` in tests (avoid env/config-file dependence by passing explicit overrides).

## Ready for Implementation

Return to Planning Agent for SSOT + plan revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-5__tonemap-wiring

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "1.4.1 Gating Rule (Deterministic)" add/change:
  - Specify `probe_is_hdr_ffprobe(path: Path) -> bool` parsing rules (which stream and which JSON fields are used).
  - Specify failure behavior for missing/unknown fields and ffprobe execution/parse failures (exact exception types or exact return policy).
  - Specify how probe failure affects fallback decisions in `render_screenshots` when `config.color.enable_tonemap` is True.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v2.md
Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
