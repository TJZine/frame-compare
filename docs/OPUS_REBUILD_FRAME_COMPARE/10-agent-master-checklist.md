# Frame Compare 2.0 — AI Agent Master Implementation Checklist

> **Version:** 1.0
> **Last Updated:** 2025-12-20
> **Purpose:** Best practice tracking for AI coding agents across implementation sessions

---

## How to Use This Document

1. **Before Starting:** Read the relevant phase/module documentation
2. **During Work:** Update checkboxes as items are completed
3. **Session Handoff:** Mark current status and any blockers
4. **Quality Gates:** Complete all checks before moving to next phase

> [!NOTE]
> If you are working in an already-initialized repo (existing `src/`, `tests/`, `pyproject.toml`, and CI), skip Phase 0 items that are already true in your working tree and start at the first Phase 1+ item that is not implemented yet.

---

## Phase 0: Foundation

### 0.1 Repository Setup

- [x] Clone repository or create new project directory (2025-12-28)
- [x] Initialize Git with `.gitignore` for Python (2025-12-28)
- [ ] Create branch protection rules (main requires PR)
- [x] Setup `pyproject.toml` with build system (2025-12-28)

### 0.2 Project Structure

```text
frame-compare/
├── src/frame_compare/
│   ├── __init__.py
│   ├── py.typed
│   ├── analysis/
│   ├── vs/
│   ├── render/
│   ├── services/
│   └── cli_entry.py
├── tests/
│   ├── conftest.py
│   └── fixtures/
├── config/
├── docs/
├── pyproject.toml
├── README.md
└── Dockerfile
```

- [x] Create `src/frame_compare/` directory structure (2025-12-28)
- [x] Add `py.typed` marker file (2025-12-28)
- [x] Create `__init__.py` with version export (2025-12-28)
- [x] Create `tests/` directory with `conftest.py` (2025-12-28)
- [ ] Add initial `README.md`

### 0.3 Development Tooling

- [x] Configure `pyproject.toml` dependencies: (2025-12-28)
  - [x] Runtime: `typer`, `rich`, `numpy`, `httpx`, `pydantic` (TOML via stdlib `tomllib`)
  - [x] Dev: `pytest`, `pytest-mock`, `pyright`, `ruff`, `structlog`
- [x] Configure Pyright in strict mode (2025-12-28)
- [x] Configure Ruff with rules: `E`, `F`, `I`, `W`, `UP` (2025-12-28)
- [x] Setup pre-commit hooks (optional but recommended) (2025-12-28)
- [x] Verify: `uv sync` completes successfully (2025-12-28)

### 0.4 CI/CD Pipeline

- [x] Create `.github/workflows/ci.yml`: (2025-12-28)
  - [x] Lint stage (Ruff)
  - [x] Type check stage (Pyright)
  - [x] Test stage (pytest)
  - [x] Python 3.13 matrix
- [x] Verify CI passes on push (2025-12-28)

### 0.5 Container Setup

- [x] Create multi-stage `Dockerfile` (2025-12-28)
- [x] Build VapourSynth R73 in container (2025-12-28)
- [x] Install libplacebo with software rasterization (2025-12-28)
- [x] Create `docker-compose.yml` (2025-12-28)
- [x] Create `.devcontainer/devcontainer.json` (2025-12-28)
- [x] Verify: `docker compose build` succeeds (2025-12-28)
- [x] Verify: DevContainer opens in VS Code (2025-12-28)

### Phase 0 Quality Gate ✓

- [x] `uv sync` completes (2025-12-28)
- [x] `.venv/bin/pyright --warnings` shows 0 errors (2025-12-28)
- [x] `.venv/bin/ruff check .` shows 0 errors (2025-12-28)
- [x] `.venv/bin/pytest` runs (empty suite OK) (2025-12-28)
- [ ] CI workflow passes
- [x] Docker container builds

---

## Phase 1: Core Infrastructure

### 1.1 Configuration Module

**Reference:** `03-architecture/api-design.md` (Section 4)

- [x] Create `src/frame_compare/config/` (2025-12-29)
- [x] Define Pydantic models: (2025-12-29)
  - [x] `PathsConfig`
  - [x] `AnalysisConfig`
  - [x] `ColorConfig`
  - [x] `ScreenshotsConfig`
  - [x] `SlowpicsConfig`
  - [x] `TmdbConfig`
  - [x] `AudioAlignmentConfig`
  - [x] `ReportConfig`
  - [x] `ConfigSchema` (root)
- [x] Implement `load_config(path: Path) -> ConfigSchema` (2025-12-29)
- [x] Implement environment variable overrides (2025-12-29)
- [x] Write unit tests for config loading (2025-12-29)
- [x] Write validation tests (2025-12-29)
- [x] Verify Pyright passes (2025-12-29)

### 1.2 Error Handling

**Reference:** `05-implementation/error-handling.md`

- [x] Create `src/frame_compare/errors.py` (2025-12-29)
- [x] Implement `ErrorContext` dataclass (2025-12-29)
- [x] Implement `FrameCompareError` base class (2025-12-29)
- [x] Implement exception hierarchy: (2025-12-29)
  - [x] `ConfigError` (+ subtypes)
  - [x] `DependencyError` (+ subtypes)
  - [x] `InputError` (+ subtypes)
  - [x] `ProcessingError` (+ subtypes)
  - [x] `NetworkError` (+ subtypes)
  - [x] `InternalError`
- [ ] Implement `Result[T, E]` pattern (optional)
- [x] Write unit tests for error handling (2025-12-29)
- [x] Verify all exceptions have error codes and hints (2025-12-29)

### 1.3 Logging Infrastructure

**Reference:** `06-operations/monitoring.md`

- [x] Create `src/frame_compare/utils/logging.py` (2025-12-29)
- [x] Configure structlog with JSON output (2025-12-29)
- [x] Implement correlation ID tracking (2025-12-29)
- [ ] Create logger per module
- [x] Write tests for log output format (2025-12-29)

### 1.4 CLI Foundation

**Reference:** `03-architecture/api-design.md` (Section 2)

- [x] Create `src/frame_compare/cli_entry.py`
- [x] Implement Typer app + commands
- [x] Add global options: `--root`, `--config`, `--quiet`, `--verbose`
- [x] Implement `run` command (stub)
- [x] Implement `wizard` command (stub)
- [x] Implement `doctor` command (stub)
- [x] Implement `preset` command group (stub)
- [x] Map exceptions to exit codes
- [x] Write CLI integration tests

### Phase 1 Quality Gate ✓

- [x] Config loads and validates TOML (2025-12-29)
- [x] Errors have codes, messages, hints (2025-12-29)
- [x] Logs output structured JSON (2025-12-29)
- [x] CLI responds to basic commands (2025-12-29)
- [x] Pyright shows 0 errors (2025-12-29)
- [x] Test coverage > 80% (94.34%) (2025-12-29)

---

## Phase 2: Analysis Module

### 2.1 Types

**Reference:** `05-implementation/module-specs/analysis-module.md`

- [x] Create `src/frame_compare/analysis/types.py`
- [x] Define `ClipIdentity` (path, hash, frame_count)
- [x] Define `FrameMetrics` (luminance, motion arrays)
- [x] Define `MetricsMetadata` (version, timestamp, config_hash)
- [x] Define `SelectionMode` enum (QUANTILE, MOTION, RANDOM)
- [x] Define `SelectionBreakdown` (counts per mode)
- [x] Define `FrameSelection` (frames, breakdown)

### 2.2 Metrics Calculation

- [x] Create `src/frame_compare/analysis/metrics.py` (2025-12-29)
- [x] Implement `calculate_metrics(clip, progress) -> FrameMetrics` (2025-12-29)
- [x] Implement `_calculate_luminance(frames) -> list[float]` (2025-12-29)
- [x] Implement `_calculate_motion(frames) -> list[float]` (2025-12-29)
- [x] Add progress reporting callbacks (2025-12-29)
- [x] Write unit tests with mock frames (2025-12-29)
- [x] Write edge case tests (empty, single frame) (2025-12-29)

### 2.3 Frame Selection

- [x] Create `src/frame_compare/analysis/selection.py`
- [x] Implement `select_frames(metrics, count, seed) -> FrameSelection`
- [x] Implement `_select_by_quantile(metrics, n) -> list[int]`
- [x] Implement `_select_by_motion(metrics, n) -> list[int]`
- [x] Implement `_select_random(count, n, seed) -> list[int]`
- [x] Verify determinism with same seed
- [x] Write unit tests
- [x] Write property-based tests (always returns n unique frames)

### 2.4 Caching

- [x] Create `src/frame_compare/analysis/cache_io.py` (2025-12-29)
- [x] Implement `compute_cache_key(clip, config) -> str` (2025-12-29)
- [x] Implement `load_cached_metrics(path) -> FrameMetrics | None` (2025-12-29)
- [x] Implement `save_metrics_cache(path, metrics)` (2025-12-29)
- [x] Handle cache versioning (2025-12-29)
- [x] Handle cache invalidation (2025-12-29)
- [x] Write cache round-trip tests (2025-12-29)
- [x] Write invalidation tests (2025-12-29)

### 2.5 Module Integration

- [x] Create `src/frame_compare/analysis/__init__.py` (2025-12-29)
- [x] Export public API: `calculate_metrics`, `select_frames`, types (2025-12-29)
- [x] Verify import contracts (no cross-layer imports) (2025-12-29)

### Phase 2 Quality Gate ✓

- [x] Metrics calculate correctly (2025-12-29)
- [x] Selection is deterministic (2025-12-29)
- [x] Cache hit/miss works (2025-12-29)
- [x] All tests pass (2025-12-29)
- [x] Pyright shows 0 errors (2025-12-29)
- [x] Test coverage > 85% (91.51%) (2025-12-29)

---

## Phase 3: VapourSynth Module

### 3.1 Environment

**Reference:** `05-implementation/module-specs/vs-module.md`

- [x] Create `src/frame_compare/vs/env.py` (2025-12-29)
- [x] Implement `init_vapoursynth() -> vs.Core` (2025-12-29)
- [x] Handle VapourSynth not available gracefully (2025-12-29)
- [x] Configure cache size (2025-12-29)
- [x] Add `@pytest.mark.vs_required` marker (2025-12-29)

### 3.2 Video Loading

- [x] Create `src/frame_compare/vs/source.py` (2025-12-29)
- [x] Implement `load_video(path) -> Result[VideoNode, str]` (2025-12-29)
- [x] Support formats: `.mkv`, `.mp4`, `.avi`, `.m2ts`, `.ts` (2025-12-29)
- [x] Use lsmas for loading (2025-12-29)
- [x] Extract clip properties (fps, frame_count, resolution) (2025-12-29)

### 3.3 Frame Properties

- [x] Create `src/frame_compare/vs/props.py` (2025-12-29)
- [x] Implement `get_color_props(frame) -> ColorProps` (2025-12-29)
- [x] Implement `is_hdr(clip) -> bool` (2025-12-29)
- [x] Detect PQ (_Transfer == 16) (2025-12-29)
- [x] Detect HLG (_Transfer == 18) (2025-12-29)
- [x] Detect BT.2020 primaries (2025-12-29)

### 3.4 Color Operations

- [x] Create `src/frame_compare/vs/color.py` (2025-12-29)
- [x] Implement color space conversions (2025-12-29)
- [x] Handle BT.709, BT.2020 (2025-12-29)
- [x] Handle limited/full range (2025-12-29)

### 3.5 Tonemapping

- [x] Create `src/frame_compare/vs/tonemap.py` (2025-12-30)
- [x] Implement `tonemap(clip, preset, **overrides)` (2025-12-30)
- [x] Implement supported presets (reference, hable, mobius, reinhard) (2025-12-30)
- [x] Handle libplacebo presence/absence (2025-12-30)
- [x] Handle missing libplacebo gracefully (2025-12-30)
- [x] Write tests for each preset (2025-12-30)

### 3.6 Module Integration

- [x] Create `src/frame_compare/vs/__init__.py` (2025-12-30)
- [x] Export public API (2025-12-30)
- [x] Mark VapourSynth tests appropriately (2025-12-30)

### Phase 3 Quality Gate ✓

- [x] Videos load correctly (2025-12-30)
- [x] HDR detection accurate (2025-12-30)
- [x] All presets produce output (2025-12-30)
- [x] Fallback works when libplacebo missing (2025-12-30)
- [x] Pyright shows 0 errors (2025-12-30)
- [x] Tests pass (with `vs_required` skipped if no VS) (2025-12-30)

---

## Phase 4: Render Module

### 4.1 Types

**Reference:** `05-implementation/module-specs/render-module.md`

- [x] Create `src/frame_compare/render/types.py` (2026-01-01)
- [x] Define `OverlayMode` enum (MINIMAL, STANDARD, DIAGNOSTIC) (2026-01-01)
- [x] Define `RenderConfig` (2026-01-01)
- [x] Define `ScreenshotResult` (2026-01-01)

### 4.2 Geometry

- [x] Create `src/frame_compare/render/geometry.py` (2026-01-01)
- [x] Implement aspect ratio calculation (2026-01-01)
- [x] Implement auto-crop detection (2026-01-01)
- [x] Implement mod-2 padding (2026-01-01)
- [x] Write geometry tests (2026-01-01)

### 4.3 Naming

- [x] Create `src/frame_compare/render/naming.py` (2026-01-01)
- [x] Implement `generate_screenshot_name(label, frame) -> str` (2026-01-01)
- [x] Sanitize label (replace non-alphanumeric) (2026-01-01)
- [x] Format: `{label}_{frame:05d}.png` (2026-01-01)
- [x] Write naming tests (2026-01-01)

### 4.4 Overlay

- [x] Create `src/frame_compare/render/overlay.py` (2026-01-01)
- [x] Implement text overlay rendering (2026-01-01)
- [x] Support overlay modes (2026-01-01)
- [x] Include frame number, label, resolution (2026-01-01)
- [x] Include HDR metadata in diagnostic mode (2026-01-01)
- [x] Write overlay tests (2026-01-01)

### 4.5 Encoders

- [x] Create `src/frame_compare/render/encoders.py` (2026-01-01)
- [x] Implement VapourSynth PNG encoder (2026-01-01)
- [x] Implement FFmpeg PNG encoder (fallback) (2026-01-01)
- [x] Abstract behind common interface (2026-01-01)
- [x] Write encoder tests (2026-01-01)

### 4.6 Orchestrator

- [x] Create `src/frame_compare/render/orchestrator.py` (2026-01-01)
- [x] Implement `render_screenshots(clips, frames, config) -> list[Path]` (2026-01-01)
- [x] Coordinate encoder selection (2026-01-01)
- [x] Apply overlays (2026-01-01)
- [x] Report progress (2026-01-01)
- [x] Write integration tests (2026-01-02)

### Phase 4 Quality Gate ✓

- [x] VS and FFmpeg renderers work
- [x] Overlays render correctly
- [x] PNG output valid
- [x] Naming convention followed
- [x] Docker verification passes (real deps, zero skips): `bash tools/verify_docker_integration.sh`
- [x] Pyright shows 0 errors
- [x] Test coverage > 80%

---

## Phase 5: Services

### 5.1 Audio Alignment

- [x] Create `src/frame_compare/services/alignment.py` (2026-01-02)
- [x] Implement audio extraction (via FFmpeg) (2026-01-02)
- [x] Implement cross-correlation alignment (2026-01-02)
- [x] Calculate frame offsets (2026-01-02)
- [x] Cache offsets in `generated/audio_offsets.toml` (2026-01-02)
- [x] Write alignment tests (2026-01-02)

### 5.2 Metadata Service

- [x] Create `src/frame_compare/services/metadata.py` (2026-01-02)
- [x] Implement GuessIt parsing (2026-01-02)
- [x] Implement Anitopy parsing (2026-01-02)
- [x] Implement TMDB lookup (2026-01-02)
- [x] Handle unattended mode (2026-01-02)
- [x] Write metadata tests (2026-01-02)

### 5.3 Publishers

- [x] Create `src/frame_compare/services/publishers.py` (2026-01-02)
- [x] Implement `SlowpicsPublisher`: (2026-01-02)
  - [x] Upload with retry logic
  - [x] Return comparison URL
  - [x] Handle errors gracefully
- [x] Implement local-only mode (2026-01-02)
- [x] Write publisher tests (mocked network) (2026-01-02)

### 5.4 Report Generator

- [x] Create `src/frame_compare/services/report.py` (2026-01-02)
- [x] Implement HTML report generation (2026-01-02)
- [x] Include slider, overlay, difference modes (2026-01-02)
- [x] Include filmstrip view (2026-01-02)
- [x] Include metadata (2026-01-02)
- [x] Include High quality Full Featured UI (2026-01-02)
- [x] Write report tests (2026-01-02)

### Phase 5 Quality Gate ✓

- [x] Audio alignment calculates offsets (2026-01-02)
- [x] Metadata parses filenames (2026-01-02)
- [x] slow.pics uploads work (2026-01-02)
- [x] HTML report generates (2026-01-02)
- [x] All services have error recovery (2026-01-02)
- [x] Docker verification passes (real deps, zero skips): `bash tools/verify_docker_integration.sh` (2026-01-02)
- [x] Test coverage > 80% and ALL tests pass (2026-01-02)

---

## Phase 5.5: Parity Closure (Pre-Runner Spec Work)

> [!NOTE]
> This sub-phase closes known legacy feature gaps at the SSOT level before Runner implementation.
> All items below are **spec-only** — implementation happens in Phase 6.

**Reference:** [feature-parity-delta.md](05-implementation/feature-parity-delta.md)

### 5.5.1 SSOT Spec Deliverables

- [x] Create `feature-parity-delta.md` — Truth table mapping legacy → 2.0 (2026-01-03)
- [x] Update `render-module.md` §1.4 — HDR Tonemap Wiring spec (2026-01-03)
- [x] Create `frame-plan-module.md` — Deterministic skip-analysis frame selection (2026-01-03)
- [x] Create `vspreview-module.md` — Optional manual alignment verification (2026-01-03)
- [x] Update `orchestration-module.md` §4.3 — Minimal runner API surface (2026-01-03)
- [x] Update `requirements-traceability.md` — Fix E2E test drift (mark as PLANNED) (2026-01-03)
- [x] Update `services-module.md` — Add VSPreview integration reference (2026-01-03)
- [x] Update this checklist — Add Parity Closure phase (2026-01-03)

### 5.5.2 Acceptance Criteria (Spec Quality)

- [x] All new specs have explicit function signatures (one-line, backticked)
- [x] All new specs have explicit error behavior and error codes
- [x] All new specs have determinism notes where relevant
- [x] Tonemap wiring spec includes exact gating rule, integration point, failure policy
- [x] FramePlan spec includes exact algorithm with blake2s hash
- [x] VSPreview spec includes optional dependency handling and cache schema
- [x] Orchestration spec includes phase ordering table and CLI→config mappings
- [x] Requirements traceability does not reference non-existent tests
- [x] Specs contain no ellipsis placeholders and no non-normative language in requirements ("should/may/etc.")

### Phase 5.5 Quality Gate ✓

- [x] All SSOT specs created/updated
- [x] No TBD sections in new specs
- [x] Traceability drift fixed
- [x] Checklist updated with Phase 6 structure

---

## Phase 6: CLI & Orchestration

> [!NOTE]
> This phase implements the orchestration layer and integrates all prior modules.
> **SSOT References:**
>
> - `05-implementation/module-specs/orchestration-module.md`
> - `05-implementation/module-specs/cli-module.md`
> - `05-implementation/module-specs/frame-plan-module.md`
> - `05-implementation/module-specs/vspreview-module.md`
> - `05-implementation/module-specs/render-module.md` §1.4 (Tonemap Wiring)

### 6.1 Orchestration Package Structure

**Reference:** `05-implementation/module-specs/orchestration-module.md`

- [x] Create `src/frame_compare/orchestration/__init__.py` (2026-01-03)
- [x] Create `src/frame_compare/orchestration/preflight.py` (2026-01-03)
- [x] Create `src/frame_compare/orchestration/doctor.py` (2026-01-03)
- [x] Create `src/frame_compare/orchestration/progress.py` (2026-01-03)
- [x] Create `src/frame_compare/orchestration/phases.py` (2026-01-03)
- [x] Update `importlinter.ini` for orchestration layer contracts (2026-01-03)

### 6.2 Preflight & Doctor

**Reference:** `05-implementation/module-specs/orchestration-module.md` §4.1, §4.2

- [x] Implement `PreflightResult` dataclass per spec §4.1 (2026-01-03)
- [x] Implement `prepare_preflight(root, config_path) -> PreflightResult` (2026-01-03)
- [x] Implement `DoctorCheck`, `CheckResult`, `DoctorReport` types per spec §4.2 (2026-01-03)
- [x] Implement `run_doctor(deps) -> DoctorReport` (2026-01-03)
- [x] Write unit tests for preflight path resolution (2026-01-03)
- [x] Write unit tests for doctor checks (2026-01-03)

### 6.3 Progress Reporting

**Reference:** `05-implementation/module-specs/orchestration-module.md` §3.3

- [x] Use canonical `ProgressReporter` protocol from `frame_compare.utils.progress` (2026-01-03)
- [x] Use `RichProgressReporter` for interactive CLI (TTY) (2026-01-03)
- [x] Use `LogProgressReporter` for `--json` / non-interactive modes (no JSON-lines reporter required yet) (2026-01-03)
- [x] Use `NullProgressReporter` for quiet mode (2026-01-03)
- [x] Implement reporter selection logic in orchestration (mode → reporter) (2026-01-03)
- [x] Write progress reporter tests (2026-01-03)

### 6.4 FramePlan Module

**Reference:** `05-implementation/module-specs/frame-plan-module.md`

- [x] Create `src/frame_compare/analysis/frame_plan.py` (2026-01-04)
- [x] Implement `FramePlan` dataclass with invariants (2026-01-04)
- [x] Implement `select_uniform_seeded_frames(num_frames, count, seed) -> FramePlan` (2026-01-04)
  - [x] Bin partitioning algorithm per spec §4
  - [x] blake2s hash selection per spec §4
  - [x] Default seed handling (seed is `None` → `42`)
- [x] Implement `create_frame_plan(num_frames, count, seed=None) -> FramePlan` (2026-01-04)
- [x] Raise `InsufficientFramesError` when count > num_frames (2026-01-04)
- [x] Verify determinism across Python sessions (subprocess test) (2026-01-04)
- [x] Write unit tests per spec §8.1: (2026-01-04)
  - [x] `test_select_uniform_seeded_frames_deterministic`
  - [x] `test_select_uniform_seeded_frames_cross_session`
  - [x] `test_select_uniform_seeded_frames_single_frame`
  - [x] `test_select_uniform_seeded_frames_all_frames`
  - [x] `test_select_uniform_seeded_frames_count_exceeds_available`
  - [x] `test_select_uniform_seeded_frames_zero_count`
  - [x] `test_create_frame_plan_uses_default_seed_when_none`
  - [x] `test_create_frame_plan_uses_default_seed_when_omitted`
- [x] Update `analysis/__init__.py` exports (2026-01-04)

### 6.5 Tonemap Wiring

**Reference:** `05-implementation/module-specs/render-module.md` §1.4

- [x] Update `render/orchestrator.py` with tonemap integration (2026-01-04)
- [x] Implement `should_tonemap(source_info, config) -> bool` gating rule (2026-01-04)
- [x] Implement `resolve_tonemap_settings(config, cli_overrides) -> TonemapSettings` (2026-01-04)
- [x] Wire `config.color.enable_tonemap` to runtime consumer (2026-01-04)
- [x] Add tonemap call between load and frame extraction in `render_screenshots` (2026-01-04)
- [x] Implement fail-fast `RenderError(FC-4004)` for HDR + tonemap required + VS unavailable (2026-01-04)
- [x] Propagate `TonemapError` on `apply_tonemap()` failure (2026-01-04)
- [x] Write integration tests: (2026-01-04)
  - [x] `test_hdr_enable_tonemap_requires_vs_when_renderer_auto`
  - [x] `test_hdr_enable_tonemap_requires_vs_when_renderer_ffmpeg`
  - [x] `test_hdr_disable_tonemap_allows_ffmpeg_when_vs_missing`
  - [x] `test_sdr_allows_ffmpeg_fallback_when_vs_missing`

### 6.6 VSPreview Integration

**Reference:** `05-implementation/module-specs/vspreview-module.md`

- [x] Create `src/frame_compare/vspreview/__init__.py` (2026-01-04)
- [x] Create `src/frame_compare/vspreview/adapter.py` (2026-01-04)
- [x] Create `src/frame_compare/vspreview/overrides.py` (2026-01-04)
- [x] Implement `is_vspreview_available() -> bool` (2026-01-04)
- [x] Implement `launch_alignment_verification_session(reference, comparisons, suggested_offsets_by_key, cache_dir, config) -> Path` (2026-01-04)
- [x] Implement `load_manual_overrides(cache_dir) -> dict[str, ManualOverride]` (2026-01-04)
- [x] Implement `save_manual_override(cache_dir, override) -> None` (2026-01-04)
- [x] Wire `config.audio_alignment.use_vspreview` to runtime consumer (2026-01-04)
- [x] Wire `config.audio_alignment.force_interactive` and `--force-interactive-alignment` to runtime consumer (2026-01-04)
- [x] Write unit tests per spec §8.1: (2026-01-04)
  - [x] `test_is_vspreview_available_returns_true_when_importable`
  - [x] `test_is_vspreview_available_returns_false_when_missing`
  - [x] `test_load_manual_overrides_parses_valid_toml`
  - [x] `test_load_manual_overrides_returns_empty_dict_on_missing_file`
  - [x] `test_load_manual_overrides_returns_empty_dict_on_parse_error`
  - [x] `test_load_manual_overrides_returns_empty_dict_on_version_mismatch`
  - [x] `test_save_manual_override_creates_file_if_missing`
  - [x] `test_save_manual_override_merges_with_existing`
  - [x] `test_save_manual_override_overwrites_same_key`
  - [x] `test_manual_override_takes_precedence_over_computed`
- [x] Update `importlinter.ini` for vspreview module (2026-01-04)

### 6.7 Runner & Phase Orchestration

**Reference:** `05-implementation/module-specs/orchestration-module.md` §4.4.4

- [ ] Create `src/frame_compare/runner.py` at package root
- [ ] Create `src/frame_compare/orchestration/context.py` and define `ClipState` / `RunContext` per spec §3.5
- [ ] Implement probe snapshot cache (`generated/clip_probe.toml`) per spec §3.5 (deterministic keying, stable TOML)
- [ ] Preserve HDR/DoVi props in `ClipProbeSnapshot` per spec §3.5 (portable primitives only; record `tonemap_prop_keys`)
- [ ] Implement consolidated FPS report per spec §5.4 (after LoadSources and after Align)
- [ ] Implement `RunRequest` dataclass per spec
- [ ] Implement `RunResult` dataclass per spec
- [ ] Implement `RunDependencies` for dependency injection
- [ ] Implement `run(request, deps) -> RunResult` entry point
- [ ] Implement `execute_run(config, preflight) -> RunResult` in orchestration/
- [ ] Implement phase orchestration per spec §4.4.4:
  - [ ] Phase 1: Preflight
  - [ ] Phase 2: LoadSources
    - [ ] Build `ClipState` list (reference + comparisons) from discovered inputs
    - [ ] Load probe snapshots from `clip_probe.toml` when valid; probe and persist when missing/stale
  - [ ] Phase 3: FramePlan (uses 6.4)
  - [ ] Phase 4: Analyze (or skip per --skip-analysis)
  - [ ] Phase 5: Align
  - [ ] Phase 6: Render (includes tonemap gating/wiring from 6.5; not a standalone phase)
  - [ ] Phase 7: Metadata
  - [ ] Phase 8: Dovi
  - [ ] Phase 9: Publish
  - [ ] Phase 10: Report
- [ ] Implement CLI flag → config override mapping per spec §4.4.5
- [ ] Implement input discovery rules per spec §4.4.6
- [ ] Write unit tests for `ClipState` and probe cache:
  - [ ] `tests/orchestration/test_context.py::test_clip_state_effective_num_frames_clamps_and_never_negative`
  - [ ] `tests/orchestration/test_probe_cache.py::test_compute_probe_cache_key_stable_for_same_fingerprint`
  - [ ] `tests/orchestration/test_probe_cache.py::test_probe_cache_round_trip_toml`
  - [ ] `tests/orchestration/test_probe_cache.py::test_probe_cache_invalidates_on_fingerprint_change`
  - [ ] `tests/orchestration/test_probe_cache.py::test_preserved_frame_props_are_toml_safe_primitives_only`
  - [ ] `tests/orchestration/test_fps_report.py::test_fps_report_marks_divergence`
- [ ] Write integration tests (Docker, real deps; zero skips):
  - [ ] `tests/integration/test_loadsources_probe_cache.py::test_loadsources_writes_clip_probe_cache_file`
  - [ ] `tests/integration/test_loadsources_probe_cache.py::test_loadsources_reuses_clip_probe_cache_file`
  - [ ] Verify in Docker: `bash tools/verify_docker_integration.sh`
- [ ] Write phase orchestration tests

### 6.8 CLI Commands

**Reference:** `05-implementation/module-specs/cli-module.md`

- [ ] Complete `run` command implementation
- [ ] Complete `wizard` command (interactive config)
- [ ] Complete `doctor` command (dependency check)
- [ ] Complete `preset` subcommands (list, apply, save)
- [ ] Implement all CLI options documented in api-design.md
- [ ] Implement `ExitCode` enum per spec §3.2
- [ ] Implement error-to-exit-code mapping per spec §3.3
- [ ] Write CLI integration tests

### Phase 6 Quality Gate ✓

- [ ] `frame-compare run` executes full pipeline
- [ ] `frame-compare wizard` configures interactively
- [ ] `frame-compare doctor` checks dependencies
- [ ] All CLI options work per api-design.md
- [ ] Exit codes match `ExitCode` enum
- [ ] FramePlan determinism verified (subprocess test passes)
- [ ] Tonemap wiring integration tests pass
- [ ] VSPreview unit tests pass (or skipped if deferred)
- [ ] Docker verification passes (real deps, zero skips): `bash tools/verify_docker_integration.sh`
- [ ] E2E tests pass

---

## Phase 7: Polish & Documentation

### 7.1 Documentation

- [ ] Complete README.md with usage examples
- [ ] Update CHANGELOG.md
- [ ] Add inline docstrings to all public APIs
- [ ] Generate API documentation

### 7.2 Quality Assurance

- [ ] Run full test suite
- [ ] Verify coverage > 80%
- [ ] Fix any Pyright errors
- [ ] Fix any Ruff errors
- [ ] Performance testing

### 7.3 Container Finalization

- [ ] Optimize Dockerfile layers
- [ ] Test Docker deployment end-to-end
- [ ] Publish to ghcr.io (if applicable)

### Phase 7 Quality Gate ✓

- [ ] All tests pass
- [ ] Coverage > 80%
- [ ] Pyright: 0 errors
- [ ] Ruff: 0 errors
- [ ] Docker image builds and runs
- [ ] Documentation complete

---

## Phase 8: Distribution — Windows Portable Bundle (Parallel Track)

**SSOT:** `docs/OPUS_REBUILD_FRAME_COMPARE/07-windows-portable-bundle/`

### 8.1 Spec + Decisions

- [ ] Confirm supported Windows versions (Windows 10 + 11)
- [ ] Confirm supported architectures (baseline x64; ARM64 best-effort or deferred)
- [ ] Confirm packaging strategy (embedded Python bundle vs PyInstaller)
- [ ] Record baseline distribution decisions in `docs/DECISIONS.md`
- [ ] Finalize SSOT bundle layout + env rules:
  - [ ] `07-windows-portable-bundle/01-bundle-spec.md`
  - [ ] `07-windows-portable-bundle/02-support-matrix.md`

### 8.2 Pinned Artifact Set (Baseline)

- [ ] Define `manifest.json` schema (versions + sha256 + license notes)
- [ ] Pin and source Windows artifacts for baseline bundle:
  - [ ] VapourSynth runtime (Windows)
  - [ ] Plugins: L-SMASH Works, vs-placebo, ffms2 (as applicable)
  - [ ] FFmpeg (Windows)

### 8.3 Bundle Assembly + Launch

- [ ] Add Windows bundle assembly scripts (PowerShell)
- [ ] Add bundle launcher(s) that set PATH + `VAPOURSYNTH_PLUGIN_PATH` deterministically
- [ ] Ensure `frame-compare doctor --json` runs in the portable bundle

### 8.4 Windows CI + Smoke Verification

- [ ] Add Windows CI job to assemble portable bundle artifact
- [ ] Add Windows smoke checks:
  - [ ] `frame-compare doctor --json` exits 0
  - [ ] VS clip creation works
  - [ ] Tonemap does not raise (fallback allowed)
- [ ] Optional: Linux GPU CI job (or manual run) that sets `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1`

### Phase 8 Quality Gate ✓

- [ ] Portable bundle assembles deterministically from pinned artifacts
- [ ] Windows CI smoke checks pass
- [ ] Documentation published: install/run instructions + support matrix

---

## Session Handoff Template

```markdown
### Session Summary

**Date:** YYYY-MM-DD
**Agent:** [Agent identifier]
**Phase:** [Current phase]
**Duration:** [Approximate time]

### Completed This Session
- [ ] Item 1
- [ ] Item 2

### In Progress
- [ ] Item with notes about current state

### Blockers
- [ ] Issue description and attempted resolution

### Next Steps
1. Priority 1 action
2. Priority 2 action

### Notes for Next Agent
[Any context, gotchas, or recommendations]
```

---

## Best Practices Reminders

### Before Each Implementation

1. Read the relevant module spec in `05-implementation/module-specs/`
2. Check ADRs for architectural decisions
3. Review existing code for patterns

### During Implementation

1. Run Pyright after each file: `.venv/bin/pyright --warnings path/to/file.py`
2. Run Ruff after each file: `.venv/bin/ruff check path/to/file.py`
3. Write tests alongside code (not after)
4. Update this checklist as items complete

### After Implementation

1. Run full test suite: `.venv/bin/pytest`
2. Check coverage: `.venv/bin/pytest --cov`
3. Update documentation if needed
4. Commit with conventional commit message

### Code Quality

- No Pyright errors in strict mode
- No Ruff errors
- All public functions have docstrings
- All exceptions have error codes and hints
- Structured logging (no f-string logs)

---

## Quick Reference

### Run Commands

```bash
uv sync                    # Install dependencies
.venv/bin/pyright --warnings # Type check
.venv/bin/ruff check .       # Lint
.venv/bin/pytest             # Test
.venv/bin/pytest --cov       # Test with coverage
docker compose up         # Run in container
```

### Documentation Locations

- Architecture: `03-architecture/`
- Module specs: `05-implementation/module-specs/`
- ADRs: `03-architecture/adr/`
- API design: `03-architecture/api-design.md`
- Error handling: `05-implementation/error-handling.md`
- Testing: `05-implementation/testing-strategy.md`
