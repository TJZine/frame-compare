# Decisions Log

- *2025-10-01:* Documented the audio alignment pipeline in `docs/audio_alignment_pipeline.md` to centralize requirements, workflow, and offsets file semantics for ongoing feature work.
- *2025-10-02:* Restricted audio alignment's NumPy warning suppression to local contexts and introduced targeted tests so global diagnostics remain available while avoiding noisy dependencies.
- *2025-09-30:* Standardised group subhead styling across CLI sections: accent-subhead prefixes (`›`/`>` fallback), dim divider rules sized to block content, column alignment for numeric values, and verbose legends describing token roles to satisfy `features/CLI/GUIDE.md`.
- *2025-09-30:* Simplified diagnostic overlays by retiring the HDR MAX/AVG measurement line and instead appending render resolution, mastering display luminance (when HDR tonemap applies), and cached `Frame Selection Type` metadata.
- *2025-09-29:* Adopted CLI layout styling DSL with semantic spans and data-driven highlight rules. Renderer now consumes palette roles (`value`, `unit`, `path`, etc.), honors section accent theming, and evaluates JSON-configured thresholds (e.g., tonemap verification, boolean states) to keep formatting declarative.
- *2025-10-02:* Bounded the TMDB response cache to a configurable entry limit with TTL-aware eviction to stop unbounded growth flagged in deep-review performance findings.
