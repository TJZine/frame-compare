# Current Architecture

This document describes the present-day Frame Compare codebase. It is intentionally about what exists now, not desired future structure.

## Operating Stance

Frame Compare is a CLI-first packaged Python app with importable internal modules. The CLI and release artifacts are the primary supported surfaces.

## Composition Roots

- CLI entrypoint: `frame_compare.cli.entry:app`
- Runtime entry surface: `frame_compare.runner.run(...)`
- Async orchestration root: `frame_compare.orchestration.execute_run(...)`
- Diagnostic entry surface: `frame_compare.orchestration.doctor.run_doctor(...)`

The CLI keeps VS-heavy imports lazy through proxy functions so help text and simple commands do not import the full runtime stack at module import time.

## Runtime Flow

The main run path is:

1. Resolve root and config.
2. Prepare preflight and workspace paths.
3. Discover input clips.
4. Validate shared analysis cache mode flags when needed.
5. Create a fresh run folder when configured.
6. Load or compute clip probe data.
7. Execute orchestration phases in order:
   `frame_plan -> analyze -> align -> render -> metadata -> dovi -> publish -> report -> post_report_cleanup`
   The `analyze` phase is automatically skipped when the effective `[analysis]`
   frame selectors request only `user_frames` and/or `random_frame_count`.
   Dark, bright, or motion frame counts require analysis.

When effective config enables both `slowpics.auto_upload` and
`slowpics.confirm_upload_after_report`, the opted-in interactive path changes
only the post-render ordering:
`frame_plan -> analyze -> align -> render -> metadata -> dovi -> report -> confirm_slowpics_upload -> publish -> post_report_cleanup`.
The non-confirmed flow keeps the normal ordering above.

`frame_compare.orchestration.context.RunContext` carries the shared run state across phases.
Phase task functions return explicit phase-output DTOs, and `execution.py` applies those
outputs back to `ExecutionState`, `RunContext`, or collected artifacts at phase boundaries.

## Module Boundaries

Import boundaries are enforced by `importlinter.ini`.

High-level layering:

- `frame_compare.cli.entry`
- `frame_compare.cli.output`
- `frame_compare.runner`
- `frame_compare.orchestration`
- sibling domain modules: `frame_compare.analysis`, `frame_compare.render`, `frame_compare.services`
- `frame_compare.vspreview`
- `frame_compare.vs`
- `frame_compare.config`
- `frame_compare.utils`
- `frame_compare.errors`

Working rule: keep new code inside the existing owner module unless there is a strong reason to create a new top-level boundary and update `importlinter.ini` in the same pass.

Package-root export policy:

| Package root | Current policy |
| --- | --- |
| `frame_compare` | Root metadata only; exports only `__version__`. |
| `frame_compare.analysis` | Namespace-only root with empty `__all__`; import concrete owner modules directly. |
| `frame_compare.config` | Namespace-only root with empty `__all__`; import concrete owner modules directly. |
| `frame_compare.render` | Namespace-only root with empty `__all__`; import concrete owner modules directly. |
| `frame_compare.services` | Namespace-only root with empty `__all__`; import concrete owner modules directly. |
| `frame_compare.utils` | Namespace-only root with empty `__all__`; import concrete owner modules directly. |
| `frame_compare.vspreview` | Namespace-only root with empty `__all__`; import concrete VSPreview owner modules directly. |
| `frame_compare.cli`, `frame_compare.services.report`, `frame_compare.render.batch`, `frame_compare.render.backend`, `frame_compare.orchestration.probing` | Nested namespace-only roots with empty `__all__`; import concrete owner modules directly. |
| `frame_compare.orchestration` | Curated lazy facade for existing run and doctor entry DTOs/functions. |
| `frame_compare.vs` | Curated lazy facade for selected VapourSynth integration symbols; preserve light imports when VapourSynth is absent. |
| `frame_compare.runner` | Convenience runtime entry surface, not a broad public package facade. |

Production code should import concrete owner modules unless a curated lazy facade is
the explicit owner of the import-time contract. Owner-specific exceptions belong in
`frame_compare.<owner>.errors`; shared base exceptions remain in
`frame_compare.errors`. Dependency-light protocols that must avoid UI or runtime
imports belong in focused protocol modules such as
`frame_compare.utils.progress_protocol`.

`docs/api.md` is generated reference material for importable conveniences. It does
not promote package roots or module exports into supported stable APIs beyond the
compatibility policy in the runbook.

## Persistence And Filesystem Owners

The repo uses filesystem persistence, not a database.

Primary owned paths:

- `config/config.toml` and `config/presets/*.toml`: config owners
- `<resolved paths.generated_dir>/cache/analysis/<label>__<fingerprint>.compframes`:
  shared analysis metrics cache (defaults to `generated/cache/analysis/` under the
  workspace root, but follows the configured `paths.generated_dir`). The
  fingerprint includes the selected reference identity and an all-source
  selection-domain token covering source identity, source trims, effective FPS
  values, configured analysis ignore windows, and the final shared selectable
  window. Metric-array cache identity excludes frame-selection counts,
  `user_frames`, random seed, and dark/bright quantile thresholds because those
  affect frame choice rather than metric computation.
- `generated/clip_probe.toml` or `<resolved paths.generated_dir>/clip_probe.toml`:
  shared clip probe cache used by `--from-cache-only` prevalidation before
  run-folder reservation
- `<run-folder>/generated/clip_probe.toml`: current-run clip probe cache when
  run folders are enabled
- `generated/audio_offsets.toml` or `<run-folder>/generated/audio_offsets.toml`:
  run-scoped alignment cache
- generated VSPreview session and override files under the current generated/run area
- screenshot output directories and generated HTML reports
- Windows portable bundle outputs under `dist/frame-compare-portable-win-x64`

`WorkspacePaths` resolves the runtime path set and can switch into run-folder mode so
screenshots and generated files live inside an input-specific run directory. The
analysis cache is the exception: `WorkspacePaths.cache_dir` remains the shared
workspace-level `<resolved paths.generated_dir>/cache/analysis` path even after
`with_run_dir()` moves `generated_dir` and `screenshots_dir` into a fresh run folder.

When `paths.use_run_folders = true`, normal runs and cache-only runs that proceed
reserve a fresh run folder. Existing run folders are not reused for analysis cache
hits. Screenshots, slow.pics upload inputs, alignment offsets, manual overrides,
and VSPreview artifacts remain scoped to the current run folder. Probe snapshots
are written to both the current run folder and the shared generated probe cache
so future `--from-cache-only` runs can validate the exact all-source analysis
selection domain before metadata prefetch or run-folder reservation. Configured
`report.output_dir` continues to own report placement; only fallback report
placement follows the screenshot/current run output location.

## External Boundaries

External runtime boundaries:

- FFmpeg / ffprobe subprocess calls
- VapourSynth runtime and plugins
- TMDB HTTP API
- slow.pics HTTP API
- outbound slow.pics post-upload webhooks
- default browser auto-open for generated reports
- default browser open for slow.pics URLs in interactive CLI runs
- clipboard integration for slow.pics URLs in interactive CLI runs
- Docker build/test runtime
- Windows PowerShell installer and updater scripts

Keep these integrations at their current owners:

- metadata lookups: `frame_compare.services.metadata` remains the facade owner;
  `frame_compare.services.tmdb_resolution` owns resolver policy and
  `frame_compare.services.tmdb_lookup` owns low-level TMDB HTTP and response mapping
- publishing: `frame_compare.services.publishers`
- slow.pics post-upload shortcut/webhook policy and action aggregation:
  `frame_compare.services.slowpics_post_upload`
- browser auto-open for generated reports, slow.pics browser opening, clipboard
  copy, report-confirmed upload prompting, and report/slow.pics browser
  precedence rules:
  `frame_compare.cli.entry`
- slow.pics URL shortcut creation: `frame_compare.services.slowpics_shortcut`
- isolated slow.pics post-upload webhook delivery:
  `frame_compare.services.slowpics_webhook`
- HTML report generation: `frame_compare.services.report`
- VS loading and HDR/tonemap logic: `frame_compare.vs.*`
- packaging/install/update flow: `tools/windows_portable/**`

slow.pics publishing is service-owned. `frame_compare.services.publishers` owns
the browser-compatible slow.pics client flow: `GET /comparison`,
`POST /upload/comparison`, and planned `POST /upload/image/{imageUuid}` image
requests. `frame_compare.services.slowpics_upload_plan` owns the explicit
upload-plan seam for current render artifacts, row/image names, and upload
ordering; the final upload path uses that plan and does not scan the screenshot
directory for membership. After a successful upload, orchestration carries the
exact uploaded planned local file paths into `post_report_cleanup` and carries
typed post-upload action results plus warnings returned by
`frame_compare.services.slowpics_post_upload` into the final `RunResult`.
Orchestration does not own clipboard, browser, shortcut, or webhook side-effect
policy. That cleanup phase owns report-safe local deletion policy for
`slowpics.delete_after_upload` and never reconstructs deletion membership from
directories, labels, render artifacts, or shortcut outputs after upload. The
`.url` shortcut is not cleanup membership.

Report-confirmed slow.pics upload uses a CLI-owned confirmation callback seam
carried on `RunDependencies.confirm_slowpics_upload`. Orchestration owns the
typed request, decision, confirmation-status state, phase ordering, and upload
skip decisions; it does not import Typer, open browsers, read stdin, or print
prompt text. If a report-confirmed runtime path reaches orchestration without
the callback, orchestration raises a typed config error before publish rather
than silently uploading. When report generation warns, fails, or produces no
report path, `confirm_slowpics_upload` records `report_unavailable`, emits the
skip warning, and prevents slow.pics upload. When the user declines through the
CLI callback, `publish` is skipped and `slowpics_url` stays `None`.

In the report-confirmed workflow, the local report is generated before upload
and is not regenerated after upload. The report payload therefore has no
slow.pics URL even if the later upload succeeds; the CLI summary is the owner
for presenting the uploaded URL. CLI report presentation happens before the
confirmation prompt and before any later post-upload slow.pics browser opening.
The existing non-confirmed rule remains: an attempted slow.pics browser open
suppresses generated-report auto-open for that run.

`frame_compare.services.slowpics_shortcut` owns deterministic `.url` output for
successful slow.pics uploads. It selects the current run folder when present, or
the safe common parent of the resolved screenshots/generated directories when
run folders are disabled. The service rejects unsafe parent choices outside the
workspace root, filesystem anchors, drive/share roots, and the user home
directory; filename selection is deterministic and repeated writes overwrite the
same path.

`frame_compare.services.slowpics_webhook` owns isolated outbound webhook
delivery for successful slow.pics uploads. It validates strict external HTTPS
targets, rejects disallowed IP literals and DNS answers, connects to a
prevalidated pinned address while preserving TLS verification for the original
hostname, sends the JSON `content` payload without redirects, and does not reuse
slow.pics client cookies, headers, proxy/environment trust, or transport state.
Webhook failures are warning-only and redact configured URL details.

`frame_compare.cli.entry` and its run-command helper own interactive-only
slow.pics URL copy/browser actions and the precedence rule between slow.pics
browser opening and generated-report auto-open. Those actions run only for
human, non-quiet, TTY stdout runs; JSON stdout stays a single object.
The same CLI owner presents the local report and asks for confirmation in the
report-confirmed workflow before post-upload URL actions are considered.

`frame_compare.services.report` owns the static offline report payload and viewer
assets. The generated viewer exposes slider, internal overlay mode presented to
users as Single where appropriate, diff, and pair-based blink modes; frame/category
navigation; a HUD toggle for stage labels and current-frame metadata; a primary
toolbar plus floating viewport palette; a collapsible, compact/normal/large
filmstrip bottom panel; an inspector drawer with Frame, Clips, Align, and Export
tabs; fullscreen support; viewport pan, zoom, actual/width/height fit, reveal, and
adjacent-frame preloading. Blink mode supports 0.3s/0.7s/1.2s speeds, pause/resume, keyboard
speed controls, and reduced-motion handling that enters Blink paused. Browser-local
viewer state is scoped by report identity and persists current frame, view mode,
clip selection, viewport/zoom/reveal, pair alignments, HUD visibility, filmstrip
collapsed/size, inspector open/tab, and blink speed. Blink paused state is not
persisted. It does not own slow.pics upload policy, prompting, or browser side
effects.

Screenshot rendering owns its geometry and writer policy inside `frame_compare.render`:
`frame_compare.render.geometry` plans optional aligned crop/scale/pad geometry, render
batch expansion attaches those plans to render requests, the FFmpeg backend applies
geometry filters after exact frame selection, and the VapourSynth path chooses between
the Pillow writer and eligible `core.fpng.Write` output without changing CLI import-time
behavior.

Runtime ownership matrix:

| Runtime concern | Owner |
| --- | --- |
| Source selector resolution, explicit reference ordering, duplicate-stem fail-fast, and per-source override application during preparation | `frame_compare.orchestration.source_selection` plus `frame_compare.orchestration.preparation` |
| Audio alignment workflow, offset cache coordination, and precedence policy | `frame_compare.services.alignment` |
| Audio stream probing, deterministic stream selection, stream overrides, and FFmpeg/channel-aware extraction policy | `frame_compare.services.alignment_audio` |
| Audio correlation, preprocessing, and refinement estimation | `frame_compare.services.alignment_correlation` |
| Audio alignment window collection, weak-window rejection, consensus selection, and ambiguity gating | `frame_compare.services.alignment_consensus` |
| Alignment-specific VSPreview verification display and override policy | `frame_compare.services.alignment_vspreview` |
| VSPreview availability and launch adapter | `frame_compare.vspreview.adapter` |
| VapourSynth import, Windows DLL registration, plugin detection/loading helpers | `frame_compare.vs.env` |
| Doctor check ordering, categories, and diagnostic result mapping | `frame_compare.orchestration.doctor` |

## Public Boundaries

The repo exposes two kinds of externally visible surfaces today:

- user-facing CLI/config/release-asset behavior
- importable package modules and re-export namespaces used by tests and internal callers

Compatibility policy for those surfaces is defined in the runbook rather than in this document.

## Current Hotspots

These files currently carry disproportionate change risk:

- `src/frame_compare/orchestration/coordinator.py` (and neighboring `types.py`, `preparation.py`, `execution.py`)
- `src/frame_compare/errors.py`
- `src/frame_compare/services/report/**`
- `src/frame_compare/cli/entry.py`
- `src/frame_compare/services/alignment.py` and its focused audio-alignment owners
  (`alignment_audio.py`, `alignment_correlation.py`, `alignment_consensus.py`,
  `alignment_vspreview.py`)
- `src/frame_compare/render/batch/orchestrator.py`
- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/vspreview/adapter.py`

Working rule: changes to these files should usually trigger full verification and, when they reshape behavior or ownership, a same-pass update to this document.

## Working Rules That Follow From The Codebase

- Keep CLI import time light; do not eagerly import VS-dependent runtime code in `cli/entry.py`.
- Keep config/env loading centralized; do not add ad hoc env reads deep in domain logic.
- The main pipeline passes HTTP clients from `runner` into orchestration, while diagnostics still create their own short-lived client for reachability checks.
- Keep persistence deterministic: stable ordering, stable JSON/TOML output, atomic writes where owners already use them.
- Respect the layered import contracts and sibling-domain independence.
- Treat Docker and Windows portable flows as first-class runtime surfaces, not optional afterthoughts.

## Unknowns And Maintainer Decisions Still Open

- Whether any import-level package APIs should be promoted from convenience-only to supported/stable.
- Whether a durable multi-session plan workflow should become active again in this repo. The runbook currently keeps `docs/plans/` inactive by default.
