# Changelog

All notable user-visible updates will be documented in this file in reverse chronological order.

- *2025-10-02:* Scoped audio alignment's NumPy flush-to-zero warning suppression to local contexts and added regression tests to guard global diagnostics.
- *2025-10-01:* Added `docs/audio_alignment_pipeline.md` to detail the alignment workflow, configuration constraints, and offsets file contract.
- *2025-09-30:* Enhanced CLI group blocks with accent subhead glyphs, dimmed divider rules, numeric alignment, and verbose legends describing token colouring for RENDER/PREPARE sections.
- *2025-09-30:* Diagnostic overlay now replaces the HDR MAX/AVG measurement block with the render resolution summary, mastering display luminance (when available), and a `Frame Selection Type` line sourced from cached selection metadata.
- *2025-09-29:* Initialize changelog to align with repository persistence rules.
- *2025-09-29:* Revamped CLI presentation: extended palette, added style spans, highlights, section accents, progress bar styling, verification metrics, and refreshed templates per `features/CLI/GUIDE.md`.
- *2025-10-02:* Hardened TMDB caching with configurable entry limits and TTL-based eviction to prevent long-running CLI sessions from leaking memory.
