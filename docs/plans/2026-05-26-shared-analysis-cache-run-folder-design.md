Status: Historical
Scope: Shared fingerprint-keyed analysis cache with fresh run-scoped outputs
Owner: Codex session

# Shared Analysis Cache With Fresh Run Outputs

## Workstream Note

Another active plan exists: `docs/plans/2026-05-25-vapoursynth-r76-dependency-update.md`.
Do not edit it for this work. This plan is a separate active workstream because the
maintainer explicitly requested a durable plan for this high-risk persistence, CLI
contract, and orchestration change.

## Verification Mode

Primary verification mode: contract-first plus regression-first.

This change affects orchestration, persistence ownership, runtime flag semantics, and
the authority docs. Full verification is required after focused regression and
contract tests pass.

## Accepted Design

Frame Compare will use a hybrid persistence model:

- Expensive reusable analysis results live in a shared workspace-level analysis cache.
- Run outputs stay fresh and run-scoped.
- Normal runs with `paths.use_run_folders = true` always reserve a fresh run folder.
- Existing run folders are never reused to obtain analysis cache hits.
- Screenshots, slow.pics upload inputs, alignment offsets, manual overrides, and
  VSPreview artifacts remain tied to the current run folder.
- Reports preserve existing `report.output_dir` public behavior as an explicit
  exception: fallback report placement stays tied to screenshot/current run output, but
  configured `report.output_dir` continues to own report location unless changed in a
  separate CLI/config contract change.

The shared analysis cache lives under the configured workspace-level generated
directory, independent of run-folder mode:

```text
<resolved paths.generated_dir>/cache/analysis/
```

Cache entries use one fingerprint-named payload per entry and no single multi-entry
index. The user request's "directory-per-entry" wording is interpreted as rejecting a
global index and requiring independently addressable fingerprint-named entries, not as
requiring an extra subdirectory around every payload file.

Cache filenames use:

```text
<safe-human-label>__<full-fingerprint>.compframes
```

Rules:

- `<safe-human-label>` is derived from input filename stems, not TMDB metadata.
- Labels are sanitized to filesystem-safe lowercase text.
- Labels are length-limited.
- The full fingerprint is included in the filename to avoid index lookup and collision
  problems.
- Correctness is based on validating the full fingerprint stored inside the payload
  when loading.

The first implementation must keep the existing `compute_cache_key(...)` identity.
That identity currently includes input paths, file size, mtime ns, analysis config, and
cache version. Do not broaden or narrow it in this change unless tests and naming are
updated deliberately.

Future improvement to record, not implement now: `calculate_metrics` currently analyzes
only the reference clip, so a later design may split metric identity from comparison and
selection identity.

## Rejected Alternatives

- Reusing an existing run folder for normal reruns is rejected. It risks stale
  screenshots because screenshot filenames are stable and slow.pics uploads all PNGs
  from the screenshot directory.
- Reusing run folders for cache hits is rejected because alignment cache keys currently
  use only filename stems, which makes stale `audio_offsets.toml` reuse unsafe.
- Requiring `--from-cache-only` to find a previous full run folder snapshot is rejected.
  The flag is analysis-cache-only for the analysis phase.
- A single multi-entry cache index is rejected. Entries must be directly addressable by
  fingerprint-named files.
- TMDB-derived cache labels are rejected. Human cache labels come from input filename
  stems.
- Moving alignment cache to shared storage is rejected for this change.
- Migrating or opportunistically reading old run-folder analysis cache files is rejected.
  Ignore old run-folder analysis caches and do not add a compatibility shim.
- Deleting or falling back to legacy run-folder analysis caches is rejected unless a
  separate approved migration design explicitly scopes that behavior.
- Moving probe cache is deferred unless it falls out as a very small, clean consequence
  of `WorkspacePaths` changes.

## Exact Path Layout

Default target layout:

```text
workspace-root/
  generated/
    cache/
      analysis/
        video-1__video-2__<full-fingerprint>.compframes
        video-1__video-2__<full-fingerprint>.meta.json
  comparison_videos/
    video 1.mkv
    video 2.mkv
    video 1.lwi
    video 2.lwi
    Movie Name (2024)/
      screenshots/
      generated/
        audio_offsets.toml
        manual_overrides.toml
        vspreview_sessions/
    Movie Name (2024)_20260526-143012/
      screenshots/
      generated/
        audio_offsets.toml
```

If `paths.generated_dir` is configured to a custom location, the shared analysis cache
must move under that resolved generated directory as `<generated_dir>/cache/analysis`,
even when `paths.use_run_folders = true`.

The `.meta.json` sidecar is optional and may be omitted unless it is useful for
diagnostics or tests. The `.compframes` payload must contain the full fingerprint used
for correctness validation.

## Exact Runtime Semantics

Normal run behavior:

- With `paths.use_run_folders = true`, reserve a fresh run folder for every normal run.
- Never reuse an existing run folder to load analysis cache.
- Analysis cache lookup and save use the shared analysis cache under the configured
  workspace-level generated directory.
- Run-scoped output paths remain under the current run folder.
- With run folders disabled, the shared analysis cache still lives under the
  configured workspace-level generated cache area.

`--no-cache` behavior:

- `--no-cache` and `--from-cache-only` remain mutually exclusive.
- `--no-cache` deletes only the matching shared analysis cache entry for the current
  inputs and analysis settings before recomputing it.
- Deletion must target the full fingerprint suffix through an owned `cache_io` helper
  in the shared analysis cache directory, not through a recomputed label alone.
- Deletion must remove the matching `.compframes` file and the matching optional
  `.meta.json` sidecar if one is created.
- `--no-cache` must not clear unrelated shared analysis entries.
- `--no-cache` must not globally wipe alignment caches.
- `--no-cache` must not delete legacy run-folder cache files or files outside the
  shared analysis cache directory unless this implementation deliberately creates new
  shared-analysis sidecars and documents/tests them.

`--from-cache-only` behavior:

- Defines cache-only as analysis-cache-only for the analysis phase.
- Requires the matching shared analysis entry when analysis is not skipped.
- Does not infer or require an old full run folder snapshot.
- Does not require run-scoped alignment offsets from a previous run folder.
- Validates the shared analysis cache before metadata prefetch and before reserving a
  run folder when analysis is not skipped, so a missing or invalid entry does not do
  unnecessary metadata work or leave an empty run folder.
- If validation succeeds and the run proceeds with run folders enabled, the run still
  creates and renders into a fresh run folder.
- If alignment is enabled after a successful analysis-cache-only load, alignment may
  compute normally or use the current fresh run folder's run-scoped alignment cache.

Alignment behavior:

- Alignment cache remains run-scoped.
- Manual overrides remain run-scoped.
- VSPreview artifacts remain run-scoped.
- Do not move alignment cache to shared storage until its schema includes file identity
  and alignment config.

Report behavior:

- Preserve existing `report.output_dir` public behavior.
- If `report.output_dir` is configured, it continues to own report placement.
- Only fallback report placement follows screenshot/current run output.

Probe cache behavior:

- Probe cache is already fingerprinted.
- Do not move probe cache unless the change is very small and clean.
- This plan targets analysis cache reuse, not probe cache reuse.

Diagnostics:

- Prefer leaving `--diagnose-paths` JSON shape unchanged.
- If the `cache` value remains the generated directory, document the shared analysis
  cache separately in `docs/current-cli-contract.md`.
- If the public JSON shape must change unexpectedly, stop and replan.

## Files In Scope

Expected production files:

- `src/frame_compare/utils/types.py`
- `src/frame_compare/orchestration/preflight.py`
- `src/frame_compare/orchestration/preparation.py`
- `src/frame_compare/orchestration/phase_tasks.py`
- `src/frame_compare/analysis/cache_io.py`
- `src/frame_compare/analysis/metrics.py`
- `src/frame_compare/services/run_folder.py`
- `src/frame_compare/services/alignment_cache.py`
- `src/frame_compare/orchestration/probing/probe_cache.py`
- `src/frame_compare/cli/run_command.py`
- `src/frame_compare/render/naming.py`

Expected tests:

- `tests/analysis/test_cache_io.py`
- `tests/analysis/test_metrics.py`
- `tests/orchestration/test_execute_run_cache_modes.py`
- `tests/orchestration/test_execute_run_run_folders.py`
- `tests/orchestration/test_preparation.py`
- `tests/integration/test_loadsources_probe_cache.py`
- `tests/cli/test_run_request_config.py`

Expected docs:

- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- This plan file.

## Files Out Of Scope

- `src/frame_compare/vspreview/adapter.py`
- `tests/vspreview/test_adapter.py`
- `.tmp/`
- The existing active plan
  `docs/plans/2026-05-25-vapoursynth-r76-dependency-update.md`
- Repo-local or installed `desloppify` skill/tool state.

Do not modify the unrelated dirty files unless the maintainer explicitly asks.

## Implementation Sequence

Use this as a one-time controlled workflow:

1. Run an adversarial review of this plan.
2. Adjudicate review findings.
3. Implement one coordinated diff.
4. Run adversarial implementation review.
5. Adjudicate implementation review findings.
6. Run focused verification.
7. Run full verification.
8. Close out with the plan status updated or otherwise resolved according to the
   runbook.

The implementation should remove the provisional existing-run-folder reuse behavior,
add a stable owner for the workspace-level shared analysis cache path, update analysis
cache IO for labeled fingerprint filenames, update analysis cache lookup/save and
cache-mode validation, preserve fresh run-folder reservation for normal outputs, and
update authority docs in the same pass.

## Test Plan

New or updated tests must cover:

- Normal rerun with run folders enabled creates a fresh second run folder and hits the
  shared analysis cache.
- Shared cache path is under the configured workspace-level generated directory at
  `cache/analysis`, not inside the run folder.
- Custom `paths.generated_dir` with run folders enabled places the shared analysis
  cache under the resolved custom generated directory.
- Changing analysis settings creates a separate cache file instead of overwriting an
  unrelated old entry.
- `--no-cache` deletes only the matching shared analysis entry, not other analysis
  cache entries.
- `--no-cache` deletes by full fingerprint suffix in the shared analysis cache
  directory, including the matching optional `.meta.json` sidecar if created, and does
  not delete unrelated fingerprints.
- `--from-cache-only` succeeds from shared analysis cache without needing an existing
  run folder.
- `--from-cache-only` with a missing or invalid shared analysis cache fails before
  analysis recompute.
- `--from-cache-only` missing-cache failure happens before fresh run-folder reservation
  when run folders are enabled.
- `--from-cache-only` missing-cache failure happens before metadata prefetch.
- `--from-cache-only` does not require old run-scoped alignment offsets. Replace any
  old cached-alignment requirement semantics with coverage showing alignment computes
  or uses the current fresh run folder's run-scoped cache as normal after a successful
  analysis cache load.
- Old run-folder-only `cache.compframes` files do not satisfy normal analysis lookup or
  `--from-cache-only` analysis lookup.
- Alignment cache remains run-scoped.
- Cache IO tests cover labeled full-fingerprint filenames and full fingerprint
  validation inside the payload.
- CLI/docs contract tests are updated if diagnose paths or runtime-only flag semantics
  are documented differently.

Classification:

- Shared cache reuse and fresh run folder behavior: new regression test required.
- Configurable generated directory ownership: new regression test required.
- `--no-cache` and `--from-cache-only` semantics: new contract tests required.
- Cache filename and payload fingerprint validation: new unit-level contract tests
  required.
- Alignment remaining run-scoped: regression coverage required.
- Probe cache relocation: no new automated test needed unless implementation touches it.

## Docs Plan

Update `docs/current-architecture.md` in the implementation pass to describe:

- Shared workspace-level analysis cache ownership.
- Run-scoped screenshots, alignment cache, manual overrides, and
  VSPreview artifacts.
- The `report.output_dir` exception: configured report output still owns report
  location, while fallback report placement follows screenshot/current run output.
- Current path layout for shared analysis cache and run folders.
- Any unchanged probe cache placement if useful to prevent ambiguity.

Update `docs/current-cli-contract.md` in the implementation pass to describe:

- `--no-cache` deletes only the matching shared analysis cache entry.
- `--no-cache` deletion is scoped to matching full-fingerprint analysis files in the
  shared analysis cache directory, including optional owned sidecars if created.
- `--from-cache-only` means analysis-cache-only, validates shared cache before metadata
  prefetch and run folder reservation when analysis is not skipped, and still renders
  into a fresh run folder if the run proceeds.
- `--from-cache-only` does not require prior run-scoped alignment offsets.
- `--no-cache` and `--from-cache-only` remain mutually exclusive.
- Runtime-only flag list remains correct.
- `--diagnose-paths` behavior, if changed. If unchanged, leave the JSON shape as-is and
  document the shared analysis cache separately.

## Verification Plan

Focused verification first:

```powershell
uv run --no-sync pytest -q tests/analysis/test_cache_io.py tests/analysis/test_metrics.py tests/orchestration/test_execute_run_cache_modes.py tests/orchestration/test_execute_run_run_folders.py tests/orchestration/test_preparation.py tests/cli/test_run_request_config.py
```

Full gate:

```powershell
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
$env:UV_CACHE_DIR = ".uv_cache"; uv run --no-sync lint-imports --config importlinter.ini
```

Expected outcomes:

- Identical reruns reuse the shared analysis cache.
- Every normal run with run folders enabled gets fresh output directories.
- Custom `paths.generated_dir` is honored for the shared analysis cache.
- Stale screenshots cannot be uploaded from reused run folders.
- `--no-cache` and `--from-cache-only` behavior is documented and tested.
- The provisional run-folder reuse patch is removed.
- Import-linter boundaries remain unchanged.

## Stop And Replan Triggers

Stop and replan if:

- Implementation requires importlinter layer changes.
- `--from-cache-only` would need a previous full run manifest.
- Alignment cache must become shared to make tests pass.
- Probe cache relocation becomes large.
- `--diagnose-paths` public JSON shape needs to change unexpectedly.
- Cache labels require a global index.
