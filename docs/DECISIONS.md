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

## 2026-01-01 — Phase 4.2 Render Geometry

### Scope

**Context:** Implementing geometry utilities for the Render module.

**Decision:** Created `render.geometry` module with `calculate_dimensions`, `calculate_overlay_position`, and `ensure_mod2`. SSOT updated with Sections 5.1–5.3 to define deterministic behavior.

**Rationale:**
- Centralizes dimension and position calculations.
- Ensures compatibility with video encoding (mod2).
- Defines deterministic clamp and rounding behavior.
- Auto-crop deferred to later phase to avoid premature VS integration dependency.

## 2026-01-01 — Phase 4.3 Render Naming

### Scope

**Context:** Implementing screenshot naming utilities.

**Decision:** Created `render.naming` module with `generate_screenshot_name` and `generate_screenshot_path`. SSOT updated with Sections 3.3.1–3.3.2 to define deterministic sanitization and formatting.

**Rationale:**
- Ensures consistent and safe filenames across platforms.
- Sanitizes user-provided labels to prevent invalid path characters.
- Deterministic padding (5 digits) ensures correct lexical sorting.

## 2026-01-01 — Phase 4.4 Render Overlay

### Dependencies

**Context:** Render module requires image processing capabilities for overlays.

**Decision:** Added `pillow>=10.0.0` as a runtime dependency.

**Rationale:**
- Standard Python imaging library.
- Provides necessary text rendering and composition features.
- Version 10.0.0+ ensures modern API availability (e.g., `ImageFont.load_default(size=...)`).

## 2026-01-01 — Phase 4.5 Render Encoders

### Dispatch Logic

**Context:** Need to support both VapourSynth and FFmpeg rendering backends efficiently.

**Decision:** Implemented dual-path dispatch in `render_frame` based on input type (`vs.VideoNode` vs `Path`) and explicit renderer preference.

**Rationale:**
- Allows specialized handling for each backend (direct VS extraction vs FFmpeg subprocess).
- Wraps internal errors (FFmpeg failures, VS exceptions) into `RenderError` for consistent public API surface.

### Secure Subprocess

**Context:** FFmpeg interaction requires shell command execution.

**Decision:** Created `utils.subproc.run_subprocess` to enforce `shell=False`, `check=True`, and timeouts.

**Rationale:**
- Mitigates shell injection risks.
- Provides unified error handling (`CalledProcessError`, `TimeoutExpired`) for all external tools.

## 2026-01-01 — Phase 4.6 Render Orchestrator

## 2026-01-01 — Workflow: Plan Review Mechanical Auto-Fix + SSOT Decision Audit

### Mechanical Auto-Fix Mode

**Context:** Plan iterations can get stuck on purely mechanical issues (validator formatting, NEXT prompt wiring) that require an entire additional Planning round even though no behavioral decisions remain.

**Decision:** Allow the Plan Review Agent to apply a tightly-scoped “Mechanical Auto-Fix Mode” that writes a corrected `plan-v(N+1).md` and an APPROVED `plan-review-v(N+1).md` when (and only when) the remaining issues are semantics-preserving and no SSOT/spec changes are required.

**Rationale:**
- Reduces iteration churn and token usage.
- Preserves the “no bypass” Plan Review gate (the plan must still pass stop-gates like `validate_spec_anchors.py`).

### SSOT Decision Audit

**Context:** When Planning updates SSOT/specs to resolve ambiguity, those changes can accidentally introduce unsound decisions (raw exceptions, nondeterministic behavior, undefined names) unless reviewed explicitly.

**Decision:** Require the Plan Review Agent to audit SSOT/spec changes made during the loop for correctness, implementability, and project best practices before approving a plan.

**Rationale:**
- Prevents spec drift and enforces typed-error, determinism, and layering policies at module boundaries.
- Ensures Planning’s “fill spec gaps” decisions are reviewed with the same rigor as code changes.

### Scope
**Run ID:** 2026-01-01__p4-6__orchestrator
**Context:** High-level orchestration for batch rendering.
**Decision:** Implemented `render_batch` with fail-fast parallel execution using bounded submission and `render_screenshots` with graceful VS-to-FFmpeg fallback.

**Rationale:**
- Fail-fast semantics prevent resource waste on doomed batches.
- Bounded submission in `render_batch` ensures predictable resource usage.
- `render_screenshots` provides a convenient API for common multi-clip, multi-frame tasks.
- VS-to-FFmpeg fallback ensures high-level tasks succeed even if the specialized VS toolchain is unavailable or fails to load a specific source (when `renderer="auto"`).
