# Summary (TL;DR)
- Validated that `frame_compare.py`, `src/screenshot.py`, and the regression tests still execute cleanly after the merge, with FFmpeg trims, upscale coordination, and cache reuse behaving exactly like the legacy runner.【F:frame_compare.py†L17-L401】【F:src/screenshot.py†L1-L381】【F:tests/test_frame_compare.py†L1-L229】
- Completed a feature-by-feature parity audit against `legacy/compv4_improved.py`; every legacy knob now has a 1:1 implementation in the modular pipeline and is catalogued in the refreshed parity matrix.【F:legacy/compv4_improved.py†L1-L200】【F:docs/PARITY_MATRIX.csv†L1-L50】
- Regression suite (39 tests) passes, covering CLI overrides, analysis heuristics, geometry planning, slow.pics uploads, and FFmpeg fallbacks so nightly parity checks stay reliable.【e40847†L1-L3】

# Repo Overview
The project modernises the legacy comparison script while keeping the CLI entry point at `frame_compare.py`. The workflow is:
1. Load and validate `config.toml` into typed dataclasses (`src/config_loader.py`, `src/datatypes.py`).【F:config.toml†L1-L59】【F:src/config_loader.py†L26-L123】
2. Discover media, parse naming metadata (`src/utils.py`), and build per-clip plans that honour trim/FPS overrides.【F:frame_compare.py†L74-L212】【F:src/utils.py†L1-L167】
3. Initialise VapourSynth clips with RAM limits, trims, and optional FPS remapping (`src/vs_core.py`).【F:src/vs_core.py†L57-L167】
4. Select frames via brightness/motion analysis with caching support (`src/analysis.py`).【F:src/analysis.py†L40-L404】
5. Render screenshots through VapourSynth or FFmpeg, with global scaling and fallback placeholders (`src/screenshot.py`).【F:src/screenshot.py†L67-L381】
6. Optionally upload to slow.pics (`src/slowpics.py`) and report the run summary via the CLI.【F:src/slowpics.py†L60-L166】【F:frame_compare.py†L320-L401】

# Architecture Review
- **`frame_compare.py`**: Clean orchestration, no lingering merge artefacts; override maps, metadata dedupe, cache wiring, and summary logging match the legacy control flow while keeping the module import-safe.【F:frame_compare.py†L74-L401】
- **`src/utils.py`**: GuessIt-first parsing with Anitopy fallback and release-group extraction mirrors the legacy filename heuristics, supplying the CLI dedupe logic without global state.【F:src/utils.py†L1-L167】
- **`src/analysis.py`**: Metric collection separates VapourSynth and fallback paths, caches include full fingerprints, and the quarter-gap motion heuristic plus smoothing radius map straight to the legacy algorithm.【F:src/analysis.py†L200-L404】
- **`src/screenshot.py`**: Geometry planner coordinates upscale/single-res, FFmpeg writer is trim-aware (including negative padding) and gracefully falls back to placeholders; compression mapping stays compatible with fpng/FFmpeg expectations.【F:src/screenshot.py†L67-L381】
- **`src/vs_core.py`**: Handles RAM limits, trims, FPS mapping, HDR tonemapping, and blank-frame extension; no `sys.exit` usage and errors surface via typed exceptions.【F:src/vs_core.py†L57-L204】
- **`src/slowpics.py`**: Upload workflow encapsulates retries, webhook registration, direct POST, and shortcut cleanup with sanitized logging—feature-for-feature with the legacy script.【F:src/slowpics.py†L60-L166】
- **Tests (`tests/*`)**: Cover CLI orchestration, analysis determinism, screenshot geometry, FFmpeg trim offsets, and slow.pics retries; no merge regressions observed.【F:tests/test_analysis.py†L1-L189】【F:tests/test_screenshot.py†L1-L170】【F:tests/test_frame_compare.py†L1-L229】【F:tests/test_slowpics.py†L1-L142】

# Quality Findings
- **Strengths**
  - Deterministic caches and seeded randomness make parity reruns reproducible, and cache fingerprints guard against stale metrics.【F:src/analysis.py†L40-L133】
  - FFmpeg and VapourSynth writers share a unified geometry plan, ensuring consistent filenames and dimensions even with trims and upscale toggles.【F:src/screenshot.py†L67-L381】
  - slow.pics client implements retries, webhook POSTs, and shortcut cleanup with graceful error handling and redacted logging.【F:src/slowpics.py†L60-L166】
- **Opportunities**
  - Quarter-gap divisor remains hard-coded; exposing it via config would make bespoke parity tweaks easier.【F:src/analysis.py†L360-L404】
  - CLI uses `sys.exit` for user messaging; a thin exception layer could aid embedding in larger tooling without manual stderr capture.【F:frame_compare.py†L320-L401】
  - Structured logging (levels/JSON) could help triage runs at scale now that parity logging is richer.【F:src/screenshot.py†L306-L381】

# Functional Parity Findings
Every legacy toggle has a modern equivalent; highlights include:
- Overrides: Trim start/end (including blank padding) and `change_fps` (numeric or `"set"`) feed directly into clip plans and FPS remapping.【F:frame_compare.py†L174-L260】【F:src/vs_core.py†L99-L167】
- Analysis: Quantile thresholds, SDR tonemapping, motion absolute-diff/scenecut filters, seeded randomness, and cache persistence mirror the old pipeline while remaining deterministic.【F:src/analysis.py†L40-L404】
- Screenshots: Global upscale, single-res override, modulus crop, FFmpeg trim alignment, compression levels, and placeholder fallbacks reproduce the legacy screenshot outputs and naming scheme.【F:src/screenshot.py†L67-L381】
- slow.pics: Auto-upload, metadata flags (public/hentai/TMDB/remove-after), webhook registration + direct POST, browser open, clipboard copy, shortcut creation, and cleanup are 1:1.【F:src/slowpics.py†L60-L166】【F:frame_compare.py†L362-L401】
See `docs/PARITY_MATRIX.csv` for the full 40-row comparison matrix.【F:docs/PARITY_MATRIX.csv†L1-L50】

# Test & CI Findings
- `uv run python -m pytest -q` passes (39 tests), exercising CLI overrides, caching, FFmpeg trims, upscale planning, motion spacing, and slow.pics retries.【e40847†L1-L3】
- No test gaps remain from the previous audit; the suite now covers all legacy behaviours enumerated in the parity matrix.【F:tests/test_analysis.py†L1-L189】【F:tests/test_frame_compare.py†L1-L229】【F:tests/test_screenshot.py†L1-L170】【F:tests/test_slowpics.py†L1-L142】
- CI still runs on Python 3.11 Ubuntu; consider extending to Python 3.12 and Windows to mirror the environments where the legacy script is used.【F:.github/workflows/ci.yml†L1-L33】

# Enhancement Proposals
1. **Expose motion gap divisor (P1, S)** — Add an `AnalysisConfig.motion_gap_divisor` field with validation so advanced users can tweak the quarter-gap behaviour without patching code.【F:src/analysis.py†L360-L404】
2. **CLI exception wrapper (P1, M)** — Replace direct `sys.exit` calls with a small exception hierarchy and a `main()` runner that converts them to exit codes, easing reuse in other tooling.【F:frame_compare.py†L320-L401】
3. **Structured logging (P2, M)** — Adopt `logging` with levels/JSON output for screenshot and slow.pics modules to simplify automation and log filtering at scale.【F:src/screenshot.py†L306-L381】【F:src/slowpics.py†L60-L166】
4. **CI matrix expansion (P2, M)** — Extend GitHub Actions to Python 3.12 and Windows, and add lint/static-analysis stages to guard parity on the platforms the legacy script targeted.【F:.github/workflows/ci.yml†L1-L33】

# Risks & Trade-offs
- FFmpeg reliance means users still need the binary installed; documenting detection/fallback paths prevents parity confusion on new hosts.【F:src/screenshot.py†L228-L306】
- Tonemapping depends on VapourSynth plugins; missing filters raise typed errors but should be highlighted in docs for HDR workflows.【F:src/vs_core.py†L130-L204】
- slow.pics retries block the CLI until completion; long webhook timeouts can extend runs, so future async support may be desirable.【F:src/slowpics.py†L60-L166】

# Next Actions
1. Land optional motion-gap divisor configuration and accompanying tests.
2. Introduce CLI-level exception handling plus structured logging for better automation hooks.
3. Expand CI to Python 3.12/Windows with linting to keep parity stable across host environments.
