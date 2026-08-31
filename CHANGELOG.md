# Changelog

All notable user-facing changes to Frame Compare are documented in this file.

Frame Compare follows Conventional Commits, and Release Please turns the
`Unreleased` section into versioned release notes.

## Unreleased

### Fixed

- Populate guarded GitHub releases from the matching validated changelog section
  instead of a placeholder, and verify the release body through publication.

### Changed

- Replace the retired interactive viewer integration with VSView 0.10.3 using its
  documented named-output API. The supported dependency is the base `vsview` extra;
  its `recommended` and `full` extras are not selected.
- Preserve generated-session L-SMASH-Works loading, Frame Compare overlays, source
  ordering, audio alignment semantics, and terminal confirmation while removing the
  old viewer compatibility bootstrap. VSView's BestSource workspace remains UI-only
  and does not replace Frame Compare's analysis, probe, render, index, or cache-key
  source loader.
- Rename interactive diagnostic and machine-readable identifiers to VSView, including
  `audio_alignment.use_vsview`, the `vsview` doctor check, and the
  `browser_clipboard_or_vsview` dry-run field. Numeric error codes remain unchanged.
- Bump the shared alignment reuse cache to schema v2 with neutral interactive origins;
  schema-v1 entries are ignored and recomputed. Run-local `manual_overrides.toml`
  remains a v1 file with the same path and offset semantics.

### Upgrade notes

- VSPreview-era native or Windows portable installations must install the complete
  VSView bundle. A code-only update fails closed when the installed requirements or
  media-runtime fingerprint does not match; it never mixes the old UI/native graph
  with new application code.
- Replace `audio_alignment.use_vspreview = true` with
  `audio_alignment.use_vsview = true` in authored configuration. The old key is no
  longer accepted, and the shared alignment reuse cache is rebuilt as schema v2.

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
