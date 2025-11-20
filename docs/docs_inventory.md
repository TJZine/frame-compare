# Documentation inventory (2025-11-20)

This catalog records the current state of the `docs/` directory and which docs are canonical vs archival after the late-2025 refactors.

<!-- markdownlint-disable MD013 -->
| File | Scope | Still useful? | Notes |
| --- | --- | --- | --- |
| `DECISIONS.md` | Running log of product/engineering choices. | ✅ Keep | Now summarized per decision; long logs trimmed. |
| `README_REFERENCE.md` | Canonical CLI/config/pipeline reference. | ✅ Keep | Aligns with current flags and JSON tails; link here from README. |
| `audio_alignment_pipeline.md` | Detailed workflow and requirements for audio offsets. | ✅ Keep | Canonical deep dive; README links here for advanced use. |
| `geometry_pipeline.md` | SDR geometry pivot rationale and console visibility notes. | ✅ Keep | Canonical geometry reference. |
| `hdr_tonemap_overview.md` | Narrative overview of HDR→SDR strategy and presets. | ✅ Keep | Short overview; defers to README_REFERENCE tonemap section. |
| `current_pipeline_trace.md` | Step-by-step trace of the HDR screenshot pipeline. | ✅ Keep | Matches `src/screenshot.py`/`src/frame_compare/vs`; useful for debugging. |
| `config_reference.md` | Deep dives for configuration options added after the main tables. | ✅ Keep | Use alongside the generated tables in `docs/_generated/config_tables.md`. |
| `refactor/frame_compare_cli_refactor.md` | Completed CLI refactor summary. | ✅ Keep | ADR-style summary; see DECISIONS for commands. |
| `refactor/runner_service_split.md` | Completed runner service extraction summary. | ✅ Keep | Canonical state of service-mode publishing. |
| `refactor/mod_refactor.md`, `typing_refactor.md`, `api_hardening.md`, `flag_audit.md`, `refactor_cleanup.md` | Refactor histories and checklists. | ✅ Keep | Treat as historical summaries; add new work as fresh entries/sections. |
| `legacy_tonemap_pipeline.md` | Historical placebo-based pipeline notes. | ⚠️ Keep (archive) | Only for regression comparisons; not current behaviour. |
| `docs_inventory.md` | This index. | ✅ Keep | Update when docs are rearranged. |
<!-- markdownlint-restore -->

## Suggested clean-up follow-ups

- When archiving or replacing a doc, add a short redirect in the old file.
- Ensure README/README_REFERENCE point to the canonical deep dives listed above after future refactors.
