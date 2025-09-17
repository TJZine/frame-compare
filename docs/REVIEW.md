# Summary (TL;DR)
- Config schema is rich but several knobs (naming, overrides, caching, ffmpeg) are disconnected from the CLI pipeline, leaving notable parity gaps with the legacy script.【F:src/datatypes.py†L31-L102】【F:frame_compare.py†L132-L188】【F:src/screenshot.py†L84-L185】【F:legacy/compv4_improved.py†L22-L154】
- Core modules are well-factored with typed exceptions and defensive fallbacks, yet runtime safeguards (ram limit, slow.pics resilience) and configuration-driven behaviour need hardening for production use.【F:src/config_loader.py†L26-L123】【F:src/analysis.py†L75-L264】【F:src/vs_core.py†L48-L203】
- Test suite passes but omits CLI, override, and error-path coverage; adding parity/golden tests is required before cutting over from the legacy tool.【f3ab21†L1-L3】

# Repo Overview
The project modernises the legacy `compv4_improved.py` workflow into a Click-powered CLI (`frame_compare.py`) that orchestrates configuration loading, VapourSynth clip init, frame analysis, screenshot generation, and optional slow.pics uploads.【F:frame_compare.py†L13-L193】 Supporting modules include config parsing (`src/config_loader.py`), structured dataclasses (`src/datatypes.py`), filename parsing utilities (`src/utils.py`), analysis heuristics (`src/analysis.py`), screenshot planning (`src/screenshot.py`), slow.pics API client (`src/slowpics.py`), and VapourSynth helpers (`src/vs_core.py`).【F:src/config_loader.py†L10-L123】【F:src/datatypes.py†L6-L102】【F:src/utils.py†L8-L167】【F:src/analysis.py†L13-L264】【F:src/screenshot.py†L12-L186】【F:src/slowpics.py†L13-L115】【F:src/vs_core.py†L14-L203】 The bundled `config.toml` mirrors dataclass defaults, providing end-user entry points.【F:config.toml†L1-L59】

# Architecture Review
- **`src/config_loader`** – Handles UTF-8 BOM stripping, boolean coercion, and range validation, raising `ConfigError` on invalid input.【F:src/config_loader.py†L26-L123】 Validation covers overrides but the application never consumes those mappings, so they effectively dead-end.
- **`src/datatypes`** – Dataclasses capture legacy settings but several fields (`save_frames_data`, `frame_data_filename`, `use_ffmpeg`, naming prefs, overrides, runtime.ram_limit) have no downstream consumers, signalling incomplete wiring.【F:src/datatypes.py†L10-L102】【F:frame_compare.py†L132-L188】【F:src/screenshot.py†L84-L185】
- **`src/utils`** – Isolates GuessIt/Anitopy parsing with safe import fallbacks and deterministic label construction; however, consumers always use defaults because they ignore `NamingConfig` overrides.【F:src/utils.py†L41-L167】【F:frame_compare.py†L132-L135】
- **`src/analysis`** – Provides quantile-based selection with deterministic RNG and VapourSynth fallbacks.【F:src/analysis.py†L75-L264】 Yet `files` parameter and caching hooks remain unused, and `_generate_metrics_fallback` produces synthetic data without logging, complicating debugging.
- **`src/screenshot`** – Plans modulus-aware crops and scales, wraps VapourSynth saves, and falls back to placeholder files on unexpected errors.【F:src/screenshot.py†L24-L185】 `parse_filename_metadata` is called without respect to naming config or `use_ffmpeg`, so toggles don’t change behaviour.
- **`src/slowpics`** – Encapsulates API interactions with explicit timeouts and shortcut creation.【F:src/slowpics.py†L20-L115】 Missing retry/backoff and webhook error handling reduces robustness compared to legacy script’s manual flow.
- **`src/vs_core`** – Clean separation of clip init, trims, FPS mapping, HDR detection, and tonemapping defaults.【F:src/vs_core.py†L48-L203】 No integration exists with override maps or runtime ram limit, and tonemap parameters aren’t exposed via config.
- **`frame_compare` CLI** – Friendly messaging and summary output, but it mutates config dataclasses directly, exits on first failure, and never applies overrides (trim/change_fps), naming toggles, or ram limit that users expect from legacy behaviour.【F:frame_compare.py†L104-L193】

# Quality Findings
- Positive: Modules declare typed exceptions, prefer dependency injection for optional libraries, and include docstrings/type hints throughout.【F:src/config_loader.py†L22-L123】【F:src/vs_core.py†L14-L203】
- Issues:
  - `RuntimeConfig.ram_limit_mb`, naming preferences, screenshot `use_ffmpeg`, and override maps are unused, leading to confusing configs and parity loss.【F:src/datatypes.py†L31-L102】【F:frame_compare.py†L132-L188】【F:src/screenshot.py†L84-L185】
  - `analysis.select_frames` swallows all VapourSynth errors and silently uses deterministic sine/cosine fallbacks; lack of logging obscures degraded runs.【F:src/analysis.py†L181-L185】
  - `frame_compare` relies on `sys.exit`, which is acceptable for CLI, but there’s no structured logging or exit codes summarised for automation consumers.【F:frame_compare.py†L104-L193】
  - No enforcement of `runtime.ram_limit_mb` akin to legacy `vs.core.max_cache_size`, losing a reliability safeguard.【F:legacy/compv4_improved.py†L22-L369】【F:src/vs_core.py†L48-L113】

# Functional Parity Findings
Key divergences vs. legacy `compv4_improved.py` (see `docs/PARITY_MATRIX.csv` for full matrix):
- Trim/FPS override dictionaries (`trim_dict`, `trim_dict_end`, `change_fps`) exist in config but are never applied when opening clips, so users cannot align sources as before.【F:legacy/compv4_improved.py†L94-L134】【F:frame_compare.py†L87-L145】【F:src/vs_core.py†L93-L203】
- Naming toggles (`always_full_filename`, `prefer_guessit`) are ignored in CLI listing and screenshot filenames, forcing full filenames regardless of config.【F:legacy/compv4_improved.py†L48-L53】【F:src/datatypes.py†L65-L66】【F:frame_compare.py†L132-L135】【F:src/screenshot.py†L84-L88】
- Legacy caching knobs (`save_frames`, `frame_filename`) and ram limit enforcement are not implemented, so repeated runs reanalyse clips and risk higher memory use.【F:legacy/compv4_improved.py†L34-L37】【F:legacy/compv4_improved.py†L144-L149】【F:src/analysis.py†L171-L264】【F:src/vs_core.py†L48-L113】
- FFmpeg rendering path is stubbed: `use_ffmpeg` only toggles a flag with no alternate writer, losing compatibility with environments lacking VapourSynth/Pillow.【F:legacy/compv4_improved.py†L44-L47】【F:src/datatypes.py†L35-L42】【F:src/screenshot.py†L84-L185】

# Test & CI Findings
- `uv run python -m pytest -q` passes (26 tests) under Python 3.11, matching CI expectations.【f3ab21†L1-L3】
- Coverage gaps: no tests execute the CLI end-to-end, validate override application, exercise HDR tonemap failures, or hit slow.pics error scenarios (missing XSRF token, webhook failures). `docs/TEST_GAPS.md` outlines concrete additions.
- CI runs only on Ubuntu 3.11; no Windows or Python 3.12 matrix, and no lint/static analysis steps beyond `pytest`.

# Enhancement Proposals
(Priority P0 highest urgency)
1. **P0 – Wire overrides/naming/runtime knobs**: Apply `cfg.overrides` when creating clips, respect `NamingConfig` in CLI/screenshot labelling, and enforce `ram_limit_mb` via `vs.core.max_cache_size` to restore parity and reliability.【F:src/datatypes.py†L31-L102】【F:frame_compare.py†L87-L188】【F:src/vs_core.py†L48-L203】 (Size: M)
2. **P0 – Implement screenshot writer selection**: Honour `use_ffmpeg`, adding an FFmpeg fallback or emitting a config error when requested but unavailable.【F:legacy/compv4_improved.py†L44-L47】【F:src/screenshot.py†L84-L185】 (Size: M)
3. **P0 – Add frame data caching**: Use `save_frames_data`/`frame_data_filename` to persist analysis metrics and skip recomputation when unchanged.【F:legacy/compv4_improved.py†L34-L37】【F:src/datatypes.py†L10-L28】【F:src/analysis.py†L171-L264】 (Size: M)
4. **P1 – Strengthen slow.pics client**: Introduce retries, webhook error handling, and redaction of sensitive URLs in logs for robustness.【F:src/slowpics.py†L20-L115】 (Size: S)
5. **P1 – Structured logging & dry-run**: Replace bare `print` calls with logging (levels) and add a `--dry-run` path to inspect planned actions without side effects.【F:frame_compare.py†L95-L193】 (Size: M)
6. **P1 – Testing enhancements**: Add CLI integration tests (using sample media/mocks), slow.pics HTTP mocks for 4xx/5xx, and property-based tests for filename parsing quantiles.【F:tests/test_slowpics.py†L1-L88】【F:tests/test_utils.py†L1-L87】 (Size: M)
7. **P2 – CI & tooling**: Extend workflow to Python 3.12/Windows, add artifact upload for generated screenshots, and integrate `ruff`/`black` checks for consistent style.【F:.github/workflows/ci.yml†L1-L28】 (Size: M)
8. **P2 – Documentation**: Document unsupported features (ffmpeg, caching) until implemented, and add troubleshooting for VapourSynth/Pillow installation gaps.【F:README.md†L1-L171】 (Size: S)

# Risks & Trade-offs
- Implementing overrides and caching touches core orchestration and may require redesigning `frame_compare._init_clips` to accept per-file metadata, increasing complexity and testing surface.【F:frame_compare.py†L87-L188】
- FFmpeg fallback must match VapourSynth output fidelity; ensuring deterministic PNG naming across writers demands rigorous tests.【F:src/screenshot.py†L146-L186】
- Enforcing ram limits globally can impact multi-run workflows if not scoped carefully, particularly when multiple comparisons run within one interpreter.【F:src/vs_core.py†L48-L113】

# Next Actions
1. Implement config parity fixes: overrides, naming prefs, ram limit, and ffmpeg toggle semantics (blocker for release).
2. Build caching layer for frame metrics respecting `save_frames_data` & `frame_data_filename`.
3. Expand automated tests per `docs/TEST_GAPS.md`, including CLI integration and slow.pics failure cases.
4. Enhance CI matrix (Python versions, Windows) and add lint/static analysis steps.
5. Update documentation to reflect current feature set and migration caveats.
