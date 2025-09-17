# Summary (TL;DR)
- FFmpeg exports now honour trim offsets and fall back with clear logging, keeping the VapourSynth and FFmpeg pipelines in sync even when per-clip overrides are active.【F:frame_compare.py†L377-L390】【F:src/screenshot.py†L306-L384】
- Global scaling parity, motion-frame quarter gaps, and label deduplication all mirror the legacy heuristics, so mixed-resolution sets produce matched heights and abbreviated labels without manual intervention.【F:src/screenshot.py†L67-L384】【F:src/analysis.py†L281-L412】【F:frame_compare.py†L74-L136】
- slow.pics uploads now replay the legacy webhook POST with retries, and the expanded regression suite exercises FFmpeg trims, upscale coordination, CLI caching, and slow.pics failure paths for real parity coverage.【F:src/slowpics.py†L3-L158】【F:tests/test_screenshot.py†L24-L156】【F:tests/test_frame_compare.py†L47-L270】【F:tests/test_slowpics.py†L54-L142】

# Repo Overview
`frame_compare.py` remains the orchestration entry point, loading TOML config, parsing metadata, applying overrides, selecting frames, rendering screenshots, and optionally uploading to slow.pics.【F:frame_compare.py†L73-L420】 Supporting modules include `src/config_loader.py` for validation, `src/datatypes.py` for structured config, `src/utils.py` for GuessIt/Anitopy parsing, `src/analysis.py` for metrics and caching, `src/screenshot.py` for crop/scale planning and writers, `src/slowpics.py` for API automation, and `src/vs_core.py` for VapourSynth initialisation and tonemapping.【F:src/config_loader.py†L10-L123】【F:src/datatypes.py†L6-L102】【F:src/utils.py†L1-L167】【F:src/analysis.py†L13-L412】【F:src/screenshot.py†L1-L384】【F:src/slowpics.py†L1-L158】【F:src/vs_core.py†L1-L204】 Defaults in `config.toml` still mirror the dataclasses.【F:config.toml†L1-L59】

# Architecture Review
- **`src/config_loader`** — Continues to enforce numeric bounds and boolean coercion, raising `ConfigError` early for invalid sections; no changes required.【F:src/config_loader.py†L26-L123】
- **`src/datatypes`** — Dataclasses cover legacy options; the existing structure now feeds the global-scaling planner directly without additional globals.【F:src/datatypes.py†L6-L102】
- **`src/utils`** — GuessIt/Anitopy wrappers remain defensive, and metadata labels feed the improved CLI deduplication logic.【F:src/utils.py†L1-L167】【F:frame_compare.py†L74-L136】
- **`src/analysis`** — Motion candidates now observe a quarter-gap override before final selection, matching legacy diversity while preserving caching and quantile logic.【F:src/analysis.py†L281-L412】 The pure functions stay deterministic and free of side effects.
- **`src/screenshot`** — Geometry planning now computes a global target height, resolves trim-aware frame indices for FFmpeg, and logs unexpected writer failures before producing placeholders, improving parity and diagnosability.【F:src/screenshot.py†L67-L384】
- **`src/slowpics`** — Adds host-redacted logging, limited retries, and the legacy-style direct webhook POST alongside the existing REST workflow, keeping uploads resilient without leaking secrets.【F:src/slowpics.py†L3-L158】
- **`src/vs_core`** — RAM limits, trim slicing, and tonemapping remain unchanged; the module cleanly supports the additional CLI wiring with no regressions.【F:src/vs_core.py†L48-L177】
- **`frame_compare`** — CLI orchestration now passes trim offsets to the writer and generates stable short labels for duplicates while preserving cache fingerprints and error messaging.【F:frame_compare.py†L74-L390】

# Quality Findings
- **Strengths**
  - Trim-aware FFmpeg calls and placeholder logging expose failure details without crashing the run, improving observability.【F:src/screenshot.py†L306-L384】
  - Global scaling is coordinated in one pass, eliminating per-clip drift and keeping the code free of mutable globals.【F:src/screenshot.py†L85-L135】【F:src/screenshot.py†L306-L384】
  - Direct webhook retries respect privacy by redacting hosts in logs, and retry backoff prevents tight loops.【F:src/slowpics.py†L60-L82】
- **Opportunities**
  - The quarter-gap factor is still hard-coded; exposing it as a tunable AnalysisConfig field would help advanced workflows without copying code.【F:src/analysis.py†L388-L404】
  - CLI error handling still exits with `sys.exit` for user-facing messaging; introducing typed CLI exceptions would make reuse as a library easier.【F:frame_compare.py†L320-L420】
  - Structured logging (JSON or `rich` log handler) could make automated consumption easier now that more events are emitted.【F:src/screenshot.py†L306-L384】【F:src/slowpics.py†L60-L82】

# Functional Parity Findings
- FFmpeg renders respect trims (positive and negative) and fall back to VapourSynth when synthetic padding would otherwise yield invalid indices, matching legacy screenshot offsets.【F:src/screenshot.py†L306-L384】
- Global `upscale=True` now aligns all clips to the tallest cropped height while preserving `single_res` semantics, reproducing the legacy tallest-height behaviour.【F:src/screenshot.py†L67-L134】【F:tests/test_screenshot.py†L106-L131】
- Motion-frame selection honours the historical quarter-gap heuristic and keeps deterministic ordering under cache reuse.【F:src/analysis.py†L281-L412】【F:tests/test_analysis.py†L156-L189】
- Duplicate labels respect `always_full_filename=false`, appending version suffixes or indices instead of reverting to raw filenames, so CLI output and screenshot names remain concise.【F:frame_compare.py†L87-L135】【F:tests/test_frame_compare.py†L139-L170】
- slow.pics uploads register the webhook and issue the direct POST with retries, restoring the legacy delivery guarantee while maintaining redacted logging.【F:src/slowpics.py†L60-L158】【F:tests/test_slowpics.py†L108-L142】

# Test & CI Findings
- The suite now covers FFmpeg trim offsets, global upscale coordination, placeholder logging, motion quarter-gap logic, CLI cache reuse, input overrides, and slow.pics webhook retries/missing tokens.【F:tests/test_screenshot.py†L80-L156】【F:tests/test_analysis.py†L156-L189】【F:tests/test_frame_compare.py†L139-L270】【F:tests/test_slowpics.py†L54-L142】
- `uv run python -m pytest -q` passes (39 tests) with the new coverage.【75eb15†L1-L3】
- CI still targets Ubuntu + Python 3.11 only; extending to Python 3.12/Windows and adding lint/static-analysis would future-proof parity work.【F:.github/workflows/ci.yml†L1-L33】

# Enhancement Proposals
1. **P1 – Document parity & configuration nuances (S)**: Update the README/config reference to describe the restored parity features (global upscale, trim-aware FFmpeg, webhook retries) and note how to tune them, so legacy users know the modern defaults.【F:README.md†L1-L171】
2. **P1 – Expand CI matrix & linting (M)**: Add Python 3.12 and Windows runners plus `ruff`/`mypy` jobs to catch regressions across environments and keep the renewed parity stable.【F:.github/workflows/ci.yml†L1-L33】
3. **P1 – Expose motion gap divisor (S)**: Promote the quarter-gap divisor to `AnalysisConfig` with validation and CLI plumbing, letting advanced users match legacy variants without code edits.【F:src/analysis.py†L281-L404】
4. **P2 – Console script packaging (S)**: Publish a `frame-compare` console entry point via `pyproject.toml` so the tool can be installed and invoked without `python -m`, improving DX for parity testers.【F:pyproject.toml†L1-L66】

# Risks & Trade-offs
- Global upscale requires accessing clip metadata up front and can increase memory use on large batches; documentation should call this out for resource-constrained hosts.【F:src/screenshot.py†L85-L135】
- Direct webhook retries currently block the CLI; on slow endpoints the run may take longer, so a future asynchronous or timeout-tunable approach may be warranted.【F:src/slowpics.py†L60-L82】
- Additional logging improves diagnostics but could leak contextual filenames; ensure downstream log aggregation handles privacy requirements appropriately.【F:src/screenshot.py†L306-L384】

# Next Actions
1. Update README/config docs to summarise the restored parity features and any new configuration knobs.
2. Extend the GitHub Actions workflow with Python 3.12, Windows coverage, and lint/static-analysis stages.
3. Add an `AnalysisConfig.motion_gap_divisor` option (with tests) to let power users customise the quarter-gap heuristic.
4. Package a console script entry point (and optional `--dry-run`) to streamline CLI usage and parity verification scripts.
