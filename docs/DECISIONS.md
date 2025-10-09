# Decisions Log

- *2025-10-02:* Restricted audio alignment's NumPy warning suppression to local contexts, paired with regression coverage that preserves global diagnostics while muting noisy dependencies.
- *2025-10-02:* Bounded the TMDB response cache to a configurable entry limit with TTL-aware eviction to stop unbounded growth flagged in deep-review performance findings.
- *2025-10-01:* Documented the audio alignment pipeline in `docs/audio_alignment_pipeline.md` to centralize requirements, workflow, and offsets file semantics for ongoing feature work.
- *2025-10-01:* Persisted selection metadata sidecar v1 with deterministic cache keys, JSON-tail exposure, and generated.compframes annotations to satisfy the CLI selection cache persistence guide.
- *2025-09-30:* Standardised group subhead styling across CLI sections: accent-subhead prefixes (`›`/`>` fallback), dim divider rules sized to block content, column alignment for numeric values, and verbose legends describing token roles to satisfy `features/CLI/GUIDE.md`.
- *2025-09-30:* Simplified diagnostic overlays by replacing the HDR MAX/AVG measurement block with render resolution, mastering display luminance (for HDR sources), and cached frame-selection metadata while trimming redundant frame-info lines to keep CLI banners uncluttered.
- *2025-09-29:* Adopted CLI layout styling DSL with semantic spans and data-driven highlight rules. Renderer now consumes palette roles (`value`, `unit`, `path`, etc.), honors section accent theming, and evaluates JSON-configured thresholds (e.g., tonemap verification, boolean states) to keep formatting declarative.
