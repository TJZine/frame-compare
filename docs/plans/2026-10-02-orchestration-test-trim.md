---
search:
  exclude: true
---

Status: Active
Scope: Shrink `tests/orchestration` (17.6k lines, the highest test-to-source ratio, 1.79:1) through shared typed builders, and through targeted E2E widening that lets orchestration tests be deleted under mutation and coverage proof.
Owner: Claude controller session (planning, rulings, verification); Codex executes through `.handoff/` prompts. Branch `agent/e2e-test-strategy` (not pushed; no PR yet, by maintainer decision).

# Orchestration test trim

## Baseline

Measured at `b35a949e`, after the closed plan
[2026-09-30-e2e-test-strategy.md](2026-09-30-e2e-test-strategy.md).

- Suite: 81,605 test lines against 46,564 `src/` lines (1.75:1, or about 1.4:1
  counting the 11k lines of `tools/` scripts under test).
- Native suite: 3,070 passed, 90 skipped, about 40 s at `-n 4`. The Docker gate's
  pytest takes about 169 s with a warm cache.
- **`tests/orchestration`:** 54 files, 371 tests and 17,609 lines, against 9,841
  lines in `src/frame_compare/orchestration`. Tests average **47 lines each**.

**Lever 2, setup weight** (measured from the AST of the current files):
- **Setup dominates:** 9,241 of 12,183 test-body lines (**76%**) come before the
  first assertion. About 5.4k more lines are module-level helpers, fixtures and
  imports.
- **Long tests:** 38 tests are 60 lines or longer, totaling 3,149 lines.
- **Repetition:** 316 distinct 6-line normalized blocks repeat 3 or more times
  (1,362 occurrences). The top repeats are hand-built `AlignmentResult(...)`,
  context and config literals, spread across 3–4 files.
- **Files with the most setup:**
  - `test_phase_post_render_outputs.py` (773 setup / 954 body lines);
  - `test_phase_tasks.py` (638 / 816);
  - `test_doctor.py` (607 / 781);
  - `test_phase_tasks_alignment.py` (559 / 744);
  - `test_execute_run_lifecycle.py` (486 / 579);
  - `test_fps_report.py` (474 / 623);
  - `test_execute_run_cache_modes.py` (437 / 457);
  - `test_execute_run_run_folders.py` (435 / 587);
  - `test_execution_phase_plan.py` (410 / 481).
- **Builders already exist** in `tests/orchestration/phase_task_helpers.py` and
  `execute_run_helpers.py`, but they were consolidated only within files in the
  previous plan's unit D.
- **Estimate:** shared typed builders could cut 30–40% of setup, about 2.8–3.7k
  lines, without dropping a case.

**Lever 1, E2E in place of tests.** Tests are classified heuristically by their
first matching assertion target; it's an estimate.

| Area asserted | Tests | Lines | Do E2E summaries observe it today? |
| --- | ---: | ---: | --- |
| warnings and stderr | 44 | 1,672 | no: `run_result` `warning_summaries` aren't in summaries |
| selection and frames | 47 | 1,492 | partly: M1–M6 frames and categories |
| trim, FPS and alignment attribution | 28 | 1,197 | partly: M5 deltas only |
| raised errors | 40 | 1,031 | partly: E2 codes |
| cache | 23 | 832 | partly: M3 |
| report payload | 13 | 709 | partly: frames and tonemap only |
| render and screenshots | 10 | 634 | partly |
| publishing and slow.pics | 10 | 445 | no; network, so it stays |
| TMDB and metadata | 11 | 354 | no; network, so it stays |
| `run_info` | 7 | 333 | no |
| source labels | 8 | 267 | no |
| other or unclassified | 112 | 2,829 | (needs the precise mapping in O2) |

- **Addressable by widening:** warnings, trim and FPS attribution, report facts,
  `run_info` and labels, about 4.2k lines.
- **Realistic deletion:** 30–50% of those, about 1.3–2.1k lines, for a few hundred
  E2E lines and about 10–30 s more Docker time.
- **The previous audit's widening notes** for these areas are W2a–W6d in
  `.handoff/test-audit/3a.b2.md` and W1–W7 in `3b.b2.md`.
- **Combined potential:** about 4–6k of orchestration's 17.6k lines.

## Rules

Everything in the closed plan's S10, S11, S7, Invariants and handoff conventions
applies unchanged. In particular:
- one owner per user-visible behavior; the flow rule;
- every deletion proven by a mutation that fails each deleted test individually;
- the C5 coverage diff, run serially (`--cov-context=test` needs no `-n`);
- carrier assertions are never trimmed without a mutation proof;
- `git restore` only after staging any file with uncommitted edits;
- worker model and effort passed explicitly;
- every plan and handoff reviewed before dispatch.

New for this plan:
- **E1. Builders don't hide inputs.** A builder takes the values a test asserts on
  as explicit arguments; only irrelevant fields get defaults. A test must still
  read as "given X, expect Y". Builders are typed (pyright runs on tests). A
  builder shared across files lives in an existing helper module; one used by a
  single file lives in that file.
- **E2. Widening is per field, with maintainer approval.** An E2E summary field or
  scenario is added only if its measured yield is at least 5× the E2E lines it
  adds. Yield means the test lines whose sole remaining reason is that the field
  isn't observed. Each widening goes to the maintainer as a short table: field,
  yield, cost, Docker seconds. This applies the closed plan's "case-by-case
  exception" to E2E widening.
- **E3. Failure paths stay as unit tests:** cancellation, cleanup, timeouts,
  malformed external data. E2E can't trigger them.

## Units

- **O1. Builder pass (lever 2).**
  - One task per file group, for example `test_phase_*`, `test_execute_run_*`,
    `test_doctor*`, `test_fps_report` plus `test_preflight`, and the rest.
  - Each task extracts or extends shared builders for the repeated
    constructions, then rewrites tests to use them under E1. Proof:
    - every test keeps its assertions **unchanged** (an AST comparison of the
      assertion statements and the call-free expected values they read, before
      and after);
    - the collected node set is identical;
    - every test executes exactly the same `src/` lines (a per-test coverage
      comparison), so the refactor changes no input's path;
    - pyright is clean;
    - one mutation per file still fails its owner test.
  - The proof scripts are `.handoff/orch-trim/assert_ast.py` and `cov_ctx.py`.
  - **Parallelism:** file groups are disjoint, so tasks may run in parallel git
    worktrees (at most 3). Each has its own `uv sync --frozen`. Builder modules are
    shared, so assign `phase_task_helpers.py` and `execute_run_helpers.py` to one
    task, or run that task first. The controller merges serially and runs one
    combined gate. Otherwise run serially.
- **O2. Precise yield ledger (lever 1).** Read-only. Run after O1, so line counts
  reflect the builders.
  - For each surviving orchestration test, record the artifact field it
    ultimately protects (trace it as the flow rule requires), and whether an E2E
    summary field observes it.
  - Group by candidate field and scenario, and compute yield against cost.
  - **Output:** `.handoff/orch-trim/O2-yield.md`, a ranked table for the E2
    approval.
- **O3. Approved E2E widening.** Add only the approved fields and scenarios to
  `tests/e2e`, under the existing S1–S4 rules: explicit expected literals, and
  determinism proven across two Docker runs.
- **O4. Deletions,** as in the closed plan's unit C: C0 verify, C2 mutation per
  deleted test (Docker route for the new E2E owners), C5 coverage diff, serial
  per file group, gates.
- **O5. Closeout:**
  - the gates;
  - the inventory against this baseline;
  - mark the plan Historical;
  - add the lessons to the global `test-suite-slimming` skill.

## Checkpoints (controller)

- **After O1:** compare assertion ASTs per file, sample builder readability against
  E1, run the full native gate, and run the controller's own mutations in 2–3
  files.
- **After O2:** present the E2 approval table to the maintainer.
- **After O3:** check determinism, and that the new expected literals are explicit.
- **After O4:** as Checkpoint C in the closed plan: C0 changes, mutation samples,
  the coverage-diff approvals, and both gates.

## Execution record

- 2026-10-02: plan created with the baseline measurements above. Next: write and
  review the O1 handoff (`.handoff/O1-codex-builders.md`), then dispatch it.
- 2026-10-02: O1 handoff written and reviewed. E1 now allows file-local builders,
  and O1's proof adds the per-test coverage comparison. Two base coverage runs of
  `tests/orchestration` were identical, at about 20 s each.
- 2026-10-03: O1 done, serially, in `05a115d9..93dcf029` (O1-1 to O1-5), plus the
  controller's `7af9b72f`, which makes the one new positional builder parameter
  keyword-only.
  - **Result:** `tests/orchestration` 17,609 → 17,330 lines, and all tests
    81,605 → 81,326 (279 lines, 1.6%). The 2.8–3.7k estimate counted overlapping
    repeated windows. Most setup is specific to its test, and E1's
    pure-refactor bar left 36 of 51 files unchanged.
  - **Checkpoint O1 (controller):**
    - `assert_ast.py` is OK against `9afd968d`.
    - The diff adds and removes no assertion lines, and `src/` is unchanged.
    - The per-test coverage comparison against `9afd968d` is identical (523
      tests).
    - The native gate passes: 3,070 passed, 90 skipped; pyright 0. Codex ran
      Docker three times (276 passed each).
    - The sampled builders meet E1.
  - **Controller mutations:** three mutations each pass their orchestration
    file, at base and at HEAD, and fail owners in `tests/analysis`:
    - the fingerprint check in `cache_io.py`, caught by
      `test_cache_validation.py`;
    - the lead trim in `window.py`, caught by `test_window.py`;
    - the source offset in `metrics.py`, caught by `test_metrics.py`.

    So the suite still guards them.
  - **Inputs for O2:** within three attempts, no mutation failed a test on an
    assertion in `test_phase_output_integration.py`, `test_phases.py` or
    `test_run_dependencies.py`. In particular,
    `test_output_phases_use_reselected_metric_metadata_after_real_initial_selection`
    survives both source-offset mutations in `phase_alignment.py` and
    `phase_selection.py`. These tests are candidates for weak or covered tests.
- 2026-10-03: O2 done at `78792ddb`. Both lane ledgers pass the checker; the
  aggregate is in `.handoff/orch-trim/O2-yield.md`.
  - **No widening meets E2.** The best ratio is 3.3×. All 74 proposed new
    scenarios together would delete 3,165 test lines for about 3,211 E2E lines and
    about 632 s of Docker time, about 1:1. There are no material field-only keys.
    Orchestration tests are mostly distinct cases that would each need their own
    scenario.
  - **Status lines:**
    - covered 221 and internal 28;
    - widen 3,165;
    - stays 10,011: failure 2,914, network 1,615, unreachable 4,879, platform
      319 and security 284.
  - **Maintainer decision (E2):** reject every widening, so O3 is skipped. O4 is
    limited to the ten direct candidates: eight `covered`, one `internal`
    (`test_execute_phases_unresolved_review_warns_and_keeps_summary`, progress
    rendering) and one R2 `redundant-failure`
    (`test_run_report_phase_requires_reserved_run_folder`, owned by
    `test_run_report_phase_rejects_short_artifacts_before_indexing`). Then O5.
