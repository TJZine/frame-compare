# Changelog

All notable user-visible updates will be documented in this file in reverse chronological order.

- *2025-10-02:* Scoped audio alignment's NumPy flush-to-zero warning suppression to local contexts, added regression tests to keep diagnostics available, and hardened TMDB caching with TTL-aware eviction to cap memory growth during long CLI sessions.
- *2025-10-01:* Added selection metadata persistence v1: cached JSON sidecar, compframes annotations, CLI summary metrics, and screenshot overlay reuse without rerunning analysis.
- *2025-10-01:* Added `docs/audio_alignment_pipeline.md` to detail the alignment workflow, configuration constraints, and offsets file contract.
- *2025-09-30:* Enhanced CLI group blocks with accent subhead glyphs, dimmed divider rules, numeric alignment, and verbose legends describing token colouring for RENDER/PREPARE sections.
- *2025-09-30:* Diagnostic overlay now replaces the HDR MAX/AVG measurement block with render resolution details, mastering display luminance (if present), and cached frame-selection metadata while trimming redundant frame-info lines for leaner CLI banners.
- *2025-09-29:* Initialize changelog to align with repository persistence rules.
- *2025-09-29:* Revamped CLI presentation: extended palette, added style spans, highlights, section accents, progress bar styling, verification metrics, and refreshed templates per `features/CLI/GUIDE.md`.
