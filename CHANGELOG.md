# Changelog

All notable user-facing changes to Frame Compare are documented in this file.

Frame Compare follows Conventional Commits, and Release Please turns the
`Unreleased` section into versioned release notes.

## Unreleased

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
