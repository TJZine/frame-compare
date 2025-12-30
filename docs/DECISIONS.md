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
