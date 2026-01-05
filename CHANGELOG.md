# Changelog

All notable changes to this project are documented in this file.

This project follows Conventional Commits and is intended to be released via Release Please.

## Unreleased

### Added

- **Tonemap Wiring:** Added `should_tonemap`, `resolve_tonemap_settings`, and `probe_is_hdr_ffprobe` helpers. Modified `render_screenshots` to require `config: ConfigSchema` and enforce HDR+tonemap fallback policy (Phase 6.5).
- **VSPreview Integration:** Added `frame_compare.vspreview` module with `is_vspreview_available`, `launch_alignment_verification_session`, `load_manual_overrides`, `save_manual_override`, `ManualOverride`, `VSPreviewConfig`, `VSPreviewNotFoundError` (FC-2008), and `VSPreviewError` (FC-4019). Integrated manual override precedence in `align_clips` (Phase 6.6).
- FramePlan module (`frame_compare.analysis.frame_plan`) for deterministic frame selection (`--skip-analysis`).
- `select_reporter()` function for CLI output mode → progress reporter mapping (Phase 6.3).
- **Preflight Validation:** `prepare_preflight()` for workspace resolution, config loading, and input discovery with `PreflightResult` type (Phase 6.2).
- **Doctor Diagnostics:** `run_doctor()` for environment validation with deterministic check ordering and `DoctorReport` type (Phase 6.2).
- **WorkspacePaths Type:** `WorkspacePaths` dataclass in `frame_compare.utils` for resolved paths (Phase 6.2).
- **NoVideosFoundError Enhancement:** Added `patterns` parameter for deterministic error introspection (Phase 6.2).
- **Orchestration Package Scaffold:** Created `frame_compare.orchestration` package structure (Phase 6.1). Includes scaffold modules for `preflight`, `doctor`, `progress`, and `phases`. Updated import-linter contract.
- **Report Generator:**
  - HTML comparison report generator with Slider, Overlay, Difference, and Blink modes.
  - Dark theme with modern styling.
  - Filmstrip thumbnail navigation.
  - Keyboard shortcuts (←/→ frames, ↑/↓ encodes, S/O/D/B modes).
  - Basic zoom controls (25%-200%).
  - Accessibility features (ARIA labels, keyboard navigation).
- **Publishers Service:**
  - `SlowpicsPublisher` for uploading screenshots to slow.pics.
  - Automatic retry logic with exponential backoff and jitter.
  - Rate limit handling (HTTP 429).
  - Configurable visibility (public/unlisted/private).
  - Optional deletion of local files after successful upload.
- **Metadata Service:**
- Filename parsing strategy using `guessit` and `anitopy` with anime/western priority heuristics.
- TMDB API client with API key validation, rate limit handling, and result mapping.
- Interactive metadata resolution workflow (`resolve_metadata`) with optional user selection callback.
- Audio alignment service (`services.alignment`) for synchronization of comparison clips to reference.
- `ProgressReporter` Protocol and implementations (`RichProgressReporter`, `LogProgressReporter`) in `utils.progress`.
- `render.orchestrator` module for high-level batch rendering and screenshot orchestration
- `ProgressReporter` Protocol for unified progress reporting
- `render.encoders` module with VapourSynth and FFmpeg frame extraction strategies
- `utils.subproc` module for secure subprocess execution
- `render.overlay` module with text overlay rendering and `pillow` dependency
- `render.naming` module with screenshot name generation and label sanitization
- `render.geometry` module with dimension calculation and overlay positioning utilities
- Added `frame_compare.render` module with type definitions
- Phase 4 (Render Module) complete: types, geometry, naming, overlay, encoders, orchestrator with integration tests
- Docker integration verification gate: `tools/verify_docker_integration.sh` + `frame-compare-test` Compose service (real VS+FFmpeg, zero skips)

### Changed

- Workflow: allow auto-generated contract view diffs from `generate_contract_views.py` without blocking review when freshness is verified.
- Workflow: Coding Agent must run the full local gate suite (pyright/ruff/pytest/import-linter + contract freshness check) before handing off `impl-vN.md` to Verification.
- Workflow: Verification Agent may apply Ruff auto-fixes (`ruff check --fix` + `ruff format`, no `--unsafe-fixes`) when Ruff is the only failing quality gate, and must record changes via `impl-v(N+1).md`.
- Workflow: Plan Review may apply mechanical auto-fixes to plans (format/wiring only) and must audit SSOT/spec changes for correctness before approval.
- Workflow: replaced `AGENTS.md` with a token-efficient SSOT pointer + command canon for IDE agents.
- **CI/CD Pipeline:** GitHub Actions workflow with Ruff linting, Pyright type checking, and pytest stages.
- **CI/CD Pipeline:** Add Docker integration workflow for VS+FFmpeg integration tests on relevant PR changes.
- **Phase 0 Foundation:** Project scaffolding with `pyproject.toml`, `src/frame_compare/` structure, and development tooling (Pyright strict, Ruff, pytest).
- CLI entry point with `version` command.
- PEP 561 `py.typed` marker for typed package support.
- Dev dependency `pyyaml` for local contract view checks.
- Dev dependency `import-linter` for running `lint-imports` locally.
- Complete error hierarchy: DependencyError, InputError, ProcessingError, NetworkError, InternalError
- `ExitCode` enum for CLI exit code mapping
- `get_exit_code()` helper function
- `format_error_console()` and `format_error_json()` formatting utilities
- Structured logging infrastructure with structlog (json/console formats)
- Correlation ID tracking for run tracing (`new_run_id`, `get_run_id`)
- CLI foundation commands: `run` (full signature), `wizard`, `doctor`, `preset` (list/apply/save) stubs.
- `handle_error` utility mapping FrameCompareError to exit codes.
- Analysis module types: `ClipIdentity`, `MetricsMetadata`, `FrameMetrics`, `SelectionBreakdown`, `FrameSelection`, `CacheLoadResult`
- Analysis module frame selection algorithms: quantile, motion, and random modes with minimum gap enforcement.
- Analysis module metrics calculation: per-frame luminance and motion analysis (`calculate_metrics`).
- Analysis module cache I/O: deterministic cache key generation, metrics persistence (JSON Schema v2), and failure-resilient cache loading.
- VapourSynth module foundation (`frame_compare.vs`) with environment detection, plugin checks, and `VSLoader` protocol.
- Video source loading (`load_source`) with LWLibavSource support.
- HDR detection from frame properties (PQ, HLG, BT.2020).
- Frame trimming with inclusive end semantics.
- `ColorProps` type for color space properties.
- `get_color_props()` function to extract color properties from clip.
- `is_hdr()` function to detect HDR clips.
- Deterministic color metadata inference and conversion logic (`vs/color.py`).
- `to_rgb24()` utility for high-quality screenshot export with range expansion.
- Opt-in performance timing logs via `FRAME_COMPARE_PERF=1` spans.
- HDR tonemapping (`apply_tonemap`) with 7 presets (BT.2390, Spline, Reinhard).
- libplacebo integration for high-quality tonemapping with automatic Reinhard fallback.
- VapourSynth module integration (`frame_compare.vs` exports).
- Public API alias `tonemap` for convenience.
- Real VapourSynth integration smoke tests (`test_integration.py`).

### Changed

- `ColorProps` range default aligned with SSOT (missing or unspecified `_ColorRange` defaults to limited/1).
- Planning/Plan Review prompts: require copy-forward plan revisions and a `## Changes Since plan-vN` summary to reduce churn during plan iteration.
- Planning/Plan Review/Coding/Review prompts + workflow docs: added SSOT anchoring guardrails (Spec Anchors + one-line signatures + SSOT drift gate), anti-churn line budget + iteration cap, and Review routing rules (implementation defect vs spec drift vs design issue).
- Verification workflow adds `scripts/validate_spec_anchors.py` as a STOP gate for plan/spec consistency.
- Planning/Plan Review prompts: do not gate plan approval on exact `docs/DECISIONS.md` prose; allow large parametric tests to anchor to the SSOT deterministic test vector policy instead of listing exhaustive constructor args.
- Import-linter configuration is treated as SSOT in `importlinter.ini`; docs/workflow updated to match real module paths and require updating `importlinter.ini` whenever new top-level modules are introduced.
- Coding Agent prompt tightened to stop at `impl-vN.md` handoff (no Verification/Review role bleed).
- Coding Agent required to run contract-view freshness check (and regenerate if needed) before handing off to Verification to prevent stale-contract churn.
- Review Agent now outputs a single-line Conventional Commit subject summarizing the full checklist item/run.
- Verification/Review flow now enforces phase gate updates only when the last item in a phase is completed.
- VS module SSOT defines Phase 3.4 color operations API (BT.709/BT.2020 + limited/full handling) and clarifies missing `_ColorRange` defaults.
- Docker build now compiles `zimg` and `l-smash` from official release tarballs with checksum verification, installs Cython via pip for Python 3.13 compatibility, pins L-SMASH-Works to a published tag, and guards SSE2 headers for ARM builds.
- Docker build adds `python3-jinja2` and `libvulkan-dev` to satisfy libplacebo tooling requirements, pins vs-placebo to a commit with submodules, and pins ffms2 to a FFmpeg 5-compatible commit.
- Docker runtime image installs `wget` and `ca-certificates` to support DevContainer server bootstrap.
- Docker runtime image installs `which` so the DevContainer bootstrap can detect `wget`.
- Docker runtime image installs `procps` to provide `ps` for DevContainer bootstrap.
- OPUS rebuild docs synced to the container baseline (`Dockerfile`) and updated to match current Bookworm/pin assumptions (deployment/system design/ADR/vs-module/feature parity).
- Documentation updates L-SMASH Works verification to prefer the `lsmas` namespace with a legacy `lw` fallback.
- Completed Analysis module public API exports (`calculate_metrics`).
- Refactored metrics module to use lazy VapourSynth imports for non-VS environments.

### Fixed

- Docker integration tests now include VS-required tests from `tests/vs/`
- Fixed PIL deprecation warning causing test failure in Docker
- Fixed test collection failure on macOS with partial VapourSynth install
- Fixed libplacebo tonemapping in Docker (16-bit input conversion)
- Fixed `vs.core` access pattern in tonemap module
- Enabled Vulkan in Docker image for libplacebo (Mesa lavapipe)
- Added runtime fallback when libplacebo fails
- Added Docker tonemap integration test; libplacebo success is optional (can be required via `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1`)
- Fixed RGB->RGB conversion error in tonemap module (removed invalid `matrix_in_s` for RGB inputs)
- Fixed Docker test runner to force deterministic lavapipe selection for Vulkan
- Added missing `pytest-mock` dependency to Docker image
