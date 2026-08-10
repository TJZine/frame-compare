# Current Architecture

This document describes the present-day Frame Compare codebase. It is intentionally about what exists now, not desired future structure.

## Contents

- [Operating Stance](#operating-stance)
- [Composition Roots](#composition-roots)
- [Runtime Flow](#runtime-flow)
- [Module Boundaries](#module-boundaries)
- [Persistence And Filesystem Owners](#persistence-and-filesystem-owners)
- [External Boundaries](#external-boundaries)
- [Public Boundaries](#public-boundaries)
- [Current Hotspots](#current-hotspots)
- [Working Rules That Follow From The Codebase](#working-rules-that-follow-from-the-codebase)
- [Unknowns And Maintainer Decisions Still Open](#unknowns-and-maintainer-decisions-still-open)

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
2. Prepare preflight and workspace paths, containing config and writable state
   beneath the resolved workspace root while permitting external media reads.
3. Discover input clips.
4. Validate shared analysis cache mode flags when needed.
5. Create a fresh run folder for every run that proceeds to output reservation.
6. Load or compute clip probe data.
7. Execute orchestration phases in order:
   `frame_plan -> analyze -> align -> render -> metadata -> publish -> report -> post_report_cleanup`
   The `analyze` phase is automatically skipped when the effective `[analysis]`
   frame selectors request only `user_frames` and/or `random_frame_count`.
   Dark, bright, or motion frame counts require analysis.

When effective config enables both `slowpics.auto_upload` and
`slowpics.confirm_upload_after_report`, the opted-in interactive path changes
only the post-render ordering:
`frame_plan -> analyze -> align -> render -> metadata -> report -> confirm_slowpics_upload -> publish -> post_report_cleanup`.
The non-confirmed flow keeps the normal ordering above.

`frame_compare.orchestration.context.RunContext` carries the shared run state across phases.
Phase task functions return explicit phase-output DTOs. `execution.py` owns phase
plan construction and timed phase execution, while
`frame_compare.orchestration.phase_output_application` applies phase outputs
back to `ExecutionState`, `RunContext`, or collected artifacts at phase
boundaries. `frame_compare.orchestration.types` owns the public run request,
dependency, result, and callback DTO contract; internal phase outputs and
mutable preparation/execution carriers live in
`frame_compare.orchestration.execution_types`.
`RunDependencies` supplies aware UTC wall time for persisted start/completion
timestamps and a separate monotonic timer for preflight, source loading, phases,
and total success/failure durations. Persisted `duration_seconds` comes from that
monotonic total rather than wall-clock subtraction.
Current phase-family owners are intentionally explicit:

- `frame_compare.orchestration.phase_selection`: frame-plan and analyze phase bodies plus shared selection/frame-translation helpers
- `frame_compare.orchestration.full_window_retry`: the run-scoped effective-config,
  confirmation-result, authoritative window/domain recomputation, and fatal
  retry-once boundary for exclusion-constrained selection failures; the CLI owns
  the injected stderr confirmation callback
- `frame_compare.orchestration.phase_alignment`: audio-alignment phase execution,
  alignment request mapping, trim application, and aligned-frame normalization
- `frame_compare.orchestration.phase_render`: screenshot-render phase execution and
  overlay diagnostic metadata mapping
- `frame_compare.orchestration.phase_post_render`: metadata, publish, report, confirmation, and cleanup phase bodies

Analysis metric algorithm identity is analysis-owned. `frame_compare.analysis.metric_identity`
builds the stable cache identity for `analysis.performance_mode`; cache I/O stores that
identity in schema v8 payload metadata, and orchestration only passes the effective
analysis config, active-rect-aware selection-domain token, analysis-owned metric
active rectangle, active-rect provenance, and exact source-frame metric range into
the analysis/cache owner.
`frame_compare.analysis.metric_strategies` owns the metric implementations:
`quality` is the default full-resolution VapourSynth PlaneStats behavior, while
`performance` is an approximate temporal-sampling strategy over the same
full-resolution luma PlaneStats metrics. Quality analyzes every eligible frame.
Performance returns metrics for exactly `ceil(window_frame_count * 0.25)` sampled
frames, distributed across up to eight deterministic centered contiguous bursts. It
may evaluate one additional unreturned source-frame lookbehind per nonzero burst so
the burst's first motion value preserves adjacent-frame semantics. Returned metric
frames in both modes stay inside the prepared selectable source-frame window and
apply the prepared active picture rectangle for the analysis source before metric
calculation. Preparation resolves that rectangle through
`frame_compare.orchestration.active_rect` for static evidence, using explicit
source overrides, trusted static metadata, configured dimension/aspect-ratio
detection, or a full-frame fallback. When
`screenshots.active_rect_detection = "auto"`, preparation then runs optional
post-selection-window content refinement through
`frame_compare.orchestration.active_rect_content` before analysis-source
resolution and analysis-cache validation. Quality returns a contiguous metric
series. Performance returns a sampled metric series with an explicit source-frame
map; metric-based dark, bright, and motion selection is limited to those samples.
Configured user and random frames remain eligible across the whole selectable
window and are not restricted to sampled metric frames.

`frame_compare.orchestration.source_labels` resolves presentation labels after
selector/override resolution and before probing or run-folder reservation.
`selection_domain` receives the resolved per-path map when constructing
`ClipState`; it does not own parsing or collision policy. Labels propagate
through presentation surfaces while source paths, fingerprints,
cache/alignment identity, and stem-based physical PNG filename ownership remain
unchanged. `frame_compare.render.naming` bounds overlong absolute screenshot paths
for legacy Windows browser compatibility by retaining a readable stem prefix and a
deterministic digest suffix.

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

Source freshness for the analysis, probe, and alignment reuse caches follows one
performance-first policy: source identity uses path, byte size, and modification
time (nanosecond precision where available), and does not hash media contents.
Reading multi-gigabyte sources solely for cache lookup would defeat the cache's
purpose. A replacement that preserves all three identity fields is intentionally
treated as the same source and can reuse cached data; workflows that replace media
while preserving size and mtime must advance the mtime or remove the relevant cache.

Automatic decoder/tool cache invalidation and decoder-ABI index isolation are
guaranteed for the managed Windows portable and Debian/Docker profiles, whose
identities include their selected packaged runtime lineages. Unmanaged Windows,
Linux, and native macOS fingerprints intentionally encode only the selected Frame
Compare contract and operating-system class; replacing native decoder or FFmpeg
binaries outside those packaged profiles requires clearing generated caches and
Frame Compare-owned indexes before reuse. See
[Supported Media Runtime](supported-media-runtime.md) for the profile boundary and
recovery requirement.

- `config/config.toml` and `config/presets/*.toml`: config owners
- `frame_compare.config.persistence`: secret-safe serialization shared by generated
  config and preset writes; runtime `slowpics.webhook_url` and `tmdb.api_key` values
  are excluded from every generated TOML payload
- `<resolved paths.generated_dir>/cache/analysis/<label>__<fingerprint>.compframes`:
  shared analysis metrics cache (defaults to `generated/cache/analysis/` under the
  workspace root, but follows the sole configured `paths.generated_dir`). The full
  fingerprint includes the selected reference identity plus an all-source
  selection-domain token. The token stores `analysis_source_path`,
  `reference_path`, source identities, source trims, effective FPS values,
  configured analysis ignore windows, active-rect resolver policy, each clip's
  resolved active rectangle, and the final shared selectable window.
  Cache schema v8 stores `analysis_source_path`, `performance_mode`,
  `algorithm_id`, `metric_backend`, stable `algorithm_identity_json`, and
  the scoped media-runtime analysis fingerprint through that algorithm identity. A
  For the managed Windows portable and Debian/Docker profiles, a selected decoder
  lineage change cannot satisfy the previous metric cache, while tone-mapping-only
  and standalone FFmpeg changes do not invalidate metric arrays. It also stores
  `metric_active_rect`, active-rect source, detection mode, and active-rect
  resolver algorithm ID in `MetricsMetadata`. It also stores the original source
  frame count and exact inclusive/exclusive selectable metric range. Performance
  cache payloads add an explicit `sampled_source_frames` map corresponding
  one-to-one with compact metric arrays; quality uses its implicit contiguous
  range. Metric-array cache identity includes the selected analysis performance
  mode, algorithm identity, active-rect resolver policy,
  every prepared clip's resolved active rectangle, and a typed metric request
  containing the analysis source, effective-FPS semantics, concrete metric active
  rectangle, active-rect provenance, and exact metric range. Request-aware cache
  loading validates the same typed identity before reporting or accepting a hit,
  with a full-frame
  rectangle representing no crop.
  Content-derived active rectangles from opt-in `auto` detection are final
  prepared rectangles and are included in the same token/provenance fields. It excludes
  frame-selection counts, `user_frames`, random seed, and dark/bright quantile
  thresholds because those affect frame choice rather than metric computation.
- `<resolved paths.generated_dir>/cache/alignment/alignment_reuse.toml`:
  shared previous alignment offset reuse cache owned by
  `frame_compare.services.alignment_reuse_cache`. It stores accepted computed or
  VSPreview-confirmed offsets keyed by a typed source-set identity, source
  fingerprints, source trims, effective FPS values, selected reference
  relationship, selected audio streams, alignment settings that affect
  computed offsets, and the scoped media-runtime alignment fingerprint. For the
  managed Windows portable and Debian/Docker profiles, a selected standalone FFmpeg
  lineage change therefore misses cleanly rather than reusing offsets computed by a
  different decoder/tool build. VSPreview-confirmed
  entries may also retain the computed
  audio alignment result that produced the preview suggestion so a later run can
  decline the human-confirmed offset without rerunning deterministic audio
  alignment. Unreadable, corrupt, unsupported-version, malformed source-table, or
  invalid-entry shared reuse data degrades to the normal alignment path with a
  warning log event. Ordinary no-match, incomplete, or stale source-set misses
  can silently return no reusable set and continue through the normal alignment
  path.
- `generated/clip_probe.toml` or `<resolved paths.generated_dir>/clip_probe.toml`:
  shared clip probe cache used by `--from-cache-only` prevalidation before
  run-folder reservation. The file format remains version 1, while each probe key
  uses key schema 2 and includes the scoped media-runtime probe fingerprint so a
  selected decoder-lineage change in the managed Windows portable or Debian/Docker
  profiles misses without invalidating unrelated file-format data.
- `<media>.frame-compare-lsw1296-<12-hex-index-fingerprint>.lwi`: Frame
  Compare-owned L-SMASH-Works index. The token is profile scoped (currently
  `lsw1296-e3c074652ffb` on managed/portable Windows,
  `lsw1296-6b9e50219ad0` on unmanaged Windows, and `lsw1296-4ea22a0b0598`
  on Debian/Docker). Managed Windows portable and Debian/Docker tokens isolate
  their packaged decoder ABIs; unmanaged profile tokens do not verify native ABI
  changes. Legacy adjacent `<media>.lwi` files are ignored,
  not deleted. A corrupt owned index is removed and rebuilt once; removal/rebuild
  failure is warned and an unusable index location falls back to a cache-free source
  open.
- `<run-folder>/run_info.toml`: root-level, write-only run identity metadata version 2 written
  immediately after every run-folder reservation. It stores creation time, final
  folder name, naming source, source filenames, Frame Compare version, the full
  supported media-runtime contract/fingerprints, and optional TMDB prefetch facts.
  It is user-facing creation-time identity, not an end-of-run outcome manifest.
- `<run-folder>/run_result.toml`: versioned V1 run outcome owned by
  `frame_compare.services.run_result_record` and written atomically only after a
  reserved run completes or fails. It stores sanitized run-folder-relative output
  facts, UTC lifecycle timing, bounded warning summaries, cache/phase facts,
  slow.pics outcome, and a sanitized typed failure when applicable. The service
  also owns strict TOML validation, immediate-child history discovery that admits
  only folders containing a supported result record, malformed-record isolation,
  deterministic ordering, exact run-name validation, record-file/run-directory
  containment, and report-path containment. Recordless folders and symlinked
  run-directory aliases are not history entries. An unavailable selected generated
  root raises a typed actionable history error; the service never creates a missing
  root, falls back, or mutates `run_info.toml`.
- `<run-folder>/generated/clip_probe.toml`: current-run clip probe cache
- `<run-folder>/generated/manual_overrides.toml`: persisted VSPreview-confirmed
  manual alignment overrides for the current run
- generated VSPreview session files under the current generated/run area
- screenshot output directories and generated HTML reports
- Windows portable bundle outputs under `dist/frame-compare-portable-win-x64`

`frame_compare.vs.runtime_contract` is the sole component-identity owner for the
coordinated media stack. It emits narrow analysis, probe, alignment, and index
fingerprints plus the full deployment fingerprint. Docker and Windows portable
declare the full fingerprint through deployment metadata; `doctor --json` compares
the declaration with the code-owned expectation without trusting the environment
value as authority. See [Supported Media Runtime](supported-media-runtime.md).

`frame_compare.orchestration.preflight` owns hybrid path enforcement. The selected
config file and configured `paths.config_dir` resolve under the workspace root after
environment expansion and symlink resolution; escaping paths raise `FC-3009` before
config or output side effects. The sole generated-data root is resolved once and may
be external, while its managed descendants are checked before runtime use.
Configured and CLI-overridden media inputs remain unrestricted read-only paths. The
only selected-config exception is the installed Windows portable shim's exact resolved
LocalAppData state `config.toml`; it does not extend to generated-data paths or a
symlinked config leaf that resolves elsewhere.

`WorkspacePaths` resolves the runtime path set and switches into a reserved run folder
so screenshots and generated files live inside a fresh directory beneath the resolved
`paths.generated_dir`, never beneath an external media input. The
analysis and shared alignment reuse caches are the exceptions:
`WorkspacePaths.cache_dir` and `WorkspacePaths.shared_analysis_cache_dir` remain
the shared workspace-level `<resolved paths.generated_dir>/cache/analysis` path,
and `WorkspacePaths.shared_alignment_cache_dir` remains the shared
workspace-level `<resolved paths.generated_dir>/cache/alignment` path, even after
`with_run_dir()` moves `generated_dir` and `screenshots_dir` into a fresh run
folder.

Normal runs and cache-only runs that proceed reserve a fresh run folder beneath the
resolved `paths.generated_dir`. Existing run folders are not reused for analysis cache
hits. Screenshots, slow.pics upload inputs, manual overrides, and VSPreview
artifacts remain scoped to the current run folder. Probe snapshots
are written to both the current run folder and the shared generated probe cache
so future `--from-cache-only` runs can validate the exact all-source analysis
selection domain before metadata prefetch or run-folder reservation. Report generation
receives the explicit canonical `<run-folder>/report.html` path from post-render
orchestration; no report-specific output directory or fallback placement exists.

Run-folder names are title-first and capped at 64 characters for Windows path
headroom. The base name comes from resolved TMDB title/year, common parsed
metadata, combined filename stems, or `unnamed_run`. Exact timestamps are not
part of folder names; collisions use compact numeric suffixes such as `_2` and
`_3`, then a short random suffix if bounded numeric claiming cannot reserve a
directory. Preparation validates the reserved immediate-child path and completes
the `WorkspacePaths` transition before writing metadata. The exact creation time
then lives in `<run-folder>/run_info.toml`, which is written before probing,
rendering, or other runtime-heavy work. If reservation validation, the workspace
transition, or the metadata write fails, the run fails immediately and cleanup
attempts to remove the empty reserved directory as best effort.

Preparation reports the reserved `WorkspacePaths` through an internal dependency
capture immediately after `run_info.toml` succeeds, without changing the
`execute_prep(request, deps)` call shape. The coordinator owns whole-run outcome
timing and asks the run-result service to write success only after post-run phases
settle, or to make one best-effort failure write while re-raising the original
exception unchanged. Completed-run record failures add a stable warning and do
not change successful media work into failure.

The align phase uses a typed orchestration-to-services request seam:
`frame_compare.orchestration.phase_alignment.run_align_phase()` builds a
`frame_compare.utils.types.AlignmentRequest` for
`frame_compare.services.alignment`. The request carries current-run generated
state, the workspace-level shared alignment cache path, reference/comparison
labels, source identity facts, trims, effective FPS values, selected reference
relationship, selected audio streams, cache-identity settings, and preserved
frame props. These cache-identity DTOs use layer-neutral primitives or
dependency-light shared utility types; `services` must not import
orchestration-owned or analysis-owned identity types such as `ClipState`,
`ClipIdentity`, or `ClipFingerprint`.

`frame_compare.services.alignment` owns alignment entrypoint sequencing and
precedence, while `frame_compare.services.alignment_previous_offsets` owns
previous-offset reuse policy. Exact-match computed audio alignment cache hits are
treated as deterministic and can be reused independently of the human
confirmed-offset policy; `previous_offsets` governs only VSPreview-confirmed
offset reuse.
`frame_compare.services.alignment_keys` owns the stable reference/comparison
alignment key shared by alignment sequencing and previous-offset policy.
`frame_compare.services.alignment_reuse_prompt` owns the Rich stderr
prompt/table helper, including TTY fallback behavior and no-color rendering.
`frame_compare.services.types.AlignmentProvenance` carries service-owned
write-source provenance such as `computed_this_run`,
`vspreview_confirmed_this_run`, `shared_computed_offsets`,
`shared_previous_offsets`, and
`preexisting_manual_override`; shared-cache writes consume only current-run
computed or VSPreview-confirmed provenance rather than inferring eligibility from
the final flattened `AlignmentResult.source`.

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

Current Docker capability contract:

| Environment | Current posture |
| --- | --- |
| macOS Docker Desktop | Supported for backend rendering, reports, and software tonemap through the default headless software-Vulkan path only; Docker-based VSPreview GUI launch is unsupported beyond those backend features, and macOS Docker is not a native GPU or native Qt desktop surface |
| Linux Docker, CPU/software Vulkan | Canonical Docker default; deterministic, headless, CI-safe software Vulkan path |
| Linux Docker with NVIDIA GPU | Optional `gpu-nvidia` compose override/profile plus `tools/verify_docker_gpu.sh`; documented-only/unverified until separately proved on a compatible Linux NVIDIA host |
| Linux Docker with X11 GUI | Optional `gui-linux` compose override/profile plus `tools/verify_docker_gui.sh`; documented-only/unverified until separately proved on a compatible Linux X11 desktop host |
| Native Windows portable | First-class native runtime with backend rendering, reports, and VSPreview GUI support outside Docker |

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
- host-side Docker report/URL opening helper for the default compose mount
  layout and `https://slow.pics/...` URLs:
  `tools/open_docker_host_target.py`
- slow.pics URL shortcut creation: `frame_compare.services.slowpics_shortcut`
- isolated slow.pics post-upload webhook delivery:
  `frame_compare.services.slowpics_webhook`
- HTML report generation: `frame_compare.services.report`
- VS loading, runtime-versioned Frame Compare-owned L-SMASH-Works index recovery,
  and HDR/tonemap logic: `frame_compare.vs.*`
- packaging/install/update flow: `tools/windows_portable/**`

The default Docker behavior is intentionally narrower than the native Windows
portable runtime: it preserves deterministic headless software Vulkan for backend
rendering and report generation. Optional Docker GPU or GUI profiles are
host-dependent runtime variants and must be documented and verified separately from
the default Docker gate. When those variants are discussed, use the official Docker
GPU/container, Docker Desktop GPU support, Compose profiles, and Compose `gpus`
documentation as the external contract reference.

Current Docker owner seams for optional profiles remain explicit:

- `docker-compose.yml`: default headless software-Vulkan services, including a
  configuration-writable `frame-compare-wizard` setup service and a
  configuration-read-only `frame-compare-run` service with the single persistent
  generated-data mount
- `docker-compose.gpu-nvidia.yml`: opt-in NVIDIA GPU override/profile only
- `docker-compose.gui-linux.yml`: opt-in Linux X11/VSPreview override/profile only
- `tools/verify_docker_integration.sh`: canonical default Docker gate
- `tools/verify_docker_gpu.sh`: optional NVIDIA visibility/Vulkan/placebo proof
- `tools/verify_docker_gui.sh`: optional Linux X11/VSPreview dependency and session-script proof
- `tools/open_docker_host_target.py`: host-side helper for default compose output mounts and explicit `https://slow.pics/...` URLs only

The GUI profile stays container-boundary aware rather than changing CLI/runtime
owners. Its explicit X11 contract is:

- host `DISPLAY`
- host `/tmp/.X11-unix` mounted into the container
- optional host `XAUTHORITY` cookie file mount when required by the desktop
- container process UID/GID aligned to the host user for narrow local-user X11 permission flows

The optional GUI proof is non-CI and non-default. It must prove VSPreview
availability through the existing doctor/adapter owners and prove session-script
generation without requiring a real desktop launch. Any real UI launch remains a
manual Linux desktop action outside the default Docker verification gate.

The host open helper is also container-boundary aware rather than a CLI contract
change. It does not alter in-container report auto-open or slow.pics browser
behavior. Instead, it runs on the host, translates only the default compose
mount `/workspace/generated` -> `./generated`, rejects `/workspace/config`,
`/workspace/comparison_videos`, and the removed `/workspace/screenshots` output
root, and allows remote opening only for explicit `https://slow.pics/...` URLs.

slow.pics publishing is service-owned. `frame_compare.services.publishers` owns
the browser-compatible slow.pics client flow: `GET /comparison`,
`POST /upload/comparison`, and planned `POST /upload/image/{imageUuid}` image
requests. Image requests use a bounded concurrency of three, retain per-image
retry/idempotency handling, and advance a nested image-count progress task after
each completed upload. `frame_compare.services.slowpics_upload_plan` owns the
explicit upload-plan seam for current render artifacts, row/image names, and
upload ordering; the final upload path uses that plan and does not scan the
screenshot directory for membership. After a successful upload, orchestration
carries the exact uploaded planned local file paths into `post_report_cleanup`
and carries typed post-upload action results plus warnings returned by
`frame_compare.services.slowpics_post_upload` into the final `RunResult`.
Orchestration does not own clipboard, browser, shortcut, or webhook side-effect
policy. That cleanup phase owns report-safe local deletion policy for
`slowpics.delete_after_upload` and never reconstructs deletion membership from
directories, labels, render artifacts, or shortcut outputs after upload. The
`.url` shortcut is not cleanup membership.

`frame_compare.orchestration.slowpics_metadata` owns pure template context,
literal/template/automatic title precedence, suffix application, and explicit
versus resolved TMDB association. It produces one service-owned immutable
`SlowpicsCollectionMetadata` value. The publish phase passes that value to the
publisher and its exact title to post-upload actions. The publisher alone maps
the DTO and config into browser-compatible field names, canonical
`MOVIE_<id>`/`TV_<id>` association, `PUBLIC`/`LINK_ONLY` visibility, collection
and row hentai values, remote retention, and size-aware image write timeouts.

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
successful slow.pics uploads. It selects the current reserved run folder and rejects
missing or escaped run aliases before writing. Filename selection is deterministic
and repeated writes overwrite the same path. Filename selection consumes the single
final resolved upload title;
it does not independently fall back through metadata or screenshot directories.

`frame_compare.services.slowpics_webhook` owns isolated outbound webhook
delivery for successful slow.pics uploads. It validates strict external HTTPS
targets, rejects disallowed IP literals and DNS answers, connects to a
prevalidated pinned address while preserving TLS verification for the original
hostname, sends the JSON `content` payload without redirects, and does not reuse
slow.pics client cookies, headers, proxy/environment trust, or transport state.
It identifies the versioned client, applies an absolute per-attempt deadline and
bounded pre-send/5xx backoff, fails permanent certificate-verification errors,
honors only short valid `Retry-After` rate-limit delays, and does not retry after
request transmission when the delivery outcome is unknown so it does not knowingly
create duplicate notifications.
Webhook failures are warning-only and redact configured URL details. Typed safe
failure categories and optional HTTP status codes feed structured diagnostics without
retaining the configured endpoint.

`frame_compare.cli.entry` and `frame_compare.cli.run_command` own run-command
coordination, interactive-only slow.pics URL copy/browser actions, and the
precedence rule between slow.pics browser opening and generated-report auto-open.
Those actions run only for human, non-quiet, TTY stdout runs; JSON stdout stays a
single object. The same CLI owner presents the local report and asks for
confirmation in the report-confirmed workflow before post-upload URL actions are
considered. `frame_compare.cli.run_contracts` owns validation policy for public
run-mode combinations before orchestration begins.

`frame_compare.cli.wizard_command` owns the interactive goal-oriented config editor,
while `frame_compare.cli.wizard_policy` owns its typed code-defined frame-selection
patches and pure summaries. The wizard reuses orchestration's lightweight filename
discovery and source-selection policy without importing media runtime code.
`frame_compare.config.loader` owns environment-independent raw TOML narrowing and
redacted schema validation for preserving an existing wizard-edited document; atomic
replacement remains owned by `frame_compare.utils.atomic_write`.

### Report Viewer

`frame_compare.services.report` owns the static offline report payload and viewer
assets. The generated viewer exposes slider, internal overlay mode presented to
users as Single where appropriate, diff, and pair-based blink modes; frame/category
navigation; a HUD toggle for stage labels and current-frame metadata; a primary
toolbar plus floating viewport palette; a collapsible, compact/normal/large
filmstrip bottom panel; an inspector drawer with Frame, Clips, Align, Review, and
Export tabs; fullscreen support; viewport pan, zoom, actual/width/height fit, reveal,
and adjacent-frame preloading.

The ordinary report artifact does not claim presentation blindness. Source identity
can be present in baked screenshot overlays, physical image filenames, and report
metadata, so viewer-only label hiding cannot provide an honest blind workflow. Any
future blind comparison must use an explicitly eligible clean artifact and a
separately approved invocation, delivery, reveal, and publishing contract.

#### Lens

`assets/lens.js` is the focused owner for the optional
floating image lens: normalized per-source mapping, fixed-window placement, dedicated
edge-grip dragging, pending touch tap-versus-viewport-gesture ownership,
160/240/320px sizing, 2x/3x/4x/6x/8x/12x magnification, Off/Ring/Brackets sample
marking, and an optional Single-mode active/comparison split. The sample follows
pointer movement across the displayed source while the lens window stays fixed;
only its grip can move the window. Diff uses separate aligned base and difference DOM
images with CSS difference blending, while the viewer exposes one palette/lens chrome
event boundary so bubbled pointer, wheel, and double-click input cannot mutate the
viewport. Activation seeds a transient center point and retains the stable palette
Lens group, which owns zoom, fixed status, and stage-clamped settings. The display-only
lens body has no titlebar or controls. It uses compact mode-aware ACTIVE, COMPARE, and
DIFF badges plus deterministic, stage-size-aware middle-ellipsized identity rails that
preserve source name beginnings and suffixes; Lens Settings exposes the full wrapping
current-source label. Report interaction highlights, including lens markers and its grip, share one
Projection Brass signal token family while semantic status and frame-category colors
remain separate. Grip pointer dragging uses capture, while its
arrow-key operation supports a larger Shift step, clamps to the stage, persists the
position, and prevents viewer shortcuts. Touch sampling remains a deliberate tap;
touch movement beyond its threshold returns ownership to viewport gestures.
Context sync remaps or reseeds the target when frames, modes, sources, or Grid entries
change; layout refresh preserves the normalized sample through pan, zoom, fit, and
alignment changes. Each Lens clone slot uses a detached, source-matched image loader;
supersede, completion, and clearing remove both loader handlers and discard the loader,
with request tokens retained as defense in depth. Stale load/error callbacks cannot
revive superseded content, same-source failures do not retry continuously, and
unavailable content remains visibly honest. It magnifies existing image elements
without canvas decoding or pixel-value claims.

#### Grid

`assets/grid_view.js` owns the viewer-only Grid
cell lifecycle: deterministic responsive 2/3/4 layouts, payload-order pages of at
most four images (one below the mobile reflow boundary), loading/missing/retry
presentation, and visible-range controls. It consumes the viewer's single viewport
state while exposing visible image entries to the lens rather than duplicating either. In
Grid mode the shared pan fields represent normalized image-box translation and each
cell derives its CSS-pixel transform from its own contained image dimensions; the
viewer converts those fields at the Grid/pair-mode boundary so mixed-aspect cells keep
one normalized viewport center without changing pair-mode persistence semantics.

#### Review State And Viewer Composition

`assets/review_state.js` owns the exact report-scoped local review schema, bounded
bookmark/tag/note/preferred-clip records, fail-closed localStorage reads, deterministic
V1 JSON export, strict import validation and preview, atomic merge/replace apply, and
the Review tab's dedicated edit/import/export interaction lifecycle. That controller is
created on first visible Review use, keeps form rendering stable across unrelated viewer
refreshes, and routes transition announcements through the existing shared polite live
region. Its storage is
separate from viewport preferences and never writes into the report or run directory.
`assets/viewer.js` caches the Review DOM and composes that focused controller with the
other owners and the existing mode,
pointer, viewport, alignment, and inspector state rather than owning duplicate
coordinate conversions
or grid mount policy. Grid remains outside the public report default-mode payload
enum and does not preload adjacent grid pages. Blink mode supports 0.3s/0.7s/1.2s speeds,
pause/resume, keyboard speed controls, and reduced-motion handling that enters Blink
paused.

#### Browser-Local State

Browser-local
viewer state is scoped by report identity and persists current frame, view mode,
clip selection, viewport/zoom/reveal, pair alignments, HUD visibility, filmstrip
collapsed/size, inspector open/tab, and blink speed. Lens preferences use a separate
best-effort browser-global v2 key for magnification, size, and sample-marker style,
whose default is Off. Report-scoped lens state stores enabled state, fixed normalized
window position, and Single comparison selection. Grip drag end and keyboard movement
persist that normalized position so size and responsive layout changes preserve its
relative placement. Pointer/sample position and Blink paused state are
transient. Storage failure leaves the lens usable for the current session and is
reported quietly inside its settings popover. It
does not own slow.pics upload policy, prompting, or browser side effects.

Active-picture resolution is owned by `frame_compare.orchestration.active_rect`
and optional `frame_compare.orchestration.active_rect_content` during
preparation. Static resolution produces explicit, metadata, dimension-derived,
aspect-ratio-derived, or full-frame rectangles from probe/config evidence.
Opt-in `auto` content refinement runs only after the shared `SelectionWindow`
exists, samples a bounded deterministic set of luma frames for unresolved
full-frame clips, and can produce `content-derived` provenance. Analysis consumes
the final prepared rectangle through analysis-owned `MetricActiveRect`; render
consumes it through render-local request fields. Screenshot rendering still owns
geometry and writer policy inside `frame_compare.render`: `frame_compare.render.geometry` plans
optional aligned crop/scale/pad geometry, mod-safe crop rectangles, fit-to-target
scale/canvas policy, padding, and overlay origins. Render batch expansion treats
prepared active rectangles as already resolved for normal orchestration requests,
while direct render batch calls without provenance can still use render-local
static geometry inference; render does not sample content. Native screenshot
render remains full-frame. The FFmpeg backend applies geometry filters after
exact frame selection, and the VapourSynth path chooses between the Pillow writer
and eligible `core.fpng.Write` output without changing CLI import-time behavior.

Runtime ownership matrix:

| Runtime concern | Owner |
| --- | --- |
| Source selector resolution, explicit reference ordering, duplicate-stem fail-fast, and per-source override application during preparation | `frame_compare.orchestration.source_selection` plus `frame_compare.orchestration.preparation` |
| Source display-label parsing, normalization, override precedence, and collision handling | `frame_compare.orchestration.source_labels` |
| slow.pics title/template/TMDB precedence and immutable collection metadata resolution | `frame_compare.orchestration.slowpics_metadata` |
| Analysis-source resolution and fastest-source benchmark policy | `frame_compare.orchestration.analysis_source` |
| Audio alignment workflow, offset cache write coordination, and precedence policy | `frame_compare.services.alignment` |
| Previous-offset reuse policy and shared-reuse eligibility | `frame_compare.services.alignment_previous_offsets` |
| Stable reference/comparison alignment key construction | `frame_compare.services.alignment_keys` |
| Shared previous alignment offset reuse cache persistence | `frame_compare.services.alignment_reuse_cache` |
| Previous-offset reuse prompt/table display | `frame_compare.services.alignment_reuse_prompt` |
| Audio stream probing, deterministic stream selection, stream overrides, and FFmpeg/channel-aware extraction policy | `frame_compare.services.alignment_audio` |
| Audio correlation, preprocessing, and refinement estimation | `frame_compare.services.alignment_correlation` |
| Audio alignment window collection, weak-window rejection, consensus selection, and ambiguity gating | `frame_compare.services.alignment_consensus` |
| Alignment-specific VSPreview verification display and override policy | `frame_compare.services.alignment_vspreview` |
| VSPreview availability, launch adapter, and managed-Windows media-runtime preload | `frame_compare.vspreview.adapter`, `frame_compare.vspreview.launcher` |
| VapourSynth import, Windows DLL registration, plugin detection/loading helpers | `frame_compare.vs.env` |
| Coordinated media component identity, scoped cache/index fingerprints, and deployment runtime comparison | `frame_compare.vs.runtime_contract` |
| Doctor execution and diagnostic result mapping | `frame_compare.orchestration.doctor` |
| Doctor check ordering, categories, and check implementations | `frame_compare.orchestration.doctor_checks` |
| Doctor diagnostic DTOs | `frame_compare.orchestration.doctor_types` |

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
- `src/frame_compare/orchestration/doctor.py` and its focused diagnostic owners
  (`doctor_checks.py`, `doctor_types.py`)
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
