# Changelog

All notable user-visible updates will be documented in this file in reverse chronological order.

- *2025-10-30:* Overhauled the offline HTML report viewer with persistent zoom/fit presets, pointer-anchored wheel zoom, pan/align controls, and shortcut legends to better mirror slow.pics.
- *2025-10-29:* Added optional HTML report generation (configurable via `[report]` or `--html-report`), including vendored assets, CLI auto-open support, JSON-tail disclosures, embedded report data for offline viewing, and unit coverage for the new generator. Added overlay mode toggle with keyboard/click encode cycling.
- *2025-10-29:* Added interactive `frame-compare wizard` with presets, introduced `frame-compare doctor` dependency checklist (JSON-capable), expanded reference docs, and strengthened CLI help/tests for the new commands.
- *2025-10-29:* Clarified the CLI audio alignment panel output (stream summaries, cached reuse messaging, offsets file footer) and aligned documentation; slow.pics shortcut filenames now derive from the sanitised collection name with regression tests for edge cases; README and reference tables updated.
- *2025-10-22:* Disabled slow.pics auto-upload by default, added an upfront CLI warning when it is enabled, aligned documentation with dataclass defaults, introduced a packaged `frame-compare` console entry point, and wired Ruff linting into CI (Pyright now blocks failures).
- *2025-10-21:* Prevented VSPreview helper crashes on Windows `cp1252` consoles by sanitising printed arrows to ASCII, preferring UTF-8 output streams, adding regression coverage, and documenting the console behaviour.
- *2025-10-20:* Hardened audio alignment's optional dependency handling by surfacing clear `AudioAlignmentError` messages when
  `numpy`, `librosa`, or `soundfile` fail during onset envelope calculation, and refreshed regression coverage for the failure
  path.
- *2025-10-20:* VSPreview-assisted manual alignment now displays existing manual trims using friendly clip labels so operators
  can immediately see which plan each baseline affects before accepting new deltas.
- *2025-10-20:* Prevented VSPreview script overwrites by appending per-run entropy to generated filenames and warning when a
  collision is detected.
- *2025-10-20:* Fixed mod-2 odd-geometry failures by pivoting subsampled SDR clips through YUV444P16 when needed, emitting Rich console notes that summarise the axis/policy, and expanding docs/config guidance for the `odd_geometry_policy` and `rgb_dither` options.
- *2025-10-19:* Normalised VapourSynth colour metadata inference for SDR clips, cached inferred props on the
  clip to avoid redundant frame grabs, exposed config overrides for HD/SD defaults and per-file colour
  corrections, refreshed documentation, and expanded regression coverage for the new heuristics.
- *2025-10-18:* Fixed VapourSynth RGB conversion when colour metadata is absent by defaulting to Rec.709
  limited parameters, preventing fpng "no path between colours" failures and adding regression coverage.
- *2025-10-17:* Documented the VSPreview-assisted manual alignment flow (README, reference tables, pipeline guide), surfaced the
  CLI help text, added a fallback regression test, and published a cross-platform QA checklist for manual verification.
- *2025-10-16:* Hardened analysis cache and audio offsets paths to stay within the workspace root, added regression tests for escape attempts, removed the generated `config.toml` from source control in favour of the packaged template, and restricted screenshot cleanup to directories created during the current run.
- *2025-10-16:* Limited supported Python versions to 3.13.x (`>=3.13,<3.14`) to align with current `librosa`/`numba` wheels; updated project metadata and lockfile.
- *2025-10-14:* Locked workspace roots to `--root`/`FRAME_COMPARE_ROOT`/sentinel discovery, seeded config under `ROOT/config/config.toml`, enforced `ROOT/comparison_videos[/screens]`, added `--diagnose-paths`, and blocked site-packages writes before screenshotting.
- *2025-10-12:* Default config now seeds to `~/.frame-compare/config.toml`, `[paths].input_dir` defaults to `~/comparison_videos`, and the packaged template ships from `src/data/` (with wheel coverage) to avoid site-packages permission issues. *(Superseded by 2025-10-14 workspace root lock.)*
- *2025-10-11:* Added an optional `$FRAME_COMPARE_TEMPLATE_PATH` override and filesystem fallback for the packaged config template plus clearer screenshot permission errors so runs targeting read-only `comparison_videos` trees fail fast with guidance.
- *2025-10-19:* Seed the packaged default config into a per-user directory when the project tree is read-only so packaged installs no longer fail to start on permission errors.
- *2025-10-20:* Allow disabling the per-frame FFmpeg timeout by setting `screenshots.ffmpeg_timeout_seconds` to 0 while keeping negative values invalid in validation and docs.
- *2025-10-18:* Added a per-frame FFmpeg timeout and disabled stdin consumption to prevent hung screenshot renders and shell freezes on Windows.
- *2025-10-17:* Streamlined CLI framing: removed the banner row, surfaced cached-metrics reuse inside the Analyze block, dropped the At-a-Glance crop-mod readout in favour of effective tonemap nits, and trimmed the Summary output frames line to match the refreshed console layout and tests.
- *2025-10-16:* Documented deep-review finding: screenshot cleanup must enforce path containment before deleting outputs; remediation planned.

- *2025-10-15:* Relocated bundled comparison fixtures to the repository-root `comparison_videos/` directory, updated CLI docs to match the default `paths.input_dir`, and noted the new resolution fallbacks.
- *2025-10-14:* Clarified CLI hierarchy by softening section badge colors, brightening subhead prefixes, expanding the At-a-Glance box with alignment, sampling, and canvas metrics for quicker triage, and realigning the Summary section with key/value formatting to remove ragged rows.
- *2025-10-13:* Removed the `types-pytest` dev dependency so `uv run` can resolve environments on fresh clones without relying on a non-existent stub package while keeping the actual `pytest` runtime dependency in the dev group for CI and local tests.
- *2025-10-10:* Reject invalid `cli.progress.style` values during configuration loading and persist normalized styles for downstream flag handling to keep CLI reporters consistent.
- *2025-10-12:* Added local type stubs for optional CLI/testing dependencies and hardened JSON-tail assertions in tests so Pyright runs cleanly without relaxing diagnostic settings.
- *2025-10-09:* Expanded minimal overlays with resolution/upscale and frame-selection type lines while simplifying diagnostic overlays by removing on-screen selection timecode/score/notes that remain available via cached metadata.
- *2025-10-02:* Scoped audio alignment's NumPy flush-to-zero warning suppression to local contexts, added regression tests to keep diagnostics available, and hardened TMDB caching with TTL-aware eviction to cap memory growth during long CLI sessions.
- *2025-10-01:* Added selection metadata persistence v1: cached JSON sidecar, compframes annotations, CLI summary metrics, and screenshot overlay reuse without rerunning analysis.
- *2025-10-01:* Added `docs/audio_alignment_pipeline.md` to detail the alignment workflow, configuration constraints, and offsets file contract.
- *2025-09-30:* Enhanced CLI group blocks with accent subhead glyphs, dimmed divider rules, numeric alignment, and verbose legends describing token colouring for RENDER/PREPARE sections.
- *2025-09-30:* Diagnostic overlay now replaces the HDR MAX/AVG measurement block with render resolution details, mastering display luminance (if present), and cached frame-selection metadata while trimming redundant frame-info lines for leaner CLI banners.
- *2025-09-29:* Initialize changelog to align with repository persistence rules.
- *2025-09-29:* Revamped CLI presentation: extended palette, added style spans, highlights, section accents, progress bar styling, verification metrics, and refreshed templates per `features/CLI/GUIDE.md`.
