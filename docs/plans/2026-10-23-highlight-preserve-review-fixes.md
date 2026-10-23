---
search:
  exclude: true
---

Status: Historical
Scope: Fixes from the independent review of commit 6bedfa31 (opt-in `highlight_preserve` preset)
Owner: Codex orchestrator chat, controlled by the maintainer

# Highlight preserve review fixes

Branch: `fix/highlight-preserve-review`, created from `6bedfa31` (tip of `v0.7.0`).
It merges back into `v0.7.0` by fast-forward after the maintainer approves.
Clause IDs (R, D, U, V) are referenced by the orchestration prompt; do not renumber.

## Review findings this plan acts on

The product change is correct: one preset entry, one resolver rule, used by
screenshots, CLI output and alignment previews through
`render.prepare.resolve_tonemap_settings`. Every other preset already sends knee
0.5, so the reset rule cannot change an existing preset. The problems are in
release hygiene, tests and documentation.

- **R1 (blocker).** `review-evidence/` (39 MB, 520 files) is on the public
  `v0.7.0` branch. It contains film frames, local media filenames and the
  maintainer's Windows username. It also fails PR #138's `Lint (Ruff)` job:
  `ruff format --check` rejects a code block in
  `review-evidence/.../highlight-softclip-expanded/REPORT.md:101`.
- **R2 (blocker).** `zensical build --clean --strict` fails at `6bedfa31` and
  passes at `f1d3b9bf`. The seven warnings are links in
  `docs/reviews/2026-10-23-opus-5-5-tonemapping-handoff.md:3` and
  `docs/reviews/2026-10-23-tonemapping-highlight-research.md:17,129,249,573,574`.
  PR #138's `Build documentation` job fails for the same reason. The research
  report has 28 `C:/` links in total; the other targets are not checked by the
  site build but are broken for every reader.
- **R3.** No test proves the knee reaches the plugin. Replacing
  `"tone_mapping_param": settings.knee_offset` in
  `src/frame_compare/vs/tonemap_libplacebo.py` with a constant `0.5` passes the
  whole suite (3,746 passed, 336 skipped on macOS). The preset's only effect is
  unprotected at that boundary.
- **R4.** Tests read developer-local settings. A bare `ConfigSchema()` loads
  `config/config.toml` from the working directory and `FRAME_COMPARE_*`
  variables (`src/frame_compare/config/schema.py:55-59`). 17 test files use it,
  and no fixture shields them. This, not base source, explains the Windows
  failure of
  `tests/orchestration/test_execute_run_lifecycle.py::test_execute_run_propagates_collection_warning_once_through_result_summary_and_record`.
  On macOS at base that test passes. It fails with the Windows message when run
  from a directory whose `config/config.toml` sets
  `[slowpics] confirm_upload_after_report = true`, or with
  `FRAME_COMPARE_SLOWPICS__CONFIRM_UPLOAD_AFTER_REPORT=true`. The earlier
  "isolated base source" run copied `src/` only and still ran from the checkout.
- **R5.** Report accuracy.
  - The porch summary leads with "about 89% less endpoint area". The same sample
    shows near-white pixels (all channels at or above 250) falling from 20.90% to
    11.45%. Most of the sky stays near white; the visible change is small.
  - Softclip is described as "changes color". The raw deltas are more specific.
    In clipped saturated areas it lowers chroma and raises luma: magenta lights
    chroma −2.24 / luma +2.52, blue light −2.53 / +2.69, neutral character
    −5.14 / +3.30. In unclipped warm backgrounds it raises chroma and darkens
    slightly: Substance orange +4.60 / −1.24, red +1.63 / −0.55. Chroma here is
    the mean change of per-pixel max−min gamma-coded RGB. Hue was not measured.
  - The report says whole-repository Ruff formatting passed. CI shows it failed
    on the committed bundle.
- **R6.** User-guide and architecture placement.
  - `docs/guides/hdr-tonemapping.md` recommends
    `--tm-preset highlight_preserve --tm-curve bt2390 --tm-target 100 --tm-speed quality`.
    The extra flags only compensate for one local config. The paragraph also
    explains internal reasoning in a user guide.
  - The guide cites `src/frame_compare/render/prepare.py:37-74`, which is stale.
  - The new `docs/current-architecture.md` section was appended under
    "Unknowns And Maintainer Decisions Still Open" instead of the tonemap section
    near line 1100.

Checked and accepted without change: preset values, the reset rule and its
same-curve exception, persistence/merge round trips (existing test covers every
preset), report effective controls (knee is already reported), fast mode and
alignment preview resolution, the configured-parity native run (it used the real
resolver), synthetic summary figures, and the effective-peak disclosures.

## Decisions

- **D1.** Remove `review-evidence/` from the branch tip. Evidence stays local on
  the Windows machine under the ignored `generated/verification/2026-10-23/`.
  Purging it from Git history (rewriting the pushed `v0.7.0`) is a maintainer
  decision outside this plan.
- **D2.** Delete `docs/reviews/2026-10-23-opus-5-5-tonemapping-handoff.md`. The
  review it requested is done and is summarised in the research report.
- **D3.** Keep `docs/reviews/2026-10-23-tonemapping-highlight-research.md`.
  Links to tracked files become repo-relative links. Paths to local-only
  artifacts become inline code, never links.
- **D4.** Tests that need default configuration use
  `frame_compare.config.loader.get_default_config()` (no TOML, no environment),
  not a bare `ConfigSchema()`. A test that deliberately exercises TOML or
  environment discovery keeps its explicit setup. An autouse fixture in
  `tests/conftest.py` removes inherited application configuration variables
  before each test, including section JSON and nested `FRAME_COMPARE_*`
  settings. Runtime and test controls remain available, including native/media
  requirements, runtime identity, and E2E artifact routing. Tests may set their
  own configuration variables explicitly. The maintainer authorized this
  distinction after the blanket prefix rule was found to remove those controls.
  Production configuration discovery does not change.
- **D5.** No product code changes. `TonemapSettings`, presets, the resolver and
  the native kwargs stay exactly as in `6bedfa31`.
- **D6.** Softclip stays experimental and unexposed.

## Units

- **U1 — remove the bundle** (D1). `git rm -r review-evidence/`. Outside
  `docs/plans/**`, no file may still reference `review-evidence` once U4 lands.
  This plan names the bundle to describe its removal, and historical plans stay
  unedited per the runbook's plan lifecycle.
- **U2 — native-boundary proof** (R3). Owns
  `tests/vs/test_tonemap_extracted_modules.py` and `tests/vs/test_integration.py`.
  - (a) Extend the existing `build_libplacebo_tonemap_kwargs` coverage. Do not add
    a new file. Use settings from `resolve_tonemap_settings` for:
    `highlight_preserve` (expect `tone_mapping_param == 1.0`),
    `highlight_preserve` plus a spline curve override (expect `0.5`), and
    `reference` (expect `0.5`).
  - (b) Add one native test next to
    `test_native_still_tonemap_is_independent_of_request_history`, with the same
    libplacebo gating and `FRAME_COMPARE_REQUIRE_LIBPLACEBO` handling. Render a
    synthetic BT.2020/PQ ramp (about 100–4000 nits) with reference settings and
    with `highlight_preserve` settings through `apply_libplacebo`. Assert that
    the outputs differ and that the knee 1.0 output has fewer pixels with all
    channels at 255. The study saw 62.3% versus 31.5% on such a ramp; assert
    direction, not those numbers.
  - (c) Mutation proof, not committed: with `"tone_mapping_param": 0.5` hardcoded,
    (a) must fail, and (b) must fail on a machine where it runs. Revert after.
- **U3 — test isolation** (R4, D4). Owns `tests/conftest.py` and the bare
  `ConfigSchema()` call sites in these files:
  `tests/cli/test_run_interactive.py`,
  `tests/orchestration/test_execute_run_lifecycle.py`,
  `tests/orchestration/test_execution_phase_plan.py`,
  `tests/orchestration/test_overlay_frame_number.py`,
  `tests/orchestration/test_phases.py`,
  `tests/orchestration/test_preparation_cache.py`,
  `tests/orchestration/test_probe_cache_persist.py`,
  `tests/orchestration/test_run_dependencies.py`,
  `tests/orchestration/test_source_labels.py`,
  `tests/render/test_expansion.py`,
  `tests/render/test_expansion_geometry.py`,
  `tests/render/test_expansion_overlay.py`,
  `tests/render/test_tonemap_wiring.py`,
  `tests/services/test_slowpics_post_upload.py`,
  `tests/test_benchmark_analysis_tiers.py`,
  `tests/test_runner_import_smoke.py`,
  `tests/utils/test_terminal.py`.
  - Before editing, check each site. If a test intends discovery behaviour, leave
    it and say why.
  - Confirm `tests/config/test_loader.py` and other tests that `chdir` and write
    `config/config.toml` still pass unchanged.
  - If D4 cannot work without a production change, stop and report.
- **U4 — documentation** (R2, R5, R6, D2, D3).
  - Delete the handoff request doc.
  - Research report:
    - fix all `C:/` links per D3;
    - correct the fourth-failure attribution (R4);
    - add the near-white porch figures and the softclip direction-dependent
      chroma/luma figures (R5);
    - correct the Ruff statement, recording that PR #138 failed `Lint (Ruff)` and
      `Build documentation` at `6bedfa31` and the cause of each;
    - say the evidence is local-only after U1;
    - replace the Opus handoff pointer with a short "Independent review" summary:
      R1–R6, what was run (strict docs build at base and `6bedfa31`, full macOS
      suite at `6bedfa31` exit 0, mutation checks, CWD/env reproductions,
      inspection of porch and Spider-Verse sheets and raw summaries), and
      verdicts as below.
  - `docs/guides/hdr-tonemapping.md`:
    - show `frame-compare run --tm-preset highlight_preserve`;
    - state that explicit `[color]` `target_nits`, `tone_curve`, `gamma_lift` and
      `contrast_recovery` override any preset, and that a `tone_curve` other than
      `bt2390` returns the curve parameter to 0.5;
    - remove the internal-reasoning sentence;
    - replace the stale line citation with the function name.
  - Move the `current-architecture.md` section into the tonemap section near the
    `resolve_tonemap_settings` text (around line 1100); merge, do not duplicate.
  - Leave `current-cli-contract.md` and `docs/reference/*` unless a fact is wrong.
  - Voice: plain documentation. No slogans, "X, not Y" constructions, buzzwords,
    rhetorical questions or decorative dashes.
  - Review verdicts to record: knee 1.0 is a sound opt-in with modest measured
    separation (fewer near-white and endpoint pixels, slightly more distinct
    values, mean about −3.5 codes on the porch). Softclip stays experimental: it
    reduces coloured endpoints partly by desaturating clipped colours, and it also
    changes unclipped saturated colours.
- **U5 — close the plan.** Set this file to `Status: Historical` in the final
  commit.

## Verification

- **V1.** Ruff check, `ruff format --check`, pyright with warnings, import
  contracts, `git diff --check`.
- **V2.** Focused:
  `tests/config/test_color_roundtrip.py tests/vs tests/render tests/orchestration tests/services/test_slowpics_post_upload.py`.
- **V3.** U3 acceptance. Run the collection-warning test twice before and after
  U3: from a scratch directory whose `config/config.toml` sets
  `confirm_upload_after_report = true` (use `--rootdir` pointing at the checkout),
  and with `FRAME_COMPARE_SLOWPICS__CONFIRM_UPLOAD_AFTER_REPORT=true`. Both must
  fail before and pass after.
- **V4.** U2(c) mutation results.
- **V5.** Full suite. On Windows, run once with the developer's normal
  `config/config.toml` present. The collection-warning failure must be gone.
  Report any remaining failures by name; the two portable-installer PATH tests and
  the generated-launcher test are known and out of scope. Do not fix them.
- **V6.** `uv run --no-sync zensical build --clean --strict` exits 0. If Zensical
  cannot run on the executing machine, mark it UNRUN; the maintainer's Mac or
  PR #138 CI supplies it.
- **V7.** The U2(b) native test must run, not skip, on the Windows RTX machine with
  `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1`.

## Commits

1. `chore(evidence): remove committed tonemapping review bundle` (U1)
2. `test(tonemap): prove the highlight_preserve knee reaches libplacebo` (U2)
3. `test(config): isolate tests from local config and environment` (U3)
4. `docs(tonemap): correct highlight_preserve guidance and review report` (U4)
5. Review fixes, if any, with precise subjects.
6. `docs(plans): close highlight preserve review fixes` (U5)
