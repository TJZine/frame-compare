# Decisions Log

- *2025-09-29:* Adopted CLI layout styling DSL with semantic spans and data-driven highlight rules. Renderer now consumes palette roles (`value`, `unit`, `path`, etc.), honors section accent theming, and evaluates JSON-configured thresholds (e.g., tonemap verification, boolean states) to keep formatting declarative.
- *2025-09-30:* Standardised group subhead styling across CLI sections: accent-subhead prefixes (`›`/`>` fallback), dim divider rules sized to block content, column alignment for numeric values, and verbose legends describing token roles to satisfy `features/CLI/GUIDE.md`.
- *2025-09-30:* Restored HDR diagnostic measurement overlay by converting tonemapped clips to grayscale via multi-plane Expr/PlaneStats, ensuring MAX/AVG nits surface in diagnostic mode.
