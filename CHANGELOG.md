# Changelog

All notable user-facing changes to Frame Compare are documented in this file.

Frame Compare follows Conventional Commits. Versioned sections supply the release
notes used by the guarded publication workflow.

## Unreleased

### Fixed

- Support stable and release-candidate versions in Windows code updates, with exact
  target verification and journaled source replacement for both apply and rollback.
  Complete backup inventories prevent restoring truncated backups. Existing RC
  installations need one full bundle reinstall to obtain the new updater and shared
  version helper: code-only ZIPs do not replace the AppData `bin` updater. Use a
  fresh bundle folder and preserve user configuration, media, and generated data.
  Same-line stable/RC transitions and signed-range downgrades remain supported.

## [0.7.0]

### Changed

- Reuse prepared audio-evidence summaries in the native alignment panel during
  preview updates while keeping live frame drafts and markers current.
- Maintain Windows bundled-runtime verification in a dedicated Python source file
  while preserving the packaged native, VSView, provenance and cleanup checks.

### Fixed

- Preserve explicitly authored tone-map settings through config save/reload and
  partial preset application without reacquiring unrelated ambient settings.
- Report unreadable or nonregular config/preset files and malformed environment
  settings as sanitized typed errors.
- Reject screenshot names that address the same physical file before rendering,
  including filesystem case and Unicode aliases, without overwriting existing files.
- Stop admitting new video-alignment frame requests after cancellation.
- Fail cache-only runs before rendering when required analysis-cache acquisition
  becomes unavailable or invalid after prevalidation.
- Let report notes use the full 1000-Unicode-scalar limit, including supplementary
  characters, while preserving import/export bounds.
- Describe `--no-cache` as refreshing the current scoped entry in CLI help.
- Add a one-time approved migration for the existing repository signing key when
  its original private file is unavailable.

### Upgrade notes

- Run-local `manual_overrides.toml` uses version "2" without a separate `confirmed`
  field. Older versions are ignored as recoverable cache state and replaced on the
  next manual save without migration. The native VSView result sidecar remains v1.

## [0.6.1]

This release includes the changes since **0.5.0**. Version 0.6.0 was prepared but
not published; its changes are included here.

### Highlights

- **Safer alignment:** audio offsets are checked against video before automatic
  application, with clearer evidence for candidates that still need review.
- **VSView replaces VSPreview:** alignment confirmation now lives in the native
  VSView panel, with the source lineup and audio evidence together.
- **Easier report review:** a reorganized Inspector, source details, lens captions,
  and better recovery when images fail to load.
- **Clearer setup and troubleshooting:** refreshed documentation, terminal output,
  wizard guidance, and local-only runtime checks.

### Before upgrading

- **Windows portable users:** install the complete 0.6.1 bundle into a fresh,
  empty folder when upgrading from a VSPreview-era or pre-native-panel schema-2
  installation. Do not overlay the new bundle on an old one. Code-only updates
  refuse incompatible runtime fingerprints, requirements, or unknown installed
  versions.
- **Rename the viewer setting:** replace `audio_alignment.use_vspreview = true`
  with `audio_alignment.use_vsview = true`. The old key is no longer accepted.
  Native installations need the base `vsview` extra; its `recommended` and `full`
  extras are not required.
- **Remove retired alignment settings:** these `[audio_alignment]` keys now fail
  validation as unknown fields: `sample_rate`, `correlation_mode`,
  `preprocessing_mode`, `confidence_threshold`, `ambiguity_peak_ratio`,
  `window_length_seconds`, `window_stride_seconds`, `minimum_valid_windows`,
  `consensus_minimum_ratio`, `refinement_mode`, and `refinement_sample_rate`.
- **Expect alignment recomputation:** older shared-cache schema-v1 entries are
  ignored, and stale computed or shared entries are recomputed under the new
  alignment policy. Run-local `manual_overrides.toml` keeps its v1 format, path,
  and offset convention.
- **Windows source installers need PowerShell 7.** Installing a published portable
  bundle still supports PowerShell 5.1. Run `frame-compare doctor` after installing
  the new runtime.

### Audio alignment and VSView review

- Alignment now compares the whole audio track in chunks, compensates for container
  start times, and checks candidate offsets against decoded video. New automatic
  audio candidates affect trims or the computed cache only when the audio authority,
  exact-frame video, and competing-offset checks pass. A video-confirmed candidate can still need
  review; video confirmation alone does not authorize automatic application.
- Level, compression, downmix, stem, quiet, and locally weak-audio differences are
  considered as context rather than automatic vetoes. Unresolved runs, credible
  chunk disagreements, and video-confirmed alternative offsets remain reasons to
  withhold automatic application.
- Video checks favor motion-rich reference frames over evenly spaced frames.
  Planned positions at targets that were not examined are not counted as evidence.
- Without stream overrides, alignment chooses the reference's best-ranked stream
  in a shared language when its default language is absent from the comparison.
- Audio follows the effective timeline when `match_fps` or `effective_fps` retimes
  a source. This supports constant offsets for 24 fps releases of 23.976 content
  and PAL 25 fps releases; verbose output and panel details identify retimed sides.
- VSView 0.12.1 replaces the old viewer integration. Confirmation uses the native
  alignment panel while preserving source ordering, overlays, generated-session
  L-SMASH-Works loading, and the `reference − comparison` offset convention.
  VSView's BestSource workspace is UI-only; Frame Compare's analysis, rendering,
  indexing, and cache source loader remain unchanged.
- Terminal and panel review share the same bounded evidence regions and check
  points. Regions use reference-video time, retain the winning local video offset,
  and explain why a candidate was not applied. Manual and cached applied offsets
  are identified as applied too.
- Alignment stops if a prepared source changes, even when audio is unavailable,
  rather than allowing rendering to use stale metadata. Excessive metadata-derived
  audio chunk counts are rejected before allocating the plan. Interrupted VSView
  waits now clean up their child processes.

### Reports and screenshot review

- The Inspector now separates **Frame**, **Clips**, **Image offset**, and **Review**.
  A per-source frame table makes timing easier to inspect, and review import and
  export live in the Review tab.
- The lens can caption the magnified source, source labels show file sizes, and the
  report header displays the generation time in your local format. The fit-width
  control has been removed.
- Failed images in Slider, Single, Diff, and Blink show source-specific unavailable
  messages and Retry actions. Navigation and successful retries recover without
  stale image events or pending Diff loads overwriting the current frame.
  Blink preserves focused Retry controls and avoids repeated error announcements.
- An explicitly paused Blink view stays paused through viewport and lens gestures.
  Review imports apply the exact file and conflict choices shown in their preview.
- `screenshots.active_rect_detection` now defaults to `auto`.

### CLI, configuration, and documentation

- Run plans, source details, alignment results, and completion summaries have a
  refreshed terminal presentation. Warning source, severity, and details no longer
  depend on clip-label wording, and full labels are retained in messages.
- The wizard prints suggested `doctor`, `run --dry-run`, and `run` commands for the
  workspace and configuration it saved. `run --help` groups options by purpose;
  invalid `--overlay`, `--tm-preset`, and `--tm-curve` values list valid choices
  before any work starts.
- `doctor` checks local runtime readiness without probing slow.pics reachability;
  `doctor --json` no longer includes a slow.pics check. Its TMDB check validates
  configuration and credential format without making a network request.
  Guidance links are repaired. Documentation now has refreshed onboarding, focused
  guides, CLI/configuration references, and current report and Windows screenshots.
- Configure `[runtime].memory_limit_mb` (integer, minimum 512) to cap the VapourSynth
  frame cache for analysis, rendering, alignment video checks, and the separate
  VSView session. Unset keeps the native default. This does **not** cap total process
  memory or audio buffers. The documented
  `FRAME_COMPARE_RUNTIME__MEMORY_LIMIT_MB` integer override is now accepted.
- Malformed UTF-8 configuration/presets, invalid filesystem paths, and nonfinite
  lead/trail windows now produce typed validation errors. Oversized numeric values
  in persisted history and caches are recoverable; valid entries are retained and
  missing cache authority requires recomputation.
- `--no-cache` and `--from-cache-only` are rejected together before runtime work,
  including in dry runs. CLI help, version, and prompts use Typer without requiring
  Click. General JSON output behavior is preserved; viewer-specific identifiers
  change to `vsview`, `audio_alignment.use_vsview`, and
  `browser_clipboard_or_vsview`. Numeric error codes are unchanged.

### Cancellation, integrations, and update safety

- The first Ctrl+C stops new phase/audio work and promptly stops starting new
  render or analysis frames. In-flight native frames must finish first and have no
  guaranteed completion deadline. Interrupted runs stop publishing results, caches,
  and diagnostics, retain their failure record, and exit with code 130.
  FFmpeg batch extraction is stopped with bounded cleanup; PNGs already written
  may remain. Repeated Ctrl+C keeps its existing behavior.
- Phase, render-failure, and slow.pics webhook cancellation outcomes are more
  predictable, including repeated cancellation while a thread-backed request drains.
  Webhook DNS resolution is bounded and its resolver does not receive application
  secrets.
- Successful TMDB variant lookups are retained when another lookup fails.
  Diagnostics keep credentials and request details private; configuration errors
  redact `slowpics.webhook_url` and `tmdb.api_key`.
- VSView child imports and the libplacebo capability probe are isolated from
  caller-controlled Python paths. The probe still uses dependencies in the trusted
  runtime's user site.
- Windows updates require signed, canonical manifests and verify signatures before
  parsing. Updates are bound to an exact clean source/version, archive extraction
  is bounded, install state is read as UTF-8 under PowerShell 5.1, and rollback
  rejects backups with missing or incompatible runtime identity before changing files.

### Runtime versions

Install the complete portable bundle when moving to this runtime.

| Component | Version |
| --- | --- |
| Python | 3.13.16 |
| VapourSynth | R81 |
| VSView | 0.12.1 |
| vsjetengine | 1.8.0 |
| vspackrgb | 2.0.0 |
| BestSource | 22 |
| Windows FFmpeg | `n8.1.3-9-g29e619e767` |
| uv | 0.13.0 |

The locked dependency graph and coordinated uv toolchain are refreshed.

### For maintainers and diagnostic-tool authors

- Merging a matching stable release PR into `main` now starts the guarded Windows
  build and release workflow automatically. Production approval remains required.
  Named signing-secret forwarding fixes key availability across reusable workflows.
  Published notes come from the full validated versioned changelog section, replacing
  the old placeholder, and the workflow verifies the body through publication.
- Shared alignment reuse uses schema v2 with neutral interactive origins. The
  recomputation policy is `whole-track-chunked-phat-video-check-motion-20260929`.
  Diagnostics use schema v4 and VSView session metadata v5, including explicit
  chunk/run/context records under one shared 2 MiB per-comparison limit; native
  metadata omits per-chunk rows.
- Docker verification retains separate artifacts for successful and failed runs,
  and Docker CI runs when source-checkout helpers or build exclusions change.
  Analysis benchmark metric acquisition and alignment benchmark media links work
  when the labels file is supplied as a relative path.

## [0.5.0]

### Added

- Add a consent-gated, run-only full-window retry when configured lead/trail
  exclusions leave too little eligible media; authored configuration remains
  unchanged.
- Add report payload v1.2 with release-aware source identities, distinct
  comparison/source-frame domains, exact picture type and Dolby Vision RPU facts
  when observable, file-size context, rendering disclosures, and expanded
  Inspector, review, and viewport behavior.
- Add a durable shared TMDB response cache with privacy-safe request identities,
  separate expiry for successful and empty responses, bounded disk usage, atomic
  writes, and safe fallback to the normal network path when cache state is unusable.
- Add code-owned media-runtime identities and scoped fingerprints for analysis,
  probing, alignment, source indexing, cache invalidation, Docker, Windows portable,
  and code-only update compatibility.
- Bundle Inter Regular under the SIL Open Font License 1.1 for deterministic overlay
  typography.

### Changed

- Bump Frame Compare to 0.5.0, classify the project as beta, and refresh the managed
  stack to Python 3.13.15, uv 0.12.7, VapourSynth R79/API R4.2,
  L-SMASH-Works 1310, vs-placebo 2.0.4, Akarin 1.5.0, VSZip 22.1.0, and
  VSPreview 0.20.1. Windows portable uses the LGPL FFmpeg
  `n8.1.2-34-g9b6c8969e0` build. Docker uses Debian FFmpeg 7.1.5 and includes
  FFMS2 5.0; Windows portable intentionally excludes FFMS2.
- Unify screenshots, reports, run records, and reusable caches under one configured
  generated-data root, which may be a normal external directory. Every
  output-producing run receives a self-contained artifact folder, while shared
  caches remain outside individual run folders for reuse and history discovery.
- Batch compatible FFmpeg frame requests through one ordered decode pass and render
  independent source batches concurrently while preserving deterministic output
  order, exact per-frame facts, failure behavior, and progress reporting.
- Make random, dark, bright, and motion frame selection deterministic and temporally
  stratified, and derive the preferred automatic separation from the effective
  reference FPS as `ceil(FPS / 2)` for an approximately half-second target. Preserve
  exact user frames, global `User`/`Dark`/`Bright`/`Motion`/`Random` precedence,
  seed reproducibility, sparse source coordinates, and category counts while
  progressively relaxing automatic spacing down to one-frame uniqueness when needed.
  Propagate the reference-domain FPS through initial random selection, metric
  selection, post-alignment reselection, and alignment fallback, and skip unattainable
  gap thresholds so fallback cost does not scale with numeric FPS.
- Classify alignment stability and harden the existing `disabled`, `prompt`, and
  `always` previous-offset reuse policies with source/runtime identity, provenance,
  schema validation, interactive evidence, and clearer presentation.
- Use prepared release identities for collision-safe compact live progress labels,
  full slow.pics column labels, and constrained report controls while preserving
  explicit labels and exact filenames on the appropriate review surfaces.
- Improve CLI help, wizard, side-effect-free dry-run planning, chronological human
  progress output on stderr, JSON output contracts, warnings, and success summaries.
- Improve offline viewer keyboard navigation, focus management, radio-group and
  filmstrip behavior, source-role labels, and accessible names without changing the
  self-contained report model.
- Make `doctor` validate observable managed-runtime versions and required plugin
  surfaces for VapourSynth, L-SMASH-Works, vs-placebo, FFMS2, FFmpeg, and ffprobe
  rather than checking only component presence. L-SMASH-Works' native version is
  reported explicitly as unobservable while its required source functions are
  verified.
- Carry canonical exact-frame, signal, presentation, geometry, and tonemap facts
  through rendering, overlays, slow.pics upload planning, and reports.
- Strengthen Frame Compare-owned L-SMASH index naming, managed-runtime isolation,
  reuse, invalid-index recovery, and cache-free fallback behavior.
- Expand deterministic Docker and Windows portable runtime, packaging, installer,
  updater, rollback, provenance, license, and extracted-bundle verification.
- Strengthen the guarded immutable release workflow with exact version, tag, channel,
  and SHA validation; collision checks; draft and asset verification; remote digest
  checks; provenance attestations; and final publication-state verification.
- Reorganize the user documentation into route-based onboarding and focused guides
  for sources, analysis, alignment, HDR, reports, generated data, configuration, and
  troubleshooting, with current screenshots for the first run, VSPreview, report
  modes, HDR diagnostics, and Windows installation.

### Fixed

- Correct computed audio-alignment offsets to use the documented
  `reference - comparison` sign convention. Published v0.1.0 cache entries miss under
  the new runtime-aware source-set identity; caches created by intermediate v0.5.0
  pre-release builds should be cleared before final validation.
- Merge FFprobe HDR color metadata field-by-field only when VapourSynth frame
  properties are missing, malformed, or H.273-unspecified.
- Capture FFmpeg picture type from the same exact-frame extraction process used to
  produce the screenshot.
- Improve recoverable selection failures, source-frame range handling, and
  post-retry fatal error behavior.
- Reject incomplete or malformed analysis-cache metadata that omits its required
  schema version instead of accepting it as the current format.
- Harden VSPreview startup compatibility checks, reuse valid Frame Compare-owned
  indexes, recover without cache when index construction is unusable, and redact
  inherited credential values from surfaced startup diagnostics.
- Clarify VSPreview matching-frame confirmation and replace duplicate or malformed
  preview frame-property warnings with Frame Compare's styled assumption details.
- Improve HDR tone-mapping failure messages and runtime diagnostics so unsupported or
  mismatched managed components fail with actionable evidence.

### Security

- Require signed Windows code-only updates to match both dependency and
  media-runtime fingerprints before replacement, with file-hash verification,
  backups, and rollback.
- Verify pinned source commits with complete tracked-tree SHA-256 digests and
  preserve native-library, plugin-manifest, license, and corresponding-source
  provenance.
- Validate ZIP path safety, case collisions, required bundle contents, bounded
  process evidence, release asset checksums, remote digests, and publication state
  before release.

### Upgrade notes

- Windows v0.1.0 portable installations require the complete v0.5.0 bundle because
  the managed media-runtime fingerprint changed; the code-only updater refuses
  incompatible runtimes.
- Existing v0.1.0 configurations must remove `paths.screenshots_dir`,
  `paths.use_run_folders`, and `report.output_dir` or be regenerated. Generated
  artifacts now follow the sole configured `paths.generated_dir` layout, which may
  point to a normal external directory. The former top-level `[diagnostics]` section
  is no longer a supported config surface and is ignored.
- Analysis, probe, alignment, and source-index caches include updated runtime
  identities and may be invalidated or rebuilt.
- Clear any shared alignment reuse cache produced by an intermediate v0.5.0 build
  before validating the final candidate after the offset-sign correction.
- Existing v1.1 reports remain self-contained; regenerated v1.2 reports start with
  fresh browser-local viewer and review state.

## [0.1.0]

This is the first public alpha release of Frame Compare.

### Added

- A complete comparison pipeline that discovers video inputs, probes media,
  selects useful frames, aligns encodes, renders labeled screenshots, and produces
  a self-contained offline HTML report.
- Reproducible random selection and quality-oriented dark, bright, and motion frame
  selection, including reusable analysis and alignment caches.
- Audio-correlation alignment with saved manual overrides and optional interactive
  verification through VSPreview.
- SDR rendering and HDR tonemapping through VapourSynth, vs-placebo, and a
  deterministic software-Vulkan Docker baseline.
- Configurable screenshot labels and an offline report with slider, overlay,
  difference, blink, grid, filmstrip, keyboard navigation, and zoom tools.
- Guided setup, environment diagnostics, dry-run planning, presets, run history,
  machine-readable JSON output, and structured logs.
- Optional slow.pics publishing and Discord-compatible webhook notifications.
  Network publishing remains disabled until deliberately configured.
- A Windows 10/11 x64 portable distribution containing Python, FFmpeg,
  VapourSynth, required plugins, VSPreview, PyQt6, user-level installation, and
  code-only update tooling.
- Reproducible Docker and native-source installation routes for macOS and Linux,
  with separately documented experimental Linux NVIDIA and X11 profiles.

### Changed

- Frame Compare is licensed under `GPL-3.0-only`, aligning the project with its
  GPL-licensed PyQt6 desktop runtime.
- Local reports are the default output. Uploading, webhook delivery, automatic
  browser opening, and clipboard integration are explicit, route-dependent
  actions.
- Release Please release PRs require human review and are never auto-merged by the
  project workflow.

### Fixed

- HDR frames that require tonemapping now fail clearly when the selected renderer
  cannot provide it instead of silently producing untonemapped output.
- Doctor recovery guidance links to the maintained installation documentation.
- Docker integration covers the real FFmpeg, VapourSynth, loader-plugin,
  screenshot, report, and software-tonemapping paths.

### Security and privacy

- External processes are invoked without shell expansion, and release/runtime
  downloads with pinned inputs are checksum-verified where supported.
- Slow.pics uploads and webhook notifications are opt-in; an offline comparison
  does not require publishing video frames or report data.
- Windows release ZIPs include SHA-256 checksum assets and documented verification
  instructions.

### Known limitations

- This is alpha software. Review generated frames and alignment before relying on
  a comparison.
- The Windows portable distribution supports Windows 10/11 x64 only.
- Default Docker on macOS and Linux is a headless backend route. It does not include
  the interactive VSPreview desktop workflow.
- Linux NVIDIA acceleration and X11 forwarding are experimental, host-dependent,
  and require their separate proof procedures.
- Native-source installation requires a compatible host FFmpeg, VapourSynth,
  loader-plugin, Vulkan, and optional VSPreview toolchain.
- Host fonts, graphics drivers, and Vulkan implementations can change rendering
  details; cross-platform output is not promised to be pixel-identical.
- slow.pics and webhook output depend on third-party network services and their
  availability.
