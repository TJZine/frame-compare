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

## 2026-01-02 — Phase 4 Integration Tests & Quality Gate

### Scope
**Run ID:** 2026-01-01__p4-integ__render-integration-tests
**Artifact versions:** plan-v3 + plan-review-v3 + impl-v1 + verify-v1 + review-v1 (as written)
**Context:** Integration testing and quality gating for the Render module.
**Decision:** Implemented integration tests covering FFmpeg, VapourSynth (conditional), and Orchestrator. Verified all Phase 4 quality gates including Docker-based validation.

**Rationale:**
- Ensures end-to-end functionality of the render pipeline.
- Validates fallback mechanisms and renderer isolation.
- `mock_video_path` using FFmpeg guarantees deterministic input for tests.
- Docker verification ensures the VapourSynth toolchain works in its target runtime environment.
- Explicit out-of-scope: E2E CLI (Phase 6), Performance benchmarks (Phase 7).
- Verification gates: All passed.

## 2026-01-02 — Phase 5.1 Audio Alignment

### Scope
**Run ID:** 2026-01-01__p5-1__audio-alignment
**Context:** Implementing audio alignment service for clip synchronization.
**Decision:** Created `services.alignment` module with `align_clips`, `load_cached_offsets`, and `save_offsets_cache`. Implemented `utils.progress` with `RichProgressReporter`, `LogProgressReporter`, and `NullProgressReporter`. Updated `importlinter.ini` with correct layered architecture.

**Rationale:**
- Cross-correlation provides frame-accurate synchronization for similar clips.
- `ProgressReporter` protocol allows decoupled progress tracking for CLI and logs.
- Caching avoids redundant expensive audio extraction/correlation.
- Deterministic ordering of results preserves correspondence with input list.
- Import contracts enforced via updated `importlinter.ini` to maintain domain independence.

## 2026-01-02 — Workflow: Docker Integration Verification Gate

### Scope

**Context:** Local developer environments and CI can lack VapourSynth/FFmpeg; passing tests via mocks/conditional skips is not sufficient for “real deps work” phase gates.

**Decision:** Standardize a single Docker-based integration verification gate and wire it into workflow docs:

- `tools/verify_docker_integration.sh` runs `pytest -m "integration or vs_required" tests/integration/` inside the Docker image and fails if any tests are skipped.
- `docker-compose.yml` adds `frame-compare-test` for running tests against real deps with the repo bind-mounted at `/home/framecompare/frame-compare`.
- `Dockerfile` installs `pytest` in the image so Docker verification does not require ad-hoc installs at runtime.
- `.github/workflows/docker-integration.yml` runs the same “zero skips” gate on relevant PR changes.

**Rationale:**
- Preserves fast, skip-tolerant local runs while guaranteeing a deterministic “real deps” verification path.
- Removes command drift (entrypoint/working_dir mismatch) by providing one canonical script.

## 2026-01-02 — Workflow: Verification Ruff Auto-Fix (Narrow Exception)

### Scope

**Context:** Some runs fail verification solely due to Ruff lint/format issues that are safe to auto-fix, causing unnecessary Coding ↔ Verification bounce.

**Decision:** Allow the Verification Agent to apply a **narrow, mechanical** Ruff auto-fix when Ruff is the only failing quality gate:

- Allowed commands: `ruff check --fix` and `ruff format` (no `--unsafe-fixes`)
- Scope: only files that Ruff reports as failing for the current run
- Traceability: if files change, Verification must emit a new `impl-v(N+1).md` documenting the mechanical edits and re-run all quality gates before handoff

**Rationale:**
- Reduces churn for purely mechanical lint fixes.
- Keeps the “Contract-First” and SSOT drift gates intact (no spec/contract edits in Verification).
- Maintains auditability by versioning the implementation artifact when verification makes changes.

## 2026-01-02 — Workflow: Coding Pre-Handoff Gate Run (Required)

### Scope

**Context:** Verification churn is often caused by basic type/lint/test failures that the Coding Agent could have caught with a full local gate run before handoff.

**Decision:** Require the Coding Agent to run the full local gate suite (pyright/ruff/pytest/import-linter + contract freshness check) before declaring `impl-vN.md` ready for Verification.

**Rationale:**
- Reduces back-and-forth for avoidable mechanical failures.
- Keeps Verification focused on compliance, traceability, and phase-gate enforcement rather than first-pass lint/type fixes.

## 2026-01-02 — Phase 5.2 Metadata Service

### Filename Parsing Strategy

**Context:** Need to support both western and anime filename formats.

**Decision:** Implemented a dual-parser strategy in `parse_filename` using `guessit` (western) and `anitopy` (anime), with a priority heuristic based on bracketed groups.

**Rationale:**
- Anime filenames often use bracketed groups (e.g., `[Group] Title - 01`) which `anitopy` handles better.
- Western filenames (e.g., `Movie.Name.2024`) are better handled by `guessit`.
- Fallback to the alternate parser and finally to the filename stem ensures a title is always returned.

### TMDB Search vs. Lookup

**Context:** The spec defines `lookup_tmdb` as returning a single result, but `resolve_metadata` requires multiple results for interactive selection.

**Decision:** Implemented an internal `_search_tmdb` helper that returns a `list[TmdbMetadata]`. `lookup_tmdb` returns the first element, while `resolve_metadata` uses the full list.

**Rationale:**
- Preserves the public API signatures specified in the plan/SSOT.
- Fulfills the requirement for interactive selection in the full resolution workflow.
- Avoids signature drift in `async-semantics.md` examples.

### Dependency Adjustments

**Context:** `anitopy 2.2.0` (as specified in the plan) is not yet available as a stable release on PyPI.

**Decision:** Used `anitopy>=2.1.1` in `pyproject.toml`.

**Rationale:**
- `2.1.1` is the current latest stable version.
- Resolves the dependency conflict that blocked `uv sync`.
- `2.1.1` provides the required functionality for Phase 5.2.


## 2026-01-02: Implement Publishers Service (slow.pics)

- **Context:** Added `SlowpicsPublisher` for uploading comparison screenshots.
- **Decision:**
  - Use `httpx` for async HTTP client, injected from outside.
  - Implement exponential backoff with jitter for retries.
  - Handle rate limits (429) and server errors (5xx) with specific exceptions.
  - Support `delete_after_upload` only on success (never on error).
  - Use `Visibility` enum for public/unlisted/private settings.
- **Status:** Implemented in `src/frame_compare/services/publishers.py`.

## 2026-01-02 — Phase 5.4 Report Service

### Report Viewer Spec

**Context:** Need a portable, offline-friendly, and modern report viewer.

**Decision:** Created `report-viewer-spec.md` as SSOT for the HTML generator.

**Rationale:**
- Defines four modes (Slider, Overlay, Diff, Blink) for comprehensive comparison.
- Specifies dark theme (`#0f1115` background) and accessible controls.
- Embeds data as JSON for single-file portability.
- Uses vanilla JS/CSS for minimal overhead (<30KB overhead).

### Report Generator Implementation

**Context:** Implementing the generator logic.

**Decision:** Implemented `frame_compare.services.report` following `report-viewer-spec.md`.

**Rationale:**
- Strict validation of input data (clips, frames, screenshots) prevents broken reports.
- Deterministic output path fallback (first clip/frame parent).
- Base64 embedding support for true portability.
- Strict type checking (Pyright strict) and rigorous testing (31 tests).

### Scope

**Run ID:** 2026-01-02__p5-4__report-service
**Context:** Phase 5.4 Report Generator.
**Decision:** Implemented `generate_report` with full viewer spec compliance.

**Rationale:**
- Delivers MVP viewer with all core features (modes, zoom, filmstrip, shortcuts).
- Defers advanced features (full zoom/pan, categories) to future phases to maintain velocity.

## 2026-01-03 — Meta: Phase 5 Quality Gate Fixes

### Scope

**Run ID:** 2026-01-02__meta__p5-quality-gate
**Artifact versions:** plan-v1 through plan-v5, verify-v1, impl-v1
**Context:** Unblocking Phase 5 Quality Gate.
**Decision:** Resolved blockers identified in `verify-v1.md` including contract freshness, PIL deprecation warnings, macOS test collection errors, and incomplete Docker integration coverage.

**Rationale:**
- **Contract Freshness:** Regenerated stale views to ensure SSOT consistency.
- **PIL Compatibility:** Replaced `Image.getdata()` with a version-safe approach to avoid `DeprecationWarning` becoming a blocker in Docker.
- **VapourSynth Guards:** Implemented `_vs_needs_mock` and `_vs_spec_available` helpers (spec-anchored in `testing-strategy.md`) to handle `ValueError` from `find_spec` on macOS with partial installs.
- **Docker Coverage:** Included `tests/vs/` in the Docker integration suite to ensure real VapourSynth dependencies are verified with “zero skips”.

### 2026-01-02__meta__p5-quality-gate

**Key Decisions:**
1. libplacebo requires 16-bit input (RGB48)
2. Dockerfile enables Vulkan via Mesa lavapipe
3. Keep `-Dopengl=disabled` for headless libplacebo
4. Runtime fallback: `_apply_libplacebo` returns `None` on failure
5. Docker gate must prove tonemap works without raising; libplacebo success is optional and can be required via `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1`
6. RGB->RGB resize must omit `matrix_in_s` to avoid VapourSynth errors.
7. Docker test runner forces lavapipe selection via `VK_ICD_FILENAMES` for deterministic headless Vulkan.
8. Added `pytest-mock` to Docker image to support `mocker` fixture.
