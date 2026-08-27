# Changelog

All notable user-facing changes to Frame Compare are documented in this file.

Frame Compare follows Conventional Commits, and Release Please turns the
`Unreleased` section into versioned release notes.

## Unreleased

### Fixed

- Correct computed audio-alignment offsets to use the documented
  `reference - comparison` sign convention. The pre-MVP shared alignment cache
  format is reset to schema v1.
- Clarify VSPreview matching-frame confirmation and avoid duplicate preview
  frame-property warnings after Frame Compare reports and applies the same defaults.

## [0.2.0]

### Added

- Add previous-offset reuse controls (`disabled`, `prompt`, and `always`) with
  shared-cache identity, provenance, stability validation, interactive acceptance,
  and structured CLI errors.
- Add post-report slow.pics upload confirmation for interactive runs.
- Add a consent-gated, run-only full-window retry when configured lead/trail
  exclusions leave too little eligible media; authored configuration remains
  unchanged.
- Add report payload v1.2 with release-aware source identities, distinct
  comparison/source-frame domains, exact picture type and Dolby Vision RPU facts
  when observable, file-size context, rendering disclosures, and expanded
  Inspector, review, and viewport behavior.
- Add code-owned media-runtime identities and scoped fingerprints for analysis,
  probing, alignment, source indexing, cache invalidation, Docker, Windows portable,
  and code-only update compatibility.
- Add a guarded immutable release workflow with exact version, tag, and SHA
  validation; collision checks; draft and asset verification; remote digest checks;
  and artifact provenance attestations.
- Bundle Inter Regular under the SIL Open Font License 1.1 for deterministic overlay
  typography.

### Changed

- Bump Frame Compare to 0.2.0 and refresh the managed stack to Python 3.13.15,
  uv 0.12.5, VapourSynth R79/API R4.2, L-SMASH-Works 1296, vs-placebo 2.0.4,
  Akarin 1.4.1, and VSZip 22.1.0. Docker includes FFMS2 5.0; Windows portable
  intentionally excludes FFMS2.
- Make random, dark, bright, and motion frame selection deterministic and temporally
  stratified while preserving seed reproducibility, minimum-gap behavior, sparse
  source coordinates, category counts, and selection diagnostics.
- Classify alignment stability and strengthen shared reuse-cache identity, schema
  validation, and previous-offset presentation.
- Improve CLI help, wizard, side-effect-free dry-run planning, chronological human
  progress output on stderr, JSON output contracts, warnings, and success summaries.
- Carry canonical exact-frame, signal, presentation, geometry, and tonemap facts
  through rendering, overlays, slow.pics upload planning, and reports.
- Strengthen Frame Compare-owned L-SMASH index naming and media-runtime-aware cache
  invalidation.
- Expand deterministic Docker and Windows portable runtime, packaging, installer,
  updater, rollback, provenance, license, and extracted-bundle verification.

### Fixed

- Merge FFprobe HDR color metadata field-by-field only when VapourSynth frame
  properties are missing, malformed, or H.273-unspecified.
- Capture FFmpeg picture type from the same exact-frame extraction process used to
  produce the screenshot.
- Improve recoverable selection failures, source-frame range handling, and
  post-retry fatal error behavior.
- Harden VSPreview startup compatibility checks and redact inherited credential
  values from surfaced startup diagnostics.

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

- Windows v0.1.0 portable installations require the complete v0.2.0 bundle because
  the managed media-runtime fingerprint changed; the code-only updater refuses
  incompatible runtimes.
- Analysis, probe, alignment, and source-index caches include updated runtime
  identities and may be invalidated or rebuilt.
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
