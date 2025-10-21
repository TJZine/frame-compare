# Context Summary — Frame Compare

## Documentation Sources Reviewed
- Project guardrails in `CODEX.md` detail the diff-plan workflow, typing requirements, and sandbox restrictions, setting approval expectations and prohibiting risky edits without review. 
- Repository overview and operator guidance from `README.md`, including setup, workspace path diagnostics, and VSPreview integration notes.
- Component deep-dives across `docs/`, covering path guardrails (`PATHS-AUDIT.md`, ADR 0001), geometry/tonemap behaviour, audio alignment, deep-review follow-ups, and configuration supplements (`docs/README_REFERENCE.md`, `docs/config_reference.md`).

## Architecture Overview
- `frame_compare.py` is the orchestration layer: it resolves the workspace root, seeds configs, validates paths, runs analysis, manages audio alignment, renders screenshots, and handles slow.pics uploads plus cleanup. Supporting helpers enforce root containment and site-packages bans.
- Core modules under `src/` split responsibilities: `analysis.py` computes frame metrics and caches; `audio_alignment.py` estimates offsets and persists TOML sidecars; `screenshot.py` prepares geometry/tonemap overlays and invokes VapourSynth/FFmpeg; `slowpics.py` manages upload sessions; `tmdb.py` resolves metadata; `vs_core.py` wraps VapourSynth plugin loading and tonemap helpers; `config_loader.py` parses and validates TOML into dataclasses defined in `datatypes.py`; `utils.py` extracts filename metadata.
- The CLI layout system in `src/cli_layout.py` renders structured Rich dashboards from JSON-like contexts with a sandboxed expression evaluator.

## Directory & Module Layout
- Repository root hosts `frame_compare.py`, `pyproject.toml`, `pyrightconfig.json`, `uv.lock`, docs, tests, bundled fixtures (`comparison_videos/`), and typed stubs under `typings/`.
- `src/data/` provides the packaged config template. `frame_compare.egg-info/` tracks packaging metadata.
- Tests in `tests/` cover analysis, CLI layout rendering/formatting, config loading, audio alignment, screenshot behaviour, slow.pics uploads, TMDB lookups, VS core helpers, path preflight, and CLI orchestration.

## Configuration Model & Guardrails
- `datatypes.py` defines strongly-typed config dataclasses (analysis quotas, screenshot geometry, HDR tonemap, slow.pics flags, TMDB options, naming preferences, CLI toggles, runtime guardrails, source plugin preference, audio alignment controls).
- `config_loader.py` coerces booleans/enums, validates numeric ranges, enforces nested tables, ensures offsets/trim overrides are typed correctly, and normalises overlay and colour override settings. Audio alignment parameters are clamped (non-negative, thresholds in `[0,1]`).
- Workspace discovery `_discover_workspace_root` prioritises CLI flag → env → sentinel-based detection → CWD, aborting when landing under site/dist-packages. `_resolve_workspace_subdir` constrains configured subdirectories to remain under the media root unless explicitly allowed, and `_path_is_within_root` double-checks before destructive actions. `_prepare_preflight` seeds configs atomically and runs writability probes, optionally surfacing diagnostics JSON when `--diagnose-paths` is set. These guardrails implement ADR 0001 and the paths audit recommendations.

## Key Workflows
- **Frame Analysis & Selection**: `src/analysis.py` loads caches (versioned metadata), computes selection windows from config (respecting lead/trail trims), merges brightness/motion scores, and exports selection metadata for downstream reuse.
- **Audio Alignment**: `_maybe_apply_audio_alignment` orchestrates reference/target selection, ffprobe-based stream discovery, onset envelope correlation via `src/audio_alignment.py`, offset biasing, TOML sidecar persistence (`update_offsets_file`), optional VSPreview prompts, and JSON tail summaries. Negative offset swaps and manual reuse prompts are handled explicitly.
- **Screenshot Generation**: `src/screenshot.py` handles geometry planning, odd-pixel detection, YUV444P16 pivoting, overlay/dithering policies, and label sanitisation, while `vs_core.py` loads sources, applies tonemapping, verifies HDR conversions, and exposes metadata for CLI rendering.
- **Slow.pics Integration**: `src/slowpics.py` uses a `requests.Session` to hit legacy upload endpoints, chunking comparisons, creating shortcuts, and closing sessions in `finally` to avoid leaks.
- **CLI Layout**: `src/cli_layout.py` loads JSON DSL definitions, validates AST expressions (only exposes safe builtins), and renders styled Rich tables using context resolvers, aligning with the documented layout tweaks in `docs/DECISIONS.md`.

## External Dependencies
- `pyproject.toml` declares runtime deps: Rich, Click, HTTPX/requests, numpy/librosa/soundfile (audio), natsort, anitopy, guessit, tqdm, plus optional `vapoursynth`. Dev group adds pytest, pytest-mock, requests-mock, ruff, black. Python `>=3.13,<3.14` is enforced due to upstream wheels.
- Vendored type stubs in `typings/` cover click, httpx, requests, rich, pytest, natsort, vapoursynth, ensuring Pyright standard mode passes with strict import checks.

## Testing & Quality Signals
- Pyright runs in standard mode with include paths for `src`, `tests`, entry script, and `typings`. `reportMissingImports` is elevated to errors and optional member access is disallowed.
- Pytest suite spans CLI guards (`test_paths_preflight.py`, `test_frame_compare.py`), audio alignment (including VSPreview flows and manual reuse), screenshot behaviour, slow.pics uploads, TMDB resolvers, CLI layout formatting, and utility helpers. Fixtures under `tests/fixtures` provide small media assets. The CLI runner tests verify JSON tail content and cleanup behaviour.
- Linting uses Ruff (E/F/I/W) and Black (line length 100).

## Security, Performance & Reliability Notes
- Deep review highlights a critical risk: misconfigured `screenshots.directory_name` can point outside the workspace, and the default slow.pics cleanup (`delete_screen_dir_after_upload=true`) will recursively delete that directory after upload. `_path_is_within_root` mitigates cross-root deletion, but directory names should be further normalized to prevent catastrophic erasure. Audio alignment preview folders share the same risk surface. Follow-up is marked urgent.
- Slow.pics session management now closes sessions in a `finally` block; remaining TODO is to close the upload session earlier or switch to context managers per deep-review note.
- Audio alignment warning suppression is scoped to targeted sections, preserving global diagnostics. Odd-geometry handling uses deterministic YUV444P16 promotion with console/log visibility, reducing VapourSynth mod errors.

## External Best-Practice Sync
- Direct MCP/context7 access is unavailable in this environment; external best practices were inferred from maintained docs (Next/VapourSynth/Python knowledge) and prior project notes. Call out if official excerpts are required so they can be sourced manually.

## Outstanding Follow-Ups / Risks
- Harden screenshot/preview output containment per deep-review guidance (normalize `screenshots.directory_name`, enforce relative-only values before deletion).
- Document layout file trust boundaries in contributor docs and consider closing slow.pics sessions after uploads as recommended.
- Ensure any future feature work updates `docs/DECISIONS.md` and `CHANGELOG.md` per guardrails.

## Ready State
With documentation, architecture, dependencies, guardrails, and workflow patterns loaded, the codebase context is primed for feature or bug-fix planning. Future work should continue honoring diff-plan approvals, Pyright checks, test additions, and workspace containment policies.
