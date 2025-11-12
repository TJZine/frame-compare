# Documentation inventory (2025-10-11)

This catalog records the current state of the `docs/` directory
and whether each artifact should stay in the tree.

<!-- markdownlint-disable MD013 -->
| File | Scope | Still useful? | Notes |
| --- | --- | --- | --- |
| `DECISIONS.md` | Running log of product/engineering choices. | ✅ Keep | Latest entries still describe shipped changes (CLI layout, tonemap defaults) and provide governance history. |
| `README_REFERENCE.md` | Config quick-reference that backs the main README. | ✅ Keep | Updated defaults now mirror `src/datatypes.py`; continue revisiting when config schema shifts. |
| `audio_alignment_pipeline.md` | Detailed workflow and requirements for audio offsets. | ✅ Keep | Matches the current code paths and is referenced from the README for advanced setup. |
| `config_reference.md` | Deep dives for configuration options added after the main tables. | ✅ Keep | Documents `odd_geometry_policy` and `rgb_dither` trade-offs introduced with odd-geometry support. |
| `current_pipeline_trace.md` | Step-by-step trace of the HDR screenshot pipeline. | ✅ Keep | Still accurate versus `src/screenshot.py`/`src/frame_compare/vs`; aids regression debugging. |
| `geometry_pipeline.md` | SDR geometry pivot rationale and console visibility notes. | ✅ Keep | New; explains the YUV444P16 pivot, axis-aware behaviour, and dithering stages. |
| `hdr_tonemap_overview.md` | Narrative overview of HDR→SDR strategy and presets. | ✅ Keep | Complements the pipeline trace with operator-facing guidance. |
| `legacy_tonemap_pipeline.md` | Historical placebo-based pipeline notes. | ⚠️ Keep (archive) | Useful for regression comparisons; tag as archival if the legacy flow is ever dropped. |
| `docs_inventory.md` | This index. | ✅ Keep | Re-run after any major docs purge or reorganization. |
<!-- markdownlint-restore -->

## Suggested clean-up follow-ups

- Mark legacy documents (`legacy_tonemap_pipeline.md`) as archival in the
  README if user-facing audiences no longer need them.
- Integrate the slow.pics session-closing action item (see
  `deep_review.md`) into the engineering backlog if uploads continue to
  run in long-lived processes.
