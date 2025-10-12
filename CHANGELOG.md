# Changelog

All notable user-visible updates will be documented in this file in reverse chronological order.

- *2025-10-19:* Seed the packaged default config into a per-user directory when the project tree is read-only so packaged installs no longer fail to start on permission errors.
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
