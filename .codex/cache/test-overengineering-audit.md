# Frame Compare Test-Suite Overengineering Audit

Status: suite-wide re-audit against `stage1` at `9a85a2f` on 2026-07-09.

This supersedes the earlier conclusion that only Package R1 remained. That
conclusion was accurate for the June candidate list, but it was not a fresh
review of the complete current suite. This pass reviewed all test areas again,
ran the complete suite, and compared candidates with current production owners.

## Baseline

- 160 Python test files.
- 2,157 collected tests.
- 52,511 lines across `test_*.py` files.
- Full suite passed at the audited revision.
- Slowest test: 1.32 seconds; only runtime/release/persistence tests appeared in
  the slowest group.
- Skips were explicit and environment-based: missing real VapourSynth,
  PowerShell/Windows semantics, or opt-in live slow.pics access.
- No duplicate test function names, unbounded subprocess calls, broad hidden
  autouse cleanup, or meaningful suite-runtime problem was found.

The debt is therefore signal duplication, implementation-shaped assertions,
hidden test state, and test-module ownership. It is not test count or runtime by
itself.

## Production Standard

Keep exact or layered tests when they protect public CLI behavior, security,
cache identity and persistence, atomic writes, filesystem containment, release
artifacts, runtime integrations, accessibility, owner DTOs, or deliberate
numeric algorithms. A unit test and an integration test are not duplicates
merely because they mention the same feature.

Remove or consolidate tests when they only prove that a dataclass stores its
constructor arguments, search bundled assets for generic tokens, repeat the
same production seam in another file, or attach unrelated progress assertions
to a behavior test. Split files when their current contents cross production
owner boundaries; do not split files solely to chase a line-count target.

## Adjudicated Findings

### A. Direct Removals And Consolidations

| ID | Decision | Scope | Evidence and required action |
| --- | --- | --- | --- |
| `NEW-001` | `REMOVE` | `tests/cli/test_cli_commands.py`; `tests/windows_portable/test_windows_portable_scripts.py` | These are one-line/three-line placeholder modules with no tests. Delete them; their comments add no routing value. |
| `NEW-002` | `CONSOLIDATE` | `tests/services/test_report.py`; `tests/services/test_report_entry.py` | Output precedence, invalid input, mismatched screenshots, parent-directory creation, and write-error translation are tested twice against `report.entry.generate_report`. Make `test_report_entry.py` authoritative for this seam. Retain unique atomic replacement, permission preservation, image encoding/path, payload, escaping, identity, and sanitization tests elsewhere. |
| `NEW-003` | `REMOVE/MODIFY` | `tests/services/test_report.py::test_generate_report_filmstrip_*`; four `test_generate_report_mode_*` tests; dark-theme, keyboard-shortcut, and generic-accessibility tests | Filmstrip DOM state is already parsed in `test_report_renderer_markup.py`. CSS, keyboard, and accessibility have focused asset/DOM/state tests. Delete the generic token tests. Replace four full-report mode tests with one parameterized payload test that checks semantic `default_mode` propagation; do not retain `clip-path`, `mix-blend-mode`, or `setInterval` assertions. |
| `NEW-004` | `CONSOLIDATE` | `tests/cli/test_cli_output.py`; `tests/cli/test_run_output.py` | The latter repeats at-a-glance and result-summary facts already tested directly by the formatter suite. Keep detailed formatting in `test_cli_output.py`; retain a small invocation-level matrix in `test_run_output.py` for stream routing, quiet/JSON suppression, environment propagation, and command integration. |
| `NEW-005` | `CONSOLIDATE` | `tests/cli/test_run_command.py`; `tests/cli/test_run_report_open.py` | `maybe_open_run_report` policy is exhaustively tested directly and then repeated through CLI invocation for TTY, quiet, JSON, config, and slow.pics suppression. Keep the direct policy matrix in `test_run_command.py`, one positive and one suppression invocation test, and the platform/browser fallback tests in `test_run_report_open.py`. Preserve the confirmed-upload ordering test. |
| `NEW-006` | `CONSOLIDATE` | `tests/vspreview/test_adapter.py::test_check_vspreview_availability`; `tests/vspreview/test_overrides.py::TestCheckVspreviewAvailability` | Both cover the same executable/import/backend availability branches. Keep one parameterized owner-level suite and remove the duplicate set. |
| `NEW-007` | `REMOVE/MODIFY` | `tests/analysis/test_types.py`; selected tests in `tests/render/test_types.py`; first five tests in `tests/orchestration/test_run_dependencies.py` | Delete pure constructor/field-echo and protocol-assignment tests. Keep cache schema/version defaults only where serialization tests do not already protect them, mutable-default isolation, public facade exports, and deliberate immutability contracts. `RunRequest` defaults remain a CLI DTO contract and should stay. `RunResult` default factories and exports should stay. |
| `NEW-008` | `REMOVE` | `tests/analysis/test_metrics.py::test_performance_cache_key_ignores_selection_counts_and_quantiles`; `test_cache_key_changes_when_metric_active_rect_changes` | These call `cache_io.compute_cache_key` directly and duplicate stronger tests in `test_cache_io.py`, including performance mode, selection exclusions, and active-rectangle identity. They do not test metrics orchestration. |
| `NEW-009` | `MODIFY` | `tests/analysis/test_metrics.py::test_calculate_metrics_cache_save_is_best_effort` | Keep proof that cache-save failure does not discard calculated metrics. Remove exact reporter advance and description assertions from this test; they are unrelated to best-effort persistence and already have strategy/progress coverage. |
| `NEW-010` | `MODIFY` | `tests/analysis/test_metrics.py::test_no_toplevel_vapoursynth_import` and module import setup | Replace the 58-line AST source-shape test with a subprocess import-boundary test that blocks VapourSynth and imports `frame_compare.analysis.metrics`. Move strategy tests out of this mixed module so it no longer installs its own import-time `sys.modules` mock or requires `E402` imports. Do not remove the separate real-VS integration route. |
| `NEW-011` | `MODIFY` | `tests/orchestration/test_fps_report.py`; `tests/analysis/test_metric_tier_validation_helpers.py` | This is former Package R1. Use required-key subset assertions for internal FPS diagnostic rows and relax benchmark progress prose while keeping tier execution, total/advance count, and completion behavior. |

### B. Structural Test Debt

These changes should preserve behavior and test count except where a direct
removal above applies.

| ID | Priority | Scope | Owner-aligned target |
| --- | --- | --- | --- |
| `NEW-012` | High | `tests/orchestration/test_phase_tasks_outputs.py` (1,610 lines) | Split render mapping from `phase_tasks` and report/publish/confirmation/cleanup behavior from `phase_post_render`. This file currently crosses the production split recorded in the architecture document. |
| `NEW-013` | High | `tests/orchestration/test_preparation.py` (1,700 lines) | Split cache-mode validation, probe/persistence, source/reference selection, active-rectangle resolution, effective-FPS matching, and fastest-source benchmarking. Share only a small config/workspace builder. |
| `NEW-014` | High | `tests/render/test_expansion.py` (1,702 lines) | Split request validation/dispatch, overlay population, and geometry/active-rectangle provenance. Preserve exact geometry cases; they protect distinct algorithms and are not overengineering. |
| `NEW-015` | High | `tests/analysis/test_metrics.py` (1,077 lines) | Move strategy primitives to `test_metric_strategies.py`, retain `calculate_metrics` orchestration/cache behavior in `test_metrics.py`, and move import-boundary proof to a dedicated module. Keep exact `MetricCacheRequest` provenance handoff because it is the cache owner seam. |
| `NEW-016` | Medium | `tests/services/test_alignment_workflow.py` (1,279 lines) | Split core computation/progress from previous-offset reuse/writeback policy, matching `alignment.py` and `alignment_previous_offsets.py`. Introduce a local, non-autouse audio-boundary fixture to reduce repeated 4-6 patch stacks; tests should override only the collaborator relevant to the branch. |
| `NEW-017` | Medium | `tests/analysis/test_cache_io.py` (1,091 lines) | Split cache-key identity, serialization/round-trip, corruption/version rejection, and atomic persistence. Do not relax malformed payload or provenance coverage. |
| `NEW-018` | Medium | `tests/orchestration/test_execute_run_run_folders.py` (1,088 lines) | Split shared/run-local cache behavior, metadata prefetch, `run_info.toml`, and failure cleanup. Keep layered prep/execution tests where they prove different ordering or side effects. |
| `NEW-019` | Medium | `tests/analysis/test_metric_tier_validation_helpers.py` (800 lines) | Move tests of `tools/benchmark_analysis_tiers.py` to a tooling-focused module; keep pure tier validation under analysis. |
| `NEW-020` | Medium | `tests/cli/test_run_command.py` (1,180 lines) | After `NEW-005`, split request/path-security/write-config behavior from interactive report/slow.pics behavior. Do not weaken path containment, JSON, or preflight-order assertions. |
| `NEW-021` | Low | `tests/test_cli_contract_docs.py` (1,055 lines) | Split by authority/routing, CLI/config, persistence/cache, and report/slow.pics sections. Keep semantic documentation coverage; avoid building a generated manifest solely to reduce substring assertions. |
| `NEW-022` | Low/defer | `tests/services/viewer_state_harness.js` (928 lines) | The harness is fast and provides meaningful state evidence. Split only alongside a viewer production refactor. Do not add jsdom or a browser framework solely to replace the small residual source checks. |

### C. Helper And Harness Concerns

1. `MINIMAL_CONFIG`, workspace setup, and cache-input builders are repeated
   across CLI and orchestration helpers. Consolidate within each ownership area
   while doing `NEW-012` through `NEW-018`; do not create a global fixture
   framework or force intentionally different configs through one abstraction.
2. `tests/conftest.py` installs a suite-global fake VapourSynth module when the
   runtime is absent. This is currently needed by several unit modules, but it
   can hide accidental import coupling and causes real-VS tests to skip. Treat a
   narrower runtime-fixture redesign as a separate, medium-risk project. The
   subprocess import boundary in `NEW-010` is the immediate safeguard.
3. Keep `report_viewer_contracts.py`; its parser helpers replaced brittle raw
   string checks with shared semantic DOM/CSS helpers and are earning their
   complexity.

## Rejected Cuts

The following explorer candidates were rejected after owner review:

- Do not collapse prep, execute-run, and run-folder cache tests into one table.
  They protect different ordering, reservation, cleanup, and persistence seams.
- Do not relax the exact `MetricCacheRequest` provenance handoff in
  `calculate_metrics`; result metadata alone cannot prove the lookup identity.
- Do not merge CSS offline checks with rendered HTML/JS offline checks; they
  guard different asset boundaries.
- Do not remove mocked performance-strategy tests because real-VS integration
  tests cover similar values. One proves deterministic algorithm branches; the
  other proves runtime compatibility and is often skipped.
- Do not weaken render geometry, active-rectangle, cache corruption, atomic
  persistence, Windows portable, Docker, workflow, security, or release tests.
- Do not remove public lazy-facade export tests. They protect deliberate package
  surfaces, not Python import mechanics in the abstract.

## Cleanup Packages

Recommended order:

1. **Package A: report duplication** (`NEW-002`, `NEW-003`). Low risk and the
   largest defensible test-count reduction.
2. **Package B: CLI duplication** (`NEW-004`, `NEW-005`). Medium risk because
   stdout/stderr and interactive ordering are public contracts.
3. **Package C: analysis signal cleanup** (`NEW-008` through `NEW-011`). Low to
   medium risk; keep cache provenance and runtime integration boundaries.
4. **Package D: DTO and placeholder cleanup** (`NEW-001`, `NEW-007`). Low risk,
   but review exports/default factories carefully.
5. **Package E: duplicate VSPreview availability coverage** (`NEW-006`). Low
   risk and independent.
6. **Structural wave 1** (`NEW-012` through `NEW-015`). No deliberate behavior
   reduction; run affected areas and then the full suite.
7. **Structural wave 2** (`NEW-016` through `NEW-019`). No deliberate behavior
   reduction; keep fixture extraction local.
8. **Structural wave 3, optional** (`NEW-020`, `NEW-021`). Do only if the earlier
   cleanup still leaves meaningful navigation or merge-conflict cost.
9. Defer `NEW-022` until viewer production work justifies it.

For efficient worker use, assign two or three cleanup packages to a worker only
when their write sets are disjoint. Structural packages should generally remain
one owner-sized assignment because file moves create high merge-conflict risk.

## Verification

Baseline commands executed:

```text
.venv/bin/pytest -o addopts='' --collect-only -q
# 2157 tests collected in 0.91s

.venv/bin/pytest -q --durations=30
# passed; environment-based skips only
```

Every behavioral cleanup package must run its focused files. Every structural
wave must additionally run the complete suite because test discovery, shared
helpers, and module-level state are part of the change.
