## 2025-12-30 — Phase 3.6 VapourSynth Integration

### Tonemap Alias

**Context:** The Spec Section 8 explicitly requires `tonemap` to be exported from `frame_compare.vs`.

**Decision:** Alias `apply_tonemap` as `tonemap` in `src/frame_compare/vs/__init__.py`.

**Rationale:**
- Satisfies the SSOT requirement.
- Provides a shorter, convenient name for the primary public API.

### Integration Tests

**Context:** Need to verify VapourSynth functionality in a real environment (if available).

**Decision:** Add `test_integration.py` with `@pytest.mark.vs_required` marker.

**Rationale:**
- Allows running smoke tests in environments with VapourSynth installed.
- Skips gracefully in environments without VapourSynth (e.g., some CI jobs or local dev without deps).

## 2026-01-01 — Phase 4.1 Render Types

### Scope

**Context:** Creating foundation for the Render module.

**Decision:** Created `frame_compare.render` module with central type definitions (`OverlayMode`, `EncoderSettings`, `RenderRequest`, `OverlayConfig`, `ScreenshotResult`) and import contracts.

**Rationale:**
- Establishes the data structures for Phase 4 (Rendering).
- `OverlayConfig` and `RenderRequest` decouple rendering from configuration.
- Import contracts prevent dependency cycles with `analysis`.

### SSOT Updates

**Context:** Need validator discoverability for SSOT anchors.

**Decision:** Added example construction snippets to `render-module.md`.

**Rationale:**
- Allows `validate_spec_anchors.py` to mechanically verify that the SSOT examples match the implemented code.

## 2026-01-01 — Workflow: Generated Contract Views

### Scope

**Context:** Contract view regeneration can update derived docs/files without functional impact, but strict plan-scoping caused review failures.

**Decision:** Allow auto-generated contract view diffs produced by `python scripts/generate_contract_views.py` as a documented exception to plan scoping and review blocking, provided Verification confirms freshness and the Coding Agent notes the generated outputs in the Implementation Report.

**Rationale:**
- Keeps contract freshness gates enforceable without unnecessary re-planning.
- Preserves review focus on functional and API-affecting changes.
