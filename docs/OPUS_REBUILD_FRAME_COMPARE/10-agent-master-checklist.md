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

```
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

- [ ] Config loads and validates TOML
- [ ] Errors have codes, messages, hints
- [ ] Logs output structured JSON
- [ ] CLI responds to basic commands
- [ ] Pyright shows 0 errors
- [ ] Test coverage > 80%

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

- [ ] Create `src/frame_compare/analysis/metrics.py`
- [ ] Implement `calculate_metrics(clip, progress) -> FrameMetrics`
- [ ] Implement `_calculate_luminance(frames) -> list[float]`
- [ ] Implement `_calculate_motion(frames) -> list[float]`
- [ ] Add progress reporting callbacks
- [ ] Write unit tests with mock frames
- [ ] Write edge case tests (empty, single frame)

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

- [ ] Create `src/frame_compare/analysis/__init__.py`
- [ ] Export public API: `calculate_metrics`, `select_frames`, types
- [ ] Verify import contracts (no cross-layer imports)

### Phase 2 Quality Gate ✓

- [ ] Metrics calculate correctly
- [ ] Selection is deterministic
- [ ] Cache hit/miss works
- [ ] All tests pass
- [ ] Pyright shows 0 errors
- [ ] Test coverage > 85%

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

- [ ] Create `src/frame_compare/vs/source.py`
- [ ] Implement `load_video(path) -> Result[VideoNode, str]`
- [ ] Support formats: `.mkv`, `.mp4`, `.avi`, `.m2ts`, `.ts`
- [ ] Use lsmas for loading
- [ ] Extract clip properties (fps, frame_count, resolution)

### 3.3 Frame Properties

- [ ] Create `src/frame_compare/vs/props.py`
- [ ] Implement `get_color_props(frame) -> ColorProps`
- [ ] Implement `is_hdr(clip) -> bool`
- [ ] Detect PQ (_Transfer == 16)
- [ ] Detect HLG (_Transfer == 18)
- [ ] Detect BT.2020 primaries

### 3.4 Color Operations

- [ ] Create `src/frame_compare/vs/color.py`
- [ ] Implement color space conversions
- [ ] Handle BT.709, BT.2020
- [ ] Handle limited/full range

### 3.5 Tonemapping

- [ ] Create `src/frame_compare/vs/tonemap.py`
- [ ] Define `TONEMAP_PRESETS` dict
- [ ] Implement `tonemap(clip, preset, **overrides) -> VideoNode`
- [ ] Implement BT.2390 curve
- [ ] Implement Spline curve
- [ ] Implement Reinhard curve
- [ ] Handle missing libplacebo gracefully
- [ ] Write tests for each preset

### 3.6 Module Integration

- [ ] Create `src/frame_compare/vs/__init__.py`
- [ ] Export public API
- [ ] Mark VapourSynth tests appropriately

### Phase 3 Quality Gate ✓

- [ ] Videos load correctly
- [ ] HDR detection accurate
- [ ] All presets produce output
- [ ] Fallback works when libplacebo missing
- [ ] Pyright shows 0 errors
- [ ] Tests pass (with `vs_required` skipped if no VS)

---

## Phase 4: Render Module

### 4.1 Types

**Reference:** `05-implementation/module-specs/render-module.md`

- [ ] Create `src/frame_compare/render/types.py`
- [ ] Define `OverlayMode` enum (MINIMAL, STANDARD, DIAGNOSTIC)
- [ ] Define `RenderConfig`
- [ ] Define `ScreenshotResult`

### 4.2 Geometry

- [ ] Create `src/frame_compare/render/geometry.py`
- [ ] Implement aspect ratio calculation
- [ ] Implement auto-crop detection
- [ ] Implement mod-2 padding
- [ ] Write geometry tests

### 4.3 Naming

- [ ] Create `src/frame_compare/render/naming.py`
- [ ] Implement `generate_screenshot_name(label, frame) -> str`
- [ ] Sanitize label (replace non-alphanumeric)
- [ ] Format: `{label}_{frame:05d}.png`
- [ ] Write naming tests

### 4.4 Overlay

- [ ] Create `src/frame_compare/render/overlay.py`
- [ ] Implement text overlay rendering
- [ ] Support overlay modes
- [ ] Include frame number, label, resolution
- [ ] Include HDR metadata in diagnostic mode
- [ ] Write overlay tests

### 4.5 Encoders

- [ ] Create `src/frame_compare/render/encoders.py`
- [ ] Implement VapourSynth PNG encoder
- [ ] Implement FFmpeg PNG encoder (fallback)
- [ ] Abstract behind common interface
- [ ] Write encoder tests

### 4.6 Orchestrator

- [ ] Create `src/frame_compare/render/orchestrator.py`
- [ ] Implement `render_screenshots(clips, frames, config) -> list[Path]`
- [ ] Coordinate encoder selection
- [ ] Apply overlays
- [ ] Report progress
- [ ] Write integration tests

### Phase 4 Quality Gate ✓

- [ ] VS and FFmpeg renderers work
- [ ] Overlays render correctly
- [ ] PNG output valid
- [ ] Naming convention followed
- [ ] Pyright shows 0 errors
- [ ] Test coverage > 80%

---

## Phase 5: Services

### 5.1 Audio Alignment

- [ ] Create `src/frame_compare/services/alignment.py`
- [ ] Implement audio extraction (via FFmpeg)
- [ ] Implement cross-correlation alignment
- [ ] Calculate frame offsets
- [ ] Cache offsets in `generated/audio_offsets.toml`
- [ ] Write alignment tests

### 5.2 Metadata Service

- [ ] Create `src/frame_compare/services/metadata.py`
- [ ] Implement GuessIt parsing
- [ ] Implement Anitopy parsing
- [ ] Implement TMDB lookup
- [ ] Handle unattended mode
- [ ] Write metadata tests

### 5.3 Publishers

- [ ] Create `src/frame_compare/services/publishers.py`
- [ ] Implement `SlowpicsPublisher`:
  - [ ] Upload with retry logic
  - [ ] Return comparison URL
  - [ ] Handle errors gracefully
- [ ] Implement local-only mode
- [ ] Write publisher tests (mocked network)

### 5.4 Report Generator

- [ ] Create `src/frame_compare/services/report.py`
- [ ] Implement HTML report generation
- [ ] Include slider, overlay, difference modes
- [ ] Include filmstrip view
- [ ] Write report tests

### Phase 5 Quality Gate ✓

- [ ] Audio alignment calculates offsets
- [ ] Metadata parses filenames
- [ ] slow.pics uploads work
- [ ] HTML report generates
- [ ] All services have error recovery
- [ ] Test coverage > 80%

---

## Phase 6: CLI & Orchestration

### 6.1 Runner

- [ ] Create `src/frame_compare/runner.py`
- [ ] Implement `run(request: RunRequest) -> RunResult`
- [ ] Implement `RunRequest` dataclass
- [ ] Implement `RunResult` dataclass
- [ ] Implement `RunDependencies` for DI
- [ ] Coordinate all phases:
  - [ ] Load config
  - [ ] Find videos
  - [ ] Calculate/load metrics
  - [ ] Select frames
  - [ ] Align audio (optional)
  - [ ] Render screenshots
  - [ ] Upload (optional)
  - [ ] Generate report (optional)

### 6.2 CLI Commands

- [ ] Complete `run` command implementation
- [ ] Complete `wizard` command
- [ ] Complete `doctor` command
- [ ] Complete `preset` commands
- [ ] Add all CLI options documented in api-design.md

### 6.3 Preflight

- [ ] Create `src/frame_compare/preflight.py`
- [ ] Implement path resolution
- [ ] Implement config loading
- [ ] Implement dependency validation

### Phase 6 Quality Gate ✓

- [ ] `frame-compare run` executes full pipeline
- [ ] `frame-compare wizard` configures interactively
- [ ] `frame-compare doctor` checks dependencies
- [ ] All CLI options work
- [ ] Exit codes correct
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
