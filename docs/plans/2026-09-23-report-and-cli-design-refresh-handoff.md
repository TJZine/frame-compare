---
search:
  exclude: true
---

Status: Reference
Scope: Copy-paste implementation handoffs for the report viewer and CLI design refresh plan, one per review checkpoint.
Owner: Maintainer; implementation sessions run in Muse Code, reviews run in the planning (controller) session.

# Design refresh implementation handoffs

This file is an execution handoff, not a second plan. The authority is
[the design refresh plan](2026-09-23-report-and-cli-design-refresh.md). Each track
below is implemented in its own session, in order, on one branch, and stops for a
maintainer/controller review before the next track starts.

| Session | Units | Starts from | Ends at |
| --- | --- | --- | --- |
| 1. Track A | A1 → A2 → A3 → A4 | branch tip after the plan commit | Checkpoint A report |
| 1b. Track A test-scope correction | Track A tests only | Track A commits | Correction report (joins the Checkpoint A review) |
| 2. Track B viewer | B1 → B2 → B3 | branch tip after Checkpoint A review and fixes | Checkpoint B-viewer report |
| 3. Track B terminal | B4 → B5 → B6 → B7 | branch tip after Checkpoint B-viewer review and fixes | Checkpoint B-terminal report |

Paste one prompt per session. Every prompt requires the session to read the
[Common rules](#common-rules) first.

**Checkpoint reviews (controller side).** When a track's final report comes back,
the controller reviews it with the repository's `reviewer` subagent
(`.claude/agents/reviewer.md`), not `deep_reviewer`. Give it the track's plan
sections, Invariants, Test scope, the final report, and `git diff <track start
SHA>..<track end SHA>`; the controller verifies its findings, re-runs the gate, and
performs the review checks by eye before accepting the track.

## Common rules

These apply to every session. The prompts refer to them by name.

### Repository and branch

- Repository: `/Users/tristan/Software/frame-compare` (on Windows, the maintainer's
  equivalent checkout).
- Branch: `dev/v0.6.0-design-refresh`. Work directly on it. Do not create, switch,
  rebase, reset, or amend branches; do not push; do not open pull requests.
- Start by recording `git rev-parse HEAD`, `git status`, and `git log --oneline -5`.
  If the working tree has changes you did not make, stop and report them.
- Environment: use `uv sync --group dev --group docs --extra vsview --frozen`
  whenever you need to install or re-sync. Never run a narrower `uv sync` (it
  removes the `vsview` extra or the docs tools and breaks pyright and the docs
  build).
- Baseline: before any edit, run `uv run --no-sync pyright --warnings` and record
  the result. It is expected to be 0 errors, 0 warnings. Never describe an error
  as pre-existing unless it appears in this baseline at the start SHA.

### Authority and reading order

1. The plan: `docs/plans/2026-09-23-report-and-cli-design-refresh.md`. Read it in
   full, including Locked decisions, Invariants, Shared specifications, your
   track's units, Sequencing, Verification, and Stop conditions.
2. The reference assets in `docs/plans/2026-09-23-design-refresh-assets/`
   (images, `viewer-mock.html`, `cli-*.svg`) for the units you implement. The plan
   text wins wherever an asset differs.
3. `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md` (Verification, Planning and Handoff,
   Review Policy), and the repo-local skills that match the changed surface in
   `.agents/skills/` (for example `report-output-patterns`,
   `cli-contract-boundaries`, `python-test-design`, `closeout-verification`).
4. The source files named as owners in each unit, read before editing.

### Follow the plan exactly

- Implement every bullet of every unit in your track, and nothing else. No extra
  features, refactors, renames, reformatting of untouched code, or "improvements".
- Use the exact strings, values, thresholds, file owners, and names in the plan.
- Do not make product, design, wording, or contract decisions. If the plan does
  not cover a situation, apply the nearest stated rule. If no rule applies, or two
  rules conflict, or a stop condition is reached: stop that unit, record the
  question, finish any independent units, and report.
- The only plan edit you may make is appending to its **Execution record**
  section. Do not change any other part of the plan or the assets.
- Preserve all invariants. In particular: no report payload key changes, no
  `phase_timings`/run-record/JSON output changes, burned-in screenshot text and
  slow.pics names keep the `|` separator, frozen audio strings verbatim, plain and
  log reporters unchanged.

### Test scope

Follow the plan's **Test scope** section (under Verification) exactly. In short:
test logic, behaviour, saved state, accessibility semantics, and invariants; do not
test positions, sizes, spacing, colours, fonts, icon markup, CSS values, exact
tooltip/Help/note wording, option label lists, or terminal layout and wrapping.
Keep the browser smoke test to "loads and core interactions work"; put viewer logic
in the Node harnesses; test each rule in one place. Visual checks are still done,
by looking, and recorded in the report's **Review checks** section.

### Subagents

Use subagents where they help. Keep one writer at a time: only the main session
edits files unless a subagent is given an explicit, disjoint file set and the
main session makes no competing edits while it runs.

Good uses:

- read-only exploration: locating callers, tests, fixtures, and every place a
  string or behaviour appears before changing it;
- running long verification (full pytest, browser smoke, docs build) and
  summarizing failures;
- performing the review checks by looking (a generated report in a browser,
  terminal output at 80 and 120 columns) and reporting what was seen;
- the adversarial reviews below (always read-only, fresh context).

### Adversarial review before every commit

After a unit's implementation and focused tests pass, and before committing it:

1. Stage the unit's changes (`git add` of the unit's files only).
2. Launch **independent, read-only reviewer subagents** with fresh context. Give
   each the plan path, the unit id, the full text of the unit's plan section plus
   the Invariants and Shared specifications it relies on, and the staged diff
   (`git diff --staged`). Do not give them your reasoning or conclusions.
   - **Plan-conformance reviewer** (every unit): "Assume this diff does not follow
     the plan. For every bullet and value in the unit's plan section, find the
     code and test that implement it, or report it missing or different. Report
     anything in the diff that the plan did not ask for. Report every invariant
     the diff could break. Report every test assertion that breaks the plan's
     Test scope section (presentation checks, duplicate checks, debug output in
     tests) as a finding."
   - **Regression and contract reviewer** (units A1, A4, B1, B4, B5, B6, B7, and any
     unit touching Python production code): "Find behaviour this diff breaks or
     changes outside the plan: public CLI/JSON/report/persistence contracts,
     callers of changed functions, saved browser state, accessibility (roles,
     names, focus), `NO_COLOR`, non-TTY output, Windows paths and encodings, and
     missing or weak tests."
3. Each reviewer returns findings as: plan clause or invariant, file:line,
   severity (blocker / major / minor), evidence, and a proposed correction; plus a
   list of plan bullets it verified as implemented.
4. Adjudicate every finding against the plan and the code: **fix** (then re-run
   focused tests and a fresh review of the changed parts), **reject with
   evidence** (quote the plan text or code that shows it is not a deviation), or
   **leave open** (record why). Never silently drop a finding.
5. Repeat until a review round has no unresolved blocker or major findings, to a
   maximum of three rounds. If blockers remain after three rounds, do not commit
   the unit; stop and report.
6. Commit the unit: one commit per unit, message
   `<type>(<scope>): <unit id> <summary>` (for example
   `feat(report): B2 proximity fade for the viewport palette`), body listing the
   plan bullets covered and any open findings.

After the last unit of the track, run one **track-level adversarial review** with
two fresh reviewers over `git diff <track start SHA>..HEAD`, given the whole
track's plan sections: one for plan conformance across units (including docs the
plan requires and cross-unit consistency), one for regressions. Fix or record
findings the same way; commit fixes as `fix(<scope>): <track> review corrections`.

### Verification

- Focused tests while editing; each unit's **Proof** list from the plan.
- Before the track report, run the full gate from the plan's Verification section
  and record every command with exit code, test counts, and every skip with its
  reason. A skipped browser suite is not browser proof.
- Keep screenshots and scratch output untracked (outside the repository or in an
  ignored path). Do not commit media.

### Final report (bring this back for review)

End the session with this report, in this order, and append a condensed version
to the plan's Execution record. Be complete and specific; the review stage relies
on it. Do not summarize problems away.

1. **Identity:** branch, start SHA, end SHA, commits (`sha` · unit · subject).
2. **Coverage matrix:** for every bullet of every unit in the track, one row:
   plan clause · implemented where (file:line) · proven by (test name or manual
   evidence) · status (done / partial / not done).
3. **Deviations:** every place the result differs from the plan text or the
   reference assets, however small, with the reason. If none, say "none found"
   and name who checked (which reviewer rounds).
4. **Judgment calls:** anything the plan did not specify exactly and what you
   chose (these should be rare; each is a review item).
5. **Stop conditions and open questions:** anything you stopped on, with the plan
   text and the facts that caused it.
6. **Adversarial review log:** each round per unit and the track-level review:
   findings, severity, and disposition (fixed in `sha` / rejected with evidence /
   open).
7. **Verification:** commands, exit codes, counts, skips with reasons, and anything
   not verified and why.
8. **Review checks:** for each "review" item in the track's Proof lines and the
   plan's Test scope review checks, what you looked at (viewport size, mode,
   columns) and what you saw, including any difference from the reference assets.
   Keep screenshots untracked and give their paths.
9. **Possible issues and risks:** suspected regressions, fragile code, weak tests,
   platform concerns (Windows, encodings, light terminal themes), performance.
10. **Files changed:** grouped by unit; flag any file outside the unit's owner list.
11. **Documentation:** which docs were updated for which unit, and the strict docs
    build result.

## Prompt 1 — Track A

```text
You are implementing Track A (units A1, A2, A3, A4) of the Frame Compare design
refresh plan.

Repository: /Users/tristan/Software/frame-compare
Branch: dev/v0.6.0-design-refresh (work directly on it; do not push)
Plan: docs/plans/2026-09-23-report-and-cli-design-refresh.md
Handoff rules: docs/plans/2026-09-23-report-and-cli-design-refresh-handoff.md,
section "Common rules". Read that section and the whole plan before any edit, and
follow both exactly. The plan text is authoritative; do not make product or design
decisions. Stop and report instead.

Scope: A1 → A2 → A3 → A4, one commit per unit, each after passing adversarial
review as the Common rules describe. Then a track-level adversarial review, the
full verification gate, and the Final report. Stop after Track A; do not start
Track B.

Unit notes (in addition to the plan text, not instead of it):
- A1: implement the service table, the "Needs WEB next" rule, the lookup order, and
  the guessit name mappings exactly. ATVP/APTV/Apple TV+ → ATVP and HMAX/HBO Max →
  HMAX are intended changes; update only the tests that asserted the old codes and
  list each updated assertion in the report. Include every proof case the plan
  lists (including the "It" title and the no-WEB IT case).
- A2: use the exact FPS, size, runtime, timestamp, tonemap label, and
  active-picture rules. Source tonemap labels only from the plan's table.
- A3: add only the G shortcut and its title/Help text. Do not add a frame-position
  counter or shortcut letters to the toolbar (decision D9).
- A4: this includes decision D10 (plain-magnifier lens): remove the split
  comparison, its controls, state, and markup; add the Caption preference
  (default off) with the S1 caption text; keep the loading/unavailable notice and
  the accessible description. Also the Ring default, the Fixed text removal and
  note, distinct icons, SVG zoom glyphs, and the vertical palette order and icon
  buttons. Check that stored lens state containing comparisonEnabled or
  comparisonTarget loads without error.

Suggested subagent use: one read-only explorer to map every reference to the lens
comparison feature (JS, CSS, renderer, tests, docs) before A4 edits; one to map
every service-code assertion in tests before A1 edits; verification runners for the
browser smoke and full pytest.

Docs to update in the units that change them: docs/guides/sources-and-labels.md
(services), docs/guides/reports-and-overlays.md (lens, shortcuts, formatting), and
the architecture's viewer sections if they describe the lens comparison.
```

## Prompt 1b — Track A test-scope correction

Give this to the Track A implementer after Track A's units are committed. If the
Track A session is still open, send it there; otherwise start a new session.

```text
You are applying a test-scope correction to Track A of the Frame Compare design
refresh plan. This changes tests only; do not change product code except to fix a
real bug found by step 2.

Repository: /Users/tristan/Software/frame-compare
Branch: dev/v0.6.0-design-refresh (work directly on it; do not push)
Plan: docs/plans/2026-09-23-report-and-cli-design-refresh.md
Handoff rules: docs/plans/2026-09-23-report-and-cli-design-refresh-handoff.md,
section "Common rules".

The maintainer added a "Test scope" section to the plan (under Verification) and
moved presentation checks from the Proof lists to review. Read that section, the
updated A1–A4 Proof lines, and the Common rules "Test scope" section first. Track A
added assertions that now break those rules. Remove them as listed below. Only
remove assertions that Track A added: compare against the plan commit with
`git diff 8a177276 HEAD -- tests/`. Pre-existing assertions stay, including
existing assertions Track A updated for new expected values.

1. Working tree. `tests/browser/test_report_browser_smoke.py` has uncommitted
   changes that restructure and extend the lens-caption browser checks. Before
   discarding them, write down why they were being made (see step 2).

2. Lens caption in Single mode. The uncommitted changes suggest the browser caption
   check failed in Single (overlay) mode while the Node harness passes. Do not
   delete a failing check to hide a bug. Open a generated report in a real
   browser, turn the lens on, set Caption to On, and check Single, Slider, and Diff
   by looking. If the caption does not show in any of those modes, that is a
   product bug: fix it in lens.js, add the missing case to the lens Node harness
   (tests/services/lens_harness.js and its pytest wrapper), and record it in the
   report. If it works, record that and continue.

3. tests/browser/test_report_browser_smoke.py: restore the file to HEAD
   (discarding the uncommitted edits after step 1), then remove every Track A
   addition except the updated advanced-tonemap label list ('Scene thresholds'):
   - the vertical palette checks: verticalZoomOrder, verticalIconButtons,
     verticalIconWidths, the rectangle and width measurements behind them, and
     their assertions;
   - the lens-caption block (lensCaption* attributes and any debug attributes) and
     its assertions (covered by the lens harness);
   - the G-shortcut and Grid-title block (gShortcutSelectsGrid, gridButtonTitle)
     and its assertions (the shortcut is covered by the viewer-state harness;
     title wording is a review item).

4. tests/services/test_report_renderer_markup.py: remove Track A-added assertions
   on:
   - the Grid title and Help wording ('title="Grid (G) — scan sources together"'
     in the HTML, "Modes (Slider/Single/Diff/Blink/Grid)", "S / O / D / B / G");
   - icon markup: svg presence on the zoom, Source labels, and Lens buttons, and
     empty button text for the zoom buttons;
   - exact visible text or title of the Lens button, option label lists for Size,
     Sample marker, and Caption, tabindex of a non-selected option, and the lens
     note text ("drag its grip to move it").
   Keep: absence of the removed features (Fixed text, comparison controls,
   data-lens-current-source, COMPARE, comparison image slot, role badges);
   Ring checked by default; Caption Off checked and On unchecked by default;
   aria-label present on the lens and palette buttons; the timestamp <time>
   element and its datetime; the FPS, runtime, active-picture, and tonemap label
   tests; and any pre-existing assertion.

5. Leave unchanged: A1 parser tests, A2 formatting tests (Python and harness), the
   viewer-state harness G test, the lens-state harness and its summary keys,
   test_fps_report.py.

6. Check the remaining Track A tests against the plan's Test scope one more time
   and remove any other presentation-only assertion Track A added; list each one
   in the report.

7. Run: the focused suites you touched, then the full gate from the plan's
   Verification section (including the browser smoke test with -rs). Record exit
   codes, counts, and skips.

8. Adversarial review before committing, as the Common rules describe, with one
   plan-conformance reviewer given the plan's Test scope section, the A1–A4 Proof
   lines, and the staged diff: "Find any removed assertion that tested logic,
   behaviour, saved state, accessibility semantics, or an invariant (it must be
   restored), and any remaining assertion that breaks the Test scope."

9. Commit as `test(report): Track A test-scope correction` (plus a separate
   `fix(report): …` commit first if step 2 found a bug), append a short entry to the
   plan's Execution record, and report: what was removed (file and assertion),
   what was kept and why, the step 2 finding, verification results, and the
   review log.
```

## Prompt 2 — Track B viewer

```text
You are implementing Track B viewer (units B1, B2, B3) of the Frame Compare design
refresh plan. Track A is complete and reviewed.

Repository: /Users/tristan/Software/frame-compare
Branch: dev/v0.6.0-design-refresh (work directly on it; do not push)
Plan: docs/plans/2026-09-23-report-and-cli-design-refresh.md
Handoff rules: docs/plans/2026-09-23-report-and-cli-design-refresh-handoff.md,
section "Common rules". Read that section, the whole plan, and the plan's
Execution record for Track A before any edit, and follow both exactly. The plan
text is authoritative; do not make product or design decisions. Stop and report
instead.

Scope: B1 → B2 → B3, one commit per unit, each after passing adversarial review as
the Common rules describe. Then a track-level adversarial review, the full
verification gate, and the Final report. Stop after B3; do not start B4.

Unit notes (in addition to the plan text, not instead of it):
- B1: add the separator keyword with a " | " default to the three formatters and
  pass " · " only from report display building. Prove with one test that, for the
  same fixture, report display profiles use "·" while burned-in screenshot text
  and slow.pics image names still use "|". The viewer shows names only: no colour
  swatches, no #n, no LEFT/RIGHT (decisions D1 and D9). Toolbar: remove L:, vs,
  R:, Clip:; 20rem select cap with end ellipsis; Offset label/value typography.
  Stage labels: the HDR/SDR word rule exactly as written. B1 also carries three
  Checkpoint A items: the lens caption wraps instead of truncating (two-line Diff
  form, lens grows to fit, truncation/capacity logic removed), the caption uses
  the UI face, and the lens accessible description has no #n prefix.
- B2: implement the proximity state machine with the exact thresholds (96 px /
  160 px hysteresis), 0.18 opacity, 150 ms transition, 3000 ms load override,
  drag override, popover override, focus-within, fine-pointer gating, and reduced
  motion. Cover each rule in the harness.
- B3: implement to viewer-inspector-frame.webp, viewer-inspector-clips.webp, and
  viewer-report-info.webp and the B3 text: tab style, Frame tab rows and Detail
  rule, the all-sources table, the shared clip card (full and compact variants),
  the shared line with omission rule, placement text, and the Report Information
  rows (Opens in / Default pair). B3 also carries two Checkpoint A items: restore
  the " · DV L5" provenance note in the active-picture text, and show the default
  mode with the toolbar names (overlay → Single).

Review checks (by looking, not by tests): generate a report from the same fixtures
the browser smoke test uses (or an equivalent synthetic fixture with three sources
and the three long names from the plan), and compare it in a real browser against
the reference images at 1440 and 375 px. Record what you saw in Review checks and
any difference in Deviations. Keep screenshots untracked. Do not add presentation
assertions to the browser smoke test (plan Test scope).

Suggested subagent use: read-only explorers to map every consumer of the display
profiles and of the stage-label and Inspector rendering before edits; a browser
verification subagent for the viewport matrix; verification runners.

Docs to update in the units that change them: docs/guides/reports-and-overlays.md
(names, palette fade, Inspector, Report Information) and the architecture's viewer
and Inspector sections.
```

## Prompt 3 — Track B terminal

```text
You are implementing Track B terminal (units B4, B5, B6, B7) of the Frame Compare
design refresh plan. Track A and Track B viewer are complete and reviewed.

Repository: /Users/tristan/Software/frame-compare
Branch: dev/v0.6.0-design-refresh (work directly on it; do not push)
Plan: docs/plans/2026-09-23-report-and-cli-design-refresh.md
Handoff rules: docs/plans/2026-09-23-report-and-cli-design-refresh-handoff.md,
section "Common rules". Read that section, the whole plan, and the plan's
Execution record for earlier tracks before any edit, and follow both exactly. The
plan text is authoritative; do not make product or design decisions. Stop and
report instead.

Scope: B4 → B5 → B6 → B7, one commit per unit, each after passing adversarial
review as the Common rules describe. Then a track-level adversarial review, the
full verification gate, and the Final report.

Unit notes (in addition to the plan text, not instead of it):
- Shared: create src/frame_compare/utils/terminal_theme.py with the S3 tokens,
  glyphs, ASCII fallback, and highlight=False console construction; keep
  lint-imports passing. Add short_source_names to services/release_identity.py
  per S1 (release group, fallback to compact name, explicit labels, collisions).
- B4: follow the Run plan row-mapping table row by row; the Sources, Execution,
  publish, and Summary rules; every publish state listed. Reproduce frozen audio
  strings verbatim (add exact-match tests). Only the Rich path changes: plain and
  log reporters keep uppercase labels and bracket tokens; --json and --quiet
  output unchanged. Fix the blank lines at their source. Update
  docs/current-cli-contract.md in this unit.
- B4 also carries two Checkpoint A items: the frame-rate line uses the A2 format
  (`frame rates match · 23.976 fps (24000/1001)`, which supersedes the SVG), and
  the Sources size segment is omitted when the size is unknown or zero.
- B5: measure the VSView wait in _run_vsview_command; carry it in memory only
  (not phase_timings, run record, or JSON); implement the Align line and the
  summary time rows with the omission rules.
- B6: generated-script helpers only (no Rich or frame_compare imports in the
  generated script); colour tiers, glyph and arrow fallback, the ready block
  exactly as shown, short_names_by_stem parameter with a None default, and
  byte-identical output for identical inputs.
- B7: doctor layout and verdict line; glyphs and accent for wizard, history,
  preset, and errors without changing their text, streams, JSON, or history list's
  tab-separated rows.

Tests (behaviour and invariants): NO_COLOR, ASCII-only encoding, --quiet, --json,
and non-TTY output, frozen strings verbatim. Do not assert colours, spacing, or
wrapping (plan Test scope).
Review checks (by looking): render each changed surface at 80 and 120 columns and
compare with the cli-*.svg references; record what you saw in Review checks and
any difference in Deviations. If a real media run is possible on this host, run one
and include its output; otherwise say so.

Suggested subagent use: read-only explorers to map every printer of the affected
panels and every test asserting their text before edits; a render subagent for the
column and mode matrix; verification runners.

Docs to update in the units that change them: docs/current-cli-contract.md (Run
plan rows, Rich phase labels, summary, doctor), the audio-alignment and publishing
guides where they quote terminal output, and docs/guides/sources-and-labels.md for
short names.
```
