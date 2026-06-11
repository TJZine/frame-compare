# Frame Compare Test-Suite Overengineering Audit

Status: revised single-source audit for user review before cleanup.

This document supersedes the first `gpt-5.4` audit draft and folds in the later critical review. It is intentionally detailed enough to hand to a conservative cleanup subagent, with explicit boundaries for what to keep, what to relax, and what to remove.

## Scope

- Repository: `frame-compare`
- Audit target: candidate test-overengineering items preserved in `.codex/cache/test-overengineering-audit-prelim.md`, plus local review of the generated audit and nearby tests.
- Out of scope: implementation, production behavior changes, broad unrelated refactors.
- Current known committed fix before this audit: `29de1ce fix: skip vspreview after confirmed alignment reuse`.

## Production-Quality Standard

The goal is not fewer tests. Production-quality code can and should be test-heavy where the tests catch meaningful regressions. The goal is higher signal density: keep heavy tests when they protect real production risk, and remove or consolidate tests that mostly create maintenance drag.

Keep exact or heavy tests when they protect:

- Public CLI stdout/stderr, JSON, help, exit-code, or generated-doc contracts.
- Security, sanitization, offline behavior, path escaping, or external URL allowlists.
- Persistence schemas, migration behavior, generated caches, atomic writes, and filesystem integrity.
- Windows portable release/update/signing/shim behavior where local non-Windows behavioral proof is limited.
- Runtime integration boundaries: VapourSynth, FFmpeg, TMDB, slow.pics, VSPreview generated scripts.
- Accessibility and durable UX behavior: focus restore, inert/tabindex state, modal precedence, reduced-motion behavior.
- Typed owner boundaries where the payload is the seam between modules.

Treat a test as overengineered when it primarily:

- Asserts private fields after a smoke path.
- Freezes exact copy, glyphs, CSS tokens, source ordering, or call tuples that are not documented contracts.
- Duplicates stronger coverage at a public or narrower owner seam.
- Makes a correct refactor fail without any user-visible or boundary-visible behavior change.
- Would become an empty "does not raise" smoke test after removing incidental assertions.

## Executive Summary

The original audit was directionally useful but too conservative. It correctly protected high-risk areas, but it grouped large clusters under single `MODIFY` IDs and undercounted removal/consolidation opportunities.

Revised posture:

- Keep exactness for CLI/docs/error output, security/offline behavior, path escaping, atomic writes, release scripts, and true owner seams.
- Be substantially more aggressive in progress reporter private-state tests, report viewer markup/CSS copy snapshots, raw JS source-order tests, duplicated HTML coverage, and render geometry internals.
- Prefer `MODIFY` for behavior that is valuable but asserted at the wrong level.
- Use `REMOVE` or `CONSOLIDATE` when a test is duplicated, smoke-only, or would have no meaningful assertion left after removing internals.

## Revised Totals

- `KEEP`: 13
- `MODIFY`: 16
- `REMOVE/CONSOLIDATE`: 7
- `DEFER`: 0

`REMOVE/CONSOLIDATE` means the cleanup agent should remove the test if existing coverage remains adequate, or merge its one useful assertion into a stronger nearby test. It should not leave behind a weak smoke test simply to preserve test count.

## Adjudication Ledger

### A. CLI / Docs / Core Contracts

| ID | Candidate refs | Revised call | Keep argument | Remove/relax argument | Cleanup instruction | Confidence | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TSO-001` | `tests/test_api_docs_cli.py::test_cli_check_reports_success_and_mismatch` | `KEEP` | This is a generated API-doc drift gate. `MISSING`/`STALE`, stream placement, and path reporting are public developer-facing contract. | Newline/path exactness is brittle in isolation, but here it is the behavior being checked. | Leave as-is unless the CLI contract changes. | High | Low |
| `TSO-002` | `tests/test_api_docs_render.py::test_render_markdown_for_small_module_doc`; `tests/test_generate_api_docs.py::test_symbols_order_case_insensitive` | `KEEP` | Stable rendered ordering is the purpose of the docs generator. | Could look implementation-shaped, but deterministic sort/render is the product contract. | Leave as-is. | High | Low |
| `TSO-003` | `tests/test_errors.py::test_format_error_console_rendered_output_preserves_literal_brackets` | `KEEP` | Protects user-visible error rendering and Rich bracket escaping. | Exact phrasing is somewhat tight, but escaping and visible structure are important. | Leave as-is unless error format contract changes. | High | Low |
| `TSO-004` | `tests/test_validate_traceability.py::test_validate_test_function_requires_exact_def`; `scripts/validate_traceability.py` | `MODIFY` | Exact `def test_name(` matching prevents fuzzy false positives in a workflow tool. | The test patches `SCAFFOLD_TESTS_DIR`, but `_resolve_test_path()` does not use it. That is stale setup. | Keep the exact-def behavior. Remove dead scaffold patching from the test, or implement a real scaffold path if still intended. | High | Low |

### B. Orchestration / Alignment

| ID | Candidate refs | Revised call | Keep argument | Remove/relax argument | Cleanup instruction | Confidence | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TSO-005` | `tests/orchestration/test_execute_run_lifecycle.py::test_execute_run_returns_success_and_records_preflight_timing` | `MODIFY` | Returned phase timing keys are orchestration output. | Exact `0.0` values for skipped phases are incidental timing implementation. | Keep key presence and non-negative timing checks. Only keep exact zero where documented or semantically required. | High | Low |
| `TSO-006` | `tests/orchestration/test_run_dependencies.py::test_execute_run_passes_no_color_to_progress_selection` | `MODIFY` | `no_color` propagation is a real CLI UX contract. | `force_tty is None` is a default implementation detail unless explicitly documented. | Keep `quiet`, `json_output`, and `no_color` propagation. Drop or relax `force_tty is None` unless nearby code/docs make it a deliberate seam. | Medium | Low |
| `TSO-007` | `tests/orchestration/test_phase_tasks_alignment.py::test_run_align_phase_applies_offsets_and_normalizes_selected_frames` | `KEEP` | This protects the typed `AlignmentRequest` owner seam, cache path, stream selection, offsets, and normalized frame behavior. | It is exhaustive, but most assertions map to downstream service inputs. | Leave as-is. Do not sweep alignment request/cache provenance tests into cleanup without new evidence. | High | Medium |
| `TSO-008` | `tests/orchestration/test_alignment_report.py::test_emit_frame_alignment_report_renders_human_panel_to_stderr` | `MODIFY` | Stderr/no-color routing and presence of alignment facts matter. | Exact Rich panel prose and row text are presentation-heavy. | Assert channel and semantic facts; relax literal sentence fragments and panel wording. | High | Low |
| `TSO-009` | `tests/orchestration/test_fps_report.py::test_emit_consolidated_fps_report_json_mode_logs_without_human_output` | `MODIFY` | JSON mode suppressing human output and logging the event are useful. | Full structured-log payload equality is internal unless log schema is documented. | Keep event/stage/channel and critical clip fields. Do not assert whole payload dict. | High | Low |
| `TSO-010` | `tests/services/test_alignment_workflow.py::test_align_clips_computed_results_advance_phase_progress`; `...::test_align_clips_advances_each_computed_comparison_before_starting_next`; `...::test_align_clips_full_manual_hit_uses_spinner_without_progress_bar` | `MODIFY` | Alignment progress milestones matter for interactive and cached flows. | Exact descriptions and reporter call choreography are brittle. | Assert semantic milestones and counts: cache spinner shown, compute comparisons advance, manual-hit path avoids compute progress, interactive suspend/resume remains. Avoid exact text/order unless needed for user contract. | High | Low |
| `TSO-011` | `tests/services/test_alignment_reuse_prompt.py::test_prompt_prints_rich_safe_table_to_stderr_and_accepts_yes`; `...::test_prompt_uses_bounded_standard_panel_width` | `MODIFY` | Prompt channel, cache identity content, and accept/decline behavior matter. | Rich glyphs and fixed width `180` are layout internals. | Keep stderr/content/decision behavior. Remove glyph and exact-width assertions; use a bounded-width invariant only if needed. | High | Low |
| `TSO-012` | `tests/services/test_alignment_vspreview.py::test_prompt_for_confirmed_offsets_writes_to_stderr`; `...::test_prompt_for_confirmed_offsets_reprompts_after_blank_and_malformed_input` | `MODIFY` | Prompting on stderr and reprompting invalid input are real interactive behavior. | Exact prompt/help/error wording and counts are over-tight. | Keep stderr routing, accepted offset math, and invalid-input reprompt. Relax literal strings. | High | Low |

### C. Report Viewer JS / State / Markup / CSS

| ID | Candidate refs | Revised call | Keep argument | Remove/relax argument | Cleanup instruction | Confidence | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TSO-013` | `tests/services/test_report_viewer_assets_js_contracts.py::test_viewer_js_initializes_help_before_renderable_gating`; `...::test_viewer_js_preserves_modal_escape_and_focus_restore_contracts`; `...::test_viewer_js_closes_alignment_popover_before_global_escape_shortcuts` | `MODIFY` | Modal precedence, focus restoration, inert/tabindex behavior, and Escape ordering are accessibility/UX contracts. | Raw JS source ordering is inferior evidence where executable harness coverage is possible. | Keep behavior. Move assertions into `viewer_state_harness.js` where practical. Leave source-order checks only for behavior the harness cannot cover. Add no new raw JS block-order tests. | High | Medium |
| `TSO-014` | `tests/services/test_report_viewer_assets_js_contracts.py::test_viewer_js_persists_report_scoped_viewport_state` | `MODIFY` | Report-scoped persistence schema is a real UX contract. | Duplicate string lists in test/source are maintenance-heavy and hide schema drift. | Keep exact persisted field behavior, but centralize valid field/mode constants if feasible. Do not remove persistence coverage. | High | Medium |
| `TSO-015` | `tests/services/test_report_viewer_state.py::test_viewer_state_harness_exercises_pair_scoped_alignment` | `REMOVE/CONSOLIDATE` | The harness covers important behaviors: pair-scoped alignment, Escape precedence, safe links, reduced motion, inspector focus, persistence. | One giant exact summary object makes every change high blast-radius and includes exact status strings, smart-label coordinates, and many unrelated facts. Splitting alone is insufficient if each split preserves exact snapshots. | Replace with focused harness assertions by behavior family. Remove exact aggregate summary equality. Keep only semantic checks for alignment/persistence/focus/safe-link/reduced-motion behavior. Avoid exact UI copy and coordinate values unless documented. | High | Medium |
| `TSO-016` | `tests/services/test_report_viewer_assets_css.py::test_viewer_css_keeps_stage_pointer_and_label_contracts`; related CSS tests in the same file | `REMOVE/CONSOLIDATE` | Some CSS assertions protect accessibility/responsiveness: hidden state, reduced motion, touch/pointer behavior, fullscreen, offline URL bans, inspector/mobile presence. | The file also asserts fonts, hover transforms, gradients, badge token values, fixed widths, icon scale, and other decorative styling. Unit tests should not freeze most visual token choices. | Split CSS tests into hard contracts and decorative snapshots. Keep offline URL and `@import` bans, `[hidden]`, reduced-motion, touch/pointer, fullscreen, inspector/mobile invariants. Remove decorative token assertions unless tied to a documented regression. | High | Low |
| `TSO-017` | `tests/services/test_metadata_parsing.py::test_metadata_parsing_direct_module_uses_anitopy_first_for_bracketed_names` | `MODIFY` | Precedence intent is valid: bracketed anime names should prefer anitopy-derived title/release-group semantics. | Exact `calls == [...]` freezes parser call ordering instead of observable result. | Assert resulting metadata precedence and merged fields. Drop exact parser call-list ordering. | Medium | Low |
| `TSO-032` | `tests/services/test_report_renderer_markup.py::test_build_html_renders_mode_aware_clip_controls`; `...::test_build_html_keeps_ten_plus_long_label_clips_reachable_and_mobile_safe`; `...::test_build_html_positions_stage_labels_outside_image_layers`; `...::test_build_html_uses_internal_category_keys_for_reserved_category_text`; `...::test_build_html_renders_viewport_audit_controls`; `...::test_build_html_renders_inspector_drawer`; `...::test_build_html_renders_keyboard_help_accessibility_hooks`; `...::test_build_html_toggles_filmstrip_visibility` | `REMOVE/CONSOLIDATE` for copy/layout snapshots; `MODIFY` for semantic DOM contracts | These tests include real contracts: required controls, roles, aria state, hidden state, mobile reachability, and stage-label placement. | Many assertions freeze button text, icon glyphs, titles, help-copy rows, raw substring ordering, CSS class choreography, and internal `cat-*` key names. | Convert to parsed-DOM semantic assertions. Keep roles/ids/aria/state/control presence, safe escaping, no inline styles, and offline behavior. Remove exact copy/glyph/title/help-row snapshots and raw `html.index(...)` checks. | High | Medium |
| `TSO-033` | `tests/services/test_report.py::test_renderer_clip_options_rendering` | `REMOVE` | Has some end-to-end smoke value. | Duplicates dedicated renderer-markup clip-select coverage at a weaker seam and freezes exact HTML. | Remove after confirming `test_report_renderer_markup.py` still covers clip controls semantically. Do not replace with another exact HTML smoke. | High | Low |

### D. VSPreview Script Generation / TMDB

| ID | Candidate refs | Revised call | Keep argument | Remove/relax argument | Cleanup instruction | Confidence | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TSO-018` | `tests/services/test_tmdb_resolution.py::test_resolve_tmdb_match_searches_variants_with_bounded_concurrency` | `KEEP` | Bounded concurrency across search variants is a reliability/performance contract at an external HTTP boundary. | Counters are internal, but directly prove the limit. | Leave as-is. | High | Low |
| `TSO-019` | `tests/vspreview/test_adapter.py::test_build_script_content_escapes_path_literals` | `KEEP` | Generated-script path escaping is injection safety. | Exact hostile-literal checks are justified. | Leave as-is. | High | Low |
| `TSO-020` | `tests/vspreview/test_adapter.py::test_build_script_content_warns_when_comparison_overlay_fails` | `MODIFY` | Best-effort overlay warning behavior matters. | Source-text-only assertion does not prove runtime behavior. | Execute generated script with fake overlay failure and assert warning behavior. Remove source snippet dependence. | High | Low |
| `TSO-021` | `tests/vspreview/test_adapter.py::test_build_script_content_uses_narrow_stream_reconfigure_helper` | `REMOVE/CONSOLIDATE` | Console stream robustness matters. | Helper source-body snapshot is duplicated by behavior tests and freezes implementation. | Remove helper-body assertions if existing generated-script execution covers stream fallback. Otherwise add one runtime behavior test, not a source-shape test. | High | Low |
| `TSO-022` | `tests/vspreview/test_adapter.py::test_build_script_content_resolves_lwlibavsource_with_lsmas_then_lw_fallback` | `MODIFY` | `lsmas` preference and `lw` fallback are real runtime behavior. | Exact generated source order is implementation-shaped. | Use fake `core.lsmas` / `core.lw` execution to prove preference/fallback. Keep minimal marker assertions only if needed. | High | Low |
| `TSO-023` | `tests/vspreview/test_adapter.py::test_generated_script_output_order_matches_prompt_input_order_for_unsorted_comparisons`; `...::test_generated_script_current_human_output_organization_without_launching_vspreview`; `...::test_generated_script_collects_preview_assumptions_before_outputs_and_ready` | `MODIFY` | Pair-order and output grouping can matter for interactive review. | Exact stderr section names and phrase ordering are brittle. | Keep pair order and presence of major sections. Relax phrase/order snapshots that are not user contract. | High | Low |
| `TSO-024` | `tests/vspreview/test_adapter.py::test_generate_vspreview_script_bootstraps_nested_legacy_workspace`; `...::test_generate_vspreview_script_bootstraps_run_folder_workspace`; `...::test_build_script_content_assert_by_section` | `REMOVE/CONSOLIDATE` for section snapshot; `MODIFY` for bootstrap behavior | Bootstrap correctness matters. Section/comment snapshots do not. | Raw embedded path and section-comment text are brittle. | Validate computed bootstrap behavior and parseability. Remove section/comment snapshotting except for minimal required runtime markers. | High | Low |
| `TSO-025` | `tests/vspreview/test_adapter.py::test_generate_vspreview_script_uses_atomic_write`; `...::test_generate_vspreview_script_handles_collision` | `KEEP` | Atomic write and collision behavior protect filesystem integrity. | Already observable and scoped. | Leave as-is. | High | Low |

### E. Windows Portable / Manual / Progress

| ID | Candidate refs | Revised call | Keep argument | Remove/relax argument | Cleanup instruction | Confidence | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TSO-026` | `tests/windows_portable/test_windows_portable_update_scripts.py::test_windows_portable_updater_uses_native_path_helpers_for_pwsh_e2e`; `...::test_windows_portable_build_update_add_file_to_zip_opens_entry_before_source`; `...::test_windows_portable_build_update_manifest_entries_use_mutable_list`; `...::test_windows_portable_updater_isolates_rename_recovery_cleanup_steps`; `...::test_windows_portable_sign_update_write_string_entry_disposes_writer` | `KEEP` | Release/update/signing behavior is high-risk, and static script assertions may be the best local proof on non-Windows hosts. | Static text tests can rot into snapshots. | Keep, but require each future assertion to name the release failure it prevents. Do not clean up unless a stronger Windows behavior test replaces it. | High | High |
| `TSO-027` | `tests/windows_portable/test_windows_portable_shim_scripts.py::test_windows_portable_shim_prefers_bundle_config_before_state_config_when_missing_explicit_config`; `...::test_windows_portable_shim_supports_dot_sourcing_without_execution` | `KEEP` | Config precedence and dot-sourcing safety are portable command-surface contracts. | Static assertions are brittle, but justified here. | Leave as-is unless replaced with stronger PowerShell execution coverage. | High | High |
| `TSO-028` | `tests/windows_portable/test_windows_portable_install_entrypoints.py::test_install_from_source_uv_install_order_is_deterministic` | `MODIFY` | Recovery guidance and install-path availability matter. | Strict positional order is over-tight unless documented. | Keep presence of install paths and copy/paste recovery semantics. Relax positional ordering if not contract. | Medium | Medium |
| `TSO-029` | `tests/windows_portable/test_windows_portable_cmd_wrappers_have_absolute_powershell_fallbacks` | `KEEP` | Absolute PowerShell fallback paths protect real Windows usability. | Minor brittleness is acceptable. | Leave as-is. | High | Medium |
| `TSO-030` | `tests/manual/test_slowpics_live.py::test_slowpics_comparison_page_exposes_passive_upload_protocol` | `KEEP` | Manual/live canary for slow.pics protocol. | Brittle to third-party changes, but intentionally opt-in and integration-facing. | Leave as-is. Narrow only if it becomes noisy. | Medium | Medium |
| `TSO-031` | `tests/utils/test_progress.py::test_rich_progress_reporter_accepts_no_color`; `...::test_log_progress_reporter_smoke`; `...::test_log_progress_reporter_supports_nested_phases`; `...::test_rich_progress_reporter_suspend_and_resume_preserves_active_task`; `...::test_rich_progress_reporter_hides_parent_while_nested_phase_is_active`; `...::test_rich_progress_reporter_indeterminate_phase_is_spinner_only`; `...::test_rich_progress_reporter_restores_parent_when_nested_phase_fails`; `...::test_rich_progress_reporter_warned_phase_does_not_force_total`; `...::test_rich_progress_reporter_refreshes_state_changes` | `REMOVE/CONSOLIDATE` | No-color, nested phase behavior, warned/failed completion, and concurrent updates matter. | Many tests assert private Rich internals, private update kwargs, refresh counts, or private state after smoke paths. `test_log_progress_reporter_smoke` is especially low-value. | Delete `test_log_progress_reporter_smoke` unless it asserts real log output. Replace private-state probes with one nested-phase behavior test, one warned/failed completion behavior test, and one no-color construction/output-routing check. Do not leave many "does not raise" smoke tests. | High | Low |

### F. Output Phases / Render Expansion / Encoders

| ID | Candidate refs | Revised call | Keep argument | Remove/relax argument | Cleanup instruction | Confidence | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TSO-034` | `tests/orchestration/test_phase_tasks_outputs.py::test_run_render_phase_prefers_typed_selection_details_in_reference_source_domain`; `...::test_output_phases_use_reselected_metric_metadata_after_real_initial_selection`; `...::test_run_publish_phase_sets_url_from_publish_result_and_delegates_post_upload_actions`; `...::test_post_report_cleanup_returns_warning_and_logs_for_delete_error`; `...::test_warn_only_publish_phase_keeps_sanitized_service_error_in_warning_and_log` | `MODIFY` | Reselected metadata, slow.pics publishing, cleanup warning behavior, and warn-only publish continuation matter. | Full diagnostic metadata equality, helper row/image internals, and exact log payloads are too tight. | Keep user-visible outputs, sanitized warnings, URL/publish result propagation, and continuation behavior. Relax helper-shape, exhaustive metadata, and exact logger payload assertions. | High | Medium |
| `TSO-035` | `tests/orchestration/test_phase_tasks_outputs.py::test_run_report_phase_without_screenshots_clears_existing_report_path`; `tests/orchestration/test_execute_run_phase_integration.py::test_execute_run_clears_report_path_when_report_phase_skipped` | `REMOVE/CONSOLIDATE` | Stale report-path clearing is worth testing. | The unit/integration two-seam defense is weak for this low-risk behavior unless there is bug history. | Prefer the integrated user-facing test. Remove the narrower duplicate if no unique branch is lost. | Medium | Low |
| `TSO-036` | `tests/render/test_expansion.py::test_expand_batch_render_requests`; `...::test_expand_batch_render_requests_maps_aligned_config_to_geometry_options`; `...::test_expand_batch_render_requests_marks_same_canvas_aligned_transform_as_target`; `...::test_expand_batch_render_requests_aligns_mixed_dimensions_with_explicit_active_rects`; `...::test_expand_batch_render_requests_rejected_trusted_metadata_falls_back_with_warning`; `tests/render/test_encoders.py::test_render_frame_vs_auto_uses_fpng_for_geometry_without_overlay`; `...::test_render_vs_applies_geometry_plan_before_saving`; `...::test_render_frame_ffmpeg_wraps_unrepresentable_geometry_as_render_error`; `...::_clip_to_rgb24_for_pillow_*` branch tests | `REMOVE/CONSOLIDATE` for repeated internals; `MODIFY` for true render contracts | Render geometry, output canvas, overlay metadata, writer selection, and tonemap/range behavior matter. | Exact call tuples, fake VapourSynth op order, repeated crop/pad numbers, pixel-by-pixel interpolation values, and repeated resize call signatures are algorithm locks. | Keep one or two canonical numeric geometry algorithm tests if deliberately documented. Convert the rest to final canvas, overlay origin, writer selection, output dimensions, warning category/core reason, and branch-intent assertions. Consolidate repeated `_clip_to_rgb24_for_pillow_*` cases into fewer branch tests. | High | Medium |

## Explicitly Rejected From Cleanup

Do not include these in the first cleanup package:

- `TSO-001` to `TSO-003`: CLI/docs/error-surface exactness is contract evidence.
- `TSO-007`: alignment request mapping protects a typed owner seam.
- `TSO-018` to `TSO-019`: TMDB bounded concurrency and VSPreview path escaping protect reliability/security behavior.
- `TSO-025`: atomic write and collision handling protect filesystem integrity.
- `TSO-026` to `TSO-030`: Windows portable/manual tests are release/runtime/public surfaces where exactness is often justified.
- Security/sanitization/offline report tests in `tests/services/test_report_renderer_markup.py`.
- Alignment cache/provenance/write-policy tests from the explorer packet that were reported as no findings.

## Cleanup Packages

### Package 1: Progress Reporter Signal Cleanup

IDs: `TSO-031`

Recommended actions:

- Delete `test_log_progress_reporter_smoke` if it only asserts private reset state.
- Reduce Rich private-update tests into semantic behavior tests.
- Keep one no-color/output-routing test, one nested-phase behavior test, one warned/failed completion behavior test, and the existing concurrency/protocol tests if still useful.

Risk: low.

Verification:

- `.venv/bin/pytest -q tests/utils/test_progress.py`

### Package 2: Duplicate HTML Coverage Removal

IDs: `TSO-033`

Recommended actions:

- Remove duplicate exact clip-option HTML test from `tests/services/test_report.py`.
- Confirm renderer-markup tests still cover clip selectors through parsed DOM semantics.

Risk: low.

Verification:

- `.venv/bin/pytest -q tests/services/test_report.py tests/services/test_report_renderer_markup.py`

### Package 3: Report Markup And CSS Relaxation

IDs: `TSO-016`, `TSO-032`

Recommended actions:

- Convert raw HTML substring/index tests to parsed DOM parentage/state checks.
- Remove exact help-copy rows, icon glyphs, decorative titles, and non-contract class choreography.
- Split CSS tests into hard invariants vs decorative tokens.
- Keep offline URL, no inline style, safe escaping, hidden state, reduced-motion, touch/pointer, fullscreen, mobile/inspector presence.

Risk: medium because viewer UX is user-facing.

Verification:

- `.venv/bin/pytest -q tests/services/test_report_renderer_markup.py tests/services/test_report_viewer_assets_css.py`

### Package 4: Viewer JS Harness Migration

IDs: `TSO-013`, `TSO-014`, `TSO-015`

Recommended actions:

- Move raw JS source-order behavior into executable harness where practical.
- Replace giant summary equality with focused behavior-family assertions.
- Keep persistence schema exactness, but consider centralizing schema constants.

Risk: medium.

Verification:

- `.venv/bin/pytest -q tests/services/test_report_viewer_assets_js_contracts.py tests/services/test_report_viewer_state.py`

### Package 5: VSPreview Source Snapshot Cleanup

IDs: `TSO-020` to `TSO-024`

Recommended actions:

- Replace source-text-only tests with generated-script execution using fake namespaces where feasible.
- Remove helper-body and section-comment snapshots.
- Keep path escaping, atomic write, collision tests.

Risk: low to medium.

Verification:

- `.venv/bin/pytest -q tests/vspreview/test_adapter.py`

### Package 6: Orchestration And Output Relaxation

IDs: `TSO-005`, `TSO-006`, `TSO-008`, `TSO-009`, `TSO-034`, `TSO-035`

Recommended actions:

- Relax exact timing zeros, `force_tty is None`, exact Rich text, full log payloads, helper-shape assertions.
- Remove duplicate stale report-path test only after confirming integrated coverage remains.

Risk: medium.

Verification:

- `.venv/bin/pytest -q tests/orchestration/test_execute_run_lifecycle.py tests/orchestration/test_run_dependencies.py tests/orchestration/test_alignment_report.py tests/orchestration/test_fps_report.py tests/orchestration/test_phase_tasks_outputs.py tests/orchestration/test_execute_run_phase_integration.py`

### Package 7: Render Geometry And Encoder Internals

IDs: `TSO-036`

Recommended actions:

- Decide which one or two numeric geometry cases are true algorithm contracts.
- Relax the rest to final canvas/overlay/writer/output/warning branch behavior.
- Consolidate repeated `_clip_to_rgb24_for_pillow_*` call-signature tests.

Risk: medium because render correctness is important.

Verification:

- `.venv/bin/pytest -q tests/render/test_expansion.py tests/render/test_encoders.py`

### Package 8: Alignment Prompt/Progress Wording

IDs: `TSO-010` to `TSO-012`

Recommended actions:

- Relax exact progress descriptions, Rich prompt glyphs, prompt wording, and fixed widths.
- Keep stderr routing, cache identity, offset behavior, invalid-input reprompt behavior, and interactive suspend/resume.

Risk: low to medium.

Verification:

- `.venv/bin/pytest -q tests/services/test_alignment_workflow.py tests/services/test_alignment_reuse_prompt.py tests/services/test_alignment_vspreview.py`

## Adjacent Maintainability Concerns

These are not test-overengineering cleanup by themselves, but they are good follow-ups:

- `scripts/validate_traceability.py` defines `SCAFFOLD_TESTS_DIR`, but `_resolve_test_path()` only consults `REPO_TESTS_DIR`.
- `docs/DECISIONS.md` mentions viewer theme baseline `#0f1115`, while `src/frame_compare/services/report/assets/viewer.css` uses `#08090c`.
- `src/frame_compare/services/report/assets/viewer.js` repeats mode/fit-mode validity lists and persisted-state schema fields. Centralizing these could make tests more behavior-focused.

## Cleanup Guardrails For A Subagent

- Do not weaken production coverage by replacing exact tests with empty smoke tests.
- Prefer parsed DOM/JSON/structured data assertions over raw string snapshots.
- Preserve tests for security, release scripts, persistence, path escaping, atomic writes, CLI contracts, and typed owner seams.
- Make each cleanup package independently reviewable.
- Run the focused test command for each package before handing off.
- If a test cannot be relaxed without losing all meaningful assertions, remove it or merge its one useful assertion into a stronger test.
