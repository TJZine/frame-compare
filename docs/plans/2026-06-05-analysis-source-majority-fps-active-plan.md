Status: Active
Scope: Add majority FPS matching and legacy-style fastest analysis source selection without making the fastest clip the global reference
Owner: Next implementation session

# Analysis Source And Majority FPS Plan

## Goal

Restore the useful legacy behavior where Frame Compare can use a cheaper/faster clip for analysis, while keeping reference/timing/display semantics explicit and stable.

Implement two config-only source features:

- `sources.match_fps = "majority"`: match effective FPS to the strict FPS majority when one exists; otherwise fall back to the selected reference FPS with a warning/report note.
- `sources.analysis_source = "reference" | "fastest" | <source selector>`: choose which clip supplies analysis metrics without changing the selected reference clip or clip display order.

The default behavior must remain conservative and compatible:

```toml
[sources]
# reference = "auto"
# analysis_source = "reference"
# match_fps = "disabled"
```

## Non-Goals

- Do not add CLI flags for `reference`, `analysis_source`, or `match_fps`.
- Do not make the fastest analysis clip become the global reference.
- Do not resample, duplicate, drop, interpolate, retime audio, or physically convert sources.
- Do not change slow.pics, report viewer UI, screenshot geometry, Docker, Windows portable, or TMDB behavior.
- Do not change `run --json` success schema.
- Do not add legacy compatibility shims beyond the explicitly documented config behavior.

## Risk And Verification Classification

Risk tier: High.

Reasons:

- Public config contract change.
- Orchestration and analysis phase behavior change.
- Analysis cache identity and persisted cache schema may change.
- Runtime probing/benchmarking touches VapourSynth-loaded clips.

Primary verification mode: `contract-first` plus `integration-ops` for VapourSynth benchmark seams.

Plan classification:

- New regression/contract tests required for config schema, source selection, majority FPS policy, analysis source selection, cache identity, and CLI contract docs.
- Broader full verification required by the runbook because this changes config, orchestration, and analysis owners.
- Manual/runtime smoke recommended with the real Fight Club inputs if available on the implementation machine.

Required commands before closeout:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/config/test_schema.py tests/orchestration/test_preparation.py tests/orchestration/test_execute_run_cache_modes.py tests/orchestration/test_execute_run_lifecycle.py tests/test_cli_contract_docs.py -q
.\.venv\Scripts\python.exe -m pyright --warnings
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m bandit -c pyproject.toml -r src --severity-level medium
$env:UV_CACHE_DIR='.uv_cache'; uv run --no-sync lint-imports --config importlinter.ini
.\.venv\Scripts\python.exe -m pytest -q
```

Expected outcomes:

- Focused tests pass.
- Pyright, Ruff, Bandit, and import-linter pass.
- Full pytest passes. If full pytest fails only because of pre-existing synthetic lifecycle fixtures that build `PrepState.input_videos` with non-existent files, stop and report that gate blocker before committing unrelated test repairs.

## Public Contract

Update `docs/current-cli-contract.md` in the same implementation pass.

`[sources]` fields after this change:

- `reference`: optional source selector. Omitted or literal `"auto"` means the first discovered input remains the selected reference. A non-auto value resolves through the existing source selector rules and moves that clip to the front.
- `analysis_source`: config-only string. Defaults to `"reference"`.
  - `"reference"` means analyze the selected reference clip.
  - `"fastest"` means benchmark discovered clips and analyze the fastest usable clip.
  - Any other value is resolved as a source selector using the existing selector rules.
- `match_fps`: enum string. Defaults to `"disabled"`.
  - `"disabled"` preserves current strict mixed-FPS validation.
  - `"assume_reference"` preserves the just-added behavior: comparison clips without explicit `effective_fps` inherit the selected reference effective FPS.
  - `"majority"` chooses the strict majority effective FPS when one exists after explicit per-source `effective_fps` overrides. If no strict majority exists, it uses the selected reference effective FPS as the target and emits a warning/report note.

Explicit per-source `effective_fps` values always take precedence over automatic matching. If an explicit override leaves effective FPS mixed after policy application, keep failing with `MixedSourceFpsError`.

Selector rules remain case-sensitive and must continue to reject absolute paths, Windows drive paths, UNC paths, empty selectors, `.` segments, and `..` segments.

`run --json` stdout remains a single success object with the existing schema. Any new diagnostics must go to human/stderr output or existing warning collection, not JSON stdout.

## Required Runtime Order

The implementation must use this order:

1. Resolve effective config.
2. Discover input clips.
3. Resolve selected reference and deterministic clip order.
4. Load or compute clip probe snapshots for every discovered clip.
5. Build initial `ClipState` values with explicit per-source overrides.
6. Apply `match_fps` policy to produce final effective FPS values.
7. Validate effective FPS compatibility.
8. Compute the shared selection window from all final effective FPS values and trims.
9. Resolve `analysis_source`.
10. Build the analysis selection-domain token including selected reference, selected analysis source, effective FPS values, trims, source identities, configured ignore windows, and final shared selection window.
11. Execute phase plan: `frame_plan -> analyze -> align -> render -> metadata -> dovi -> publish -> report -> post_report_cleanup`, preserving the existing report-confirmed upload ordering exception.

FPS matching must happen before analysis-domain calculation and before frame selection.

## Owner Seams

Use existing owners and add focused owners only where they prevent hotspot growth.

In scope:

- `src/frame_compare/config/schema_enums.py`
- `src/frame_compare/config/schema_models.py`
- `src/frame_compare/config/defaults.py`
- `src/frame_compare/orchestration/source_selection.py`
- `src/frame_compare/orchestration/selection_domain.py`
- `src/frame_compare/orchestration/preparation.py`
- `src/frame_compare/orchestration/phase_selection.py`
- `src/frame_compare/orchestration/execution.py` only if needed to pass analysis-source state into phase construction
- `src/frame_compare/orchestration/types.py`
- `src/frame_compare/orchestration/context.py`
- `src/frame_compare/orchestration/errors.py`
- `src/frame_compare/orchestration/fps_report.py` or a new adjacent orchestration diagnostics owner if needed
- `src/frame_compare/analysis/cache_io.py`
- `src/frame_compare/analysis/metrics.py`
- `src/frame_compare/analysis/types.py`
- Tests under `tests/config/`, `tests/orchestration/`, `tests/analysis/` if present, and `tests/test_cli_contract_docs.py`
- `docs/current-cli-contract.md`
- `docs/current-architecture.md` only if the implementation adds a new owner module or materially changes documented runtime flow/cache ownership

Preferred new focused module if needed:

- `src/frame_compare/orchestration/analysis_source.py`

Use it only for analysis-source resolution and fastest-source benchmarking policy. Do not put this logic into `coordinator.py`.

Out of scope:

- `src/frame_compare/cli/entry.py`, unless only contract tests prove no CLI flag change is needed.
- `src/frame_compare/runner.py`
- `src/frame_compare/render/**`
- `src/frame_compare/services/**`
- `src/frame_compare/vs/**`, unless a small protocol-friendly benchmark helper absolutely needs a VS-loader-facing type.
- `importlinter.ini`, unless a new module violates layers. Prefer placing new code where the current layers already allow imports.

## Detailed Implementation Plan

### 1. Config Schema

Update `SourceMatchFpsMode`:

- Keep `DISABLED = "disabled"`.
- Keep `ASSUME_REFERENCE = "assume_reference"`.
- Add `MAJORITY = "majority"`.

Add `SourcesConfig.analysis_source: str = "reference"`.

Do not use an enum for `analysis_source`, because selector values are arbitrary strings. Validate/resolve the value at source-selection/preparation time, not in Pydantic schema, except that empty strings must eventually fail through the same typed selector error path as other source selectors.

Update `DEFAULT_CONFIG_TOML` comments:

```toml
[sources]
# reference = "auto"
# analysis_source = "reference"  # reference, fastest, or a source selector
# match_fps = "majority"  # opt-in; timing metadata only, no frame resampling
```

Keep the default model values equivalent to omitted config:

- `reference is None`
- `analysis_source == "reference"`
- `match_fps == SourceMatchFpsMode.DISABLED`

### 2. Source Reference Resolution

Update `resolve_source_selection()` so `config.reference in {None, "auto"}` means the existing default: first discovered path is the reference.

The literal `"auto"` is reserved for reference auto-selection. A source file named `auto.mkv` can still be selected by filename `auto.mkv` or relative path; the bare stem selector `"auto"` means auto and does not select that file.

Keep all existing duplicate-stem and selector rejection behavior.

### 3. FPS Matching Policy

Move FPS matching policy into a focused function owned by `selection_domain.py` or an adjacent orchestration owner. It must operate on already ordered `ClipState` values.

Apply policy after explicit per-source `effective_fps` overrides have been applied.

Policy rules:

- `disabled`: return clips unchanged.
- `assume_reference`: preserve current behavior. Set every non-reference clip without explicit `effective_fps` override to the selected reference effective FPS.
- `majority`:
  - Count current effective FPS values for all clips after explicit overrides.
  - A strict majority means one FPS appears more than `len(clips) / 2`.
  - If a strict majority exists, target that FPS.
  - If no strict majority exists, target the selected reference effective FPS.
  - Set every clip without explicit `effective_fps` override to the target FPS, including the reference when the reference is a non-explicit outlier.
  - Preserve every clip with explicit `effective_fps`.
  - Return diagnostics describing target FPS, reason (`majority` or `reference_fallback_no_majority`), and every clip whose effective FPS changed.

After policy application, call the existing mixed-FPS validation. If explicit overrides leave mixed effective FPS values, raise `MixedSourceFpsError`.

The matching remains AssumeFPS-style timing metadata only.

### 4. Analysis Source Resolution

Add a typed preparation result field for the chosen analysis clip.

Recommended shape:

- Add `analysis_clip: ClipState` or `analysis_source: ClipState` to `PrepState`.
- Add corresponding field to `RunContext`.
- Keep `reference` and `comparisons` unchanged.

Resolution rules:

- `"reference"`: selected analysis clip is `clips[0]`.
- `"fastest"`: benchmark eligible clips and choose the fastest usable clip.
- Other string: resolve as a source selector against discovered inputs using the same selector rules as `sources.reference` and `sources.overrides`, then choose the matching prepared `ClipState`.

If the configured analysis source selector does not match exactly one discovered input, fail before phase execution with the existing typed source-selection error path.

Do not reorder `clips`, `input_videos`, `reference`, or `comparisons` because of `analysis_source`.

### 5. Fastest Analysis Benchmark

Implement fastest-source benchmarking only when `sources.analysis_source == "fastest"`.

Benchmark after probe snapshots exist and after effective FPS policy is resolved. Use the same `RunDependencies.vs_loader` boundary already used for probing.

Benchmark behavior:

- For each clip, load the source through `VSLoader.load(path)` and time two small frame-read windows, equivalent in spirit to legacy:
  - window near one-third of the clip
  - window near two-thirds of the clip
  - read up to 15 frames per window, reduced for very short clips
- Prefer `clip.std.PlaneStats()` when available. If unavailable, time direct `clip.get_frame()` reads.
- If a candidate fails to load or read during benchmarking, mark it unusable for `fastest` and continue.
- If all candidates fail benchmarking, fail with a typed input/runtime error that says no source could be benchmarked for `sources.analysis_source = "fastest"`.
- Tie-break by existing deterministic clip order.
- Do not persist benchmark timings across runs. Decode speed depends on runtime state, cache warmth, plugin behavior, and host machine. The analysis cache identity stores the selected analysis source, not speed data.

If implementation can reuse an already loaded clip from probe without broadening owner seams, it may do so. Do not weaken `ClipProbeSnapshot` by storing live VS clip objects.

### 6. Analysis Phase Semantics

Update analysis to compute metrics from the selected analysis source, not necessarily the selected reference.

Required behavior:

- `selected_frames` remains the aligned frame-offset list used by render and alignment.
- `user_frames` remain original selected-reference source-frame numbers.
- Convert configured reference `user_frames` into aligned frame offsets by subtracting `reference.trim.trim_start_frames`, then constrain them to the shared selection window.
- When trimming analysis metrics to the shared selection window, use:
  - `analysis_clip.trim.trim_start_frames + selection_window.start_frame`
  - `selection_window.frame_count`
- Dark/bright/motion scoring comes from the analysis source metrics.
- Selection details exposed to reports and overlays remain keyed by selected-reference source-frame numbers:
  - `reference_source_frame = reference.trim.trim_start_frames + aligned_frame`
  - detail `source` may say `"analysis"` and may include the analysis clip label/name in notes if an existing DTO field can carry it without schema churn.
- Timecodes in selection details must use the final effective FPS used for the shared domain. Because mixed effective FPS validation passes before analysis, reference effective FPS and analysis effective FPS should be equal unless an explicit override mismatch already failed.

Do not let analysis use native source FPS when render/report uses matched effective FPS.

### 7. Analysis Cache Identity And Schema

Analysis cache identity must distinguish runs with different selected analysis sources.

Required changes:

- Add `analysis_source_path` to the stable selection-domain token built by `build_analysis_selection_domain_token()`.
- Pass the selected analysis source path into `cache_io.compute_cache_key()` through the selection-domain token; do not add a second ad hoc hash input.
- Update `calculate_metrics()` so it loads the selected analysis source path while still validating cache identities for all ordered input clips.

Persisted cache metadata should be unambiguous:

- Extend `MetricsMetadata` with `analysis_source_path: str`.
- Bump `CACHE_VERSION`.
- Save and load the new field.
- Old cache files must miss through version mismatch or schema validation rather than being interpreted as new-shape cache hits.

The metrics cache filename may keep using the current human label from ordered input paths, as long as the full fingerprint includes `analysis_source_path`.

### 8. Diagnostics And User Visibility

Add user-visible diagnostics for automatic choices.

Human non-quiet output after load-sources should make these facts clear:

- selected reference
- selected analysis source and reason (`reference`, `configured`, or `fastest`)
- FPS target and reason (`majority`, `reference`, or `reference fallback; no FPS majority`)
- per-clip FPS changes, showing source FPS and final effective FPS when changed

Example text shape; exact wording can follow existing Rich/report style:

```text
Reference: Fight.Club...TheFarm.mkv
Analysis source: Fight.Club...D-Z0N3.mkv (fastest)
FPS target: 24000/1001 (majority)
FPS matched: PTer 24 -> 24000/1001
```

JSON stdout must not change. If diagnostics are represented as warnings in `RunResult`, they must remain off `run --json` stdout per current CLI contract.

### 9. Error Message Updates

Update mixed-FPS hint text to include:

- `sources.match_fps = "majority"`
- `sources.match_fps = "assume_reference"`
- explicit `sources.overrides.<selector>.effective_fps`
- preprocessing as the last-resort option

Add a typed error or reuse `SourceSelectionError` for invalid `analysis_source` selectors. Avoid raw `ValueError` or tracebacks for user config mistakes.

### 10. Tests

Add or update tests through public/runtime seams rather than private implementation shapes.

Required config tests:

- default `analysis_source == "reference"`
- `match_fps = "majority"` is accepted
- invalid `match_fps` is rejected
- default config template documents `analysis_source` and `majority`

Required source/prep tests:

- `reference = "auto"` behaves like omitted reference
- `analysis_source = "reference"` chooses selected reference
- `analysis_source = <selector>` chooses that clip without reordering reference/comparisons
- invalid `analysis_source` selector fails through typed source-selection/config error path
- `match_fps = "majority"` with a strict majority matches outliers to majority
- `match_fps = "majority"` with no majority falls back to selected reference and records a warning/report diagnostic
- `match_fps = "majority"` can match a non-explicit reference outlier to the majority FPS
- explicit per-source `effective_fps` is preserved and can still trigger `MixedSourceFpsError`
- source FPS is preserved while effective FPS changes

Required analysis/cache tests:

- analysis metrics load the configured analysis source path, not `input_videos[0]`
- `analysis_source = "fastest"` chooses the fastest candidate by benchmark time and tie-breaks by deterministic clip order
- failed benchmark candidates are skipped; all-failed benchmark produces typed failure
- selected frames remain aligned frame offsets when analysis source differs from reference
- selection details are keyed by selected-reference source-frame numbers
- analysis cache fingerprint differs when only `analysis_source` differs
- old cache schema without `analysis_source_path` does not load as a valid hit after `CACHE_VERSION` bump

Required docs contract tests:

- `tests/test_cli_contract_docs.py` must assert documentation for:
  - `analysis_source`
  - `match_fps = "majority"`
  - majority fallback to reference when no majority exists
  - no CLI flags for these fields
  - JSON stdout schema unchanged

Runtime-dependent tests:

- Default unit tests must use fake VS loader/clip objects and must not require real VapourSynth.
- Any real VS benchmark smoke must be marked/skipped using existing runtime marker patterns if added.

## Manual Runtime Smoke

When the Fight Club sources are available locally, run one smoke after automated tests:

Config shape:

```toml
[sources]
analysis_source = "fastest"
match_fps = "majority"
```

Expected behavior for the known source set:

- FPS target is `24000/1001` by majority.
- The `24` FPS PTer source is effective `24000/1001`.
- The `13978/583` D-Z0N3 source is effective `24000/1001` only if the majority policy target requires it and it has no explicit override.
- The chosen analysis source is whichever benchmark is fastest, reported explicitly.
- The selected reference remains the auto/default discovered reference unless config sets `reference`.

If exact local files differ, record the actual reference, analysis source, FPS target, and matched clips.

## Authority Docs

Update `docs/current-cli-contract.md` in the same implementation pass.

Update `docs/current-architecture.md` only if:

- a new `orchestration.analysis_source` owner module is added,
- `PrepState`/`RunContext` runtime flow is materially re-described,
- analysis cache ownership text needs to mention selected analysis source in the canonical persistence description.

Do not update `AGENTS.md`, the runbook, or `importlinter.ini` unless implementation proves those authority docs or import layers must change.

## Stop And Replan Triggers

Stop before implementing further if any of these occur:

- Making fastest analysis source the selected/global reference seems necessary.
- `run --json` schema would need to change.
- Selector resolution requires weakening current invalid path protections.
- Analysis selected frames cannot remain aligned frame offsets while preserving reference-domain `user_frames`.
- Cache identity cannot include analysis source without changing persisted schema; the plan already requires schema/version updates, so any alternative must be reviewed.
- Import-linter requires a new cross-domain dependency between `analysis`, `render`, or `services`.
- Fastest benchmark requires storing live VapourSynth clip objects in persisted probe snapshots.
- Full verification fails for reasons other than known pre-existing lifecycle fixture failures.

## Closeout Checklist

- Config schema and defaults updated.
- Config-only public contract documented.
- Majority FPS fallback warning/report is visible to human users.
- Analysis source choice is visible to human users.
- JSON stdout unchanged.
- Cache version and schema updated if `MetricsMetadata` changes.
- Tests cover strict majority, no-majority fallback, reference outlier, explicit override precedence, configured analysis source, fastest analysis source, cache identity, and reference-domain selected-frame mapping.
- Focused tests and full verification commands run and recorded.
